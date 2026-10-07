# ADR-0043 — Pessoa morta existe no mundo; agressão é detectada pelo servidor

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (Fase 1)
**Supersede:** —

---

## Contexto

O jogador escreveu que queria matar um NPC e o NPC morreu na prosa, sem combate. Depois
clicou em "Conversar" e ele respondeu. Três causas, todas lidas no código:

1. `PessoaMundo.disposicao` só aceitava `reservado | cooperativo | hostil | ausente`. Não
   existia "morto", então o servidor não tinha onde guardar o fato.
2. O grupo de ferramentas de combate só abria com as raízes `atac`, `lutar`, `combate` e
   `agredir`. "Matar", "esfaquear" e "degolar" não abriam: o modelo só via ferramentas de
   mundo e narrava a morte sem registrar nada.
3. Vencer uma luta contra um inimigo com o nome do NPC não tocava a pessoa do mundo; o
   vínculo era só pelo nome, na hora de negociar.

## Decisão

**1. `morto` é uma disposição.** `PessoaMundo.indisponivel` junta `ausente` e `morto`, e todos
os pontos que checavam `ausente` (conversa, comércio, vínculos, trilha, remessas,
organizações) passam a usar essa propriedade. Conversar com um morto devolve um erro claro.

**2. O servidor detecta a violência.** `detectar_agressao` (em `services/living_world.py`) lê o
texto do jogador por verbos (matar, esfaquear, degolar, atacar…) e acha a pessoa visada pelo
nome. Quando casa, `tools_para` abre `iniciar_combate` e o prompt ganha um bloco
`[AGRESSÃO]` pedindo a ferramenta com o nome exato, sem narrar o desfecho. A decisão do
jogador, "sempre vira combate", é cumprida pelo servidor oferecendo e exigindo o caminho
certo, não por palavra do modelo.

**3. O inimigo carrega `pessoa_id`.** Em `iniciar_combate`, o inimigo que casa com uma
pessoa do local guarda o id. Na vitória, `registrar_mortes` marca a pessoa como `morto`,
zera a mercadoria e o estoque. Quem só recuou (afastado, ainda com PV) continua vivo.

**4. Guardrail.** `validar_narrativa` reprova narração em que um morto age, e narração em
que uma pessoa viva morre sem o combate ter registrado.

## Consequências

- O XP de "falar com X" e o passo da trilha deixam de valer para um morto (o passo vira
  impossível e é trocado, como já acontecia com `ausente`).
- O palco mostra o NPC morto apagado e desabilitado.
- **Limite conhecido:** o servidor *oferece e pede* o combate, mas o modelo ainda pode
  ignorar o pedido. O guardrail pega a morte narrada sem registro; a garantia total (abrir o
  combate sem passar pelo modelo) fica como evolução se o teste ao vivo mostrar falhas.
- Consequências sociais da morte (testemunhas, guardas) continuam por conta do narrador,
  via `desenvolver_consequencia`; a Fase 2 trata isso.

## Alternativas descartadas

- **Só adicionar o estado `morto` e confiar no narrador.** Resolve a conversa com o morto,
  mas não impede a morte sem combate.
- **O servidor abrir o combate sozinho, sem o modelo.** Mais forte, mas pula a narração da
  intenção e acopla o detector por palavra a uma ação irreversível. Fica para depois.
