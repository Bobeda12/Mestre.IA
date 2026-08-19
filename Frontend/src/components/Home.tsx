import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
// CORREÇÃO: Adicionei ChevronRight aqui na lista
import { Sword, Scroll, Crown, ArrowRight, Loader2, Trash2, Play, ChevronRight } from 'lucide-react';

interface SavedGame {
    id: string;
    name: string;
    race: string;
    class: string;
    image: string;
    maxHp: number;
    defense: number;
    date: string;
}

export default function Home() {
  const navigate = useNavigate();
  const [loadId, setLoadId] = useState("");
  const [loading, setLoading] = useState(false);

  // Lista de Saves Locais
  const [localSaves, setLocalSaves] = useState<SavedGame[]>([]);

  useEffect(() => {
      const saved = localStorage.getItem('mestre_ia_saves');
      if (saved) {
          try {
              setLocalSaves(JSON.parse(saved));
          } catch(e) {
              console.error("Erro ao ler saves", e);
          }
      }
  }, []);

  const handleLoadGame = async (sessionId: string, saveInfo?: SavedGame) => {
    setLoading(true);
    try {
      // Confere que a sessão ainda existe no backend antes de navegar. O
      // resto dos dados (HP, defesa, atributos...) o próprio GameChat busca
      // de novo ao montar, a partir da URL — o backend é a fonte da verdade.
      await axios.post("http://127.0.0.1:8000/load_game", { session_id: sessionId });

      navigate(`/jogar/${sessionId}`, {
        state: { charImage: saveInfo?.image }
      });

    } catch (e) {
      alert("Erro: O save no servidor expirou ou não existe mais. Crie um novo.");
    } finally {
      setLoading(false);
    }
  };

  const deleteSave = (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const newSaves = localSaves.filter(s => s.id !== id);
      setLocalSaves(newSaves);
      localStorage.setItem('mestre_ia_saves', JSON.stringify(newSaves));
  };

  return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center relative overflow-hidden font-sans">

      {/* Background */}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/80 to-black/40 z-10" />
        <img src="https://image.pollinations.ai/prompt/dark%20fantasy%20rpg%20table%20dnd%20mood%20lighting%20candle?width=1920&height=1080&nologo=true" className="w-full h-full object-cover opacity-50"/>
      </div>

      <div className="z-20 w-full max-w-6xl px-8 flex flex-col h-full justify-center">

        {/* Header */}
        <div className="text-center mb-12 animate-fade-in">
            <div className="mb-4 flex justify-center">
                <Crown size={60} className="text-rpg-gold animate-pulse-slow drop-shadow-[0_0_15px_rgba(197,160,89,0.5)]" />
            </div>
            <h1 className="text-6xl md:text-8xl font-rpg text-white drop-shadow-lg tracking-wider mb-2">
            MESTRE<span className="text-red-600">.IA</span>
            </h1>
            <p className="text-gray-400 font-hand text-xl">Aventure-se no desconhecido.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-12 items-start justify-center h-[400px]">

            {/* COLUNA 1: MENU PRINCIPAL */}
            <div className="flex-1 flex flex-col gap-6 items-center md:items-end w-full">
                <button onClick={() => navigate('/criar')} className="w-full md:w-80 group relative px-8 py-6 bg-gradient-to-r from-red-900 to-red-800 hover:from-red-800 hover:to-red-700 text-white font-bold rounded-lg border border-red-700 shadow-2xl transition-all transform hover:-translate-y-1 flex items-center justify-between overflow-hidden">
                    <div className="flex items-center gap-4 text-2xl font-rpg z-10">
                        <Sword size={32} className="text-red-300"/>
                        NOVO JOGO
                    </div>
                    <div className="absolute inset-0 bg-black/20 group-hover:bg-transparent transition-colors"/>
                    <ChevronRight size={24} className="opacity-50 group-hover:opacity-100 transition-opacity transform group-hover:translate-x-1"/>
                </button>

                {/* Input Manual (Fallback) */}
                <div className="w-full md:w-80 opacity-70 hover:opacity-100 transition-opacity">
                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-widest mb-1 block">Carregar por ID</label>
                    <div className="flex bg-gray-900/80 rounded border border-gray-700 p-1">
                        <input
                            type="text"
                            placeholder="Cole o ID..."
                            className="bg-transparent text-white px-3 outline-none w-full font-mono text-sm"
                            value={loadId}
                            onChange={e => setLoadId(e.target.value)}
                        />
                        <button onClick={() => handleLoadGame(loadId)} disabled={loading} className="bg-gray-800 hover:bg-gray-700 text-rpg-gold p-2 rounded">
                            <ArrowRight size={16}/>
                        </button>
                    </div>
                </div>
            </div>

            {/* COLUNA 2: LISTA DE SAVES (ESTILO SKYRIM) */}
            <div className="flex-1 w-full md:w-auto h-full flex flex-col">
                <h3 className="text-rpg-gold font-rpg text-xl mb-4 flex items-center gap-2 border-b border-gray-800 pb-2">
                    <Scroll size={20}/> CONTINUAR JORNADA
                </h3>

                <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3">
                    {localSaves.length === 0 ? (
                        <div className="text-gray-600 italic text-center mt-10">Nenhum herói encontrado...<br/>Crie sua lenda.</div>
                    ) : (
                        localSaves.map((save) => (
                            <div
                                key={save.id}
                                onClick={() => handleLoadGame(save.id, save)}
                                className="group flex items-center gap-4 p-3 bg-gray-900/60 hover:bg-gray-800 border border-gray-800 hover:border-rpg-gold/50 rounded-lg cursor-pointer transition-all relative"
                            >
                                {/* Foto Pequena */}
                                <div className="w-16 h-16 rounded bg-black border border-gray-700 overflow-hidden shrink-0">
                                    <img src={save.image} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" onError={(e) => (e.currentTarget.src = "")}/>
                                </div>

                                {/* Info */}
                                <div className="flex-1 min-w-0">
                                    <h4 className="text-lg font-rpg text-gray-200 group-hover:text-white truncate">{save.name}</h4>
                                    <p className="text-xs text-gray-500 uppercase tracking-wide">{save.race} {save.class}</p>
                                    <p className="text-[10px] text-gray-600 mt-1 flex items-center gap-2">
                                        <span>📅 {save.date}</span>
                                    </p>
                                </div>

                                {/* Botão Play */}
                                <div className="w-10 h-10 rounded-full bg-black/50 group-hover:bg-rpg-gold text-gray-500 group-hover:text-black flex items-center justify-center transition-colors">
                                    {loading ? <Loader2 size={20} className="animate-spin"/> : <Play size={20} className="ml-1"/>}
                                </div>

                                {/* Deletar */}
                                <button
                                    onClick={(e) => deleteSave(save.id, e)}
                                    className="absolute top-2 right-2 p-1 text-gray-700 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                    title="Apagar Save"
                                >
                                    <Trash2 size={14}/>
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>

        </div>
      </div>

      <footer className="absolute bottom-4 text-gray-700 text-xs font-sans">v2.1 • Auto-Save Enabled</footer>
    </div>
  );
}
