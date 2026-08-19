import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  Send, Scroll, Menu, X, Dices, User, Skull, Backpack, Map, Sword
} from 'lucide-react';

interface GameChatProps { sessionId?: string; }
interface Message { role: 'user' | 'assistant' | 'system'; content: string; }

export default function GameChat({ sessionId: propSessionId }: GameChatProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { charImage, charName, charRace, charClass } = location.state || {};
  
  const [currentSessionId, setCurrentSessionId] = useState(propSessionId || "");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // DADOS DO JOGO
  const [hpAtual, setHpAtual] = useState(10);
  const [hpMax, setHpMax] = useState(10);
  const [inventory, setInventory] = useState<string[]>([]);
  const [attributes, setAttributes] = useState<any>({ forca: 10, destreza: 10, inteligencia: 10 });
  const [quest, setQuest] = useState<any>(null);
  
  // COMBATE
  const [combatActive, setCombatActive] = useState(false);
  const [enemies, setEnemies] = useState<any[]>([]);
  const [gameOver, setGameOver] = useState(false);
  
  // EFEITOS
  const [shakeScreen, setShakeScreen] = useState(false);
  const [wasDamaged, setWasDamaged] = useState(false);

  useEffect(() => {
    const fetchGameData = async () => {
        let id = currentSessionId;
        if (!id) {
            const saves = JSON.parse(localStorage.getItem('mestre_ia_saves') || '[]');
            const match = saves.find((s:any) => s.name === charName);
            id = match ? match.id : (saves.length > 0 ? saves[0].id : null);
        }
        if (id) {
            setCurrentSessionId(id);
            try {
                const res = await axios.post("http://127.0.0.1:8000/load_game", { session_id: id });
                setHpAtual(res.data.hp_atual); 
                setHpMax(res.data.hp_max); 
                setInventory(res.data.inventory || []); 
                setAttributes(res.data.atributos || {});
                setQuest(res.data.missao);
                setCombatActive(res.data.combat_active);
                setEnemies(res.data.inimigos || []);
                
                if (res.data.hp_atual <= 0) setGameOver(true);
                if (messages.length === 0) setMessages([{ role: 'assistant', content: `Conectado ao mundo. Local: ${res.data.local}.` }]);
            } catch (e) { console.error(e); }
        }
    };
    fetchGameData();
  }, []);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  const sendAction = async (text: string) => {
    if (!currentSessionId || gameOver) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);

    try {
      const res = await axios.post(`http://127.0.0.1:8000/chat`, { session_id: currentSessionId, action: text });
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.narrativa || "..." }]);
      
      if (res.data.hp_atual !== undefined && res.data.hp_atual < hpAtual) {
          setWasDamaged(true); setShakeScreen(true);
          setTimeout(() => { setWasDamaged(false); setShakeScreen(false); }, 500);
      }
      setHpAtual(res.data.hp_atual); setHpMax(res.data.hp_max || hpMax);
      setInventory(res.data.inventory || []); 
      setCombatActive(res.data.combat_active);
      setEnemies(res.data.inimigos || []);
      if (res.data.missao) setQuest(res.data.missao);
      if (res.data.game_over) setGameOver(true);

    } catch (error) { setMessages(prev => [...prev, { role: 'assistant', content: "*(Erro de conexão)*" }]); } 
    finally { setLoading(false); }
  };

  const handleSendMessage = () => { if (!input.trim()) return; sendAction(input); setInput(""); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };

  return (
    <div className={`flex h-screen w-screen bg-black text-gray-100 font-sans overflow-hidden relative ${shakeScreen ? 'animate-shake' : ''}`}>
      
      <div className={`absolute inset-0 z-50 bg-red-600 pointer-events-none transition-opacity duration-200 ${wasDamaged ? 'opacity-20' : 'opacity-0'}`} />
      
      {gameOver && <div className="absolute inset-0 z-[100] bg-black/95 flex flex-col items-center justify-center"><h1 className="text-5xl font-rpg text-red-600">GAME OVER</h1><button onClick={() => navigate('/')} className="mt-4 border px-4 py-2 text-gray-400">Voltar</button></div>}

      {/* SIDEBAR (Ficha) */}
      <div className={`${showSidebar ? 'w-80' : 'w-0'} transition-all duration-300 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0 overflow-hidden`}>
          <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-black/20">
              <h2 className="font-rpg text-lg text-rpg-gold flex items-center gap-2"><Scroll size={18}/> FICHA</h2>
              <button onClick={() => setShowSidebar(false)} className="text-gray-500 hover:text-white"><X size={18}/></button>
          </div>
          
          <div className="p-4 space-y-6 overflow-y-auto custom-scrollbar flex-1">
              {/* Foto */}
              <div className="w-full aspect-[3/4] bg-black rounded border border-gray-800 relative shadow-lg overflow-hidden">
                   <img src={charImage} className="w-full h-full object-cover opacity-90" onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/300x400")}/>
                   <div className="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-3 pt-8">
                       <p className="text-white font-rpg text-lg">{charName}</p>
                       <p className="text-xs text-gray-400 uppercase tracking-wide">{charRace} {charClass}</p>
                   </div>
              </div>

              {/* Vida */}
              <div className="bg-gray-800/30 p-3 rounded border border-gray-700">
                  <div className="flex justify-between text-xs font-bold uppercase mb-1"><span>Vida</span><span>{hpAtual}/{hpMax}</span></div>
                  <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden"><div className="h-full bg-red-700 transition-all duration-500" style={{ width: `${Math.min(100, (hpAtual / hpMax) * 100)}%` }}></div></div>
              </div>

               {/* Atributos (Sidebar) */}
               <div className="grid grid-cols-3 gap-2">
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">FOR</span>
                      <span className="font-rpg text-gray-200">{attributes.forca}</span>
                  </div>
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">DES</span>
                      <span className="font-rpg text-gray-200">{attributes.destreza}</span>
                  </div>
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">INT</span>
                      <span className="font-rpg text-gray-200">{attributes.inteligencia}</span>
                  </div>
              </div>

              {/* Missão */}
              {quest && (
                  <div className="bg-blue-900/10 border border-blue-900/30 p-3 rounded relative">
                      <h3 className="text-[10px] text-blue-400 uppercase font-bold mb-1 tracking-widest flex items-center gap-2"><Map size={12}/> Missão</h3>
                      <p className="text-sm text-blue-100 font-serif leading-tight">{quest.nome_missao}</p>
                      <p className="text-[10px] text-gray-400 mt-1 italic">"{quest.objetivo_missao}"</p>
                  </div>
              )}

              {/* Inventário */}
              <div>
                  <h3 className="text-xs text-gray-500 uppercase font-bold mb-2 flex items-center gap-2"><Backpack size={12}/> Inventário</h3>
                  <ul className="text-xs text-gray-400 space-y-1 max-h-40 overflow-y-auto custom-scrollbar">
                      {inventory.length > 0 ? inventory.map((item, i) => (
                          <li key={i} className="border-b border-gray-800 pb-1 flex items-center gap-2">
                              <span className="w-1 h-1 bg-gray-600 rounded-full"></span> {item}
                          </li>
                      )) : <li className="italic opacity-50">Mochila vazia...</li>}
                  </ul>
              </div>
          </div>
      </div>

      {/* CHAT AREA */}
      <div className="flex-1 flex flex-col relative bg-[#050505]">
        {!showSidebar && <button onClick={() => setShowSidebar(true)} className="absolute top-4 left-4 z-40 p-2 bg-black/50 rounded-full text-gray-400 border border-gray-700"><Menu size={20}/></button>}
        
        {/* HUD Inimigos */}
        {combatActive && enemies.length > 0 && !gameOver && (
            <div className="absolute top-0 w-full bg-gradient-to-b from-red-950/90 to-transparent p-2 z-30 flex justify-center gap-4 animate-fade-in shadow-lg">
                <span className="absolute left-4 top-4 text-red-500 font-rpg text-xs animate-pulse flex items-center gap-2"><Sword size={14}/> COMBATE</span>
                {enemies.map((en, i) => (
                    <div key={i} className="min-w-[100px] bg-black/80 p-2 rounded border border-red-900/50 backdrop-blur-sm">
                        <div className="flex justify-between items-center mb-1"><span className="text-[10px] font-bold text-red-100 truncate">{en.nome}</span></div>
                        <div className="h-1 bg-gray-800 rounded-full overflow-hidden"><div className="h-full bg-red-600 transition-all duration-300" style={{ width: `${(en.hp / en.max_hp) * 100}%` }}></div></div>
                    </div>
                ))}
            </div>
        )}

        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 custom-scrollbar scroll-smooth">
            <div className="h-12"></div>
            {messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                const isSystem = msg.role === 'system';
                
                if (isSystem) {
                    return (
                        <div key={idx} className="flex justify-center my-2 animate-fade-in">
                            <div className="bg-yellow-900/20 border border-yellow-700/30 text-yellow-500 px-4 py-2 rounded-full text-xs font-mono flex items-center gap-2">
                                <Dices size={12}/> {msg.content}
                            </div>
                        </div>
                    );
                }

                return (
                    <div key={idx} className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-fade-in`}>
                        {/* CORREÇÃO DO AVATAR:
                           - Se for User: Mostra charImage.
                           - Se for Mestre (Assistant): Mostra ícone Dices/Shield (sem foto do user).
                        */}
                        <div className={`w-9 h-9 rounded-md shrink-0 flex items-center justify-center border shadow-md overflow-hidden ${isUser ? 'border-blue-900 bg-blue-950' : 'border-gray-700 bg-gray-900'}`}>
                             {isUser ? (
                                 <img src={charImage} className="w-full h-full object-cover" onError={(e) => {e.currentTarget.style.display='none'}}/>
                             ) : (
                                 <Dices size={16} className="text-rpg-gold"/> 
                             )}
                             {/* Fallback Icon se a imagem do user falhar */}
                             {isUser && <User size={16} className="text-blue-400 absolute -z-10"/>}
                        </div>
                        
                        <div className={`max-w-[85%] p-3.5 rounded-lg text-sm md:text-base leading-relaxed shadow-lg backdrop-blur-sm 
                            ${isUser 
                                ? 'bg-blue-950/40 border border-blue-900/30 text-blue-100 rounded-tr-none' 
                                : 'bg-gray-900/60 border border-gray-800 text-gray-300 rounded-tl-none'
                            }`}>
                            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                        </div>
                    </div>
                );
            })}
            
            {loading && <div className="text-center py-4 text-xs text-gray-600 animate-pulse italic">O mestre está narrando...</div>}
            <div ref={messagesEndRef} className="h-4" />
        </div>

        {/* INPUT AREA (CORRIGIDA: bg-gray-900 para combinar com a sidebar) */}
        <div className="p-4 border-t border-gray-800 bg-gray-900 z-40 relative">
            <div className="max-w-4xl mx-auto flex gap-2 bg-black/40 p-1.5 rounded-xl border border-gray-700 focus-within:border-blue-800 transition-colors shadow-inner">
                <textarea 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)} 
                    onKeyDown={handleKeyDown} 
                    placeholder={combatActive ? "Ameaça iminente! (Ex: 'Ataco o inimigo', 'Fujo')" : "Sua ação..."}
                    disabled={gameOver} 
                    className="flex-1 bg-transparent text-gray-200 p-3 outline-none resize-none h-12 max-h-32 custom-scrollbar font-serif text-sm placeholder-gray-500 disabled:opacity-50"
                />
                <button onClick={handleSendMessage} disabled={loading || !input.trim() || gameOver} className="h-10 w-10 bg-gray-800 hover:bg-gray-700 text-rpg-gold rounded-lg flex items-center justify-center transition-all mt-1 mr-1 border border-gray-600">
                    <Send size={18}/>
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}