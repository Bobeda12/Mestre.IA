import { useEffect, useRef } from 'react';
import RollCard, { type DadosRolagem } from '../RollCard';
import StatusCard, { type EventoStatus } from '../StatusCard';
import PanelFrame from '../PanelFrame';
import PixelIcon from '../PixelIcon';
import { renderizarNarrativa } from '../../lib/utils';

// Fase 6 ("uma tela só") — o log de narrativa sai de GameChat.tsx como
// componente de apresentação puro: recebe as mensagens e devolve cliques.
// O tipo `Message` mora aqui porque é o contrato entre o log e quem o
// alimenta (GameChat continua dono do estado e do streaming).
export type Message =
  // `turnoIndex` (Etapa 9) é a posição desta narração em `historico_chat`
  // no servidor — o que o 👍/👎 manda pra POST /personagens/:id/feedback.
  // `raw` (Fase 1 da revisão de gameplay) só existe em bolhas de
  // assistente em streaming: o texto CRU acumulado, nunca limpo/truncado.
  // `id` é a chave estável do React (o modo de emergência pode cortar
  // mensagens do fim da lista; índice como key reiniciaria animações).
  | { kind: 'texto'; id: number; role: 'user' | 'assistant' | 'system'; content: string; raw?: string; isError?: boolean; turnoIndex?: number; feedback?: 1 | -1 }
  // Etapa 10 (A-7): cura e morte de inimigo chegam pelo mesmo frame
  // `tool_event` que ataque/teste, só com um `dados.tipo` diferente.
  | { kind: 'rolagem'; id: number; dados: DadosRolagem | EventoStatus };

interface Props {
  messages: Message[];
  loading: boolean;
  comentarioAbertoIdx: number | null;
  setComentarioAbertoIdx: (idx: number | null) => void;
  comentarioTexto: string;
  setComentarioTexto: (texto: string) => void;
  /** `idx` é o índice no array (é o que GameChat.enviarFeedback espera). */
  enviarFeedback: (idx: number, turnoIndex: number, valor: 1 | -1, comentario?: string) => void;
}

