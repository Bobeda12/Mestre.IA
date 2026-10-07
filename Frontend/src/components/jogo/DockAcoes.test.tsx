import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DockAcoes from './DockAcoes';
import type { AcaoDireta, ItemInfo, PessoaMundo, TurnoCombate } from '../../lib/gameplay';

// Fase 6 ("uma tela só", ADR-0036) — o dock é a barra de ação única que
// substitui os três lugares que existiam antes (console do palco,
// controles do Mundo Vivo, chips do input). Estes testes cobrem os três
// contextos que ele decide sozinho: combate, seleção de alguém/algo no
// palco, e "nada selecionado" (sugestões do narrador).

function pessoa(overrides: Partial<PessoaMundo> = {}): PessoaMundo {
  return {
    id: 'olma', nome: 'Olma', descricao: 'Uma comerciante.', disposicao: 'neutro',
    confianca: 0, necessidade: 'Corda', lembrancas: [], promessas: [], ...overrides,
  };
}

// Controla `input`/`setInput` de verdade (DockAcoes é controlado pelo pai,
// como faz GameChat) para o teste poder digitar e apertar Enter.
function Harness(props: { aoAgir: (a: AcaoDireta, r: string) => void } & Partial<Parameters<typeof DockAcoes>[0]>) {
  const [input, setInput] = useState('');
  return (
    <DockAcoes
      combate={false}
      caido={false}
      ocupado={false}
      encerrado={false}
      loading={false}
      alvo={undefined}
      selecao={null}
      pessoaSelecionada={undefined}
      entidadeSelecionada={undefined}
      cena={null}
      progressao={null}
      nivel={1}
      inventory={[]}
      catalogoItens={{}}
      entidades={[]}
      opcoes={[]}
      erro={null}
      input={input}
      setInput={setInput}
      handleSendMessage={() => { props.aoAgir({ acao: 'atacar' } as AcaoDireta, input); setInput(''); }}
      handleKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) props.aoAgir({ acao: 'atacar' } as AcaoDireta, input); }}
      onAbrirBalcao={() => {}}
      onLimparSelecao={() => {}}
      {...props}
    />
  );
}

describe('DockAcoes — sem seleção', () => {
  it('preenche uma sugestão e devolve o foco para escrever', () => {
    render(<Harness aoAgir={vi.fn()} opcoes={['Observar os arredores']} />);
    fireEvent.click(screen.getByRole('button', { name: /observar os arredores/i }));
    expect(screen.getByLabelText('Sua ação')).toHaveValue('Observar os arredores');
    expect(screen.getByLabelText('Sua ação')).toHaveFocus();
  });

  it('protege o texto e bloqueia ações enquanto um turno é resolvido', () => {
    const aoAgir = vi.fn();
    const { rerender } = render(<Harness aoAgir={aoAgir} />);
    fireEvent.change(screen.getByLabelText('Sua ação'), { target: { value: 'Examino a porta' } });
    rerender(<Harness aoAgir={aoAgir} loading opcoes={['Outra ação']} />);
    expect(screen.getByLabelText('Sua ação')).toBeDisabled();
    expect(screen.getByRole('button', { name: /descansar/i })).toBeDisabled();
    fireEvent.keyDown(screen.getByLabelText('Sua ação'), { key: 'Enter' });
    expect(aoAgir).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Sua ação')).toHaveValue('Examino a porta');
    expect(screen.getByRole('status')).toHaveTextContent('O Mestre está narrando');
    rerender(<Harness aoAgir={aoAgir} />);
    expect(screen.getByLabelText('Sua ação')).toHaveFocus();
  });

  it('não envia Enter de composição de texto ou repetição da tecla', () => {
    const aoAgir = vi.fn();
    render(<Harness aoAgir={aoAgir} />);
    const campo = screen.getByLabelText('Sua ação');
    fireEvent.change(campo, { target: { value: 'Examino a porta' } });
    fireEvent.keyDown(campo, { key: 'Enter', isComposing: true });
    fireEvent.keyDown(campo, { key: 'Enter', repeat: true });
    fireEvent.keyDown(campo, { key: 'Enter', shiftKey: true });
    expect(aoAgir).not.toHaveBeenCalled();
  });

  it('mostra as sugestões do narrador e o botão Descansar', () => {
    render(<Harness aoAgir={vi.fn()} opcoes={['Observar os arredores', 'Seguir em frente']} />);
    expect(screen.getByText('Observar os arredores')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /descansar/i })).toBeInTheDocument();
  });
});

