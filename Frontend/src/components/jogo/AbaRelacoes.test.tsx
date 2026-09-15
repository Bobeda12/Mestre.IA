import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PessoaMundo } from '../../lib/gameplay';
import AbaRelacoes from './AbaRelacoes';

const pessoa: PessoaMundo = {
  id: 'ivo', nome: 'Ivo', descricao: 'Um faroleiro cansado', disposicao: 'cooperativo', confianca: 20,
  necessidade: '', lembrancas: [], promessas: [],
};

describe('Aba Relações', () => {
  it('mostra estado vazio sem NPCs nem reputações', () => {
    render(<AbaRelacoes reputacoes={{}} pessoas={[]} />);
    expect(screen.getByText('Nenhum NPC conhecido ainda.')).toBeInTheDocument();
  });

  it('mostra hábito e voz quando o Mundo Vivo os informa', () => {
    render(<AbaRelacoes reputacoes={{}} pessoas={[{ ...pessoa, habito: 'Acende o farol ao anoitecer', voz: 'Fala baixo, como quem guarda segredo' }]} />);
    expect(screen.getByText('Acende o farol ao anoitecer')).toBeInTheDocument();
    expect(screen.getByText('Fala baixo, como quem guarda segredo')).toBeInTheDocument();
  });

  it('não quebra nem mostra nada quando hábito e voz estão ausentes', () => {
    render(<AbaRelacoes reputacoes={{}} pessoas={[pessoa]} />);
    expect(screen.getByText('Ivo')).toBeInTheDocument();
    expect(screen.queryByText(/Acende|guarda segredo/)).not.toBeInTheDocument();
  });
});
