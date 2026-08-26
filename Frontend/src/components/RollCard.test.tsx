import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import RollCard, { DURACAO_ANIMACAO_DADO_MS, type DadosRolagem } from './RollCard';

function dados(overrides: Partial<DadosRolagem> = {}): DadosRolagem {
  return {
    texto: 'texto bruto (não usado pelo card)',
    tipo: 'ataque',
    quem: 'heroi',
    alvo: 'Goblin',
    d20: 15,
    bonus: 4,
    total: 19,
    ca: 15,
    sucesso: true,
    critico: false,
    falha_critica: false,
    dano: 6,
    ...overrides,
  };
}

// Fase 8 (revisão de gameplay) — o card agora nasce girando e só revela o
// resultado depois de DURACAO_ANIMACAO_DADO_MS ("fator cassino"); os testes
// existentes verificavam o conteúdo logo após o render, então cada um
// precisa avançar o relógio fake até o card revelar antes de checar texto.
beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function renderRevelado(dadosRolagem: DadosRolagem) {
  const utils = render(<RollCard dados={dadosRolagem} />);
  act(() => {
    vi.advanceTimersByTime(DURACAO_ANIMACAO_DADO_MS + 1);
  });
  return utils;
}

describe('RollCard', () => {
  it('nasce girando, sem mostrar o resultado, antes da animação terminar', () => {
    render(<RollCard dados={dados()} />);
    expect(screen.getByText('rolando')).toBeInTheDocument();
    expect(screen.queryByText('ACERTO')).not.toBeInTheDocument();
  });

  it('revela o resultado depois da animação', () => {
    renderRevelado(dados());
    expect(screen.queryByText('rolando')).not.toBeInTheDocument();
    expect(screen.getByText('ACERTO')).toBeInTheDocument();
  });

  it('mostra a conta d20 + bônus = total vs CA, e ACERTO em sucesso', () => {
    // "vs CA 15" atravessa dois elementos (o "vs" solto e "CA 15" dentro
    // do tooltip da sigla) — getByText só casa texto dentro de UM
    // elemento, então esta parte da checagem usa o texto normalizado do
    // container inteiro em vez de procurar um nó só.
    const { container } = renderRevelado(dados());
    expect(screen.getByText(/d20\(15\)/)).toBeInTheDocument();
    expect(screen.getByText(/\+4/)).toBeInTheDocument();
    expect(screen.getByText(/= 19/)).toBeInTheDocument();
    expect(container.textContent?.replace(/\s+/g, ' ')).toContain('vs CA 15');
    expect(screen.getByText('ACERTO')).toBeInTheDocument();
  });

  it('mostra CD em vez de CA, e rotula SUCESSO/FALHA (não ACERTO/ERROU) para um teste de atributo', () => {
    const { container } = renderRevelado(dados({ tipo: 'teste', ca: undefined, cd: 12, dano: undefined }));
    expect(container.textContent?.replace(/\s+/g, ' ')).toContain('vs CD 12');
    expect(screen.getByText('SUCESSO')).toBeInTheDocument();
  });

  it('rotula SUCESSO/FALHA para um teste sem sucesso', () => {
    renderRevelado(dados({ tipo: 'teste', ca: undefined, cd: 12, sucesso: false, dano: undefined }));
    expect(screen.getByText('FALHA')).toBeInTheDocument();
  });

  it('rotula ERROU (não FALHA) quando um ataque não acerta', () => {
    renderRevelado(dados({ sucesso: false, dano: undefined }));
    expect(screen.getByText('ERROU')).toBeInTheDocument();
  });

  it('rotula CRÍTICO! e não FALHA/ACERTO quando crítico é true', () => {
    renderRevelado(dados({ critico: true }));
    expect(screen.getByText('CRÍTICO!')).toBeInTheDocument();
    expect(screen.queryByText('ACERTO')).not.toBeInTheDocument();
  });

  it('rotula FALHA CRÍTICA quando falha_critica é true', () => {
    renderRevelado(dados({ sucesso: false, falha_critica: true, dano: undefined }));
    expect(screen.getByText('FALHA CRÍTICA')).toBeInTheDocument();
  });

  it('não mostra a conta do d20 para um evento sem rolagem (ex: dano direto) — e revela na hora, sem animação', () => {
    render(<RollCard dados={dados({ tipo: 'dano', d20: null, bonus: null, total: null, ca: null, dano: 4 })} />);
    expect(screen.queryByText('rolando')).not.toBeInTheDocument();
    expect(screen.queryByText(/d20/)).not.toBeInTheDocument();
    expect(screen.getByText(/4 dano/)).toBeInTheDocument();
  });

  it('omite o dano quando não houve (ataque errado)', () => {
    renderRevelado(dados({ sucesso: false, dano: 0 }));
    expect(screen.queryByText(/dano/)).not.toBeInTheDocument();
  });
});
