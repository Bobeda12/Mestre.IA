import { useEffect, useState } from 'react';
import type { AcaoDireta, AliadoVisual, Cena, EntidadeMundo, InimigoVisual, PessoaMundo, Selecao } from '../../lib/gameplay';
import { SAIDA_LIVRE, alvoValido, spriteInimigo } from '../../lib/gameplay';
import { iconeEntidade } from '../../lib/verbos';
import { getLocalImage } from '../../lib/utils';
import PixelIcon from '../PixelIcon';
import PixelBar from '../PixelBar';
import FloatingCombatText from '../FloatingCombatText';

// Fase 6 ("uma tela só", ADR-0036) — o palco é a cena inteira: herói,
// aliados, PESSOAS do Mundo Vivo (antes num painel separado), inimigos, e
// uma prateleira com os objetos e saídas do lugar. Clicar em qualquer um
// deles seleciona (uma seleção só, guardada em GameChat) e o dock embaixo
// mostra o que dá para fazer com o selecionado. Altura fixa: o palco não
// rola, só a narrativa embaixo dele.
interface Props {
  nome: string;
  classe: string;
  hp: number;
  hpMax: number;
  local: string;
  clima: string;
  hora: number | null;
  combate: boolean;
  ocupado: boolean;
  cena: Cena | null;
  inimigos: InimigoVisual[];
  aliados: AliadoVisual[];
  pessoas: PessoaMundo[];
  entidades: EntidadeMundo[];
  escondido: boolean;
  bonusDefesa: number;
  danos: { id: number; valor: number; idx: number }[];
  resultado: string | null;
  selecao: Selecao | null;
  aoSelecionar: (selecao: Selecao | null) => void;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
  aoInspecionarHeroi: () => void;
  aoRecolher: () => void;
}

const DURACAO_RESULTADO_MS = 4000;

