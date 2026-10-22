# Relatório 0008 — Teste ao vivo das Fases 1 a 4

**Data:** 13/10/2026 · **Provedor:** Gemini (`gemini-3.5-flash-lite`, com `gemini-3.1-flash-lite` no fundo) ·
**Reproduzir:** `uv run python -m scripts.teste_ao_vivo --saida relatorio.json` (em `Backend/`).

## Como foi feito

O roteiro (`Backend/scripts/teste_ao_vivo.py`) cria um herói num banco descartável e joga quatro turnos de
texto livre contra o provedor real. Ele confere o **estado** (o que ficou no banco), não só a prosa. Os
embeddings são trocados por um dublê para não gastar cota. Cada tentativa de chamada é contada e há um teto.

Foram três rodadas, 21 requisições no total, nenhuma com falha do provedor.

## Resultado final por cenário

| Cenário | O que se esperava | O que aconteceu |
|---|---|---|
| **Violência** ("mato Balseiro") | O servidor abre combate; ao vencer, a pessoa vira `morto`; conversar depois falha | ✅ O modelo chamou `iniciar_combate` com `perfis`; o inimigo carregou `pessoa_id`; na vitória a pessoa ficou `morto`, sem mercadoria; "conversar" devolveu "Balseiro está morto(a) e não pode falar nem agir" |
| **Impossível** ("fogueira no fundo do mar") | `resolver_intencao` com dificuldade `impossivel`, sem dano | ✅ Escolheu `impossivel`; HP 7 → 7; narração curta e coerente |
| **Desvio** ("vou nadar no lago a tarde toda") | Aceita, não puxa de volta, o mundo se adapta | ✅ Depois da correção: aceitou, chamou `definir_objetivo` para o novo rumo e o relógio andou 10 min |
| **Perfis** ("desafio o Duque Valmir para um duelo") | `iniciar_combate` com `perfis`, ficha de pessoa | ✅ Depois da correção: chamou com `perfis` (guarda, orgulhoso) e recebeu a ficha de pessoa (Valentão de Taverna) |

## O que o teste achou (e foi corrigido)

1. **Perfis: a ferramenta de combate nem era oferecida.** "Luta" e "duelo" não estavam nos gatilhos (só "atac",
   "lutar", "combate", "agredir"). O modelo tentou `resolver_intencao` cinco vezes e desistiu ("perdeu o fio da
   meada"). Os gatilhos ganharam `lut`, `duel`, `batalh`, `enfrent` e `brig`.
2. **Desvio: o relógio não andava.** Um turno só de narração não gastava tempo, então conflitos e remessas
   ficavam parados enquanto o jogador nadava. Todo turno de texto livre sem ação gasta agora 10 minutos.
3. **Um "guarda" no nível 1 virava Esqueleto.** Não há ficha de guarda nesse nível e o servidor caía no sorteio de
   criaturas. Agora, se o papel é de pessoa, cai em outra pessoa do nível.

## O que o teste não provou

- **A luta contra o Duque Valmir:** o modelo preferiu um "Guarda" ao nobre nomeado. A ficha usada foi coerente com
  o que ele pediu, mas é uma escolha dele; não se corrige no servidor.
- **Chefe de arco, aliados e loja encantada** não foram exercitados ao vivo.
- **Uma amostra pequena por cenário.** Uma execução bem-sucedida não mede com que frequência o modelo acerta.
- A heurística "puxou de volta" do roteiro (palavras como "objetivo" e "deve") deu falso positivo no desvio; a
  leitura da narração mostra que não houve puxão.

## Custo

Cada passo do agente é uma requisição. Um turno típico gastou de 1 a 6. Os limites observados nos logs são de
15 por minuto e 500 por dia por modelo, bem acima dos 20 que a memória do projeto registrava (limite antigo).
