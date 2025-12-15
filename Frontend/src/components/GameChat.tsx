import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom'; // Importante para pegar a foto
import { 
  Send, Shield, Heart, Zap, Scroll, Menu, X, Dices, Backpack, User 
} from 'lucide-react';

interface GameChatProps {
  sessionId: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function GameChat({ sessionId }: GameChatProps) {
  // 1. RECUPERA OS DADOS VINDOS DA CRIAÇÃO
  const location = useLocation();
  const { charImage, charName, charRace, charClass } = location.state || {};

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (messages.length === 0) {
        setMessages([{
            role: 'assistant',
            content: `Seja bem-vindo, ${charName || "Aventureiro"}. O mundo reage à sua presença. Você está equipado e pronto. O que deseja fazer?`
        }]);
    }
  }, [charName]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setInput("");
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await axios.post(`http://127.0.0.1:8000/chat`, {
        session_id: sessionId,
        message: userMsg
      });
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "*(O destino parece nebuloso... Tente novamente)*" }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen w-screen bg-black text-gray-100 font-sans overflow-hidden">
      
      {/* --- SIDEBAR --- */}
      <div className={`${showSidebar ? 'w-80' : 'w-0'} transition-all duration-300 bg-gray-900 border-r border-gray-800 flex flex-col relative`}>
        <div className="p-6 border-b border-gray-800 flex justify-between items-center overflow-hidden">
            <h2 className="font-rpg text-xl text-rpg-gold flex items-center gap-2">
                <Scroll size={20}/> GRIMÓRIO
            </h2>
            <button onClick={() => setShowSidebar(false)} className="text-gray-500 hover:text-white lg:hidden">
                <X size={20}/>
            </button>
        </div>

        <div className={`p-6 space-y-6 overflow-y-auto ${!showSidebar && 'hidden'}`}>
            
            {/* FOTO DO PERSONAGEM (AGORA DINÂMICA) */}
            <div className="w-full aspect-[3/4] bg-black rounded-lg border border-rpg-gold/30 overflow-hidden relative group shadow-lg">
                 <img 
                    src={charImage || "/assets/classes/guerreiro.jpg"} // Fallback se der erro
                    className="w-full h-full object-cover object-top" 
                    alt="Retrato"
                    onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/300x400?text=Sem+Imagem")}
                 />
                 <div className="absolute bottom-0 w-full bg-gradient-to-t from-black to-transparent p-4 pt-10">
                     <p className="text-white font-rpg text-lg leading-none">{charName || "Herói"}</p>
                     <p className="text-rpg-gold text-xs font-bold uppercase tracking-wider opacity-80">
                        {charRace || "Desconhecido"} {charClass || ""}
                     </p>
                 </div>
            </div>

            {/* STATUS */}
            <div className="space-y-4 bg-black/20 p-4 rounded border border-gray-800">
                <div>
                    <div className="flex justify-between text-xs text-gray-400 mb-1 font-bold uppercase">
                        <span className="flex items-center gap-2"><Heart size={14} className="text-red-500"/> Vida</span>
                        <span className="text-red-200">12 / 12</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-red-700 w-full"></div>
                    </div>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-gray-800/50">
                     <span className="flex items-center gap-2 text-xs text-gray-400 font-bold uppercase"><Shield size={14} className="text-blue-500"/> Defesa</span>
                     <span className="text-blue-200 font-rpg text-lg">14</span>
                </div>
            </div>

            {/* INVENTÁRIO */}
            <div>
                <h3 className="text-rpg-gold font-bold text-xs uppercase tracking-widest mb-3 flex items-center gap-2 opacity-70">
                    <Backpack size={14}/> Mochila
                </h3>
                <ul className="text-sm text-gray-400 space-y-2">
                    <li className="border-b border-gray-800 pb-2 flex justify-between"><span>Rações de Viagem</span> <span className="text-gray-600">x5</span></li>
                    <li className="border-b border-gray-800 pb-2 flex justify-between"><span>Cantil de Água</span> <span className="text-gray-600">x1</span></li>
                    <li className="border-b border-gray-800 pb-2 flex justify-between"><span>Tochas</span> <span className="text-gray-600">x3</span></li>
                    <li className="border-b border-gray-800 pb-2 flex justify-between text-rpg-gold/80"><span>15 Peças de Ouro</span></li>
                </ul>
            </div>
        </div>
      </div>

      {/* --- CHAT --- */}
      <div className="flex-1 flex flex-col relative bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
        
        {!showSidebar && (
            <button onClick={() => setShowSidebar(true)} className="absolute top-4 left-4 z-50 text-gray-500 hover:text-rpg-gold transition-colors">
                <Menu size={24}/>
            </button>
        )}

        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar scroll-smooth pb-24">
            {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                    
                    {/* AVATAR NO CHAT */}
                    {msg.role === 'assistant' && (
                        <div className="w-8 h-8 rounded border border-rpg-gold/50 bg-black mr-3 flex-shrink-0 overflow-hidden mt-1">
                            <img src="/assets/mestre-avatar.jpg" className="w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')}/>
                            <Dices size={16} className="text-rpg-gold m-1.5 absolute" /> 
                        </div>
                    )}

                    <div className={`max-w-[80%] p-5 rounded-lg relative shadow-md ${
                        msg.role === 'user' 
                        ? 'bg-blue-900/20 border border-blue-800/50 text-blue-100 rounded-tr-none' 
                        : 'bg-black/60 border border-gray-700 text-gray-300 font-serif leading-relaxed text-lg rounded-tl-none'
                    }`}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>

                    {msg.role === 'user' && (
                         <div className="w-8 h-8 rounded border border-blue-500/50 bg-black ml-3 flex-shrink-0 overflow-hidden mt-1">
                            <img src={charImage} className="w-full h-full object-cover" />
                         </div>
                    )}
                </div>
            ))}
            
            {loading && (
                <div className="flex justify-start animate-pulse pl-12">
                    <span className="text-gray-600 text-sm font-serif italic">O mestre está escrevendo...</span>
                </div>
            )}
            <div ref={messagesEndRef} />
        </div>

        {/* INPUT */}
        <div className="p-4 bg-gray-900/90 border-t border-gray-800 backdrop-blur-md">
            <div className="max-w-4xl mx-auto relative flex gap-4 items-end">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={`O que ${charName || "você"} faz agora?`}
                    className="flex-1 bg-black border border-gray-700 rounded-lg p-4 text-gray-100 focus:border-rpg-gold focus:ring-1 focus:ring-rpg-gold outline-none resize-none h-14 max-h-32 custom-scrollbar transition-all font-serif text-lg"
                />
                <button 
                    onClick={sendMessage} 
                    disabled={loading || !input.trim()}
                    className="h-14 w-14 bg-rpg-gold hover:bg-yellow-600 text-black rounded-lg flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(197,160,89,0.2)]"
                >
                    <Send size={24}/>
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}