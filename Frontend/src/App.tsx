import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Home from './components/Home';
import CharacterCreation from './components/CharacterCreation';
import GameChat from './components/GameChat';

// Etapa 7, ADR-0013: TanStack Query substitui os `useEffect` + `axios`
// soltos por cache/estado de servidor de verdade. `retry: false` porque a
// maioria das chamadas aqui é contra o próprio backend local — se falhar,
// tentar de novo sozinho só atrasa o erro aparecer pro jogador.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Rota 1: Página Inicial */}
          <Route path="/" element={<Home />} />

          {/* Rota 2: Criação de Personagem */}
          <Route path="/criar" element={<CharacterCreation />} />

          {/* Rota 3: O Jogo — o sessionId vive na URL, não em estado do App.
              Recarregar a página não perde mais a sessão (ver docs/adr/0002). */}
          <Route path="/jogar/:sessionId" element={<GameChat />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;