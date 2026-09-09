import type { Progressao } from '../../lib/gameplay';
import PixelIcon from '../PixelIcon';

// Item 10 da rodada de melhorias pós-Fase-6 — antes, "técnicas" (habilidades)
// só apareciam num popover DENTRO do dock, e só em combate; talentos e
// especializações escolhidos no level-up (LevelUpModal.tsx) nunca eram
// exibidos em lugar nenhum depois de escolhidos. A trilha de níveis 1–N, que
// morava na aba JORNADA, muda pra cá — é sobre a build do personagem, não
// sobre a missão em andamento.
interface Props {
  progressao: Progressao | null;
  nivel: number;
}

function Secao({ titulo, icone, children }: { titulo: string; icone: Parameters<typeof PixelIcon>[0]['name']; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[10px] text-gray-300 uppercase font-rpg tracking-widest flex items-center gap-2"><PixelIcon name={icone} size={12} /> {titulo}</h3>
      {children}
    </section>
  );
}

export default function AbaPoderes(p: Props) {
  const habilidades = p.progressao?.habilidades ?? [];
  const talentos = p.progressao?.talentos ?? [];
  const especializacoes = Object.entries(p.progressao?.especializacoes ?? {});
  const foco = p.progressao?.recurso;

  return (
    <div className="animate-fade-in space-y-5">
      {!p.progressao && <p className="text-sm text-gray-400 font-rpg text-center py-4">Progressão indisponível.</p>}

      {habilidades.length > 0 && (
        <Secao titulo="Técnicas" icone="pocao-azul">
          <div className="space-y-1.5">
            {habilidades.map(h => {
              const trancada = h.nivel > p.nivel;
              return (
                <div key={h.id} className={`border-2 p-2 space-y-0.5 ${trancada ? 'border-gray-800 bg-black/20 opacity-60' : 'border-gray-700 bg-black/40'}`}>
                  <p className="flex items-center justify-between gap-2 font-rpg text-sm text-gray-100">
                    <strong>{h.nome}</strong>
                    <span className="text-[11px] text-sky-300 shrink-0">{h.custo} {foco?.nome ?? 'Foco'}</span>
                  </p>
                  <p className="text-[11px] text-gray-300 leading-snug">{h.descricao}</p>
                  {trancada && <p className="text-[10px] text-gray-500 font-rpg">Desbloqueia no nível {h.nivel}</p>}
                </div>
              );
            })}
          </div>
        </Secao>
      )}

      {talentos.length > 0 && (
        <Secao titulo="Talentos" icone="pergaminho">
          <div className="space-y-1.5">
            {talentos.map(t => (
              <div key={t.id} className="border-2 border-gray-700 bg-black/40 p-2 space-y-0.5">
                <p className="font-rpg text-sm text-gray-100">{t.nome}</p>
                <p className="text-[11px] text-gray-300 leading-snug">{t.descricao}</p>
              </div>
            ))}
          </div>
        </Secao>
      )}

      {especializacoes.length > 0 && (
        <Secao titulo="Especializações" icone="seta">
          <div className="space-y-1">
            {especializacoes.map(([marco, nome]) => (
              <p key={marco} className="text-xs text-gray-200 font-rpg">Nível {marco}: <span className="text-rpg-gold">{nome}</span></p>
            ))}
          </div>
        </Secao>
      )}

      {p.progressao && (
        <Secao titulo={`Jornada 1–${p.progressao.nivel_maximo}`} icone="estrela">
          <p className="text-[11px] text-rpg-gold font-rpg">{p.progressao.estilo || 'Explore, resolva situações e vença encontros para evoluir.'}</p>
          <ol className="space-y-1">
            {p.progressao.niveis.map(etapa => {
              const atual = etapa.nivel === p.nivel;
              const feito = etapa.nivel < p.nivel;
              return (
                <li key={etapa.nivel} aria-current={atual ? 'step' : undefined}
                  className={`flex gap-2 border p-1.5 ${atual ? 'border-rpg-gold bg-rpg-gold/10 text-gray-100' : feito ? 'border-gray-600 text-gray-200' : 'border-gray-800 text-gray-500'}`}>
                  <span className="font-pixel-title text-[10px] min-w-6 text-center pt-0.5 text-rpg-gold/80">{etapa.nivel}</span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-rpg leading-snug">{etapa.descricao}</p>
                    <p className="text-[10px] text-gray-500">{etapa.xp} XP{atual ? ' · Você está aqui' : feito ? ' · Conquistado' : ''}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Secao>
      )}

      {habilidades.length === 0 && talentos.length === 0 && especializacoes.length === 0 && !p.progressao && (
        <p className="text-sm text-gray-400 font-rpg text-center py-4">Nenhum poder desbloqueado ainda.</p>
      )}
    </div>
  );
}
