import { describe, expect, it } from 'vitest';
import { isValidElement } from 'react';
import { esconderTagOpcoes, limparMarkdownLeve, renderizarNarrativa } from './utils';

describe('esconderTagOpcoes', () => {
  it('esconde a tag na última linha, sem acento', () => {
    const texto = 'O goblin recua.\n[OPCOES]: Perseguir|Recuar|Examinar';
    expect(esconderTagOpcoes(texto)).toBe('O goblin recua.');
  });

  it('reconhece a grafia acentuada que o modelo às vezes usa', () => {
    const texto = 'O goblin recua.\n[OPÇÕES]: Perseguir|Recuar';
    expect(esconderTagOpcoes(texto)).toBe('O goblin recua.');
  });

  it('só esconde quando "ES" já chegou — antes disso é um flicker aceito, não uma narração apagada', () => {
    // O regex exige o padrão inteiro (`OP.{0,2}ES`); "[OPC" sozinho não
    // fecha "ES" ainda, então nada é escondido — mesmo comportamento de
    // antes desta correção, só que agora escopado à última linha.
    expect(esconderTagOpcoes('O goblin recua.\n[OPC')).toBe('O goblin recua.\n[OPC');
    expect(esconderTagOpcoes('O goblin recua.\n[OPCOES')).toBe('O goblin recua.');
  });

  it('texto sem tag nenhuma passa intacto', () => {
    const texto = 'O goblin recua para a escuridão.';
    expect(esconderTagOpcoes(texto)).toBe(texto);
  });

  it('rodada de conserto — não apaga narração de verdade quando "[OP" aparece fora da última linha', () => {
    // Antes desta correção, o corte valia pro texto INTEIRO: um "[OP"
    // em qualquer parágrafo (mesmo sem formar a tag completa) apagava
    // tudo que vinha depois. Agora só a ÚLTIMA linha é candidata a tag.
    const texto = 'Ele grita "[OP-3, retirada!" e foge.\nO resto do grupo hesita.';
    expect(esconderTagOpcoes(texto)).toBe(texto);
  });
});

describe('limparMarkdownLeve', () => {
  it('remove código inline e preserva negrito para o destaque da narrativa', () => {
    expect(limparMarkdownLeve('Isto é **importante** e `código`.')).toBe('Isto é **importante** e código.');
  });
});

// O que a tela mostra: texto comum como está, destaque entre colchetes.
function desenhado(texto: string) {
  return renderizarNarrativa(texto)
    .map(no => (isValidElement<{ children: string }>(no) ? `[${no.props.children}]` : String(no)))
    .join('');
}

describe('renderizarNarrativa', () => {
  it('transforma o par de asteriscos em destaque', () => {
    expect(desenhado('Há um **cofre de ferro** ali.')).toBe('Há um [cofre de ferro] ali.');
  });

  it('esconde a abertura que ainda espera o par, durante a digitação', () => {
    expect(desenhado('Há um **cofre de fe')).toBe('Há um ');
    expect(desenhado('Há um *')).toBe('Há um ');
    expect(desenhado('Há um **cofre** e uma **cha')).toBe('Há um [cofre] e uma ');
  });

  it('nunca mostra asteriscos crus nem esconde o resto do texto por causa de um par quebrado', () => {
    expect(desenhado('Um **cofre fechado.\n\nA estrada segue.')).toBe('Um cofre fechado.\n\nA estrada segue.');
    expect(desenhado('Um **homem\nde avental** olha.')).toBe('Um homem\nde avental olha.');
    expect(desenhado('Um **cofre.\nUm **martelo** na mesa.')).toBe('Um cofre.\nUm [martelo] na mesa.');
    expect(desenhado('Um **cofre.\nUm **martelo** e uma **cha')).toBe('Um cofre.\nUm [martelo] e uma cha');
  });
});
