import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PessoaMundo } from '../../lib/gameplay';
import BalcaoMercador from './BalcaoMercador';

const pessoa: PessoaMundo = {
  id: 'lia', nome: 'Lia', descricao: '', disposicao: 'cooperativo', confianca: 10,
  necessidade: '', lembrancas: [], promessas: [],
  vitrine: [
    { item: 'Poção de Cura', preco: 10, quantidade: 3 },
    { item: 'Corda', preco: 5, quantidade: 0 },
  ],
};

describe('Balcão do mercador', () => {
  it('permite comprar um item em estoque', () => {
    const agir = vi.fn();
    render(<BalcaoMercador pessoa={pessoa} inventario={[]} catalogo={{}} ouro={50} ocupado={false} combate={false} aoAgir={agir} aoFechar={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Poção de Cura/ }));
    expect(agir).toHaveBeenCalledWith(
      { acao: 'comerciar', alvo: 'lia', operacao: 'comprar', item: 'Poção de Cura' },
      'Comprar Poção de Cura de Lia',
    );
  });

  it('mostra "Esgotado" e desabilita a compra quando a quantidade é zero', () => {
    render(<BalcaoMercador pessoa={pessoa} inventario={[]} catalogo={{}} ouro={50} ocupado={false} combate={false} aoAgir={vi.fn()} aoFechar={vi.fn()} />);
    expect(screen.getByText('Esgotado')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Corda/ })).toBeDisabled();
  });

  it('desabilita a compra quando o ouro não é suficiente, mesmo com estoque', () => {
    render(<BalcaoMercador pessoa={pessoa} inventario={[]} catalogo={{}} ouro={2} ocupado={false} combate={false} aoAgir={vi.fn()} aoFechar={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Poção de Cura/ })).toBeDisabled();
  });
});
