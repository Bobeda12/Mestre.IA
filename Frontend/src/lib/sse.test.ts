import { describe, expect, it } from 'vitest';
import { parseSseStream } from './sse';

// Constrói uma Response cujo corpo chega em pedaços (`chunks`) — simula a
// rede entregando o stream aos poucos, não tudo de uma vez, que é
// exatamente o caso que um parser ingênuo (split by "\n\n" sem buffer)
// erraria.
function respostaFalsa(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream);
}

async function coletar(resp: Response) {
  const eventos = [];
  for await (const evt of parseSseStream(resp)) eventos.push(evt);
  return eventos;
}

describe('parseSseStream', () => {
  it('lê um frame simples inteiro num único chunk', async () => {
    const resp = respostaFalsa(['event: token\ndata: {"texto":"Olá"}\n\n']);
    const eventos = await coletar(resp);
    expect(eventos).toEqual([{ event: 'token', data: { texto: 'Olá' } }]);
  });

  it('remonta um frame cortado no meio entre dois chunks de rede', async () => {
    // O separador "\n\n" fica dividido entre os dois pedaços — é o caso
    // que testa se o parser usa um buffer entre leituras, ou se ele perde
    // o frame por só olhar um chunk de cada vez.
    const resp = respostaFalsa(['event: token\ndata: {"tex', 'to":"Olá"}\n\n']);
    const eventos = await coletar(resp);
    expect(eventos).toEqual([{ event: 'token', data: { texto: 'Olá' } }]);
  });

  it('entrega múltiplos frames do mesmo chunk, em ordem', async () => {
    const resp = respostaFalsa([
      'event: token\ndata: {"texto":"a"}\n\nevent: token\ndata: {"texto":"b"}\n\n',
    ]);
    const eventos = await coletar(resp);
    expect(eventos.map(e => e.data)).toEqual([{ texto: 'a' }, { texto: 'b' }]);
  });

  it('ignora um frame com JSON malformado sem travar os seguintes', async () => {
    const resp = respostaFalsa([
      'event: token\ndata: {isso nao e json}\n\nevent: token\ndata: {"texto":"depois"}\n\n',
    ]);
    const eventos = await coletar(resp);
    expect(eventos).toEqual([{ event: 'token', data: { texto: 'depois' } }]);
  });

  it('usa "message" como tipo padrão quando o frame não declara "event:"', async () => {
    const resp = respostaFalsa(['data: {"x":1}\n\n']);
    const eventos = await coletar(resp);
    expect(eventos[0].event).toBe('message');
  });

  it('não produz nada para uma resposta sem corpo', async () => {
    const resp = new Response(null);
    const eventos = await coletar(resp);
    expect(eventos).toEqual([]);
  });
});
