import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DockAcoes from './DockAcoes';
import type { AcaoDireta, PessoaMundo } from '../../lib/gameplay';

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
  it('mostra as sugestões do narrador e o botão Descansar', () => {
    render(<Harness aoAgir={vi.fn()} opcoes={['Observar os arredores', 'Seguir em frente']} />);
    expect(screen.getByText('Observar os arredores')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /descansar/i })).toBeInTheDocument();
  });
});

describe('DockAcoes — combate', () => {
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
