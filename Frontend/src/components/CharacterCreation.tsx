import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Sword, Crown, ChevronRight, ArrowLeft, Sparkles,
  Minus, Plus, Heart, Scroll, User, Zap, Edit2
} from 'lucide-react';

interface CharacterCreationProps {
  onCharacterCreated?: (sessionId: string) => void; // Opcional agora
}

// Helpers
const formatAttribute = (key: string) => {
    const map: Record<string, string> = { "forca": "FOR", "destreza": "DES", "constituicao": "CON", "inteligencia": "INT", "sabedoria": "SAB", "carisma": "CAR", "livre_escolha": "LIVRE" };
    return map[key] || key.substring(0,3).toUpperCase();
};
const getLocalImage = (type: 'classes' | 'races', name: string) => `/assets/${type}/${name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, '-')}.jpg`;
const getPointCost = (score: number) => { if (score <= 8) return 0; const costs: Record<number, number> = {9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9}; return costs[score] || 99; };

export default function CharacterCreation({ onCharacterCreated }: CharacterCreationProps) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  
  // Listas e Dados
  const [races, setRaces] = useState<string[]>([]);
  const [classes, setClasses] = useState<string[]>([]);
  const [raceData, setRaceData] = useState<any>(null);
  const [classData, setClassData] = useState<any>(null);
  
  // --- SELEÇÕES (DADOS DO PERSONAGEM) ---
  const [selectedRace, setSelectedRace] = useState("");
  const [selectedClass, setSelectedClass] = useState("");
  const [name, setName] = useState("");
  const [gender, setGender] = useState("");
  
  // Novos Campos de Profundidade
  const [alignment, setAlignment] = useState("Neutro");
  const [background, setBackground] = useState("");
  const [goal, setGoal] = useState("");
  const [history, setHistory] = useState("");
  
  // Atributos
  const [attributes, setAttributes] = useState<Record<string, number>>({ forca: 8, destreza: 8, constituicao: 8, inteligencia: 8, sabedoria: 8, carisma: 8 });
  const [pointsRemaining, setPointsRemaining] = useState(27);
  const [freePointsAllocation, setFreePointsAllocation] = useState<Record<string, number>>({});
  
  // UI
  const [loading, setLoading] = useState(false);
  const [finalImageUrl, setFinalImageUrl] = useState(""); 

  // Carregamento Inicial
  useEffect(() => {
    axios.get("http://127.0.0.1:8000/options/races").then(res => setRaces(res.data.opcoes)).catch(() => {});
    axios.get("http://127.0.0.1:8000/options/classes").then(res => setClasses(res.data.opcoes)).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedRace) {
        axios.get(`http://127.0.0.1:8000/options/races/${selectedRace}`).then(res => { setRaceData(res.data); setFreePointsAllocation({}); }).catch(() => {});
    }
  }, [selectedRace]);

  useEffect(() => {
    if (selectedClass) axios.get(`http://127.0.0.1:8000/options/classes/${selectedClass}`).then(res => setClassData(res.data)).catch(() => {});
  }, [selectedClass]);

  // Gerador de Imagem (IA)
  useEffect(() => {
    if (step === 4 && name && gender && selectedRace && selectedClass) {
        const prompt = `fantasy rpg character portrait of a ${gender} ${selectedRace} ${selectedClass}, ${background}, highly detailed face, looking at camera, dnd art style, masterpiece, sharp focus, dark fantasy background`;
        const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=500&height=750&nologo=true&seed=${name.length + 123}`;
        setFinalImageUrl(url);
    }
  }, [step, name, gender, selectedRace, selectedClass, background]);

  // Lógica de Atributos
  const handleAttributeChange = (attr: string, delta: number) => {
      const currentVal = attributes[attr]; const newVal = currentVal + delta;
      if (newVal < 8 || newVal > 15) return; 
      const costDiff = getPointCost(newVal) - getPointCost(currentVal);
      if (pointsRemaining - costDiff < 0) return;
      setAttributes(prev => ({ ...prev, [attr]: newVal })); setPointsRemaining(prev => prev - costDiff);
  };

  const handleFreeAllocation = (attr: string) => {
      setFreePointsAllocation(prev => {
          const isSelected = prev[attr] === 1;
          if (isSelected) { const { [attr]: _, ...rest } = prev; return rest; }
          const currentTotal = Object.values(prev).reduce((a, b) => a + b, 0);
          const maxFree = raceData?.bonus_atributos?.['livre_escolha'] || 0;
          if (currentTotal < maxFree) return { ...prev, [attr]: 1 };
          return prev;
      });
  };

  const getFinalAttribute = (attr: string) => {
      return attributes[attr] + (raceData?.bonus_atributos?.[attr] || 0) + (freePointsAllocation[attr] || 0);
  };

  const getModifierValue = (score: number) => Math.floor((score - 10) / 2);
  const formatModifier = (mod: number) => mod >= 0 ? `+${mod}` : `${mod}`;
  const getInitialHP = () => (classData?.dado_vida || 0) + getModifierValue(getFinalAttribute('constituicao'));

  const maxFreePoints = raceData?.bonus_atributos?.['livre_escolha'] || 0;
  const usedFreePoints = Object.values(freePointsAllocation).reduce((a, b) => a + b, 0);
  
  // --- VALIDAÇÃO DO BOTÃO "PRÓXIMO" ---
  const canProceed = 
    (step === 1 && !!selectedRace) || 
    (step === 2 && !!selectedClass) || 
    // AGORA O PASSO 3 EXIGE NOME, GÊNERO E OS NOVOS CAMPOS
    (step === 3 && !!name && !!gender && !!background && !!goal) || 
    (step === 4 && pointsRemaining === 0 && usedFreePoints === maxFreePoints);

  const handleFinish = async () => {
    setLoading(true);
    try {
      // Manda os atributos "crus" (antes do bônus racial) e a lista de
      // atributos escolhidos para o ponto livre da raça — o servidor
      // recalcula tudo e é ele quem decide o valor final. Ver ADR-0002.
      const atributosLivreEscolhidos = Object.keys(freePointsAllocation).filter(attr => freePointsAllocation[attr] === 1);

      const res = await axios.post("http://127.0.0.1:8000/create_character", {
        nome: name, raca: selectedRace, classe: selectedClass,
        alinhamento: alignment, background: background, objetivo: goal,
        historia_texto: history,
        atributos: attributes,
        atributos_livre: atributosLivreEscolhidos,
      });

      const sessionId = res.data.session_id;
      if (onCharacterCreated) onCharacterCreated(sessionId);

      const imageToSend = finalImageUrl || getLocalImage('classes', selectedClass);

      // Salva no LocalStorage só como índice para a tela inicial listar os
      // heróis — HP, defesa e atributos de verdade vivem no servidor.
      const saveInfo = {
          id: sessionId,
          name: name,
          race: selectedRace,
          class: selectedClass,
          image: imageToSend,
          maxHp: res.data.hp_max,
          defense: res.data.defesa,
          date: new Date().toLocaleDateString()
      };

      const existingSaves = JSON.parse(localStorage.getItem('mestre_ia_saves') || '[]');
      localStorage.setItem('mestre_ia_saves', JSON.stringify([saveInfo, ...existingSaves]));

      navigate(`/jogar/${sessionId}`, { state: { charImage: imageToSend } });

    } catch (err: any) {
      const detalhe = err?.response?.data?.detail;
      alert(detalhe ? `Não deu para criar o personagem: ${detalhe}` : "Erro ao conectar com o servidor.");
    } finally {
      setLoading(false);
    }
  };

  const activeImage = step === 5 && finalImageUrl ? finalImageUrl : step === 2 && selectedClass ? getLocalImage('classes', selectedClass) : step === 1 && selectedRace ? getLocalImage('races', selectedRace) : "/assets/background-default.jpg";
  const activeTitle = step === 5 ? name : step === 1 ? (selectedRace || "Linhagem") : step === 2 ? (selectedClass || "Vocação") : step === 3 ? "Identidade" : "Atributos";
  const currentDetails = step === 1 ? raceData : step === 2 ? classData : null;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-black font-sans text-gray-100">
      <button onClick={() => navigate('/')} className="absolute top-4 left-4 z-50 text-gray-500 hover:text-white flex items-center gap-2"><ArrowLeft size={20}/> Sair</button>

      <div className="w-1/3 h-full flex flex-col bg-gray-900 border-r border-gray-800 z-20 shadow-2xl relative">
        <div className="p-6 border-b border-gray-800 bg-black/40 mt-10">
           <h1 className="text-3xl font-rpg text-rpg-gold flex items-center gap-2"><Crown className="text-red-600"/> CRIAÇÃO</h1>
           <div className="flex justify-between mt-4 px-2">{[1,2,3,4,5].map(s => (<button key={s} disabled={s > step && s !== step + 1} onClick={() => { if (step === 5 || (s < step)) setStep(s); }} className={`h-1 flex-1 mx-1 rounded transition-all duration-300 ${step >= s ? 'bg-rpg-gold cursor-pointer hover:h-2' : 'bg-gray-800 cursor-not-allowed'}`}/>))}</div>
           <p className="text-xs text-gray-500 mt-1 uppercase tracking-widest text-right">{step === 5 ? "Ficha Final" : `Passo ${step}/5`}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar pb-24">
            
            {/* PASSO 1: RAÇA */}
            {step === 1 && races.map(r => <OptionButton key={r} label={r} active={selectedRace === r} image={getLocalImage('races', r)} onClick={() => setSelectedRace(r)} />)}
            
            {/* PASSO 2: CLASSE */}
            {step === 2 && classes.map(c => <OptionButton key={c} label={c} active={selectedClass === c} image={getLocalImage('classes', c)} onClick={() => setSelectedClass(c)} />)}
            
            {/* PASSO 3: IDENTIDADE (CORRIGIDO) */}
            {step === 3 && (
                <div className="p-4 space-y-4 animate-fade-in">
                    {/* Campos Essenciais (Isso que faltava) */}
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Nome do Herói</label>
                        <input type="text" className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white outline-none focus:border-rpg-gold" placeholder="Ex: Vorag" value={name} onChange={e => setName(e.target.value)} />
                    </div>
                    
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Gênero</label>
                        <div className="grid grid-cols-3 gap-2">
                            {["Masculino", "Feminino", "Outro"].map(g => (
                                <button key={g} onClick={() => setGender(g)} className={`p-2 rounded border text-sm transition-all ${gender === g ? 'bg-rpg-gold text-black border-rpg-gold' : 'bg-black border-gray-700 hover:border-gray-500'}`}>{g}</button>
                            ))}
                        </div>
                    </div>

                    <div className="w-full h-px bg-gray-800 my-4"></div>

                    {/* Campos de Profundidade (Novos) */}
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Alinhamento Moral</label>
                        <select className="w-full bg-black/50 border border-gray-600 p-2 rounded text-white outline-none" value={alignment} onChange={e => setAlignment(e.target.value)}>
                            <option value="Neutro">Neutro Verdadeiro</option>
                            <option value="Leal e Bom">Leal e Bom (O Paladino)</option>
                            <option value="Neutro e Bom">Neutro e Bom (O Benfeitor)</option>
                            <option value="Caótico e Bom">Caótico e Bom (O Rebelde)</option>
                            <option value="Leal e Neutro">Leal e Neutro (O Juiz)</option>
                            <option value="Caótico e Neutro">Caótico e Neutro (O Espírito Livre)</option>
                            <option value="Leal e Mau">Leal e Mau (O Tirano)</option>
                            <option value="Neutro e Mau">Neutro e Mau (O Criminoso)</option>
                            <option value="Caótico e Mau">Caótico e Mau (O Destruidor)</option>
                        </select>
                    </div>

                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Profissão / Origem</label>
                        <input type="text" className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white outline-none" placeholder="Ex: Soldado, Eremita, Nobre..." value={background} onChange={e => setBackground(e.target.value)} />
                        <p className="text-[10px] text-gray-500 mt-1">Isso define onde você começa o jogo.</p>
                    </div>

                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Objetivo de Vida</label>
                        <input type="text" className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white outline-none" placeholder="Ex: Vingar meu clã..." value={goal} onChange={e => setGoal(e.target.value)} />
                    </div>

                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">História Extra (Opcional)</label>
                        <textarea className="w-full bg-black/50 border border-gray-600 p-3 rounded text-white h-20 outline-none resize-none" placeholder="Detalhes adicionais..." value={history} onChange={e => setHistory(e.target.value)} />
                    </div>
                </div>
            )}

            {/* PASSO 4: ATRIBUTOS */}
            {step === 4 && (<div className="p-4 space-y-6 animate-fade-in"><div className="bg-black/40 p-4 rounded border border-blue-900 text-center"><span className="block text-gray-400 text-xs uppercase tracking-widest">Pontos Restantes</span><span className={`text-4xl font-rpg ${pointsRemaining === 0 ? 'text-green-500' : 'text-blue-400'}`}>{pointsRemaining}/27</span></div>{maxFreePoints > 0 && (<div className={`p-3 rounded border text-center ${usedFreePoints === maxFreePoints ? 'bg-green-900/20 border-green-700' : 'bg-rpg-gold/10 border-rpg-gold'}`}><span className="text-sm font-bold text-gray-200 block mb-1"><Sparkles size={12} className="inline mr-1"/> Bônus Racial Extra</span><span className={`text-xl font-rpg ${usedFreePoints === maxFreePoints ? 'text-green-400' : 'text-rpg-gold'}`}>{usedFreePoints}/{maxFreePoints}</span></div>)}<div className="space-y-2">{Object.keys(attributes).map(attr => { const fixedBonus = raceData?.bonus_atributos?.[attr] || 0; const isFreeSelected = freePointsAllocation[attr] === 1; const isFreeAvailable = maxFreePoints > 0 && fixedBonus === 0; return (<div key={attr} className="flex items-center justify-between bg-gray-900/50 p-2 rounded border border-gray-800 hover:border-gray-600"><div className="w-20"><span className="font-bold text-sm text-gray-300 block">{formatAttribute(attr)}</span>{fixedBonus > 0 && <span className="text-[10px] text-blue-400 font-bold">+{fixedBonus} Raça</span>}{isFreeAvailable && (<button onClick={() => handleFreeAllocation(attr)} disabled={!isFreeSelected && usedFreePoints >= maxFreePoints} className={`text-[10px] px-1 rounded border mt-1 transition-colors ${isFreeSelected ? 'bg-green-600 text-white border-green-500' : 'bg-black text-gray-500 border-gray-700 hover:border-gray-500'}`}>{isFreeSelected ? '+1 Extra' : '+ Adicionar'}</button>)}</div><div className="flex items-center gap-3"><button onClick={() => handleAttributeChange(attr, -1)} className="w-8 h-8 rounded bg-gray-800 hover:bg-red-900 flex items-center justify-center text-white disabled:opacity-30" disabled={attributes[attr] <= 8}><Minus size={14}/></button><span className="text-xl w-6 text-center font-mono">{attributes[attr]}</span><button onClick={() => handleAttributeChange(attr, 1)} className="w-8 h-8 rounded bg-gray-800 hover:bg-green-900 flex items-center justify-center text-white disabled:opacity-30" disabled={attributes[attr] >= 15 || pointsRemaining === 0}><Plus size={14}/></button></div><div className="text-[10px] text-gray-500 w-12 text-right">{attributes[attr] >= 15 ? 'MÁX' : `-${getPointCost(attributes[attr] + 1) - getPointCost(attributes[attr])}`}</div></div>); })}</div></div>)}
            
            {/* PASSO 5: RESUMO */}
            {step === 5 && (<div className="p-6 h-full flex flex-col justify-center items-center text-center animate-fade-in"><Crown size={48} className="text-rpg-gold mb-4 animate-pulse"/><h3 className="text-2xl font-rpg text-white mb-2">Destino Selado</h3><p className="text-gray-400 text-sm mb-8">Confirme os dados da ficha ao lado para iniciar.</p><button onClick={handleFinish} disabled={loading} className="w-full py-5 bg-green-700 hover:bg-green-600 text-white font-bold text-lg rounded shadow-lg flex items-center justify-center gap-3 transition-all hover:scale-105 mb-4">{loading ? "Iniciando..." : <>JOGAR AGORA <ChevronRight /></>}</button><button onClick={() => setStep(4)} className="text-gray-500 hover:text-rpg-gold flex items-center gap-2 text-sm underline decoration-gray-700 hover:decoration-rpg-gold"><Edit2 size={14}/> Editar Atributos</button></div>)}
        </div>
      </div>

      <div className="flex-1 h-full relative bg-gray-900 overflow-hidden flex items-center justify-center p-8 bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
         <div className="relative z-30 w-full max-w-5xl h-[600px] flex bg-[#121212] border-2 border-rpg-gold rounded-xl shadow-2xl overflow-hidden animate-scale-in">
             <div className="w-[45%] h-full relative border-r border-rpg-gold/30 bg-black">
                 <img src={activeImage} className="w-full h-full object-cover object-top" alt="Visual" onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/500x750?text=...")}/>
                 <div className="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-6 pt-12">
                     <h2 className="text-3xl font-rpg text-white text-center drop-shadow-md">{activeTitle}</h2>
                     {step === 5 && <p className="text-rpg-gold text-center font-bold text-xs uppercase tracking-widest opacity-80">{selectedRace} • {selectedClass}</p>}
                 </div>
             </div>
             <div className="w-[55%] p-8 flex flex-col relative overflow-y-auto custom-scrollbar">
                 <div className="absolute top-4 right-4 opacity-10 pointer-events-none"><Crown size={120}/></div>
                 <h3 className="text-rpg-gold font-rpg text-2xl border-b border-gray-700 pb-3 mb-6 flex items-center gap-2">
                    {step === 5 ? <Scroll size={24}/> : step === 1 ? <User size={24}/> : step === 2 ? <Sword size={24}/> : <Sparkles size={24}/>}
                    {step === 5 ? "Ficha Técnica" : step === 1 ? "Detalhes da Raça" : step === 2 ? "Detalhes da Classe" : "Planejamento"}
                 </h3>
                 
                 {/* Conteúdo Dinâmico da Direita */}
                 {step === 5 ? (
                     <>
                        <div className="flex justify-around mb-8 bg-black/20 p-4 rounded-lg">
                             <div className="text-center"><div className="text-2xl font-bold text-blue-400 font-rpg">{10 + getModifierValue(getFinalAttribute('destreza'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Defesa</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-red-500 font-rpg">{getInitialHP()}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Vida</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-green-500 font-rpg">{10 + getModifierValue(getFinalAttribute('sabedoria'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Percepção</span></div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                             {Object.keys(attributes).map(attr => (
                                 <div key={attr} className="bg-gray-800/40 border border-gray-700 rounded p-2 text-center relative"><span className="block text-[10px] text-gray-500 uppercase font-bold mb-1">{formatAttribute(attr)}</span><span className="block text-xl text-white font-rpg">{getFinalAttribute(attr)}</span><div className="absolute -top-2 -right-2 w-6 h-6 bg-gray-700 rounded-full flex items-center justify-center text-[10px] text-blue-300 font-bold border border-gray-600 shadow-sm">{formatModifier(getModifierValue(getFinalAttribute(attr)))}</div></div>
                             ))}
                        </div>
                        <div className="mt-6 bg-black/30 p-3 rounded text-sm text-gray-400">
                            <p><strong className="text-rpg-gold">Origem:</strong> {background}</p>
                            <p><strong className="text-rpg-gold">Missão:</strong> {goal}</p>
                        </div>
                     </>
                 ) : currentDetails ? (
                     <div className="space-y-6 animate-fade-in">{currentDetails.quote && <p className="text-xl text-rpg-gold italic font-serif text-center px-4">"{currentDetails.quote}"</p>}<div className="text-gray-300 leading-relaxed text-justify bg-black/20 p-4 rounded border border-gray-800">{currentDetails.descricao}</div>{step === 1 && currentDetails.bonus_atributos && (<div className="mt-4"><span className="text-xs text-gray-500 uppercase tracking-widest block mb-2">Bônus de Atributo</span><div className="flex gap-2 flex-wrap">{Object.entries(currentDetails.bonus_atributos).filter(([k]) => k !== 'livre_escolha').map(([k,v]) => (<span key={k} className="text-xs bg-blue-900/40 px-3 py-1 rounded text-blue-200 border border-blue-800 uppercase flex items-center gap-1"><Zap size={10} /> +{v as number} {formatAttribute(k)}</span>))}{currentDetails.bonus_atributos.livre_escolha > 0 && (<span className="text-xs bg-purple-900/40 px-3 py-1 rounded text-purple-200 border border-purple-800 uppercase flex items-center gap-1"><Sparkles size={10} /> +{currentDetails.bonus_atributos.livre_escolha} Escolha</span>)}</div></div>)}{step === 2 && currentDetails.dado_vida && <div className="mt-4 flex gap-4"><span className="flex items-center gap-2 text-gray-300 bg-gray-800 px-3 py-1 rounded border border-gray-700"><Heart size={14} className="text-red-500"/> Vida Base: d{currentDetails.dado_vida}</span></div>}</div>
                 ) : step === 3 ? (
                     <div className="flex flex-col items-center justify-center h-full text-gray-600 text-center px-8">
                         <User size={64} className="mb-4 text-rpg-gold opacity-50"/>
                         <h3 className="text-xl font-rpg text-white mb-2">Quem é você?</h3>
                         <p className="text-sm">Defina sua identidade. O nome e o passado do seu herói moldarão como o mundo reage a ele.</p>
                     </div>
                 ) : (<div className="flex flex-col items-center justify-center h-full text-gray-600"><Sparkles size={48} className="mb-4 opacity-50"/><span className="text-xl font-rpg">Selecione uma opção...</span></div>)}
                 
                 {/* BOTÃO PRÓXIMO (O QUE SUMIU) */}
                 {canProceed && step < 5 && (<div className="mt-auto pt-6 flex justify-end"><button onClick={() => setStep(s => s + 1)} className="bg-rpg-gold hover:bg-white text-black p-3 rounded-full shadow-lg transition-all hover:scale-110 flex items-center gap-2 font-bold px-6">PRÓXIMO <ChevronRight size={20} /></button></div>)}
             </div>
         </div>
      </div>
    </div>
  );
}

function OptionButton({ label, active, onClick, image }: any) { return <button onClick={onClick} className={`w-full text-left flex items-center gap-4 p-2 rounded border transition-all group relative overflow-hidden ${active ? 'bg-gray-800 border-rpg-gold shadow-lg' : 'bg-black/20 border-gray-800 hover:bg-gray-800 hover:border-gray-600'}`}><div className={`w-12 h-12 rounded bg-black shrink-0 overflow-hidden border ${active ? 'border-rpg-gold' : 'border-gray-700'}`}><img src={image} onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/50?text=?")} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" /></div><div className="flex-1 z-10"><span className={`font-rpg text-base block ${active ? 'text-rpg-gold text-glow' : 'text-gray-400 group-hover:text-gray-200'}`}>{label}</span></div>{active && <div className="absolute inset-0 bg-gradient-to-r from-rpg-gold/10 to-transparent pointer-events-none"/>}</button>; }