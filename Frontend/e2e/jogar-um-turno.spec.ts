import { test, expect } from '@playwright/test';

// Smoke e2e (Etapa 7) — "criar personagem → jogar um turno → ver
// resposta", o critério de "pronto" da própria etapa (PLANO_MESTRE.md).
// Criação de personagem sobe o backend de verdade (POST /create_character);
// o turno de chat intercepta `/chat/stream` via page.route, pelo mesmo
// motivo que tests/test_smoke.py no backend zera `narrator.client`: não
// depender de rede nem de GROQ_API_KEY pra um teste que precisa ser rápido
// e determinístico.
test('criar personagem, jogar um turno e ver a resposta com card de rolagem', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /novo jogo/i }).click();

  // Passo 1 — Raça. Humano não tem bônus de "livre_escolha" (ver
  // tests/test_smoke.py no backend), o que simplifica o Passo 4 abaixo.
  await page.getByRole('button', { name: 'Humano' }).click();
  await page.getByRole('button', { name: /próximo/i }).click();

  // Passo 2 — Classe.
  await page.getByRole('button', { name: 'Guerreiro' }).click();
  await page.getByRole('button', { name: /próximo/i }).click();

  // Passo 3 — Identidade.
  const nomeHeroi = `TesteE2E_${Date.now()}`;
  await page.getByPlaceholder('Ex: Vorag').fill(nomeHeroi);
  await page.getByRole('button', { name: 'Masculino' }).click();
  await page.getByPlaceholder('Ex: Soldado, Eremita, Nobre...').fill('Andarilho');
  await page.getByPlaceholder('Ex: Vingar meu clã...').fill('Provar que o sistema roda');
  await page.getByRole('button', { name: /próximo/i }).click();

  // Passo 4 — Atributos: gasta os 27 pontos levando FOR/DES/CON de 8 a 15
  // (custo 9 cada, 9×3=27) — o botão "Próximo" só libera com o total
  // zerado.
  // `div.space-y-6 > div.space-y-2 > div`, não só `div.space-y-2 > div`: o
  // painel de rolagem do próprio passo 4 (o scroll da esquerda) também
  // carrega a classe `space-y-2` entre outras, e um seletor mais solto
  // pega os dois containers, desalinhando os índices das linhas.
  const linhasDeAtributo = page.locator('div.space-y-6 > div.space-y-2 > div');
  for (const indice of [0, 1, 2]) {
    const botaoMais = linhasDeAtributo.nth(indice).getByRole('button').nth(1);
    for (let clique = 0; clique < 7; clique++) {
      await botaoMais.click();
    }
  }
  await expect(page.getByText('0/27')).toBeVisible();
  await page.getByRole('button', { name: /próximo/i }).click();

  // Passo 5 — Resumo. A partir daqui o próximo turno de chat vai ser
  // interceptado: a criação do personagem em si ainda é real.
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
        inventory: [], combat_active: false, ordem_iniciativa: [], turno_atual: 0, inimigos: [], missao: {},
        narrativa: 'Você avista um goblin espreitando nas sombras.',
      }),
    ].join('');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: frames });
  });

  await page.getByRole('button', { name: /jogar agora/i }).click();

  // Chegou no jogo — a ficha carregou de verdade (GET real a /load_game).
  await expect(page.getByText(nomeHeroi)).toBeVisible();

  await page.getByPlaceholder('Sua ação...').fill('Eu observo a sala com cuidado.');
  await page.getByRole('button', { name: /enviar ação/i }).click();

  // A narração (via SSE mockado) e o card de rolagem aparecem.
  await expect(page.getByText('Você avista um goblin espreitando nas sombras.')).toBeVisible();
  await expect(page.getByText(/d20\(15\)/)).toBeVisible();
  await expect(page.getByText('SUCESSO')).toBeVisible();
});

function sse(evento: string, dados: unknown): string {
  return `event: ${evento}\ndata: ${JSON.stringify(dados)}\n\n`;
}
