# ADR-0002 — Revalidar no servidor tudo que o cliente propõe na criação de personagem

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 1
**Supersede:** —

---

## Contexto

Antes desta etapa, `POST /create_character` (`Backend/api.py`) recebia só `nome`, `raca`, `classe` e os campos narrativos (`alinhamento`, `background`, `objetivo`, `historia_texto`) — nunca os atributos. O passo 4 do wizard (`CharacterCreation.tsx`) deixa o jogador gastar 27 pontos de point-buy entre Força, Destreza, Constituição, Inteligência, Sabedoria e Carisma, com bônus racial por cima. Esse cálculo inteiro acontecia só no navegador; o servidor então **hardcoded** os seis atributos (`15/14/13/12/10/10` fixos) e ignorava tudo que o jogador tinha escolhido.

Consequência prática: dois personagens com escolhas de atributo completamente diferentes nasciam com a mesma ficha. E como `POST /create_character` é um endpoint HTTP público, qualquer requisição feita fora da interface — `curl`, Postman, o DevTools do navegador — já podia mandar o que quisesse no corpo da requisição; o problema não era só a UI ignorar a escolha do jogador, era que **nada no servidor teria barrado um valor absurdo** (`forca: 99`) se o campo existisse sem validação.

A Defesa (CA) tinha o mesmo problema por outro caminho: era calculada no front (`10 + modificador de Destreza`) e só guardada no `localStorage` do navegador (`Home.tsx:50`, campo `saveInfo.defense`) — nunca no banco. Trocar de navegador, ou só limpar o `localStorage`, apagava a Defesa do personagem.

## Decisão

`POST /create_character` passa a receber os atributos **crus** (antes do bônus racial, valores entre 8 e 15) e a lista de atributos escolhidos para o ponto livre da raça (`atributos_livre`) — e o servidor é quem decide o valor final. Duas camadas de validação, cada uma no lugar que sabe o suficiente para validá-la:

1. **Pydantic (`field_validator`)**, em `CharacterCreationRequest`: confere que as seis chaves existem, que cada valor está entre 8 e 15, e que o custo total (tabela oficial de point-buy) não passa de 27 pontos. Isso não depende de nada externo — é validação de formato puro.
2. **Dentro do endpoint** (`create_character`, `Backend/api.py:171`): confere a contagem de pontos livres contra `d_raca.get('bonus_atributos', {}).get('livre_escolha', 0)` e recusa um ponto livre em atributo que já tem bônus fixo. Isso *precisa* estar no corpo da função porque depende de `data_manager.regras`, que o Pydantic sozinho não enxerga.

A Defesa (`10 + modificador de Destreza`) vira uma coluna (`defesa`) na tabela `herois`, calculada a partir do atributo já validado e devolvida em `create_character`, `load_game` e `chat`.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Confiar no cliente (manter como estava) | zero código novo | qualquer requisição direta ao endpoint cria um personagem com atributo fora da faixa; o wizard vira decoração | é exatamente o bug que esta etapa existe para consertar |
| Validar só no front (Zod/checagem manual antes de enviar) | mais simples, sem tocar no backend | não impede nada — o front é código que roda na máquina do usuário; ele pode simplesmente não usar o front | validação de UI é experiência, não segurança; a regra precisa valer onde ela não pode ser contornada |
| Construir já um "motor de regras" genérico (`domain/regras.py`) que valide isto e futuras mecânicas de combate | evita retrabalho quando a Etapa 3 (o Juiz) chegar | mistura o escopo fechado desta etapa com arquitetura que a Etapa 2 (camadas) e a Etapa 3 (motor de regras) ainda vão desenhar | construir a abstração cedo demais, sem saber ainda a forma que o Juiz da Etapa 3 vai precisar, é o tipo de decisão cara de desfazer depois |

## Consequências

**Ganhamos:**
- criar um personagem por fora da interface (curl, Postman) não passa mais de um atributo fora do point-buy — o teste `test_atributo_fora_do_intervalo_e_rejeitado` (`Backend/tests/test_smoke.py`) prova isso
- a Defesa sobrevive a trocar de navegador ou limpar o `localStorage`, porque mora no banco
- nasce o padrão "o cliente propõe, o servidor decide", que a Etapa 3 (o Juiz) vai reaplicar para combate — este ADR é a primeira aparição dessa regra, não a última

**Pagamos:**
- a validação ficou em dois lugares (o `field_validator` do Pydantic e uma checagem manual dentro do endpoint), porque a segunda depende de dado externo (`data_manager`) que o modelo Pydantic não tem acesso sozinho — é uma pequena quebra de coesão que vale a pena registrar
- o corpo da requisição HTTP ficou maior e mais rígido (`atributos` e `atributos_livre` agora são obrigatórios), o que quebra qualquer cliente antigo que só mandava `nome/raca/classe` — não existe cliente antigo em produção ainda, então o custo real hoje é zero, mas o precedente importa

**Fica em aberto:**
- HP durante o jogo (dano recebido em combate) ainda não é validado por ninguém — o modelo pode "escrever" qualquer coisa e o servidor ignora, mas também não impede. Esse é o buraco que a Etapa 3 (`ADR-0006`, ainda não escrito) fecha de vez.

## Como saber que erramos

Se, ao construir o motor de regras da Etapa 3, a validação de atributos daqui precisar ser reescrita do zero em vez de reaproveitada — sinal de que devíamos ter esperado e desenhado as duas juntas. Até lá, a hipótese é que "validação de criação de personagem" e "validação de uma jogada de combate" são problemas parecidos o bastante para não precisar da mesma abstração ainda.

## Referências

- [Pydantic — Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [D&D 5e — Point Buy (regra oficial de custo por atributo)](https://www.dndbeyond.com/sources/dnd/free-rules/character-creation-rules#Step5AbilityScores)
