import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AbaJornada from './AbaJornada';
import type { ArcoAtual, MundoPersistente } from '../../lib/gameplay';

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
  it('mostra pistas e permite escolher um aprendizado gerado pela jornada', () => {
    const aoAgir = vi.fn();
    const mundo: MundoPersistente = {
      local: 'Ponte', descricao: '', entidades: [], pessoas: [], conflitos: [], conhecimento: [],
      objetivos: [], especializacoes: {}, aptidao: { nome: 'Escuta', acoes: [], bonus: 0 }, minutos: 0,
      emergencia: {
        acontecimentos: [], condicoes: {}, consequencias: [{ id: 'carta', sinal: 'Ivo prepara uma carta', estado: 'pendente' }],
        particularidades: [{ id: 'sino', alvo: 'Ponte', pista: 'O bronze vibra', pistas: ['Ivo recorda vozes baixas'] }],
        aprendizados: [{ id: 'eco', nome: 'Ouvido das pontes', descricao: 'Você reconhece ecos', atributo: 'sabedoria', alvo: 'Ponte', ativo: false }],
      },
    };
    mundo.imersao = {
      oportunidades: [],
      marcas: [{ id: 'nome', nome: 'Guardião do bronze', significado: 'Ivo lembra do reparo', tipo: 'apelido', alvo: 'ivo', local: 'Ponte' }],
      momentos: [{ id: 'cha', npc: 'ivo', gesto: 'Ivo serve chá', convite: 'Quer ouvir uma história?', local: 'Ponte', turno: 1 }],
    };
    mundo.organizacoes = [{
      id: 'guarda', nome: 'Guardiões do campanário', proposito: 'Preservar a travessia',
      principio: 'Acesso para todos', local: 'Ponte', membros: [{ id: 'ivo', nome: 'Ivo' }],
      iniciativas: [{ id: 'isolar', nome: 'Isolar passagem', estado: 'ativo', sinal: 'Ivo prepara uma barreira' }],
    }];
    const { rerender } = render(<AbaJornada {...BASE} mundo={mundo} arco={null} aoAgir={aoAgir} />);
    expect(screen.getByText('Ivo recorda vozes baixas')).toBeInTheDocument();
    expect(screen.getByText('Guardião do bronze')).toBeInTheDocument();
    expect(screen.getByText('Guardiões do campanário')).toBeInTheDocument();
    expect(screen.getByText('Ivo prepara uma barreira')).toBeInTheDocument();
    expect(screen.getByText('Quer ouvir uma história?')).toBeInTheDocument();
    expect(aoAgir).not.toHaveBeenCalled();
    expect(screen.getByText('O bronze vibra')).toBeInTheDocument();
    expect(screen.getByText('Ivo prepara uma carta')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /desenvolver este aprendizado/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'escolher_aprendizado', alvo: 'eco' }, 'Aprender: Ouvido das pontes');
    rerender(<AbaJornada {...BASE} mundo={mundo} arco={null} aoAgir={aoAgir} combate />);
    expect(screen.getByRole('button', { name: /desenvolver este aprendizado/i })).toBeDisabled();
  });

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
