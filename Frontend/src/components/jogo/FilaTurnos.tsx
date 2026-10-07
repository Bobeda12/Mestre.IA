import type { AliadoVisual, InimigoVisual } from '../../lib/gameplay';

// Combate v2 (ADR-0040) — a ordem rolada na iniciativa vale, então ela
// aparece: quem age, em que ordem, e de quem é a vez agora. Os ids vêm do
// servidor ("heroi", "i1", "a1"); o aliado "aN" é o N-ésimo da lista.
interface Props {
  fila: string[];
  vez: string;
  heroi: string;
  inimigos: InimigoVisual[];
  aliados: AliadoVisual[];
}

interface Participante { id: string; nome: string; tipo: 'heroi' | 'aliado' | 'inimigo'; fora: boolean }

function resolver(id: string, p: Props): Participante | null {
  if (id === 'heroi') return { id, nome: p.heroi || 'Você', tipo: 'heroi', fora: false };
  if (id.startsWith('a')) {
    const aliado = p.aliados[Number(id.slice(1)) - 1];
    return aliado ? { id, nome: aliado.nome, tipo: 'aliado', fora: aliado.hp <= 0 } : null;
  }
  const inimigo = p.inimigos.find(i => i.id === id);
  return inimigo ? { id, nome: inimigo.nome, tipo: 'inimigo', fora: inimigo.hp <= 0 || !!inimigo.afastado } : null;
}

export default function FilaTurnos(p: Props) {
  const participantes = p.fila.map(id => resolver(id, p)).filter((x): x is Participante => x !== null);
  if (participantes.length === 0) return null;
  return (
    <ol className="fila-turnos font-rpg" aria-label="Ordem dos turnos">
      {participantes.map(x => (
        <li key={x.id} aria-current={x.id === p.vez ? 'true' : undefined}
          className={`fila-turnos__item fila-turnos__item--${x.tipo} ${x.id === p.vez ? 'is-vez' : ''}`}>
          <span className={x.fora ? 'line-through opacity-50' : ''}>{x.nome}</span>
        </li>
      ))}
    </ol>
  );
}
