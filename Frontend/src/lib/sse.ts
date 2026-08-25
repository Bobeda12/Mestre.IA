// Parser de SSE feito à mão (Etapa 7, ADR-0012) — `EventSource` não manda
// corpo em POST, e `/chat/stream` precisa mandar `session_id`/`action`.
// `fetch` + `ReadableStream` dá o corpo; este módulo só sabe cortar esse
// fluxo de bytes em frames `event: ...\ndata: ...\n\n`, sem saber nada do
// jogo (isso é papel de quem consome, em GameChat.tsx).

import { getChaveGemini } from './config';

export interface SseEvent<T = unknown> {
  event: string;
  data: T;
}

/** Erro de `postSse` antes da stream abrir — `codigo` (Etapa 15, BYOK)
 *  distingue "bateu no teto diário" (`teto_diario_atingido`) de qualquer
 *  outro 4xx/5xx, pra GameChat.tsx decidir se oferece o modal de BYOK. */
export class ErroSse extends Error {
  codigo?: string;
  constructor(mensagem: string, codigo?: string) {
    super(mensagem);
    this.codigo = codigo;
  }
}

function parseFrame(raw: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

export async function* parseSseStream(response: Response): AsyncGenerator<SseEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex: number;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const frame = parseFrame(raw);
        if (frame) yield frame;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function postSse(
  url: string,
  body: unknown,
  opts?: { modoEmergencia?: boolean },
): Promise<AsyncGenerator<SseEvent>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // BYOK (Etapa 15) — a chave do jogador (se houver) vai em todo pedido de
  // turno; nunca em `lib/api.ts` (o axios compartilhado), porque `/chat/stream`
  // usa `fetch` direto, não axios, e um interceptor lá não alcançaria isto.
  // `modoEmergencia` é como GameChat.tsx reenvia a MESMA ação depois que a
  // chave própria falhou, topando gastar a cota do servidor — por isso NÃO
  // manda `X-Gemini-Key` neste caso: se mandasse as duas, o backend usaria
  // de novo a chave (já sabida quebrada) e ignoraria a emergência.
  if (opts?.modoEmergencia) {
    headers["X-Modo-Emergencia"] = "1";
  } else {
    const chave = getChaveGemini();
    if (chave) headers["X-Gemini-Key"] = chave;
  }

  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    // Mesmo comportamento do axios em lib/api.ts (`withCredentials: true`)
    // — sem isso, o cookie de sessão não vai quando front e back estão em
    // origens diferentes (localhost:5173 → localhost:8000 em dev), e todo
    // /chat/stream cai em 401 mesmo com sessão válida.
    credentials: "include",
  });
  if (!resp.ok) {
    // Etapa 10 (A-3) — o `detail` do backend já é uma frase pronta pro
    // jogador ler (429 do teto diário, 404 de sessão sumida, etc.) — jogar
    // isso fora e mostrar só o código escondia exatamente a mensagem
    // honesta que o teto de custo existe para dar.
    //
    // Etapa 15 (BYOK) — `detail` pode ser uma string simples (like antes)
    // ou um objeto `{codigo, mensagem}` (teto diário atingido) — `codigo`
    // é o que deixa GameChat.tsx oferecer o modal de BYOK.
    let mensagem: string | undefined;
    let codigo: string | undefined;
    try {
      const detail = (await resp.json()).detail;
      if (typeof detail === "string") mensagem = detail;
      else if (detail && typeof detail === "object") {
        mensagem = detail.mensagem;
        codigo = detail.codigo;
      }
    } catch {
      // Corpo não é JSON (ou stream já fechou) — sem detalhe, cai no genérico.
    }
    throw new ErroSse(mensagem ?? `Falha ao abrir o stream (${resp.status})`, codigo);
  }
  return parseSseStream(resp);
}
