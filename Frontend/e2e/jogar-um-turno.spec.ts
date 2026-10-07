import { test, expect, type Page } from '@playwright/test';

// Smoke e2e — "entrar → ter um herói → jogar um turno → ver a resposta".
//
// O que é real: a entrada como convidado pela tela, a criação do personagem
// no backend e o carregamento do jogo. O que é interceptado: o turno de chat
// (`/chat/stream`), para o teste não depender da IA nem de cota.
//
// O personagem é criado pela API, com a sessão do próprio navegador, e não
// clicando pelo assistente de criação: o assistente mudou de 5 para 6 passos
// desde a primeira versão deste teste e o deixou quebrado por meses. O que
// este smoke protege é o caminho até o primeiro turno, não o assistente.
const API = 'http://localhost:8000';

// Criar o personagem chama a IA de verdade para escrever o prólogo; em dia
// de provedor lento isso passa dos 30 s padrão do Playwright.
test.describe.configure({ timeout: 120_000 });

async function entrarComoConvidado(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /novo jogo/i }).click();
  // Sem sessão, "Novo jogo" leva à tela de entrada; "Jogar agora" cria a
  // conta de convidado e segue para a criação.
  await page.getByRole('button', { name: /jogar agora/i }).click();
  await expect(page).toHaveURL(/\/criar$/);
}

async function criarHeroi(page: Page, nome: string): Promise<string> {
  const resposta = await page.request.post(`${API}/create_character`, {
    data: {
      nome, raca: 'Humano', classe: 'Guerreiro', alinhamento: 'Neutro', background: 'Andarilho',
      objetivo: 'Provar que o sistema roda',
      atributos: { forca: 15, destreza: 14, constituicao: 13, inteligencia: 12, sabedoria: 10, carisma: 8 },
    },
  });
  expect(resposta.status(), await resposta.text()).toBe(200);
  return (await resposta.json()).session_id;
}

async function abrirJogo(page: Page, sessionId: string, nome: string) {
  await page.goto(`/jogar/${sessionId}`);
  // Herói novo abre na tela de prólogo; "Começar" entra no jogo.
  await page.getByRole('button', { name: /come[cç]ar/i }).click();
  await expect(page.getByText(nome).first()).toBeVisible();
}

function sse(evento: string, dados: unknown): string {
  return `event: ${evento}\ndata: ${JSON.stringify(dados)}\n\n`;
}

test('entrar como convidado, jogar um turno e ver a resposta com card de rolagem', async ({ page }) => {
  await entrarComoConvidado(page);
  const nome = `TesteE2E${Date.now() % 100000}`;
  const sessionId = await criarHeroi(page, nome);

  await page.route('**/chat/stream', async (route) => {
    const frames = [
      sse('token', { texto: 'Você ' }),
      sse('token', { texto: 'avista um goblin espreitando nas sombras.' }),
      sse('tool_event', {
        texto: '🎲 Teste de percepção: d20(15)+2=17 vs CD 15 → SUCESSO.',
        tipo: 'teste', quem: 'heroi', alvo: null, d20: 15, bonus: 2, total: 17,
        cd: 15, ca: null, sucesso: true, critico: false, falha_critica: false, dano: null,
      }),
      sse('state', {
        hp_atual: 10, hp_max: 10, defesa: 11, nivel: 1, xp: 0, xp_proximo_nivel: 300,
        inventory: [], combat_active: false, turno_combate: null, inimigos: [], missao: {},
        narrativa: 'Você avista um goblin espreitando nas sombras.',
      }),
    ].join('');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: frames });
  });

  await abrirJogo(page, sessionId, nome);
  await page.getByPlaceholder('Sua ação...').fill('Eu observo a sala com cuidado.');
  await page.getByRole('button', { name: /enviar ação/i }).click();

  // A narração (via SSE interceptado) e o card de rolagem aparecem.
  await expect(page.getByText('Você avista um goblin espreitando nas sombras.')).toBeVisible();
  await expect(page.getByText(/d20\(15\)/)).toBeVisible();
  await expect(page.getByText('SUCESSO')).toBeVisible();
});

test('a aba Jornada mostra a trilha do capítulo de um herói novo', async ({ page }) => {
  await entrarComoConvidado(page);
  const nome = `TrilhaE2E${Date.now() % 100000}`;
  const sessionId = await criarHeroi(page, nome);
  await abrirJogo(page, sessionId, nome);

  await page.getByRole('tab', { name: /jornada/i }).click();
  await expect(page.getByRole('heading', { name: /seu objetivo agora/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /capítulo 1 ·/i })).toBeVisible();
  const passos = page.getByRole('list', { name: /passos do capítulo/i }).getByRole('listitem');
  await expect(passos).toHaveCount(2);  // o passo de agora e o "???"
  await expect(passos.nth(0)).toHaveAttribute('aria-current', 'step');
  await expect(passos.nth(1)).toContainText('???');
});
