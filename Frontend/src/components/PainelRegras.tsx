import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import Carregando from './Carregando';

// Rodada de conserto (Parte 2, item K — C-8 do backlog antigo) — a aba de
// regras é gerada de GET /regras (Backend/app/routers/regras.py), nunca
// digitada à mão: se o motor mudar um número (curva de XP, CD de uma ação
// tática), esta tela muda junto sem precisar editar nada aqui. De propósito
// NÃO é a bíblia do mestre — isso seria vazar o prompt de sistema.
interface DadosRegras {
  niveis: { nivel: number; xp_necessario: number; bonus_proficiencia: number }[];
  escala_dificuldade: { cd: number; rotulo: string }[];
  acoes_taticas: { nome: string; efeito: string }[];
  armas: Record<string, Record<string, { dano: string; tipo: string; propriedades: string[] }>>;
  aliado_padrao: { ca: number; bonus_ataque: number; dano_dado: string };
  bonus_item_com_tag: number;
}

function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="bg-black/50 border-2 border-gray-700 p-2">
      <h4 className="text-[10px] text-rpg-gold uppercase tracking-widest font-rpg mb-1.5">{titulo}</h4>
      {children}
    </div>
  );
}

export default function PainelRegras() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['regras'],
    queryFn: async () => (await api.get<DadosRegras>('/regras')).data,
    staleTime: Infinity, // regras do sistema não mudam durante uma sessão
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8 text-rpg-gold">
        <Carregando rotulo="Carregando regras" />
      </div>
    );
  }
  if (isError || !data) {
    return <p className="text-sm text-gray-400 font-rpg text-center py-8">Não consegui carregar as regras agora.</p>;
  }

  return (
    <div className="space-y-2 animate-fade-in">
      <Bloco titulo="Nível e experiência">
        <table className="w-full text-[11px] text-gray-300 font-rpg">
          <thead>
            <tr className="text-gray-500 text-left">
              <th className="font-normal">Nível</th>
              <th className="font-normal">XP</th>
              <th className="font-normal">Proficiência</th>
            </tr>
          </thead>
          <tbody>
            {data.niveis.map((n) => (
              <tr key={n.nivel}>
                <td>{n.nivel}</td>
                <td>{n.xp_necessario}</td>
                <td>+{n.bonus_proficiencia}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Bloco>

      <Bloco titulo="Dificuldade dos testes">
        <ul className="text-[11px] text-gray-300 font-rpg space-y-0.5">
          {data.escala_dificuldade.map((e) => (
            <li key={e.cd} className="flex justify-between">
              <span>{e.rotulo}</span>
              <span className="text-gray-500">CD {e.cd}</span>
            </li>
          ))}
        </ul>
      </Bloco>

      <Bloco titulo="Ações em combate">
        <ul className="text-[11px] text-gray-300 font-rpg space-y-1.5">
          {data.acoes_taticas.map((a) => (
            <li key={a.nome}>
              <span className="text-rpg-gold">{a.nome}:</span> {a.efeito}
            </li>
          ))}
        </ul>
      </Bloco>

      <Bloco titulo="Aliados e itens">
        <ul className="text-[11px] text-gray-300 font-rpg space-y-1">
          <li>
            Aliado recrutado: CA {data.aliado_padrao.ca}, ataque +{data.aliado_padrao.bonus_ataque}, dano{' '}
            {data.aliado_padrao.dano_dado}.
          </li>
          <li>Usar um item com efeito na hora certa: +{data.bonus_item_com_tag} no teste.</li>
        </ul>
      </Bloco>
    </div>
  );
}
