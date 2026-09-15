import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SinaisDaCena from './SinaisDaCena';

describe('Sinais da cena', () => {
  it('não renderiza nada sem oportunidades', () => {
    const { container } = render(<SinaisDaCena oportunidades={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('mostra a contagem e as percepções, com risco quando informado', () => {
    render(<SinaisDaCena oportunidades={[
      { id: 'a', alvo: 'porta', percepcao: 'A fechadura parece recém-forçada', risco: 'Pode haver alguém por perto' },
      { id: 'b', alvo: 'mesa', percepcao: 'Um mapa rabiscado está sobre a mesa', risco: '' },
    ]} />);
    expect(screen.getByText('(2)')).toBeInTheDocument();
    expect(screen.getByText('A fechadura parece recém-forçada')).toBeInTheDocument();
    expect(screen.getByText('Pode haver alguém por perto')).toBeInTheDocument();
    expect(screen.getByText('Um mapa rabiscado está sobre a mesa')).toBeInTheDocument();
  });
});
