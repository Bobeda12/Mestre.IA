import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { 
  Send, Shield, Heart, Scroll, Menu, X, Dices, Backpack, User 
} from 'lucide-react';

interface GameChatProps {
  sessionId: string; // Se vier via props (opcional)
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export default function GameChat({ sessionId: propSessionId }: GameChatProps) {
  const location = useLocation();
  // Pega o estado inicial, mas NÃO confia cegamente no charMaxHp dele
  const { charImage, charName, charRace, charClass, charDefense, charMaxHp } = location.state || {};
  
  // Se não vier via Props, tenta pegar do state (Home -> Play)
  // Num app real, usaríamos Context API, mas isso resolve agora.
  // Nota: Precisamos recuperar o ID salvo no Home se o state falhar, mas vamos assumir que vem do Home.
  // O componente Home salva no localStorage, podemos pegar de lá se precisar.
  const [currentSessionId, setCurrentSessionId] = useState(propSessionId || "");

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ESTADOS VITAIS (Inicializa seguro)
  const [hpAtual, setHpAtual] = useState(charMaxHp || 10);
  const [hpMax, setHpMax] = useState(charMaxHp || 10);
  const [inventory, setInventory] = useState<string[]>([]);

  // Carrega ID do LocalStorage se não vier via navegação (Recarregar página)
  useEffect(() => {
      if (!charName) {
          // Lógica de fallback se o usuário der F5 na página
          const saves = JSON.parse(localStorage.getItem('mestre_ia_saves') || '[]');
          if (saves.length > 0) {
              // Carrega o último save
              const last = saves[0];
              // Precisaríamos de uma rota no backend para pegar o histórico, 
              // por enquanto, se der F5, volta pra Home é mais seguro.
              window.location.href = "/";
          }
      } else {
          // Tenta encontrar o ID no localStorage que bate com o nome/classe para setar o ID correto
          const saves = JSON.parse(localStorage.getItem('mestre_ia_saves') || '[]');
          const match = saves.find((s:any) => s.name === charName);
          if (match) setCurrentSessionId(match.id);
      }
  }, []);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  // Mensagem Inicial
  useEffect(() => {
    if (messages.length === 0 && charName) {
        setMessages([{
            role: 'assistant',
            content: `Aventura iniciada para ${charName}, o ${charRace} ${charClass}. O mundo aguarda suas escolhas.`
        }]);
    }
  }, [charName]);

  const sendAction = async (text: string, type: 'user' | 'system' = 'user') => {
    if (!currentSessionId) {
        // Tenta recuperar do localStorage de emergência
        const saves = JSON.parse(localStorage.getItem('mestre_ia_saves') || '[]');
        if (saves.length > 0) setCurrentSessionId(saves[0].id);
        else return alert("Sessão perdida. Volte para o menu.");
    }

    setMessages(prev => [...prev, { role: type, content: text }]);
    setLoading(true);

    try {
      const res = await axios.post(`http://127.0.0.1:8000/chat`, {
        session_id: currentSessionId, // Usa o ID do state
        action: text
      });
      
      // Atualiza Chat
      const narrativa = res.data.narrativa || "...";
      setMessages(prev => [...prev, { role: 'assistant', content: narrativa }]);
      
      // Atualiza Vida (Backend manda a verdade absoluta)
      if (res.data.hp_atual !== undefined) setHpAtual(res.data.hp_atual);
      if (res.data.hp_max !== undefined) setHpMax(res.data.hp_max);
      
      if (res.data.inventory) setInventory(res.data.inventory);

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'assistant', content: "*(Conexão perdida... Tente enviar novamente)*" }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = () => { if (!input.trim()) return; sendAction(input, 'user'); setInput(""); };
  const handleRollDice = () => { if (loading) return; const roll = Math.floor(Math.random() * 20) + 1; sendAction(`[SISTEMA] 🎲 ${charName} rolou um D20 e tirou: ${roll}`, 'system'); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };

  return (
    <div className="flex h-screen w-screen bg-black text-gray-100 font-sans overflow-hidden">
      {/* SIDEBAR */}
      <div className={`${showSidebar ? 'w-80' : 'w-0'} transition-all duration-300 bg-gray-900 border-r border-gray-800 flex flex-col relative`}>
        <div className="p-6 border-b border-gray-800 flex justify-between items-center overflow-hidden">
            <h2 className="font-rpg text-xl text-rpg-gold flex items-center gap-2"><Scroll size={20}/> GRIMÓRIO</h2>
            <button onClick={() => setShowSidebar(false)} className="text-gray-500 hover:text-white lg:hidden"><X size={20}/></button>
        </div>
        <div className={`p-6 space-y-6 overflow-y-auto ${!showSidebar && 'hidden'}`}>
            <div className="w-full aspect-[3/4] bg-black rounded-lg border border-rpg-gold/30 overflow-hidden relative group shadow-lg">
                 <img src={charImage} className="w-full h-full object-cover object-top" onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/300x400?text=Sem+Imagem")}/>
                 <div className="absolute bottom-0 w-full bg-gradient-to-t from-black to-transparent p-4 pt-10">
                     <p className="text-white font-rpg text-lg leading-none">{charName}</p>
                     <p className="text-rpg-gold text-xs font-bold uppercase tracking-wider opacity-80">{charRace} {charClass}</p>
                 </div>
            </div>
            <div className="space-y-4 bg-black/20 p-4 rounded border border-gray-800">
                <div>
                    <div className="flex justify-between text-xs text-gray-400 mb-1 font-bold uppercase">
                        <span className="flex items-center gap-2"><Heart size={14} className="text-red-500"/> Vida</span>
                        <span className="text-red-200">{hpAtual} / {hpMax}</span>
                    </div>
                    {/* BARRA DE VIDA DINÂMICA */}
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-red-700 transition-all duration-500" 
                            style={{ width: `${Math.max(0, Math.min 
                                (100, (hpAtual / hpMax) * 100))}%` }}
                        ></div>
                    </div>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-gray-800/50">
                     <span className="flex items-center gap-2 text-xs text-gray-400 font-bold uppercase"><Shield size={14} className="text-blue-500"/> Defesa</span>
                     <span className="text-blue-200 font-rpg text-lg">{charDefense || "?"}</span>
                </div>
            </div>
            <div>
                <h3 className="text-rpg-gold font-bold text-xs uppercase tracking-widest mb-3 flex items-center gap-2 opacity-70"><Backpack size={14}/> Mochila</h3>
                <ul className="text-sm text-gray-400 space-y-2">
                    {inventory.length > 0 ? inventory.map((item, idx) => (
                        <li key={idx} className="border-b border-gray-800 pb-2 flex justify-between"><span>{item}</span></li>
                    )) : <li className="text-gray-600 italic">Mochila vazia...</li>}
                </ul>
            </div>
        </div>
      </div>

      {/* ÁREA PRINCIPAL (CHAT) */}
      <div className="flex-1 flex flex-col relative bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
        {!showSidebar && (<button onClick={() => setShowSidebar(true)} className="absolute top-4 left-4 z-50 text-gray-500 hover:text-rpg-gold transition-colors"><Menu size={24}/></button>)}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8 custom-scrollbar scroll-smooth">
            {messages.map((msg, idx) => (
                <div key={idx} className={`flex items-start gap-4 ${msg.role === 'user' || msg.role === 'system' ? 'flex-row-reverse' : 'flex-row'} animate-fade-in`}>
                    <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center overflow-hidden border-2 shadow-lg relative ${msg.role === 'user' ? 'border-blue-500/50 bg-blue-900/20' : msg.role === 'system' ? 'border-purple-500/50 bg-purple-900/20' : 'border-rpg-gold/50 bg-black'}`}>
                        <div className="absolute inset-0 flex items-center justify-center">{msg.role === 'user' ? <User size={20} className="text-blue-400"/> : msg.role === 'system' ? <Dices size={20} className="text-purple-400"/> : <Dices size={20} className="text-rpg-gold"/>}</div>
                        {msg.role === 'user' && <img src={charImage} className="relative w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />}
                        {msg.role === 'assistant' && <img src="/assets/mestre-avatar.jpg" className="relative w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />}
                    </div>
                    <div className={`relative max-w-[85%] md:max-w-[75%] p-5 rounded-xl text-lg leading-relaxed shadow-md ${msg.role === 'user' ? 'bg-blue-950/40 border border-blue-800/30 text-blue-100 rounded-tr-none' : msg.role === 'system' ? 'bg-purple-950/40 border border-purple-800/30 text-purple-100 font-mono text-center rounded-xl' : 'bg-black/60 border border-gray-700 text-gray-300 font-serif rounded-tl-none shadow-[0_0_15px_rgba(0,0,0,0.5)]'}`}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                </div>
            ))}
            {loading && (<div className="flex items-center gap-4 animate-pulse ml-2"><div className="w-10 h-10 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center"><Dices size={18} className="text-gray-500 animate-spin"/></div><span className="text-gray-500 text-sm font-serif italic tracking-wide">O mestre está escrevendo...</span></div>)}
            <div ref={messagesEndRef} className="h-4" />
        </div>
        <div className="p-4 md:p-6 bg-gray-900/90 border-t border-gray-800 backdrop-blur-md">
            <div className="max-w-4xl mx-auto relative flex gap-3 items-end">
                <button onClick={handleRollDice} disabled={loading} className="h-16 w-16 bg-purple-900/50 hover:bg-purple-800 border border-purple-500/50 text-purple-200 rounded-xl flex flex-col items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed group" title="Rolar D20"><Dices size={24} className="group-hover:rotate-180 transition-transform duration-500"/><span className="text-[10px] font-bold mt-1">D20</span></button>
                <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder={`O que ${charName || "você"} faz?`} className="flex-1 bg-[#0a0a0a] border border-gray-700 rounded-xl p-4 text-gray-100 text-lg focus:border-rpg-gold focus:ring-1 focus:ring-rpg-gold outline-none resize-none h-16 max-h-32 custom-scrollbar transition-all font-serif placeholder-gray-600 shadow-inner"/>
                <button onClick={handleSendMessage} disabled={loading || !input.trim()} className="h-16 w-16 bg-rpg-gold hover:bg-yellow-600 text-black rounded-xl flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(197,160,89,0.3)] hover:scale-105 active:scale-95"><Send size={28}/></button>
            </div>
        </div>
      </div>
    </div>
  );
}