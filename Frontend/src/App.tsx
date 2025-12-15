import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Send, Sword, Shield, Backpack, User, Skull } from 'lucide-react';

// Tipos de dados
interface GameState {
  hp: number;
  inventory: string[];
  narrativa?: string;
}

interface Message {
  role: 'user' | 'master';
  text: string;
}

function App() {
  // Estados do Jogo
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [gameState, setGameState] = useState<GameState>({
    hp: 20,
    inventory: []
  });

  // Referência para rolar o chat para baixo automaticamente
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Função para começar o jogo (Envia "START" escondido)
  const iniciarJogo = async () => {
    if (messages.length > 0) return; // Se já começou, não faz nada
    
    setLoading(true);
    try {
      const res = await axios.post("http://127.0.0.1:8000/chat", {
        session_id: "sessao_demo_1", // ID fixo por enquanto
        action: "START"
      });
      
      const respostaIA = res.data;
      
      // Adiciona a resposta inicial do Mestre
      setMessages([{ role: 'master', text: respostaIA.narrativa }]);
      setGameState({
        hp: respostaIA.hp_atual,
        inventory: respostaIA.inventory || []
      });

    } catch (error) {
      console.error("Erro ao iniciar:", error);
      setMessages([{ role: 'master', text: "Erro: O Mestre está dormindo (Verifique se o backend está rodando)." }]);
    } finally {
      setLoading(false);
    }
  };

  // Inicia o jogo assim que a tela abre
  useEffect(() => {
    iniciarJogo();
  }, []);

  // Função de enviar mensagem
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setInput(""); // Limpa o campo
    setMessages(prev => [...prev, { role: 'user', text: userText }]); // Adiciona msg do usuário na tela
    setLoading(true);

    try {
      const res = await axios.post("http://127.0.0.1:8000/chat", {
        session_id: "sessao_demo_1",
        action: userText
      });

      const data = res.data;

      // Adiciona resposta do Mestre
      setMessages(prev => [...prev, { role: 'master', text: data.narrativa }]);

      // Atualiza a Ficha (HP e Inventário) automaticamente
      setGameState(prev => ({
        ...prev,
        hp: data.hp_atual,
        inventory: data.inventory || prev.inventory
      }));

      // Efeito visual se morrer
      if (data.game_over) {
        alert("GAME OVER! Você morreu.");
      }

    } catch (error) {
      setMessages(prev => [...prev, { role: 'master', text: "Erro de conexão com o além..." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-rpg-darker text-gray-200 font-sans overflow-hidden">
      
      {/* === COLUNA DA ESQUERDA (FICHA) === */}
      <div className="w-1/4 bg-rpg-dark border-r border-gray-800 p-6 flex flex-col gap-6">
        <div className="flex items-center gap-3 text-rpg-accent mb-4">
          <User size={32} />
          <h2 className="text-2xl font-bold tracking-wider">PERSONAGEM</h2>
        </div>

        {/* Barra de Vida */}
        <div className="bg-black/40 p-4 rounded-lg border border-gray-700">
          <div className="flex justify-between mb-2">
            <span className="flex items-center gap-2 font-bold"><Shield size={18} className="text-red-500"/> HP</span>
            <span className="text-xl font-mono">{gameState.hp} / 20</span>
          </div>
          <div className="w-full bg-gray-800 h-4 rounded-full overflow-hidden">
            <div 
              className="bg-red-700 h-full transition-all duration-500 ease-out" 
              style={{ width: `${(gameState.hp / 20) * 100}%` }}
            ></div>
          </div>
        </div>

        {/* Inventário */}
        <div className="flex-1 bg-black/40 p-4 rounded-lg border border-gray-700 overflow-y-auto">
          <h3 className="flex items-center gap-2 font-bold mb-4 text-yellow-600">
            <Backpack size={18} /> INVENTÁRIO
          </h3>
          {gameState.inventory.length === 0 ? (
            <p className="text-gray-500 text-sm italic">Sua mochila está vazia...</p>
          ) : (
            <ul className="space-y-2">
              {gameState.inventory.map((item, idx) => (
                <li key={idx} className="flex items-center gap-2 text-sm bg-gray-800/50 p-2 rounded text-gray-300">
                  <Sword size={14} className="text-gray-500"/> {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* === COLUNA DA DIREITA (CHAT) === */}
      <div className="flex-1 flex flex-col relative bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
        
        {/* Header */}
        <div className="h-16 bg-rpg-dark border-b border-gray-800 flex items-center px-6 shadow-lg z-10">
          <h1 className="text-xl font-bold text-gray-400 flex items-center gap-2">
            <Skull className="text-rpg-accent" /> AVENTURA NA MASMORRA
          </h1>
        </div>

        {/* Área de Mensagens */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div 
                className={`max-w-[80%] p-4 rounded-lg shadow-md leading-relaxed ${
                  msg.role === 'user' 
                    ? 'bg-rpg-accent text-white rounded-tr-none' 
                    : 'bg-gray-800 text-gray-300 border border-gray-700 rounded-tl-none'
                }`}
              >
                {msg.role === 'master' && <span className="block text-xs font-bold text-yellow-600 mb-1 uppercase tracking-widest">Mestre</span>}
                <p>{msg.text}</p>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 p-3 rounded-lg animate-pulse text-gray-500 text-sm">
                O mestre está pensando... 🎲
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-rpg-dark border-t border-gray-800">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="O que você faz? (Ex: Ataco o esqueleto...)"
              className="flex-1 bg-black/50 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-rpg-accent focus:ring-1 focus:ring-rpg-accent transition-all"
              disabled={loading}
            />
            <button 
              onClick={handleSend}
              disabled={loading}
              className="bg-rpg-accent hover:bg-red-900 text-white p-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send size={24} />
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;