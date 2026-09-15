import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ProjetosJornada from './ProjetosJornada';

describe('Projetos da jornada', () => {
  it('mostra contrapartidas e bloqueia aceitar proposta incompatível', () => {
    const agir = vi.fn();
    render(<ProjetosJornada bloqueado={false} aoAgir={agir} projetos={[{
      id: 'ponte', ambicao: 'Reabrir a ponte', local: 'Rio', estado: 'ativo',
      condicoes: [{ id: 'acesso', descricao: 'Acesso seguro', alvo: 'rio', estado: 'aberta', evidencia: '' }],
      propostas: [
        { id: 'ivo', npc: 'ivo', nome_npc: 'Ivo', condicao: 'acesso', oferta: 'Ajuda no reparo',
          contrapartida: 'Acesso gratuito', motivo_declarado: 'Servir moradores', exclusiva: true, estado: 'aceita', evidencia: '' },
        { id: 'lia', npc: 'lia', nome_npc: 'Lia', condicao: 'acesso', oferta: 'Madeira',
          contrapartida: 'Cobrar pedágio', motivo_declarado: 'Financiar comércio', exclusiva: true, estado: 'oferecida', evidencia: '' },
      ],
    }]} />);
    expect(screen.getByText('Em troca: Cobrar pedágio')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aceitar' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Renunciar ao compromisso' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'decidir_acordo_projeto', operacao: 'renunciar', alvo: 'ponte', proposta: 'ivo' }, 'Renunciar ao acordo');
  });
  it('envia a ambição do jogador e impede decisões durante perigo ou espera', () => {
    const agir = vi.fn();
    const { rerender } = render(<ProjetosJornada projetos={[]} bloqueado={false} aoAgir={agir} />);
    fireEvent.change(screen.getByLabelText('Minha ambição'), { target: { value: 'Recuperar a ponte' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assumir esta ambição' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'gerir_projeto', operacao: 'iniciar', proposta: 'Recuperar a ponte' }, 'Iniciar meu projeto');
    rerender(<ProjetosJornada projetos={[]} bloqueado aoAgir={agir} />);
    expect(screen.getByLabelText('Minha ambição')).toBeDisabled();
  });

  it('preserva o texto da ambição se o envio falhar (o projeto não nasce)', () => {
    // Achado da auditoria pré-lançamento: antes, o campo era limpo no
    // clique, mesmo se a chamada ao servidor falhasse — só limpa quando um
    // projeto ativo de fato aparece (`projetos` continua vazio aqui).
    const agir = vi.fn();
    render(<ProjetosJornada projetos={[]} bloqueado={false} aoAgir={agir} />);
    fireEvent.change(screen.getByLabelText('Minha ambição'), { target: { value: 'Recuperar a ponte' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assumir esta ambição' }));
    expect(screen.getByLabelText('Minha ambição')).toHaveValue('Recuperar a ponte');
  });

  it('aceita uma proposta sem conflito e permite recusar outra', () => {
    const agir = vi.fn();
    render(<ProjetosJornada bloqueado={false} aoAgir={agir} projetos={[{
      id: 'ponte', ambicao: 'Reabrir a ponte', local: 'Rio', estado: 'ativo',
      condicoes: [{ id: 'acesso', descricao: 'Acesso seguro', alvo: 'rio', estado: 'aberta', evidencia: '' }],
      propostas: [
        { id: 'ivo', npc: 'ivo', nome_npc: 'Ivo', condicao: 'acesso', oferta: 'Ajuda no reparo',
          contrapartida: 'Acesso gratuito', motivo_declarado: 'Servir moradores', exclusiva: false, estado: 'oferecida', evidencia: '' },
      ],
    }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Aceitar' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'decidir_acordo_projeto', operacao: 'aceitar', alvo: 'ponte', proposta: 'ivo' }, 'Aceitar acordo');
    fireEvent.click(screen.getByRole('button', { name: 'Recusar' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'decidir_acordo_projeto', operacao: 'recusar', alvo: 'ponte', proposta: 'ivo' }, 'Recusar acordo');
  });

  it('permite deixar um projeto ativo para trás', () => {
    const agir = vi.fn();
    render(<ProjetosJornada bloqueado={false} aoAgir={agir} projetos={[{
      id: 'ponte', ambicao: 'Reabrir a ponte', local: 'Rio', estado: 'ativo', condicoes: [],
    }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Deixar para trás' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'gerir_projeto', operacao: 'abandonar', alvo: 'ponte' }, 'Deixar este projeto para trás');
  });

  it('exige mudanças verificadas e mostra o caminho alternativo', () => {
    const agir = vi.fn();
    const projeto = {
      id: 'ponte', ambicao: 'Recuperar a travessia', local: 'Rio', estado: 'ativo' as const,
      condicoes: [{ id: 'acesso', descricao: 'Travessia acessível', alvo: 'rio', estado: 'aberta' as const, evidencia: '' }],
    };
    const { rerender } = render(<ProjetosJornada projetos={[projeto]} bloqueado={false} aoAgir={agir} />);
    expect(screen.getByRole('button', { name: 'Concretizar projeto' })).toBeDisabled();
    expect(screen.queryByLabelText('Minha ambição')).not.toBeInTheDocument();
    rerender(<ProjetosJornada projetos={[{ ...projeto, condicoes: [{ ...projeto.condicoes[0], estado: 'superada', evidencia: 'A balsa permite atravessar' }] }]} bloqueado={false} aoAgir={agir} />);
    expect(screen.getByText('A balsa permite atravessar')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Concretizar projeto' }));
    expect(agir).toHaveBeenCalledWith({ acao: 'gerir_projeto', operacao: 'concluir', alvo: 'ponte' }, 'Celebrar minha conquista');
  });
});