describe('DockAcoes — combate', () => {
  it('agrupa consumíveis repetidos e informa a quantidade disponível', () => {
    render(<Harness aoAgir={vi.fn()} combate inventory={['Poção de Cura', 'Poção de Cura']} />);
    fireEvent.click(screen.getByRole('button', { name: /itens/i }));
    expect(screen.getByLabelText('Quantidade: 2')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /poção de cura/i })).toHaveLength(1);
  });

  it('desabilita Atacar sem alvo e habilita com alvo', () => {
    const { rerender } = render(<Harness aoAgir={vi.fn()} combate={true} alvo={undefined} />);
    expect(screen.getByRole('button', { name: /atacar/i })).toBeDisabled();
    rerender(<Harness aoAgir={vi.fn()} combate={true} alvo="Goblin" />);
    expect(screen.getByRole('button', { name: /atacar goblin/i })).toBeEnabled();
  });

  it('chama aoAgir com a ação atacar ao clicar', () => {
    const aoAgir = vi.fn();
    render(<Harness aoAgir={aoAgir} combate={true} alvo="Goblin" />);
    fireEvent.click(screen.getByRole('button', { name: /atacar goblin/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'atacar', alvo: 'Goblin' }, 'Atacar Goblin');
  });
});

describe('DockAcoes — pessoa selecionada', () => {
  it('mostra o chip com o nome e os verbos, incluindo os sociais', () => {
    render(<Harness aoAgir={vi.fn()} selecao={{ tipo: 'pessoa', id: 'olma' }} pessoaSelecionada={pessoa()} />);
    expect(screen.getByText('Olma')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /negociar/i })).toBeInTheDocument();
  });

  it('verbo social entra em modo proposta: Enter envia agir_no_mundo com a proposta do texto', () => {
    const aoAgir = vi.fn();
    render(<Harness aoAgir={aoAgir} selecao={{ tipo: 'pessoa', id: 'olma' }} pessoaSelecionada={pessoa()} />);
    fireEvent.click(screen.getByRole('button', { name: /negociar/i }));

    const campo = screen.getByLabelText('Sua ação');
    expect(campo).toHaveAttribute('placeholder', expect.stringContaining('Olma'));

    fireEvent.change(campo, { target: { value: 'Ofereço a corda em troca de informação.' } });
    fireEvent.keyDown(campo, { key: 'Enter' });

    expect(aoAgir).toHaveBeenCalledWith(
      { acao: 'agir_no_mundo', alvo: 'olma', operacao: 'negociar', meio: undefined, proposta: 'Ofereço a corda em troca de informação.' },
      'Negociar: Olma',
    );
  });

  it('verbo não-social (examinar) envia direto, sem modo proposta', () => {
    const aoAgir = vi.fn();
    render(<Harness aoAgir={aoAgir} selecao={{ tipo: 'pessoa', id: 'olma' }} pessoaSelecionada={pessoa()} />);
    fireEvent.click(screen.getByRole('button', { name: /^examinar$/i }));
    expect(aoAgir).toHaveBeenCalledWith(
      { acao: 'agir_no_mundo', alvo: 'olma', operacao: 'examinar', meio: undefined, proposta: undefined },
      'Examinar: Olma',
    );
    expect(screen.getByLabelText('Sua ação')).toHaveAttribute('placeholder', 'Sua ação...');
  });

  it('limpar seleção pelo × chama onLimparSelecao', () => {
    const onLimparSelecao = vi.fn();
    render(<Harness aoAgir={vi.fn()} selecao={{ tipo: 'pessoa', id: 'olma' }} pessoaSelecionada={pessoa()} onLimparSelecao={onLimparSelecao} />);
    fireEvent.click(screen.getByRole('button', { name: /limpar seleção/i }));
    expect(onLimparSelecao).toHaveBeenCalled();
  });
});

