// Etapa 14 (revisão) — substitui o `Loader2` do lucide-react (um círculo de
// traço fino girando com `animate-spin`) usado em Home, Login e
// CharacterCreation. Círculo girando suave é vocabulário de app web; jogo
// 8-bit indica espera com blocos piscando em sequência, que é o que este
// componente faz. Sem SVG e sem dependência: três divs e um `animation-delay`
// escalonado, com a mesma paleta do resto (`--color-rpg-gold`).
//
// `prefers-reduced-motion` é respeitado no CSS (index.css), não aqui — assim
// vale pra qualquer animação do app de uma vez, em vez de cada componente
// checar por conta própria.
export default function Carregando({
  tamanho = 8,
  className = '',
  rotulo = 'Carregando',
}: {
  tamanho?: number;
  className?: string;
  rotulo?: string;
}) {
  return (
    <span role="status" aria-label={rotulo} className={`inline-flex items-center gap-1 ${className}`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="bg-current animate-blocos-carregando"
          style={{ width: tamanho, height: tamanho, animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  );
}
