// Parser de SSE feito à mão (Etapa 7, ADR-0012) — `EventSource` não manda
// corpo em POST, e `/chat/stream` precisa mandar `session_id`/`action`.
// `fetch` + `ReadableStream` dá o corpo; este módulo só sabe cortar esse
// fluxo de bytes em frames `event: ...\ndata: ...\n\n`, sem saber nada do
// jogo (isso é papel de quem consome, em GameChat.tsx).

export interface SseEvent<T = unknown> {
  event: string;
  data: T;
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

export async function postSse(url: string, body: unknown): Promise<AsyncGenerator<SseEvent>> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    let detalhe: string | undefined;
    try {
      detalhe = (await resp.json()).detail;
    } catch {
      // Corpo não é JSON (ou stream já fechou) — sem detalhe, cai no genérico.
    }
    throw new Error(detalhe ?? `Falha ao abrir o stream (${resp.status})`);
  }
  return parseSseStream(resp);
}
