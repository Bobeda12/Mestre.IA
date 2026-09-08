import { useState } from 'react';
import type { AcaoDireta, Cena, InimigoVisual, Progressao } from '../lib/gameplay';
import { alvoValido, spriteInimigo } from '../lib/gameplay';
import { getLocalImage } from '../lib/utils';
import PixelIcon, { type PixelIconName } from './PixelIcon';
import PixelBar from './PixelBar';
import FloatingCombatText from './FloatingCombatText';

interface Props {
  nome: string;
  classe: string;
  nivel: number;
  hp: number;
  hpMax: number;
  local: string;
  clima: string;
  hora: number | null;
  combate: boolean;
  ocupado: boolean;
  encerrado: boolean;
  cena: Cena | null;
  progressao: Progressao | null;
  marcos: string[];
  inimigos: InimigoVisual[];
  escondido: boolean;
  bonusDefesa: number;
  danos: { id: number; valor: number; idx: number }[];
  erro: string | null;
  resultado: string | null;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
  aoInspecionarHeroi: () => void;
}

const TATICAS: { acao: AcaoDireta['acao']; nome: string; dica: string; icone: PixelIconName }[] = [
  { acao: 'esquivar', nome: 'Esquivar', dica: 'Dificulte os ataques inimigos até seu próximo turno.', icone: 'seta' },
  { acao: 'investir', nome: 'Investir', dica: 'Ataque com mais força, expondo sua defesa.', icone: 'machado' },
  { acao: 'esconder_se', nome: 'Esconder', dica: 'Teste furtividade para preparar uma emboscada.', icone: 'adaga' },
  { acao: 'fugir', nome: 'Fugir', dica: 'Tente escapar; a perseguição pode ser perigosa.', icone: 'alerta' },
];

