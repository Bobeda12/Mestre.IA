import { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Sword, Shield, Scroll, User, Heart, Zap, 
  ChevronRight, BookOpen, Crown, Sparkles 
} from 'lucide-react';

interface CharacterCreationProps {
  onCharacterCreated: (sessionId: string) => void;
}

// Gerador de imagens (Pollinations)
const getImage = (prompt: string) => 
  `https://image.pollinations.ai/prompt/fantasy%20rpg%20dnd%20${prompt}%20character%20portrait%20cinematic%20lighting%20highly%20detailed?width=600&height=800&nologo=true`;

const classImages: Record<string, string> = {
  "Bárbaro": getImage("barbarian%20fury"),
  "Bardo": getImage("bard%20musician%20tavern"),
  "Clérigo": getImage("cleric%20holy%20light"),
  "Druida": getImage("druid%20nature%20forest"),
  "Guerreiro": getImage("knight%20armor%20sword"),
  "Monge": getImage("monk%20martial%20arts"),
  "Paladino": getImage("paladin%20shining%20armor"),
  "Patrulheiro": getImage("ranger%20hooded%20bow"),
  "Ladino": getImage("rogue%20shadow%20dagger"),
  "Feiticeiro": getImage("sorcerer%20fire%20magic"),
  "Bruxo": getImage("warlock%20dark%20magic"),
  "Mago": getImage("wizard%20library%20spell")
};

const raceImages: Record<string, string> = {
  "Anão": getImage("dwarf%20warrior%20beard"),
  "Elfo": getImage("elf%20archer%20elegant"),
  "Humano": getImage("human%20hero%20sword"),
  "Halfling": getImage("hobbit%20peaceful"),
  "Draconato": getImage("dragonborn%20breath"),
  "Tiefling": getImage("tiefling%20horns%20fire"),
  "Meio-Orc": getImage("orc%20warrior%20fierce"),
  "Gnomo": getImage("gnome%20inventor"),
  "Meio-Elfo": getImage("half-elf%20adventurer")
};