// Combate v2 (ADR-0040) — o turno tem ação, ação bônus e movimento; o dock
// mostra o que já foi gasto e trava só aquela parte.
describe('DockAcoes — turno de combate', () => {
  const turno = (extra: Partial<TurnoCombate> = {}): TurnoCombate => ({
    fila: ['heroi', 'i1'], vez: 'heroi', rodada: 1, acao_usada: false, bonus_usada: false,
    movimento_usado: false, efeitos_heroi: {}, alvo_marcado: null, ...extra,
  });
  const POCAO: Record<string, ItemInfo> = { 'Poção de Cura': { tipo: 'consumivel', tags: ['Cura'], descricao: 'Recupera PV.', preco_venda: 10 } };

  it('mostra o que o turno ainda tem e o que já foi gasto', () => {
    render(<Harness aoAgir={vi.fn()} combate alvo="Goblin" turno={turno({ acao_usada: true })} />);
    expect(screen.getByLabelText('Ação: usada')).toBeInTheDocument();
    expect(screen.getByLabelText('Bônus: livre')).toBeInTheDocument();
    expect(screen.getByLabelText('Movimento: livre')).toBeInTheDocument();
  });

  it('com a ação usada, trava atacar e defender e destaca Encerrar turno', () => {
    const aoAgir = vi.fn();
    render(<Harness aoAgir={aoAgir} combate alvo="Goblin" turno={turno({ acao_usada: true })} />);
    expect(screen.getByRole('button', { name: /atacar goblin/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /defender/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /encerrar turno/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'encerrar_turno' }, 'Encerrar turno');
  });

  it('Mover oferece aproximar do alvo longe e recuar de quem está perto', () => {
    const aoAgir = vi.fn();
    const { rerender } = render(<Harness aoAgir={aoAgir} combate alvo="Goblin" turno={turno()} alvoLonge haInimigoPerto={false} />);
    fireEvent.click(screen.getByRole('button', { name: /mover/i }));
    expect(screen.getByRole('button', { name: /recuar/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /aproximar de goblin/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'aproximar', alvo: 'Goblin' }, 'Aproximar de Goblin');
    rerender(<Harness aoAgir={aoAgir} combate alvo="Goblin" turno={turno()} alvoLonge={false} haInimigoPerto />);
    fireEvent.click(screen.getByRole('button', { name: /mover/i }));
    fireEvent.click(screen.getByRole('button', { name: /recuar/i }));
    expect(aoAgir).toHaveBeenLastCalledWith({ acao: 'recuar' }, 'Recuar');
  });

  it('com o movimento usado, Mover fica travado; caído, oferece levantar', () => {
    const aoAgir = vi.fn();
    const { rerender } = render(<Harness aoAgir={aoAgir} combate alvo="Goblin" turno={turno({ movimento_usado: true })} haInimigoPerto />);
    expect(screen.getByRole('button', { name: /mover/i })).toBeDisabled();
    rerender(<Harness aoAgir={aoAgir} combate alvo="Goblin" turno={turno({ efeitos_heroi: { caido: 1 } })} haInimigoPerto />);
    fireEvent.click(screen.getByRole('button', { name: /mover/i }));
    fireEvent.click(screen.getByRole('button', { name: /levantar/i }));
    expect(aoAgir).toHaveBeenCalledWith({ acao: 'levantar' }, 'Levantar');
  });

  it('poção é ação bônus: trava quando o bônus já foi usado, não quando a ação foi', () => {
    const base = { aoAgir: vi.fn(), combate: true, alvo: 'Goblin', inventory: ['Poção de Cura'], catalogoItens: POCAO };
    const { rerender } = render(<Harness {...base} turno={turno({ acao_usada: true })} />);
    fireEvent.click(screen.getByRole('button', { name: /itens/i }));
    expect(screen.getByRole('button', { name: /poção de cura/i })).toBeEnabled();
    rerender(<Harness {...base} turno={turno({ bonus_usada: true })} />);
    expect(screen.getByRole('button', { name: /poção de cura/i })).toBeDisabled();
  });

  it('o campo de texto vira o improviso e avisa quando a ação já foi', () => {
    const { rerender } = render(<Harness aoAgir={vi.fn()} combate alvo="Goblin" turno={turno()} />);
    expect(screen.getByLabelText('Sua ação')).toHaveAttribute('placeholder', expect.stringMatching(/improvis/i));
    rerender(<Harness aoAgir={vi.fn()} combate alvo="Goblin" turno={turno({ acao_usada: true })} />);
    expect(screen.getByLabelText('Sua ação')).toBeDisabled();
  });

  it('com arma de corpo a corpo, alvo longe e movimento gasto, Atacar trava e explica', () => {
    const base = { aoAgir: vi.fn(), combate: true, alvo: 'Goblin', alvoLonge: true };
    const { rerender } = render(<Harness {...base} turno={turno({ alcance_ataque: 'corpo', movimento_usado: true })} />);
    const atacar = screen.getByRole('button', { name: /atacar goblin/i });
    expect(atacar).toBeDisabled();
    expect(atacar).toHaveAttribute('title', expect.stringMatching(/longe/i));
    rerender(<Harness {...base} turno={turno({ alcance_ataque: 'corpo' })} />);  // ainda pode avançar
    expect(screen.getByRole('button', { name: /atacar goblin/i })).toBeEnabled();
    rerender(<Harness {...base} turno={turno({ alcance_ataque: 'distancia', movimento_usado: true })} />);  // arco alcança
    expect(screen.getByRole('button', { name: /atacar goblin/i })).toBeEnabled();
  });

  it('sem os dados do turno (luta antiga), o dock continua como era', () => {
    render(<Harness aoAgir={vi.fn()} combate alvo="Goblin" />);
    expect(screen.getByRole('button', { name: /atacar goblin/i })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /encerrar turno/i })).not.toBeInTheDocument();
  });
});