export default function AdventureStage(p: Props) {
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [aba, setAba] = useState<'acoes' | 'progressao'>('acoes');
  const [taticas, setTaticas] = useState(false);
  const alvo = alvoValido(selecionado, p.inimigos);
  const bloqueado = p.ocupado || p.encerrado;
  const caido = p.hp <= 0;
  const foco = p.progressao?.recurso;
  const progresso = p.cena && p.cena.meta > 0 ? Math.min(p.cena.progresso / p.cena.meta, 1) : 0;
  const tema = /floresta|bosque|estrada|lobo/i.test(`${p.local} ${p.cena?.nome}`) ? 'bosque'
    : /ruína|ruina|cripta|masmorra|templo|tumba/i.test(`${p.local} ${p.cena?.nome}`) ? 'ruinas' : 'cidade';
  const noite = p.hora !== null && (p.hora >= 18 || p.hora < 6);

  return (
    <section className="adventure-stage" aria-label="Cena interativa da aventura" aria-busy={p.ocupado}>
      <header className="adventure-stage__header">
        <div className="min-w-0">
          <span className="font-pixel-title text-[8px] text-rpg-gold tracking-widest">{p.combate ? 'ENCONTRO' : 'EXPLORAÇÃO'}{p.cena?.rodada ? ` · RODADA ${p.cena.rodada}` : ''}</span>
          <h2 className="font-rpg text-xl text-white mt-1">{p.cena?.nome || p.local || 'Sua aventura'}</h2>
        </div>
        <span className="adventure-stage__level font-pixel-title"><PixelIcon name="estrela" size={13} /> NV. {p.nivel}</span>
      </header>

      <div className={`adventure-world adventure-world--${tema} ${noite ? 'adventure-world--noite' : ''}`}>
        <div className="adventure-world__sky" aria-hidden="true" />
        <div className="adventure-world__silhouette" aria-hidden="true" />
        <div className="adventure-world__floor" aria-hidden="true" />
        {/chuva|tempestade/i.test(p.clima) && <div className="absolute inset-0 animate-chuva opacity-40 pointer-events-none" aria-hidden="true" />}
        <div className="adventure-world__party">
          <button type="button" className={`adventure-actor adventure-actor--hero ${caido ? 'adventure-actor--dead' : ''}`}
            onClick={p.aoInspecionarHeroi} aria-label={`Inspecionar ${p.nome}, ${p.hp} de ${p.hpMax} pontos de vida`}>
            <span className="adventure-actor__tag font-pixel-title">{p.escondido ? 'OCULTO' : p.bonusDefesa > 0 ? `DEFESA +${p.bonusDefesa}` : p.classe}</span>
            <img className="adventure-actor__sprite" src={getLocalImage('classes', p.classe || 'Guerreiro')} alt="" draggable={false} />
            <span className="adventure-actor__shadow" aria-hidden="true" />
            <span className="adventure-actor__name font-rpg">{p.nome || 'Herói'}</span>
            <span className="adventure-actor__life font-rpg">{p.hp}/{p.hpMax} PV</span>
            <PixelBar value={p.hp} max={p.hpMax} segments={8} colorClass="bg-emerald-500" />
          </button>
          <div className="adventure-world__opponents">
            {p.inimigos.map((inimigo, indice) => (
              <button type="button" key={inimigo.nome}
                className={`adventure-actor ${alvo === inimigo.nome && p.combate ? 'adventure-actor--selected' : ''} ${inimigo.hp <= 0 ? 'adventure-actor--dead' : ''}`}
                disabled={inimigo.hp <= 0 || bloqueado || !p.combate}
                onClick={() => setSelecionado(inimigo.nome)}
                aria-pressed={alvo === inimigo.nome && p.combate}
                aria-label={`Selecionar ${inimigo.nome}, ${inimigo.hp}/${inimigo.max_hp} PV${inimigo.intencao ? `, intenção: ${inimigo.intencao}` : ''}`}>
                <span className="adventure-actor__tag font-pixel-title">{inimigo.hp <= 0 ? 'DERROTADO' : inimigo.intencao || 'OBSERVANDO'}</span>
                <FloatingCombatText itens={p.danos.filter(dano => dano.idx === indice).map(dano => ({ id: dano.id, texto: `−${dano.valor}`, cor: 'text-red-300' }))} />
                <img className="adventure-actor__sprite" src={spriteInimigo(inimigo)} alt="" draggable={false} />
                <span className="adventure-actor__shadow" aria-hidden="true" />
                <span className="adventure-actor__name font-rpg">{inimigo.nome}</span>
                <span className="adventure-actor__life font-rpg">{inimigo.hp}/{inimigo.max_hp} PV · DEF {inimigo.ca}</span>
                <PixelBar value={inimigo.hp} max={inimigo.max_hp} segments={8} colorClass="bg-red-500" />
                {Object.entries(inimigo.efeitos ?? {}).filter(([, duracao]) => duracao > 0).map(([efeito, duracao]) => <span className="adventure-actor__effect font-rpg" key={efeito}>{efeito.replaceAll('_', ' ')} · {duracao}</span>)}
              </button>
            ))}
            {!p.combate && !p.inimigos.length && <div className="adventure-world__landmark font-rpg" aria-hidden="true"><PixelIcon name={tema === 'ruinas' ? 'pergaminho' : 'bau'} size={44} /><span>O mundo espera sua decisão</span></div>}
          </div>
        </div>
        {(p.cena?.interacoes.length ?? 0) > 0 && <div className="adventure-world__objects font-rpg" aria-label="Objetos e caminhos da cena">
          {p.cena!.interacoes.map((interacao, indice) => <button type="button" key={interacao.id} disabled={bloqueado || caido}
            title={interacao.descricao}
            onClick={() => p.aoAgir({ acao: 'interagir', interacao: interacao.id }, interacao.nome)}>
            <PixelIcon name={(['pergaminho', 'bau', 'seta', 'rosto'] as const)[indice % 4]} size={20} />
            <span>{interacao.nome}</span><span className="adventure-world__object-hint">{interacao.descricao}</span>
          </button>)}
        </div>}
        {p.ocupado && <div className="adventure-world__busy font-rpg" role="status"><PixelIcon name="dado" size={18} /> Resolvendo sua ação…</div>}
      </div>

      {p.resultado && <p className="adventure-stage__result font-rpg" role="status">{p.resultado}</p>}
      {p.cena && <div className="adventure-objective font-rpg">
        <div><PixelIcon name="pergaminho" size={14} /><strong>{p.cena.objetivo || p.cena.descricao}</strong>{p.cena.meta > 0 && <span>{p.cena.progresso}/{p.cena.meta}</span>}</div>
        {p.cena.meta > 0 && <div className="adventure-objective__track"><span style={{ width: `${progresso * 100}%` }} /></div>}
        {p.cena.descricao && p.cena.objetivo && <p>{p.cena.descricao}</p>}
      </div>}

      <div className="adventure-console">
        <div className="adventure-console__tabs">
          <button type="button" className="font-pixel-title" aria-pressed={aba === 'acoes'} onClick={() => setAba('acoes')}>Comandos</button>
          <button type="button" className="font-pixel-title" aria-pressed={aba === 'progressao'} onClick={() => setAba('progressao')}>Jornada 1–{p.progressao?.nivel_maximo ?? 10}</button>
          {foco && <span className="adventure-focus font-rpg"><PixelIcon name="pocao-azul" size={15} />{foco.nome} {foco.atual}/{foco.maximo}</span>}
        </div>
        {p.erro && <p className="adventure-error font-rpg" role="alert">{p.erro}</p>}
        {aba === 'acoes' ? <>
          <div className="adventure-console__hint font-rpg">{p.encerrado ? 'Esta jornada chegou ao fim.' : caido ? 'Você está caído. Avance a rodada para resolver seu teste de morte.' : p.combate ? `Alvo: ${alvo ?? 'nenhum'} · clique em uma criatura para mudar.` : 'Toque nos objetos do cenário para agir ou conte ao Mestre sua ideia.'}</div>
          {p.combate ? <>
            <div className="adventure-actions">
              <button type="button" className="adventure-command adventure-command--primary" disabled={bloqueado || caido || !alvo}
                onClick={() => p.aoAgir({ acao: 'atacar', alvo }, `Atacar ${alvo}`)}><PixelIcon name="espada" size={22} /><span className="font-pixel-title">Atacar<small className="font-rpg">Sem custo de foco</small></span></button>
              <button type="button" className="adventure-command" disabled={bloqueado}
                onClick={() => p.aoAgir({ acao: caido ? 'resistir' : 'defender' }, caido ? 'Resistir e avançar a rodada' : 'Defender')}><PixelIcon name="escudo" size={22} /><span className="font-pixel-title">{caido ? 'Resistir' : 'Defender'}<small className="font-rpg">{caido ? 'Teste de morte' : 'Proteção e recuperar foco'}</small></span></button>
              <button type="button" className="adventure-command" aria-expanded={taticas} onClick={() => setTaticas(!taticas)}><PixelIcon name="dado" size={22} /><span className="font-pixel-title">Táticas<small className="font-rpg">{taticas ? 'Recolher opções' : 'Risco, furtividade, fuga'}</small></span></button>
            </div>
            {taticas && <div className="adventure-actions adventure-actions--tactics">{TATICAS.map(tatica => <button type="button" className="adventure-command" key={tatica.acao} title={tatica.dica} disabled={bloqueado || caido || (tatica.acao === 'investir' && !alvo)}
              onClick={() => p.aoAgir({ acao: tatica.acao, ...(tatica.acao === 'investir' ? { alvo } : {}) }, tatica.nome)}><PixelIcon name={tatica.icone} size={16} /><span className="font-pixel-title">{tatica.nome}<small className="font-rpg">{tatica.dica}</small></span></button>)}</div>}
          </> : !p.encerrado && <button type="button" className="adventure-command" disabled={bloqueado || caido}
            onClick={() => p.aoAgir({ acao: 'descansar' }, 'Fazer um descanso curto')}><PixelIcon name="cura" size={20} /><span className="font-pixel-title">Descansar<small className="font-rpg">Recupere forças entre encontros</small></span></button>}
          {(p.progressao?.habilidades.length ?? 0) > 0 && <div className="adventure-skills" aria-label={`Habilidades de ${p.classe}`}>
            {p.progressao!.habilidades.map(habilidade => {
              const trancada = habilidade.nivel > p.nivel;
              const semFoco = (foco?.atual ?? 0) < habilidade.custo;
              const motivo = trancada ? `Desbloqueia no nível ${habilidade.nivel}` : semFoco ? 'Foco insuficiente' : !p.combate ? 'Disponível em combate' : habilidade.alvo === 'todos' ? 'Todos os inimigos' : habilidade.alvo === 'heroi' ? 'Seu herói' : `Alvo: ${alvo ?? 'selecione um inimigo'}`;
              return <button type="button" className={`adventure-skill ${trancada ? 'adventure-skill--locked' : ''}`} key={habilidade.id}
                disabled={bloqueado || caido || !habilidade.disponivel || (habilidade.alvo === 'inimigo' && !alvo)}
                onClick={() => p.aoAgir({ acao: 'usar_habilidade', habilidade: habilidade.id, ...(habilidade.alvo === 'inimigo' ? { alvo } : {}) }, `${habilidade.nome}${habilidade.alvo === 'inimigo' ? ` em ${alvo}` : ''}`)}>
                <span className="adventure-skill__heading font-pixel-title"><strong>{habilidade.nome}</strong><span>{habilidade.custo} {foco?.nome ?? 'Foco'}</span></span>
                <span className="adventure-skill__description font-rpg">{habilidade.descricao}</span><small className="font-rpg">{motivo}</small>
              </button>;
            })}
          </div>}
        </> : <div className="adventure-progression font-rpg">
          <p className="text-sm text-rpg-gold">{p.progressao?.estilo || 'Explore, resolva situações e vença encontros para evoluir.'}</p>
          <ol className="adventure-progression__levels">{p.progressao?.niveis.map(etapa => <li key={etapa.nivel} className={etapa.nivel <= p.nivel ? 'is-unlocked' : ''} aria-current={etapa.nivel === p.nivel ? 'step' : undefined}>
            <span className="font-pixel-title">{etapa.nivel}</span><div><strong>{etapa.descricao}</strong><small>{etapa.xp} XP{etapa.nivel === p.nivel ? ' · Você está aqui' : etapa.nivel < p.nivel ? ' · Conquistado' : ''}</small></div>
          </li>)}</ol>
          {p.marcos.length > 0 && <div className="adventure-progression__milestones"><h3 className="font-rpg">As marcas da sua história</h3>{p.marcos.map((marco, indice) => <p key={`${indice}-${marco}`}><PixelIcon name="estrela" size={12} />{marco}</p>)}</div>}
        </div>}
      </div>
    </section>
  );
}
