import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AbaJornada from './AbaJornada';
import type { ArcoAtual } from '../../lib/gameplay';

// Fase 6 ("uma tela só", ADR-0036) — o capítulo atual (arco) migrou do
// painel Mundo Vivo para esta aba; o servidor é quem decide se pode
// encerrar (`pode_encerrar`), a UI só obedece.

function arco(overrides: Partial<ArcoAtual> = {}): ArcoAtual {
  return {
    ativo: true, id: 'arco_1', titulo: 'Uma testemunha de partida', premissa: 'Ravi quer partir.',
    conflito: 'Uma testemunha de partida', estado_conflito: 'ativo', turnos: 2, marcos: 1,
    pode_encerrar: false, motivo_bloqueio: 'faltam 6 turnos de jogo', ...overrides,
  };
}

const BASE = {
  quest: null, resumoJornada: null, jornadaAberta: false, setJornadaAberta: vi.fn(),
  mundo: null, progressao: null, marcos: [], nivel: 1, ocupado: false, combate: false,
};

describe('AbaJornada — capítulo atual', () => {
  it('desabilita Encerrar capítulo quando o servidor diz que não pode', () => {
    render(<AbaJornada {...BASE} arco={arco({ pode_encerrar: false })} aoAgir={vi.fn()} />);
    expect(screen.getByRole('button', { name: /encerrar capítulo/i })).toBeDisabled();
    expect(screen.getByText(/faltam 6 turnos de jogo/i)).toBeInTheDocument();
  });

  it('habilita Encerrar capítulo quando pode_encerrar é true, e chama aoAgir ao clicar', () => {
    const aoAgir = vi.fn();
    render(<AbaJornada {...BASE} arco={arco({ pode_encerrar: true })} aoAgir={aoAgir} />);
    const botao = screen.getByRole('button', { name: /encerrar capítulo/i });
    expect(botao).toBeEnabled();
    fireEvent.click(botao);
    expect(aoAgir).toHaveBeenCalledWith(
      { acao: 'encerrar_arco', operacao: 'encerrar' },
      'Encerrar o capítulo: Uma testemunha de partida',
    );
  });

  it('sem arco ativo, não mostra a seção de capítulo', () => {
    render(<AbaJornada {...BASE} arco={null} aoAgir={vi.fn()} />);
    expect(screen.queryByText(/capítulo atual/i)).not.toBeInTheDocument();
  });
});
