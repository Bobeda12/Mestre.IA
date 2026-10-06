import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import AbaJornada from './AbaJornada';
import type { Capitulo } from '../../lib/gameplay';

// Trilha do capítulo (ADR-0039) — a aba mostra três coisas, nesta ordem: o
// objetivo de agora, os passos do capítulo e o que ficou para trás. Quem
// decide o estado de cada passo e se o capítulo pode fechar é o servidor.

function capitulo(overrides: Partial<Capitulo> = {}): Capitulo {
  return {
    ativo: true, id: 'arco_2', numero: 2, titulo: 'A Água Negra', premissa: 'O poço de Valdren foi envenenado.',
    objetivo: 'Descobrir quem envenenou o poço',
    passos: [
      { texto: 'Fale com a curandeira.', estado: 'feito', evidencia: 'Você ouviu Maren.' },
      { texto: 'Entre no moinho velho.', estado: 'atual', evidencia: '' },
    ],
    pode_encerrar: false, motivo_bloqueio: 'faltam 2 passos da trilha',
    anteriores: [{ numero: 1, titulo: 'A Dívida', resultado: 'acordo' }],
    marcos: ['Poupou o contrabandista.'],
    ...overrides,
  };
}

const BASE = { ocupado: false, combate: false, erro: null };

describe('AbaJornada — trilha do capítulo', () => {
  it('mostra objetivo, capítulo e passos em sequência, com um só passo futuro oculto', () => {
    render(<AbaJornada {...BASE} capitulo={capitulo()} aoAgir={vi.fn()} />);
    expect(screen.getByText('Descobrir quem envenenou o poço')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /capítulo 2 · a água negra/i })).toBeInTheDocument();
    const passos = within(screen.getByRole('list', { name: /passos do capítulo/i })).getAllByRole('listitem');
    expect(passos.map(li => li.textContent)).toEqual([
      expect.stringContaining('Fale com a curandeira.'),
      expect.stringContaining('Entre no moinho velho.'),
      expect.stringContaining('???'),
    ]);
    expect(passos[0]).toHaveTextContent('Você ouviu Maren.');
    expect(passos[1]).toHaveAttribute('aria-current', 'step');
  });

  it('não mostra os painéis que saíram da tela', () => {
    render(<AbaJornada {...BASE} capitulo={capitulo()} aoAgir={vi.fn()} />);
    for (const titulo of [/o que quero construir/i, /lugares que você transformou/i, /quem move este mundo/i,
      /o mundo continua/i, /abastecimento/i]) {
      expect(screen.queryByText(titulo)).not.toBeInTheDocument();
    }
  });

  it('só oferece Encerrar quando o servidor diz que pode, e aí não há passo oculto', () => {
    const aoAgir = vi.fn();
    const { rerender } = render(<AbaJornada {...BASE} capitulo={capitulo()} aoAgir={aoAgir} />);
    expect(screen.queryByRole('button', { name: /encerrar capítulo/i })).not.toBeInTheDocument();
    // as regras de fechamento ficam com o servidor; a tela mostra só o passo
    expect(screen.queryByText(/faltam 2 passos da trilha/i)).not.toBeInTheDocument();
    const pronto = capitulo({
      pode_encerrar: true, motivo_bloqueio: '',
      passos: [
        { texto: 'Fale com a curandeira.', estado: 'feito', evidencia: 'Você ouviu Maren.' },
        { texto: 'Feche este capítulo quando estiver pronto.', estado: 'atual', evidencia: '' },
      ],
    });
    rerender(<AbaJornada {...BASE} capitulo={pronto} aoAgir={aoAgir} />);
    expect(screen.queryByText('???')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /encerrar capítulo/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'encerrar_arco', operacao: 'encerrar' }, 'Encerrar o capítulo: A Água Negra');
  });

  it('passo pulado aparece riscado, sem contar como feito', () => {
    const c = capitulo({ passos: [
      { texto: 'Fale com o moleiro.', estado: 'pulado', evidencia: '' },
      { texto: 'Entre no moinho velho.', estado: 'atual', evidencia: '' },
    ] });
    render(<AbaJornada {...BASE} capitulo={c} aoAgir={vi.fn()} />);
    expect(screen.getByText('Fale com o moleiro.')).toHaveClass('line-through');
  });

  it('abandonar pede confirmação', () => {
    const aoAgir = vi.fn();
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<AbaJornada {...BASE} capitulo={capitulo()} aoAgir={aoAgir} />);
    fireEvent.click(screen.getByRole('button', { name: /abandonar/i }));
    expect(aoAgir).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /abandonar/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'encerrar_arco', operacao: 'abandonar' }, 'Abandonar o capítulo: A Água Negra');
    confirmar.mockRestore();
  });

  it('mudar de rumo fica recolhido e envia o novo objetivo', () => {
    const aoAgir = vi.fn();
    render(<AbaJornada {...BASE} capitulo={capitulo()} aoAgir={aoAgir} />);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /mudar de rumo/i }));
    fireEvent.change(screen.getByRole('textbox', { name: /novo objetivo/i }), { target: { value: 'Sair da vila' } });
    fireEvent.click(screen.getByRole('button', { name: /seguir/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'definir_objetivo', proposta: 'Sair da vila' }, 'Meu objetivo: Sair da vila');
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('o que ficou para trás lista marcos e capítulos encerrados, do mais recente ao mais antigo', () => {
    const c = capitulo({ marcos: ['Chegou a Valdren.', 'Poupou o contrabandista.'] });
    render(<AbaJornada {...BASE} capitulo={c} aoAgir={vi.fn()} />);
    const itens = within(screen.getByRole('list', { name: /o que ficou para trás/i })).getAllByRole('listitem');
    expect(itens.map(li => li.textContent)).toEqual([
      'Poupou o contrabandista.', 'Chegou a Valdren.', 'Capítulo 1 · A Dívida (acordo)',
    ]);
  });

  it('sem capítulo aberto, explica e mantém o passado', () => {
    const c = capitulo({ ativo: false, passos: [], titulo: undefined, numero: undefined });
    render(<AbaJornada {...BASE} capitulo={c} aoAgir={vi.fn()} />);
    expect(screen.getByText(/nenhum capítulo aberto/i)).toBeInTheDocument();
    expect(screen.getByText('Capítulo 1 · A Dívida (acordo)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /abandonar/i })).not.toBeInTheDocument();
  });

  it('em combate ou com ação em curso, os botões travam; erro e status aparecem na aba', () => {
    const pronto = capitulo({ pode_encerrar: true });
    const { rerender } = render(<AbaJornada {...BASE} capitulo={pronto} aoAgir={vi.fn()} combate />);
    expect(screen.getByRole('button', { name: /encerrar capítulo/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /abandonar/i })).toBeDisabled();
    rerender(<AbaJornada {...BASE} capitulo={pronto} aoAgir={vi.fn()} ocupado erro="A rodada mudou." />);
    expect(screen.getByRole('alert')).toHaveTextContent('A rodada mudou.');
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('antes de o estado chegar, não quebra', () => {
    render(<AbaJornada {...BASE} capitulo={null} aoAgir={vi.fn()} />);
    expect(screen.getByText(/nenhum objetivo definido/i)).toBeInTheDocument();
  });
});
