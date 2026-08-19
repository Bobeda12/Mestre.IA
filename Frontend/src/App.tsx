import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './components/Home';
import CharacterCreation from './components/CharacterCreation';
import GameChat from './components/GameChat';

function App() {
  return (
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
  );
}

export default App;