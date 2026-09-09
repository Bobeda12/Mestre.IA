import { describe, expect, it } from 'vitest';
import { ACEITAM_MEIO, ACOES, SOCIAIS, iconeEntidade, verbosPara } from './verbos';
import type { EntidadeMundo, PessoaMundo } from './gameplay';

// Fase 6 ("uma tela só", ADR-0036) — `verbosPara` é o coração do dock
// contextual: decide quais botões aparecem quando o jogador seleciona
// alguém ou algo no palco. Esses testes espelham as regras que existiam
// em LivingWorld.tsx antes da extração, garantindo que a mudança de lugar
// não mudou o comportamento.

function pessoa(overrides: Partial<PessoaMundo> = {}): PessoaMundo {
  return {
    id: 'p1', nome: 'Olma', descricao: 'Uma comerciante.', disposicao: 'neutro',
    confianca: 0, necessidade: 'Corda', lembrancas: [], promessas: [], ...overrides,
  };
}

function entidade(overrides: Partial<EntidadeMundo> = {}): EntidadeMundo {
  return {
    id: 'e1', nome: 'Baú', descricao: 'Um baú de madeira.', tipo: 'objeto',
    propriedades: [], estado: 'intacto', destino: '', descoberto: false, ...overrides,
  };
}

describe('verbosPara', () => {
  it('devolve vazio sem alvo', () => {
    expect(verbosPara(undefined)).toEqual([]);
  });

  it('pessoa sempre tem examinar, conversar e os cinco verbos sociais', () => {
    const verbos = verbosPara(pessoa());
    expect(verbos).toEqual(['examinar', 'conversar', ...SOCIAIS]);
  });

  it('objeto comum tem examinar, investigar e quebrar', () => {
    const verbos = verbosPara(entidade());
    expect(verbos).toEqual(['examinar', 'investigar', 'abrir', 'quebrar']);
  });

  it('saída ganha atravessar e bloquear (mas ainda "quebrar", regra herdada de LivingWorld: só animal tira o quebrar)', () => {
    const verbos = verbosPara(entidade({ tipo: 'saida' }));
    expect(verbos).toContain('atravessar');
    expect(verbos).toContain('bloquear');
    expect(verbos).toContain('quebrar');
  });

  it('objeto bloqueado ganha desbloquear', () => {
    const verbos = verbosPara(entidade({ estado: 'bloqueado' }));
    expect(verbos).toContain('desbloquear');
  });

  it('propriedade trancado troca abrir por destrancar', () => {
    const verbos = verbosPara(entidade({ propriedades: ['trancado'] }));
    expect(verbos).toContain('destrancar');
    expect(verbos).not.toContain('abrir');
  });

  it('propriedades móvel/coletável/inflamável somam mover/pegar/acender', () => {
    const verbos = verbosPara(entidade({ propriedades: ['movel', 'coletavel', 'inflamavel'] }));
    expect(verbos).toEqual(expect.arrayContaining(['mover', 'pegar', 'acender']));
  });

  it('objeto aceso ganha apagar', () => {
    const verbos = verbosPara(entidade({ estado: 'aceso' }));
    expect(verbos).toContain('apagar');
  });

  it('cobertura ganha esconder-se (ocultar)', () => {
    const verbos = verbosPara(entidade({ propriedades: ['cobertura'] }));
    expect(verbos).toContain('ocultar');
  });

  it('animal ganha acalmar em vez de quebrar', () => {
    const verbos = verbosPara(entidade({ tipo: 'animal' }));
    expect(verbos).toContain('acalmar');
    expect(verbos).not.toContain('quebrar');
  });
});

describe('ACOES', () => {
  it('tem rótulo para todo verbo social', () => {
    for (const verbo of SOCIAIS) expect(ACOES[verbo]).toBeTruthy();
  });
});

describe('ACEITAM_MEIO', () => {
  it('bloquear exige meio', () => {
    expect(ACEITAM_MEIO).toContain('bloquear');
  });
});

describe('iconeEntidade', () => {
  it('saída vira seta', () => {
    expect(iconeEntidade(entidade({ tipo: 'saida' }))).toBe('seta');
  });
  it('animal vira rosto', () => {
    expect(iconeEntidade(entidade({ tipo: 'animal' }))).toBe('rosto');
  });
  it('investigável vira pergaminho', () => {
    expect(iconeEntidade(entidade({ propriedades: ['investigavel'] }))).toBe('pergaminho');
  });
  it('objeto comum vira baú', () => {
    expect(iconeEntidade(entidade())).toBe('bau');
  });
});
