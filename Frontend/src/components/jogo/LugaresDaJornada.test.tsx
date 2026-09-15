import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MundoPersistente } from '../../lib/gameplay';
import LugaresDaJornada from './LugaresDaJornada';

const mundo: MundoPersistente = {
  local: 'Campanário', descricao: '', entidades: [], pessoas: [], conflitos: [], conhecimento: [],
  objetivos: [], especializacoes: {}, aptidao: { nome: '', acoes: [], bonus: 0 }, minutos: 60,
  instalacoes: { preparacao: null, lugares: [{ id: 'sala', projeto: 'p', nome: 'Sala dos ecos',
    descricao: 'Uma sala recuperada', tipo: 'abrigo', atributo: 'carisma', local: 'Campanário',
    ativa: true, disponivel: true, evidencia: 'A sala está segura' }] },
};

describe('Lugares da jornada', () => {
  it('envia descanso longo e impede uso quando o local está inacessível', () => {
    const agir = vi.fn();
    const { rerender } = render(<LugaresDaJornada mundo={mundo} bloqueado={false} aoAgir={agir} />);
    fireEvent.click(screen.getByRole('button', { name: 'Descansar — 8 horas' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'descansar', tipo: 'longo' }, 'Descansar no abrigo');
    rerender(<LugaresDaJornada mundo={{ ...mundo, instalacoes: { preparacao: null,
      lugares: [{ ...mundo.instalacoes!.lugares[0], disponivel: false }] } }} bloqueado={false} aoAgir={agir} />);
    expect(screen.getByRole('button', { name: 'Descansar — 8 horas' })).toBeDisabled();
  });

  it('preparação existente bloqueia acumulação e exibe prazo', () => {
    render(<LugaresDaJornada bloqueado={false} aoAgir={vi.fn()} mundo={{ ...mundo, instalacoes: {
      lugares: [{ ...mundo.instalacoes!.lugares[0], tipo: 'oficina' }],
      preparacao: { nome: 'Sala dos ecos', atributo: 'carisma', expira_em: 1500 },
    } }} />);
    expect(screen.getByRole('button', { name: 'Preparar — 1 hora' })).toBeDisabled();
    expect(screen.getByText(/Expira em 1440 min de jogo/)).toBeInTheDocument();
  });

  it('envia inaugurar para uma melhoria ainda não ativa', () => {
    const agir = vi.fn();
    render(<LugaresDaJornada bloqueado={false} aoAgir={agir} mundo={{ ...mundo, instalacoes: {
      preparacao: null,
      lugares: [{ ...mundo.instalacoes!.lugares[0], ativa: false }],
    } }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Inaugurar' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'usar_instalacao', alvo: 'sala', operacao: 'inaugurar' }, 'Inaugurar melhoria');
  });

  it('envia preparar numa oficina ativa e disponível, sem preparação em curso', () => {
    const agir = vi.fn();
    render(<LugaresDaJornada bloqueado={false} aoAgir={agir} mundo={{ ...mundo, instalacoes: {
      preparacao: null,
      lugares: [{ ...mundo.instalacoes!.lugares[0], tipo: 'oficina' }],
    } }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Preparar — 1 hora' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'usar_instalacao', alvo: 'sala', operacao: 'preparar' }, 'Preparar próxima expedição');
  });

  it('mostra estado vazio quando não há lugares nem preparação', () => {
    render(<LugaresDaJornada bloqueado={false} aoAgir={vi.fn()} mundo={{ ...mundo, instalacoes: { preparacao: null, lugares: [] } }} />);
    expect(screen.getByText('Nenhum lugar transformado ainda.')).toBeInTheDocument();
  });

  it('avisa quando a melhoria está inacessível fora do local dela', () => {
    render(<LugaresDaJornada bloqueado={false} aoAgir={vi.fn()} mundo={{ ...mundo, local: 'Outro lugar', instalacoes: {
      preparacao: null,
      lugares: [{ ...mundo.instalacoes!.lugares[0], disponivel: false }],
    } }} />);
    expect(screen.getByText('Visite este lugar para usar a melhoria.')).toBeInTheDocument();
  });
});
