import { Component, type ErrorInfo, type ReactNode } from 'react';

// Pré-lançamento — sem isto, uma exceção em qualquer componente deixava a
// tela inteira em branco, sem saída para o jogador. O servidor guarda o
// progresso a cada turno, então recarregar é seguro: é isso que a tela oferece.
interface Props { children: ReactNode }
interface Estado { falhou: boolean }

export default class ErrorBoundary extends Component<Props, Estado> {
  state: Estado = { falhou: false };

  static getDerivedStateFromError(): Estado {
    return { falhou: true };
  }

  componentDidCatch(erro: Error, info: ErrorInfo) {
    console.error('Falha de renderização', erro, info.componentStack);
  }

  render() {
    if (!this.state.falhou) return this.props.children;
    return (
      <div className="min-h-[100dvh] w-screen bg-rpg-darker flex items-center justify-center px-4">
        <div className="max-w-sm text-center font-rpg">
          <h1 className="text-base font-pixel-title text-rpg-gold mb-4 leading-relaxed">ALGO DEU ERRADO</h1>
          <p className="text-gray-300 text-sm mb-6">
            A tela travou, mas o seu progresso está salvo no servidor. Recarregue para voltar de onde parou.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="border-2 border-rpg-gold text-rpg-gold px-6 py-3 text-xs uppercase tracking-widest hover:bg-rpg-gold hover:text-black transition-colors"
          >
            Recarregar
          </button>
          <p className="mt-4">
            <a href="/" className="text-gray-400 hover:text-rpg-gold text-sm underline">Ir para o início</a>
          </p>
        </div>
      </div>
    );
  }
}
