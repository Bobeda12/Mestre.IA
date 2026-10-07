import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import FilaTurnos from './FilaTurnos';
import type { AliadoVisual, InimigoVisual } from '../../lib/gameplay';

// Combate v2 (ADR-0040) — a iniciativa vale, então a tela mostra a ordem e
// de quem é a vez.
const orc: InimigoVisual = { id: 'i1', nome: 'Orc', hp: 10, max_hp: 15, ca: 13 };
const lobo: InimigoVisual = { id: 'i2', nome: 'Lobo', hp: 0, max_hp: 11, ca: 13 };
const dara: AliadoVisual = { nome: 'Dara', classe: 'Batedora', hp: 8, hp_max: 10 };

describe('FilaTurnos', () => {
  it('lista quem age, na ordem, e marca de quem é a vez', () => {
    render(<FilaTurnos fila={['i2', 'heroi', 'a1', 'i1']} vez="heroi" heroi="Lia" inimigos={[orc, lobo]} aliados={[dara]} />);
    const itens = within(screen.getByRole('list', { name: /ordem dos turnos/i })).getAllByRole('listitem');
    expect(itens.map(li => li.textContent)).toEqual(['Lobo', 'Lia', 'Dara', 'Orc']);
    expect(itens[1]).toHaveAttribute('aria-current', 'true');
    expect(itens[0]).not.toHaveAttribute('aria-current');
  });

  it('quem caiu ou fugiu aparece riscado', () => {
    const fujao = { ...orc, afastado: true };
    render(<FilaTurnos fila={['heroi', 'i1', 'i2']} vez="heroi" heroi="Lia" inimigos={[fujao, lobo]} aliados={[]} />);
    expect(screen.getByText('Orc')).toHaveClass('line-through');
    expect(screen.getByText('Lobo')).toHaveClass('line-through');
    expect(screen.getByText('Lia')).not.toHaveClass('line-through');
  });

  it('sem fila não desenha nada', () => {
    const { container } = render(<FilaTurnos fila={[]} vez="heroi" heroi="Lia" inimigos={[]} aliados={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
