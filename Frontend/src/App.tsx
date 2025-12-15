import { useState } from 'react';
import CharacterCreation from './components/CharacterCreation';
import GameChat from './components/gamechat';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  return (
    <div>
      {!sessionId ? (
        // Se não tem sessão, mostra a Criação de Personagem
        <CharacterCreation onCharacterCreated={(id) => setSessionId(id)} />
      ) : (
        // Se tem sessão (personagem criado), mostra o Chat
        <GameChat sessionId={sessionId} />
      )}
    </div>
  );
}

export default App;