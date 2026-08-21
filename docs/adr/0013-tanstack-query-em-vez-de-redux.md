# ADR-0013 — TanStack Query para estado de servidor, em vez de Redux ou continuar sem gerenciador nenhum

**Data:** 21/08/2026
**Status:** Aceito
**Etapa:** 7
**Supersede:** —

---

## Contexto

Até esta etapa, todo dado que vem do backend chega ao frontend do mesmo jeito, repetido em três componentes: um `useEffect` dispara um `axios.get/post`, e o resultado cai em `useState` soltos — `Frontend/src/components/GameChat.tsx:75-96` (antes desta etapa) tinha um `useEffect` só para `load_game`, com `try/catch`/`setNotFound` escritos à mão; `Home.tsx` fazia o mesmo para conferir se um save ainda existia no servidor antes de navegar. Cada cópia reimplementa loading, erro e sucesso à mão, sem cache nenhum — sair da tela de jogo e voltar refaz a chamada do zero, mesmo que nada tenha mudado.

Isso não é o mesmo problema que "estado de UI" (`showSidebar`, `input`, `loading` local) resolve bem com `useState` — é especificamente dado que **mora no servidor** e só o cliente espelha: a ficha do personagem, a lista de saves confirmados. `PLANO_MESTRE.md`, Etapa 7, já nomeia a troca: "TanStack Query substitui os `useEffect` + `axios` soltos".

## Decisão

`@tanstack/react-query` entra como dependência nova; `App.tsx` ganha um `QueryClient` único (`retry: false, refetchOnWindowFocus: false` — a maioria das chamadas é contra o próprio backend local, então retry automático só atrasa o erro aparecer) envolvendo as rotas via `QueryClientProvider`.

Dois usos concretos, não uma reescrita do app inteiro:
- `GameChat.tsx`: `useQuery({ queryKey: ['load_game', sessionId], ... })` substitui o `useEffect` de carregamento inicial da ficha. `staleTime: 0` de propósito — HP, inventário e combate mudam a cada turno, então nunca é seguro servir do cache sem revalidar.
- `Home.tsx`: `useMutation` substitui o `try/finally` + `setLoading` manual de "confirma que o save existe no servidor antes de navegar".

O `sendAction` de `GameChat.tsx` (o turno de chat via SSE, ADR-0012) **não** virou `useMutation` — uma mutation do TanStack Query modela uma chamada de request/response única; o turno é uma sequência de eventos incrementais (`token`, `tool_event`, `state`) que atualizam vários pedaços de estado ao longo do tempo, um encaixe ruim para o modelo de mutation. Continua uma função assíncrona comum.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Redux (ou Redux Toolkit + RTK Query) | ecossistema grande, DevTools maduro, о que a maioria dos tutoriais de React ensina | Redux "puro" resolve estado de **cliente** compartilhado (carrinho, tema, seleção) — este projeto não tem esse tipo de estado global; RTK Query já é, na prática, outra implementação da mesma ideia do TanStack Query (cache por chave, invalidação), só que acoplada ao Redux | traria a maquinaria de um gerenciador de estado de cliente inteiro pra resolver um problema que é só de estado de servidor — peso conceitual sem ganho real aqui |
| Continuar com `useEffect` + `axios`, só limpando a duplicação num hook próprio (`useLoadGame`) | zero dependência nova, controle total do código | reimplementa loading/erro/cache — exatamente o que uma lib madura já testa; sem cache, "voltar duas telas e voltar pro jogo" continua refazendo a chamada à toa | escrever de novo um cache com invalidação por chave, só que pior testado, não é o tipo de "não usar biblioteca" que os outros ADRs de arquitetura escolhem (ver `docs/adr/README.md`, "decisões já tomadas sem ADR") — lá a lógica é não esconder o que o projeto existe pra demonstrar (LangChain, banco vetorial); aqui não há nada de específico do domínio pra demonstrar em reimplementar cache de HTTP |
| SWR (biblioteca concorrente, API parecida) | mais leve, API também simples | TanStack Query tem suporte melhor a mutations com callbacks (`onSuccess`/`onError`) usados em `Home.tsx`, e é a opção mais citada no ecossistema React atual — sem motivo concreto pra preferir SWR aqui | escolha entre duas opções tecnicamente equivalentes; TanStack Query levou por adoção/documentação, não por uma diferença técnica que importasse pra este projeto |

## Consequências

**Ganhamos:**
- `GameChat.tsx` perdeu o `try/catch`/`setNotFound` manual — `isError` do próprio `useQuery` dirige a tela de "sessão não encontrada".
- `Home.tsx::loadGame` (a `useMutation`) centraliza sucesso (navegar) e erro (alertar) num só lugar, em vez de misturado no meio de um `try/finally`.
- Cache por `sessionId`: navegar para outro personagem e voltar não refaz a chamada de `load_game` à toa dentro da janela de `staleTime` — aqui `staleTime: 0` desliga isso deliberadamente para os dados voláteis do jogo, mas a infraestrutura de cache fica pronta pro que vier depois (ex: lista de saves do servidor, na Etapa 8).

**Pagamos:**
- Mais uma dependência de runtime (`@tanstack/react-query`, ~15kB gzip) num app que antes não tinha gerenciador de estado de servidor nenhum.
- O turno de chat (a parte mais visível da Etapa 7) **não** usa TanStack Query — é uma função assíncrona lendo um stream, por bom motivo (ver Decisão), mas isso significa que a lib resolve menos do "estado do jogo" do que o nome do ADR sozinho sugeriria. Vale deixar isso explícito para não dar a impressão de que todo fetch do app passou a ser `useQuery`.

**Fica em aberto:**
- A Etapa 8 (contas e biblioteca de heróis) é onde `staleTime`/invalidação de cache de verdade importam mais — uma lista de heróis do servidor, com criar/arquivar, é o caso de uso onde o TanStack Query paga mais do que paga aqui.

## Como saber que erramos

Se a Etapa 8 chegar e a lista de saves do servidor continuar precisando de `useEffect` manual porque o padrão `useQuery`/`useMutation` não encaixou bem nela, reavaliar se TanStack Query resolve o problema certo — a hipótese aqui é que ele paga mais quanto mais telas dependerem de dado de servidor cacheável, e a Etapa 8 é o primeiro teste real dessa hipótese.

## Referências

- [TanStack Query — documentação oficial](https://tanstack.com/query/latest) — `useQuery`/`useMutation`, `staleTime`, `QueryClient`.
- `PLANO_MESTRE.md`, Etapa 7 — "TanStack Query substitui os `useEffect` + `axios` soltos".
- [ADR-0012](0012-sse-em-vez-de-websocket-ou-polling.md) — por que o turno de chat continua fora do modelo de mutation.
