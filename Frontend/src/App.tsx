import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './components/Home';
import CharacterCreation from './components/CharacterCreation';
import GameChat from './components/GameChat';

function App() {
  // O SessionID agora controla se o usuário está jogando
  const [sessionId, setSessionId] = useState<string | null>(null);

  return (
    <BrowserRouter>
      <Routes>
        {/* Rota 1: Página Inicial */}
        <Route path="/" element={<Home />} />
        
        {/* Rota 2: Criação de Personagem */}
        <Route 
          path="/criar" 
          element={
            <CharacterCreation onCharacterCreated={(id: string) => setSessionId(id)} />
          } 
        />
        
        {/* Rota 3: O Jogo (Só entra se tiver ID, senão volta pra home) */}
        <Route 
          path="/jogar" 
          element={
            sessionId ? <GameChat sessionId={sessionId} /> : <Navigate to="/" />
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;