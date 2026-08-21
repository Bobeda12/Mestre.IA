import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import RollCard, { type DadosRolagem } from './RollCard';

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

describe('RollCard', () => {
  it('mostra a conta d20 + bônus = total vs CA, e ACERTO em sucesso', () => {
    render(<RollCard dados={dados()} />);
    expect(screen.getByText(/d20\(15\)/)).toBeInTheDocument();
    expect(screen.getByText(/\+4/)).toBeInTheDocument();
    expect(screen.getByText(/= 19/)).toBeInTheDocument();
    expect(screen.getByText(/vs CA 15/)).toBeInTheDocument();
    expect(screen.getByText('ACERTO')).toBeInTheDocument();
  });

  it('mostra CD em vez de CA, e rotula SUCESSO/FALHA (não ACERTO/ERROU) para um teste de atributo', () => {
    render(<RollCard dados={dados({ tipo: 'teste', ca: undefined, cd: 12, dano: undefined })} />);
    expect(screen.getByText(/vs CD 12/)).toBeInTheDocument();
    expect(screen.getByText('SUCESSO')).toBeInTheDocument();
  });

  it('rotula SUCESSO/FALHA para um teste sem sucesso', () => {
    render(<RollCard dados={dados({ tipo: 'teste', ca: undefined, cd: 12, sucesso: false, dano: undefined })} />);
    expect(screen.getByText('FALHA')).toBeInTheDocument();
  });

  it('rotula ERROU (não FALHA) quando um ataque não acerta', () => {
    render(<RollCard dados={dados({ sucesso: false, dano: undefined })} />);
    expect(screen.getByText('ERROU')).toBeInTheDocument();
  });

  it('rotula CRÍTICO! e não FALHA/ACERTO quando crítico é true', () => {
    render(<RollCard dados={dados({ critico: true })} />);
    expect(screen.getByText('CRÍTICO!')).toBeInTheDocument();
    expect(screen.queryByText('ACERTO')).not.toBeInTheDocument();
  });

  it('rotula FALHA CRÍTICA quando falha_critica é true', () => {
    render(<RollCard dados={dados({ sucesso: false, falha_critica: true, dano: undefined })} />);
    expect(screen.getByText('FALHA CRÍTICA')).toBeInTheDocument();
  });

  it('não mostra a conta do d20 para um evento sem rolagem (ex: dano direto)', () => {
    render(<RollCard dados={dados({ tipo: 'dano', d20: null, bonus: null, total: null, ca: null, dano: 4 })} />);
    expect(screen.queryByText(/d20/)).not.toBeInTheDocument();
    expect(screen.getByText(/4 dano/)).toBeInTheDocument();
  });

  it('omite o dano quando não houve (ataque errado)', () => {
    render(<RollCard dados={dados({ sucesso: false, dano: 0 })} />);
    expect(screen.queryByText(/dano/)).not.toBeInTheDocument();
  });
});
