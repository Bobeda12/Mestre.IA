import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Home from './components/Home';
import CharacterCreation from './components/CharacterCreation';
import GameChat from './components/GameChat';
import Login from './components/Login';
import ConfirmeEmail from './components/ConfirmeEmail';
import Carregando from './components/Carregando';
import { useAuth } from './lib/auth';

// Etapa 7, ADR-0013: TanStack Query substitui os `useEffect` + `axios`
// soltos por cache/estado de servidor de verdade. `retry: false` porque a
// maioria das chamadas aqui é contra o próprio backend local — se falhar,
// tentar de novo sozinho só atrasa o erro aparecer pro jogador.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

// Etapa 8, ADR-0014: criar personagem e jogar exigem estar logado — o
// servidor já recusa com 401/403 (ver routers/character.py e game.py),
// isto só evita a viagem: manda direto pra /entrar em vez de deixar o
// jogador digitar tudo do wizard pra descobrir isso só no fim.
function RotaProtegida({ children }: { children: React.ReactNode }) {
  const { usuario, logado, carregando } = useAuth();
  if (carregando) {
    return (
      <div className="min-h-[100dvh] w-full bg-rpg-darker flex items-center justify-center">
        <Carregando tamanho={10} rotulo="Carregando" />
      </div>
    );
  }
  if (!logado) return <Navigate to="/entrar" replace />;
  // Etapa 10 (A-2) — bloqueia criar personagem/jogar até confirmar. Só
  // afeta quem TEM e-mail; convidado (`email === null`) e conta Google
  // (já verificada no OAuth) passam direto.
  if (usuario?.email !== null && usuario?.email_verificado === false) {
    return <ConfirmeEmail email={usuario.email} />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Rota 1: Página Inicial — também é a tela "Meus heróis" quando logado */}
          <Route path="/" element={<Home />} />

          {/* Login por senha + Google opcional (Etapa 8) */}
          <Route path="/entrar" element={<Login />} />

          {/* Rota 2: Criação de Personagem */}
          <Route
            path="/criar"
            element={
              <RotaProtegida>
                <CharacterCreation />
              </RotaProtegida>
            }
          />

          {/* Rota 3: O Jogo — o sessionId vive na URL, não em estado do App.
              Recarregar a página não perde mais a sessão (ver docs/adr/0002). */}
          <Route
            path="/jogar/:sessionId"
            element={
              <RotaProtegida>
                <GameChat />
              </RotaProtegida>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
