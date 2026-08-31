// Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — generaliza o número de
// dano flutuante (Etapa 7, `.animate-float-up` em index.css) pra qualquer
// mudança de recurso do herói: cura, ouro, XP. Continua CSS puro (sobe e
// some) — o "voo" coreografado de verdade (o baú de loot) é o único ponto
// desta fase que usa framer-motion, não este.
//
// O card de dano dos INIMIGOS (GameChat.tsx, HUD de combate) também usa
// este componente — mesma anatomia, alvo diferente (posição relativa ao
// card do inimigo em vez de a um ícone da faixa de vitais).
export interface FlutuanteHeroi {
  id: number;
  texto: string;
  cor: string;
}

export default function FloatingCombatText({ itens }: { itens: FlutuanteHeroi[] }) {
  return (
    <>
      {itens.map((f) => (
        <span
          key={f.id}
          className={`absolute left-1/2 top-0 -translate-x-1/2 font-bold text-sm pointer-events-none animate-float-up ${f.cor}`}
        >
          {f.texto}
        </span>
      ))}
    </>
  );
}