export default function CharacterCreation({ onCharacterCreated }: CharacterCreationProps) {
  const [step, setStep] = useState(1);
  const [races, setRaces] = useState<string[]>([]);
  const [classes, setClasses] = useState<string[]>([]);
  
  // Detalhes
  const [details, setDetails] = useState<any>(null);
  
  // Seleções
  const [selectedRace, setSelectedRace] = useState("");
  const [selectedClass, setSelectedClass] = useState("");
  const [name, setName] = useState("");
  const [history, setHistory] = useState("");
  const [loading, setLoading] = useState(false);

  // Carrega listas iniciais
  useEffect(() => {
    axios.get("http://127.0.0.1:8000/options/races").then(res => setRaces(res.data.opcoes));
    axios.get("http://127.0.0.1:8000/options/classes").then(res => setClasses(res.data.opcoes));
  }, []);

  // Busca detalhes quando muda a seleção
  useEffect(() => {
    const fetchDetails = async () => {
      setDetails(null); // Limpa para mostrar loading
      if (step === 1 && selectedRace) {
        try {
            const res = await axios.get(`http://127.0.0.1:8000/options/races/${selectedRace}`);
            setDetails(res.data);
        } catch(e) { console.error(e) }
      } 
      else if (step === 2 && selectedClass) {
        try {
            // AGORA VAI FUNCIONAR (Se você atualizou o api.py)
            const res = await axios.get(`http://127.0.0.1:8000/options/classes/${selectedClass}`);
            setDetails(res.data);
        } catch(e) { console.error(e) }
      }
    };
    fetchDetails();
  }, [selectedRace, selectedClass, step]);

  const handleFinish = async () => {
    if (!name) return alert("Todo herói precisa de um nome!");
    setLoading(true);
    try {
      await axios.post("http://127.0.0.1:8000/create_character", {
        nome: name, raca: selectedRace, classe: selectedClass, historia: history
      }).then(res => onCharacterCreated(res.data.session_id));
    } catch {
      alert("Erro ao criar personagem.");
    } finally {
      setLoading(false);
    }
  };

  // Imagem de Fundo Dinâmica
  const currentBg = step === 1 && selectedRace ? raceImages[selectedRace] :
                    step === 2 && selectedClass ? classImages[selectedClass] :
                    "https://image.pollinations.ai/prompt/dark%20fantasy%20rpg%20table%20map?nologo=true";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-black font-sans text-gray-100">
      
      {/* 1. PAINEL ESQUERDO (Seleção) */}
      <div className="w-1/3 h-full flex flex-col bg-gray-900 border-r border-gray-800 z-20 shadow-2xl">
        {/* Cabeçalho */}
        <div className="p-6 border-b border-gray-800 bg-black/40">
           <h1 className="text-3xl font-rpg text-rpg-gold flex items-center gap-2">
             <Crown className="text-red-600"/> MESTRE.IA
           </h1>
           <div className="flex mt-4 gap-2">
             <StepBadge num={1} label="Raça" active={step === 1} done={!!selectedRace} onClick={() => setStep(1)} />
             <StepBadge num={2} label="Classe" active={step === 2} done={!!selectedClass} onClick={() => selectedRace && setStep(2)} />
             <StepBadge num={3} label="Lenda" active={step === 3} done={!!name} onClick={() => selectedClass && setStep(3)} />
           </div>
        </div>

        {/* Lista de Opções (Scroll) */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
            {step === 1 && (
                <>
                <h2 className="text-gray-500 uppercase text-xs font-bold tracking-widest mb-2 pl-2">Escolha sua Origem</h2>
                {races.map(r => (
                    <OptionButton 
                        key={r} 
                        label={r} 
                        active={selectedRace === r} 
                        image={raceImages[r]}
                        onClick={() => setSelectedRace(r)} 
                    />
                ))}
                </>
            )}

            {step === 2 && (
                <>
                <h2 className="text-gray-500 uppercase text-xs font-bold tracking-widest mb-2 pl-2">Escolha sua Vocação</h2>
                {classes.map(c => (
                    <OptionButton 
                        key={c} 
                        label={c} 
                        active={selectedClass === c} 
                        image={classImages[c]}
                        onClick={() => setSelectedClass(c)} 
                    />
                ))}
                </>
            )}

            {step === 3 && (
                <div className="p-4 space-y-6">
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-2">Nome do Herói</label>
                        <input 
                            type="text" 
                            className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white text-lg focus:border-rpg-gold outline-none"
                            placeholder="Ex: Vorag, o Bárbaro"
                            value={name} onChange={e => setName(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-2">História</label>
                        <textarea 
                             className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white h-32 focus:border-rpg-gold outline-none resize-none"
                             placeholder="Qual é o seu passado?"
                             value={history} onChange={e => setHistory(e.target.value)}
                        />
                    </div>
                    <button 
                        onClick={handleFinish} 
                        disabled={loading || !name}
                        className="w-full py-4 bg-red-700 hover:bg-red-600 text-white font-bold rounded flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? "Criando..." : <>INICIAR AVENTURA <Sword size={20}/></>}
                    </button>
                </div>
            )}
        </div>
      </div>

      {/* 2. PAINEL DIREITO (Visualização Épica) */}
      <div className="flex-1 h-full relative bg-gray-900 overflow-hidden">
         {/* Background Image com Fade */}
         <div className="absolute inset-0 z-0">
             <div className="absolute inset-0 bg-gradient-to-l from-transparent via-black/50 to-gray-900 z-10"></div>
             <img 
                src={currentBg} 
                className="w-full h-full object-cover opacity-60 transition-opacity duration-700 animate-pulse-slow" 
                alt="Background"
             />
         </div>

         {/* Conteúdo Sobreposto */}
         <div className="relative z-20 h-full flex flex-col justify-end p-12 pb-24 max-w-3xl">
            {details ? (
                <div className="animate-slide-up">
                    <h1 className="text-6xl font-rpg text-white drop-shadow-lg mb-2 text-glow uppercase">
                        {step === 1 ? selectedRace : step === 2 ? selectedClass : "Sua Lenda"}
                    </h1>
                    
                    {/* Linha Decorativa */}
                    <div className="h-1 w-24 bg-rpg-gold mb-6"></div>

                    {/* Citação */}
                    {details.quote && (
                        <p className="text-xl text-rpg-gold italic font-serif mb-6">"{details.quote}"</p>
                    )}

                    {/* Descrição Longa */}
                    <p className="text-lg text-gray-200 leading-relaxed mb-8 font-hand text-shadow-md">
                        {details.descricao}
                    </p>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 gap-4">
                        {details.bonus_atributos && (
                            <div className="bg-black/60 p-4 rounded border-l-2 border-rpg-gold backdrop-blur-sm">
                                <span className="text-gray-400 text-xs uppercase tracking-widest block mb-1">Atributos</span>
                                <div className="flex gap-2">
                                    {Object.entries(details.bonus_atributos).map(([k,v]) => (
                                        <span key={k} className="text-sm font-bold text-white">+{v as number} {k.slice(0,3).toUpperCase()}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                        {details.dado_vida && (
                            <div className="bg-black/60 p-4 rounded border-l-2 border-red-500 backdrop-blur-sm">
                                <span className="text-gray-400 text-xs uppercase tracking-widest block mb-1">Combate</span>
                                <div className="flex items-center gap-4 text-white">
                                    <span className="flex items-center gap-1"><Heart size={14} className="text-red-500"/> HP: d{details.dado_vida}</span>
                                    <span className="flex items-center gap-1"><Shield size={14} className="text-blue-500"/> Prof: {details.proficiencias?.[0]}</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="h-full flex flex-col items-center justify-center text-gray-500">
                    {step < 3 && (selectedRace || selectedClass) ? (
                        <div className="flex flex-col items-center animate-pulse">
                           <Sparkles size={48} className="text-rpg-gold mb-4"/>
                           <span className="text-xl font-rpg">Invocando Imagem...</span>
                           <span className="text-sm">(Isso pode levar alguns segundos)</span>
                        </div>
                    ) : (
                        <span className="text-2xl font-rpg opacity-30">Selecione uma opção ao lado</span>
                    )}
                </div>
            )}
            
            {/* Botão de Avançar Flutuante */}
            {step < 3 && (selectedRace || (step === 2 && selectedClass)) && (
                <button 
                  onClick={() => setStep(s => s + 1)}
                  className="absolute bottom-10 right-10 bg-rpg-gold hover:bg-white text-black p-4 rounded-full shadow-[0_0_20px_rgba(197,160,89,0.5)] transition-all hover:scale-110"
                >
                  <ChevronRight size={32} />
                </button>
            )}
         </div>
      </div>
    </div>
  );
}

// --- Componentes Menores ---

function StepBadge({ num, label, active, done, onClick }: any) {
    return (
        <button onClick={onClick} disabled={!done && !active}
            className={`px-3 py-1 rounded text-sm font-bold transition-all border ${
                active ? 'bg-rpg-gold text-black border-rpg-gold' :
                done ? 'bg-gray-800 text-gray-300 border-gray-600 hover:border-gray-400' :
                'bg-transparent text-gray-600 border-transparent cursor-not-allowed'
            }`}
        >
            {num}. {label}
        </button>
    )
}

function OptionButton({ label, active, onClick, image }: any) {
    return (
        <button 
            onClick={onClick}
            className={`w-full text-left flex items-center gap-4 p-3 rounded-lg border transition-all group relative overflow-hidden ${
                active 
                ? 'bg-gray-800 border-rpg-gold shadow-lg' 
                : 'bg-black/20 border-gray-800 hover:bg-gray-800 hover:border-gray-600'
            }`}
        >
            {/* Miniatura */}
            <div className={`w-12 h-12 rounded bg-black shrink-0 overflow-hidden border ${active ? 'border-rpg-gold' : 'border-gray-700'}`}>
                <img src={image} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
            </div>
            
            <div className="flex-1 z-10">
                <span className={`font-rpg text-lg block ${active ? 'text-rpg-gold text-glow' : 'text-gray-400 group-hover:text-gray-200'}`}>
                    {label}
                </span>
            </div>
            
            {/* Efeito de brilho no fundo */}
            {active && <div className="absolute inset-0 bg-gradient-to-r from-rpg-gold/10 to-transparent pointer-events-none"/>}
        </button>
    )
}