export default function Palco(p: Props) {
  const caido = p.hp <= 0;
  const bloqueado = p.ocupado;
  const alvo = p.combate ? alvoValido(p.selecao?.tipo === 'inimigo' ? p.selecao.id : null, p.inimigos) : undefined;
  const tema = /floresta|bosque|estrada|lobo/i.test(`${p.local} ${p.cena?.nome}`) ? 'bosque'
    : /ruína|ruina|cripta|masmorra|templo|tumba|farol|caverna/i.test(`${p.local} ${p.cena?.nome}`) ? 'ruinas' : 'cidade';
  const noite = p.hora !== null && (p.hora >= 18 || p.hora < 6);
  const progresso = p.cena && p.cena.meta > 0 ? Math.min(p.cena.progresso / p.cena.meta, 1) : 0;

  // O resultado do juiz aparece como faixa por alguns segundos e some — a
  // mesma narrativa já entra no log, então aqui é só o "flash" da ação.
  // A sincronização com a prop acontece durante o render (padrão do React
  // para "resetar estado quando uma prop muda"); o efeito só cuida do
  // timer, que é a parte que de fato precisa de um sistema externo.
  const [resultadoVisivel, setResultadoVisivel] = useState<string | null>(null);
  const [resultadoAnterior, setResultadoAnterior] = useState<string | null>(null);
  if (p.resultado !== resultadoAnterior) {
    setResultadoAnterior(p.resultado);
    setResultadoVisivel(p.resultado);
  }
  useEffect(() => {
    if (!resultadoVisivel) return;
    const id = setTimeout(() => setResultadoVisivel(null), DURACAO_RESULTADO_MS);
    return () => clearTimeout(id);
  }, [resultadoVisivel]);

  const selecionado = (tipo: Selecao['tipo'], id: string) => p.selecao?.tipo === tipo && p.selecao.id === id;
  const alternar = (tipo: Selecao['tipo'], id: string) => p.aoSelecionar(selecionado(tipo, id) ? null : { tipo, id });

  return (
    <section className={`palco adventure-world adventure-world--${tema} ${noite ? 'adventure-world--noite' : ''}`}
      aria-label="Cena interativa da aventura" aria-busy={p.ocupado}>
      <div className="adventure-world__sky" aria-hidden="true" />
      <div className="adventure-world__silhouette" aria-hidden="true" />
      <div className="adventure-world__floor" aria-hidden="true" />
      {/chuva|tempestade/i.test(p.clima) && <div className="absolute inset-0 animate-chuva opacity-40 pointer-events-none" aria-hidden="true" />}

      <div className="palco__badge">
        <div className="flex items-center justify-between gap-3">
          <span className="font-pixel-title text-[8px] text-rpg-gold tracking-widest">{p.combate ? `ENCONTRO${p.cena?.rodada ? ` · RODADA ${p.cena.rodada}` : ''}` : 'EXPLORACAO'}</span>
          {/* Item do pedido "palco recolhível" — mesmo botão sempre no
              mesmo canto do badge, pra não competir com [OBJETIVO] no
              canto oposto. */}
          <button type="button" onClick={p.aoRecolher} aria-label="Recolher o palco" className="shrink-0 opacity-70 hover:opacity-100 transition-opacity">
            <PixelIcon name="seta" size={10} className="rotate-90" />
          </button>
        </div>
        <span className="font-rpg text-sm text-white leading-tight">{p.cena?.nome || p.local || 'Sua aventura'}</span>
      </div>
      {p.cena && (p.cena.objetivo || p.cena.descricao) && (
        <div className="palco__objective font-rpg" title={p.cena.descricao}>
          <span><PixelIcon name="pergaminho" size={12} /> {p.cena.objetivo || p.cena.descricao}{p.cena.meta > 0 && <b> {p.cena.progresso}/{p.cena.meta}</b>}</span>
          {p.cena.meta > 0 && <div className="adventure-objective__track"><span style={{ width: `${progresso * 100}%` }} /></div>}
        </div>
      )}

      <div className="adventure-world__party">
        <div className="palco__group">
          <button type="button" className={`adventure-actor adventure-actor--hero ${caido ? 'adventure-actor--dead' : ''}`}
            onClick={p.aoInspecionarHeroi} aria-label={`Inspecionar ${p.nome}, ${p.hp} de ${p.hpMax} pontos de vida`}>
            <span className="adventure-actor__tag font-rpg uppercase tracking-wide">{p.escondido ? 'OCULTO' : p.bonusDefesa > 0 ? `DEFESA +${p.bonusDefesa}` : p.classe}</span>
            <img className="adventure-actor__sprite" src={getLocalImage('classes', p.classe || 'Guerreiro')} alt="" draggable={false} />
            <span className="adventure-actor__shadow" aria-hidden="true" />
            <span className="adventure-actor__name font-rpg">{p.nome || 'Herói'}</span>
            <span className="adventure-actor__life font-rpg">{p.hp}/{p.hpMax} PV</span>
            <PixelBar value={p.hp} max={p.hpMax} segments={8} colorClass="bg-emerald-500" />
          </button>

          {p.aliados.map(aliado => (
            <div key={`aliado:${aliado.nome}`} className={`adventure-actor adventure-actor--ally ${aliado.hp <= 0 ? 'adventure-actor--dead' : ''}`}
              aria-label={`${aliado.nome}, aliado, ${aliado.hp}/${aliado.hp_max} PV`}>
              <span className="adventure-actor__tag font-rpg uppercase tracking-wide">{aliado.hp <= 0 ? 'CAIDO' : p.combate ? (aliado.ja_agiu ? 'JA AGIU' : 'PRONTO') : 'ALIADO'}</span>
              <img className="adventure-actor__sprite" src={getLocalImage('races', aliado.raca || 'Humano')} alt="" draggable={false} />
              <span className="adventure-actor__shadow" aria-hidden="true" />
              <span className="adventure-actor__name font-rpg">{aliado.nome}</span>
              <span className="adventure-actor__life font-rpg">{aliado.hp}/{aliado.hp_max} PV</span>
              <PixelBar value={aliado.hp} max={aliado.hp_max} segments={8} colorClass="bg-sky-500" />
              {p.combate && aliado.hp > 0 && (
                <button type="button" className="adventure-actor__ally-attack font-pixel-title"
                  disabled={bloqueado || aliado.ja_agiu || !alvo}
                  title={!alvo ? 'Escolha um inimigo primeiro' : aliado.ja_agiu ? 'Já atacou nesta rodada' : `${aliado.nome} ataca ${alvo}`}
                  onClick={() => alvo && p.aoAgir({ acao: 'atacar_com_aliado', aliado: aliado.nome, alvo }, `${aliado.nome} ataca ${alvo}`)}>
                  ATACAR
                </button>
              )}
            </div>
          ))}

          {/* Pessoas do Mundo Vivo: em combate ficam em segundo plano. */}
          {p.pessoas.map(npc => (
            <button type="button" key={`npc:${npc.id}`}
              className={`adventure-actor adventure-actor--npc ${selecionado('pessoa', npc.id) ? 'adventure-actor--selected' : ''} ${p.combate ? 'adventure-actor--bystander' : ''}`}
              disabled={bloqueado || p.combate || caido}
              aria-pressed={selecionado('pessoa', npc.id)}
              aria-label={`Selecionar ${npc.nome}, ${npc.disposicao}, confiança ${npc.confianca}`}
              title={npc.descricao}
              onClick={() => alternar('pessoa', npc.id)}>
              <span className="adventure-actor__tag font-rpg uppercase">{npc.disposicao}</span>
              <img className="adventure-actor__sprite" src={getLocalImage('races', npc.raca || 'Humano')} alt="" draggable={false} />
              <span className="adventure-actor__shadow" aria-hidden="true" />
              <span className="adventure-actor__name font-rpg">{npc.nome}</span>
              <span className="adventure-actor__life font-rpg">confiança {npc.confianca}</span>
            </button>
          ))}
        </div>

        <div className="adventure-world__opponents">
          {p.inimigos.map((inimigo, indice) => (
            <button type="button" key={inimigo.nome}
              className={`adventure-actor ${alvo === inimigo.nome && p.combate ? 'adventure-actor--selected' : ''} ${inimigo.hp <= 0 ? 'adventure-actor--dead' : ''}`}
              disabled={inimigo.hp <= 0 || inimigo.afastado || bloqueado || !p.combate}
              onClick={() => p.aoSelecionar({ tipo: 'inimigo', id: inimigo.nome })}
              aria-pressed={alvo === inimigo.nome && p.combate}
              aria-label={`Selecionar ${inimigo.nome}, ${inimigo.hp}/${inimigo.max_hp} PV${inimigo.intencao ? `, intenção: ${inimigo.intencao}` : ''}`}>
              <span className="adventure-actor__tag font-rpg uppercase tracking-wide">{inimigo.afastado ? 'AFASTADO' : inimigo.hp <= 0 ? 'DERROTADO' : inimigo.intencao || 'OBSERVANDO'}</span>
              <FloatingCombatText itens={p.danos.filter(dano => dano.idx === indice).map(dano => ({ id: dano.id, texto: `−${dano.valor}`, cor: 'text-red-300' }))} />
              <img className="adventure-actor__sprite" src={spriteInimigo(inimigo)} alt="" draggable={false} />
              <span className="adventure-actor__shadow" aria-hidden="true" />
              <span className="adventure-actor__name font-rpg">{inimigo.nome}</span>
              <span className="adventure-actor__life font-rpg">{inimigo.hp}/{inimigo.max_hp} PV · DEF {inimigo.ca}</span>
              <PixelBar value={inimigo.hp} max={inimigo.max_hp} segments={8} colorClass="bg-red-500" />
              {Object.entries(inimigo.efeitos ?? {}).filter(([, duracao]) => duracao > 0).map(([efeito, duracao]) => <span className="adventure-actor__effect font-rpg" key={efeito}>{efeito.replaceAll('_', ' ')} · {duracao}</span>)}
            </button>
          ))}
          {!p.combate && !p.inimigos.length && !p.pessoas.length && (
            <div className="adventure-world__landmark font-rpg" aria-hidden="true"><PixelIcon name={tema === 'ruinas' ? 'pergaminho' : 'bau'} size={44} /><span>O mundo espera sua decisão</span></div>
          )}
        </div>
      </div>

      {p.entidades.length > 0 && (
        <div className="palco__shelf font-rpg" aria-label="Objetos e caminhos deste lugar">
          {p.entidades.map(e => {
            const saida = e.tipo === 'saida';
            const destino = saida && e.destino && e.destino !== SAIDA_LIVRE ? e.destino : null;
            return (
              <button type="button" key={`obj:${e.id}`} disabled={bloqueado || caido || p.combate}
                aria-pressed={selecionado('objeto', e.id)}
                className={`palco__shelf-item ${saida ? 'palco__shelf-item--exit' : ''} ${selecionado('objeto', e.id) ? 'is-selected' : ''}`}
                title={`${e.descricao}${destino ? ` → ${destino}` : ''}`}
                onClick={() => alternar('objeto', e.id)}>
                <PixelIcon name={iconeEntidade(e)} size={16} className={saida ? '-rotate-90' : ''} />
                <span className="min-w-0 truncate">{e.nome}</span>
                {(e.estado !== 'intacto' || e.descoberto) && <small>{e.estado !== 'intacto' ? e.estado : 'examinado'}</small>}
              </button>
            );
          })}
        </div>
      )}

      {resultadoVisivel && <p className="palco__result font-rpg" role="status">{resultadoVisivel}</p>}
      {p.ocupado && <div className="adventure-world__busy font-rpg" role="status"><PixelIcon name="dado" size={18} /> Resolvendo sua ação…</div>}
    </section>
  );
}