export default function LogNarrativa(p: Props) {
  // Auto-scroll: o sentinel no fim do log é rolado a cada mensagem nova ou
  // token de streaming. Funciona porque o log é o ÚNICO ancestral rolável
  // da coluna central (palco com overflow:hidden) — ver ADR-0036.
  const fimRef = useRef<HTMLDivElement>(null);
  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [p.messages]);

  const fecharComentario = () => { p.setComentarioAbertoIdx(null); p.setComentarioTexto(''); };

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-8 space-y-6 custom-scrollbar scroll-smooth" role="log" aria-live="polite" aria-atomic="false">
      {p.messages.map((msg, idx) => {
        if (msg.kind === 'rolagem') {
          if (msg.dados.tipo === 'cura' || msg.dados.tipo === 'morte_inimigo' || msg.dados.tipo === 'morte_aliado') {
            return <StatusCard key={msg.id} dados={msg.dados} />;
          }
          return <RollCard key={msg.id} dados={msg.dados as DadosRolagem} />;
        }

        if (msg.role === 'system') {
          return (
            <div key={msg.id} className="flex justify-center my-2 animate-fade-in">
              <div className="bg-yellow-900/20 border border-yellow-700/30 text-yellow-500 px-4 py-2 text-xs font-mono flex items-center gap-2">
                <PixelIcon name="dado" size={12} /> {msg.content}
              </div>
            </div>
          );
        }

        // A narração do Mestre é a protagonista visual (moldura de
        // pergaminho); a ação do jogador é só uma linha alinhada à direita.
        if (msg.role === 'user') {
          return (
            <div key={msg.id} className="flex justify-end animate-fade-in">
              <div className="max-w-[80%] md:max-w-[70%] text-right border-r-2 border-rpg-gold/30 pr-3">
                <span className="block font-pixel-title text-[8px] tracking-widest text-rpg-gold/70 mb-1">VOCÊ</span>
                <p className="whitespace-pre-wrap break-words font-rpg text-sm md:text-base italic text-gray-300 leading-relaxed">{msg.content}</p>
              </div>
            </div>
          );
        }

        const podeAvaliar = !msg.isError && msg.turnoIndex !== undefined;
        return (
          <div key={msg.id} className="animate-fade-in">
            <PanelFrame borderWidth={10} className={`relative max-w-[820px] mx-auto p-4 md:p-6 ${msg.isError ? 'bg-amber-950/20' : 'bg-[#1a140d]/85'} backdrop-blur-sm`}>
              <span className={`absolute -top-3 left-3 px-2 py-0.5 font-pixel-title text-[8px] tracking-widest ${msg.isError ? 'bg-amber-800 text-amber-100' : 'bg-rpg-leather text-rpg-gold'}`}>
                {msg.isError ? 'AVISO' : 'MESTRE'}
              </span>
              <p className={`whitespace-pre-wrap break-words font-rpg text-base md:text-lg leading-loose ${msg.isError ? 'text-amber-200 italic' : 'text-gray-300'}`}>
                {msg.isError ? msg.content : renderizarNarrativa(msg.content)}
              </p>
              {podeAvaliar && (p.comentarioAbertoIdx === idx ? (
                <div className="mt-2 -mb-1 flex flex-col gap-1.5">
                  <input
                    type="text"
                    autoFocus
                    value={p.comentarioTexto}
                    onChange={(e) => p.setComentarioTexto(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') { p.enviarFeedback(idx, msg.turnoIndex!, -1, p.comentarioTexto.trim() || undefined); fecharComentario(); }
                    }}
                    maxLength={500}
                    placeholder="O que ficou estranho? (opcional)"
                    aria-label="O que ficou estranho? Opcional."
                    className="bg-black/40 border border-gray-700 px-2 py-1 text-xs text-gray-200 outline-none focus:border-red-700 w-full max-w-xs"
                  />
                  <div className="flex gap-2">
                    <button type="button" onClick={() => { p.enviarFeedback(idx, msg.turnoIndex!, -1, p.comentarioTexto.trim() || undefined); fecharComentario(); }}
                      className="text-[11px] font-bold text-red-400 hover:text-red-300">Enviar</button>
                    <button type="button" onClick={fecharComentario} className="text-[11px] text-gray-500 hover:text-gray-300">Cancelar</button>
                  </div>
                </div>
              ) : (
                // `PixelIcon` é um PNG com cor própria: o voto vira o FUNDO do
                // chip, não a cor do ícone.
                <div className="flex gap-2 mt-2 -mb-1">
                  <button type="button" onClick={() => p.enviarFeedback(idx, msg.turnoIndex!, 1)} disabled={msg.feedback !== undefined}
                    aria-label="Gostei desta narração"
                    className={`p-2.5 border-2 transition-all active:scale-95 ${msg.feedback === 1
                      ? 'border-emerald-500 bg-emerald-600/90 shadow-[0_0_8px_rgba(16,185,129,0.7)]'
                      : 'border-transparent text-gray-600 hover:text-emerald-500 hover:border-gray-700 disabled:hover:text-gray-600 disabled:hover:border-transparent'}`}
                  ><PixelIcon name="polegar-cima" size={16} /></button>
                  <button type="button" onClick={() => { if (msg.feedback === undefined) p.setComentarioAbertoIdx(idx); }} disabled={msg.feedback !== undefined}
                    aria-label="Não gostei desta narração"
                    className={`p-2.5 border-2 transition-all active:scale-95 ${msg.feedback === -1
                      ? 'border-red-500 bg-red-600/90 shadow-[0_0_8px_rgba(239,68,68,0.7)]'
                      : 'border-transparent text-gray-600 hover:text-red-500 hover:border-gray-700 disabled:hover:text-gray-600 disabled:hover:border-transparent'}`}
                  ><PixelIcon name="polegar-baixo" size={16} /></button>
                </div>
              ))}
            </PanelFrame>
          </div>
        );
      })}

      {p.loading && <div className="text-center py-4 text-xs text-gray-600 animate-pulse italic">O mestre está narrando...</div>}
      <div ref={fimRef} className="h-4" />
    </div>
  );
}
