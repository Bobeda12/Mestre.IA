import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { getLocalImage, getRetrato } from '../lib/utils';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import PanelFrame from './PanelFrame';
import BotaoSom from './BotaoSom';
import RetratoPixelado from './RetratoPixelado';

interface CharacterCreationProps {
  onCharacterCreated?: (sessionId: string) => void; // Opcional agora
}

// Helpers
const formatAttribute = (key: string) => {
    const map: Record<string, string> = { "forca": "FOR", "destreza": "DES", "constituicao": "CON", "inteligencia": "INT", "sabedoria": "SAB", "carisma": "CAR", "livre_escolha": "LIVRE" };
    return map[key] || key.substring(0,3).toUpperCase();
};
// Hash estável (FNV-1a de 32 bits) pro seed do gerador de imagem. Precisa ser
// determinístico entre sessões — o mesmo herói tem que reproduzir o mesmo
// retrato — e espalhar bem, pra dois heróis diferentes não colidirem.
function hashSeed(texto: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return Math.abs(h) % 1_000_000;
}

const getPointCost = (score: number) => { if (score <= 8) return 0; const costs: Record<number, number> = {9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9}; return costs[score] || 99; };

// O modelo de imagem foi treinado majoritariamente em inglês — mandar o
// nome da raça/classe em português ("Draconato", "Meio-Orc") não significa
// nada pra ele, e é a causa mais provável da arte não bater com o
// personagem. Estes descritores existem só para o prompt de imagem; o
// resto do app continua em português (ver Backend/data/races.json).
const RACE_VISUAL_EN: Record<string, string> = {
  "Anão": "dwarf, short and stocky build, thick braided beard",
  "Elfo": "elf, tall and slender, pointed ears, elegant features",
  "Halfling": "halfling, very short stature, curly hair, cheerful round face",
  "Humano": "human",
  "Draconato": "dragonborn, reptilian scaled skin, dragon-like head, no hair",
  "Gnomo": "gnome, tiny stature, large expressive eyes, pointed ears",
  "Meio-Elfo": "half-elf, slightly pointed ears, human build with elven grace",
  "Meio-Orc": "half-orc, greenish-gray skin, prominent lower tusks, muscular build",
  "Tiefling": "tiefling, small horns, thin tail, reddish or violet skin",
};

const CLASS_VISUAL_EN: Record<string, string> = {
  "Bárbaro": "barbarian wielding a greataxe, fur and leather",
  "Bardo": "bard with a lute, flamboyant light armor",
  "Clérigo": "cleric in chainmail holding a holy symbol",
  "Druida": "druid with a wooden shield and natural adornments",
  "Guerreiro": "warrior in chainmail with a longsword and shield",
  "Monge": "monk in simple robes, hands ready, no weapon",
  "Paladino": "paladin in gleaming plate armor with a shield",
  "Patrulheiro": "ranger in scale armor with a longbow",
  "Ladino": "rogue in leather armor with daggers, hooded",
  "Feiticeiro": "sorcerer with an arcane focus, flowing robes",
  "Bruxo": "warlock in dark leather armor with an eerie arcane focus",
  "Mago": "wizard in robes holding a staff and spellbook",
};

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
  // Quantas vezes o jogador pediu outro retrato. Entra no seed, então cada
  // clique é um sorteio novo — e como o seed continua derivado (não
  // aleatório), o retrato escolhido se reproduz igual depois.
  const [variacao, setVariacao] = useState(0);

  // Carregamento Inicial
  useEffect(() => {
    api.get("/options/races").then(res => setRaces(res.data.opcoes)).catch(() => {});
    api.get("/options/classes").then(res => setClasses(res.data.opcoes)).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedRace) {
        api.get(`/options/races/${selectedRace}`).then(res => { setRaceData(res.data); setFreePointsAllocation({}); }).catch(() => {});
    }
  }, [selectedRace]);

  useEffect(() => {
    if (selectedClass) api.get(`/options/classes/${selectedClass}`).then(res => setClassData(res.data)).catch(() => {});
  }, [selectedClass]);

  // Gerador de Imagem (IA)
  useEffect(() => {
    // Passo 4 E 5: o retrato nasce ao fechar os atributos (4), mas o botão
    // "gerar outro" vive na ficha final (5). Com o guard só em `step === 4`
    // o clique mudava `variacao` e nada regerava — a condição precisa cobrir
    // a tela onde o botão está.
    if ((step === 4 || step === 5) && name && gender && selectedRace && selectedClass) {
        const genderEn = gender === "Feminino" ? "female" : gender === "Masculino" ? "male" : "androgynous";
        const raceVisual = RACE_VISUAL_EN[selectedRace] || selectedRace;
        const classVisual = CLASS_VISUAL_EN[selectedClass] || selectedClass;
        const prompt = `fantasy rpg character portrait of a ${genderEn} ${raceVisual}, ${classVisual}, highly detailed face, looking at camera, dnd art style, masterpiece, sharp focus, dark fantasy background`;
        // O seed saía de `name.length + 123`, ou seja dependia SÓ do
        // comprimento do nome: como quase todo nome tem 4 a 8 letras, todo
        // mundo caía entre 127 e 131, e "Pedro" e "Vorag" geravam com o
        // mesmo seed. Agora entra a identidade inteira, então trocar
        // qualquer parte dela muda o resultado — e o mesmo herói continua
        // reproduzindo o mesmo retrato, que é o motivo de existir um seed
        // fixo em vez de aleatório.
        const seed = hashSeed(`${name}|${gender}|${selectedRace}|${selectedClass}|${variacao}`);
        const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=500&height=750&nologo=true&model=flux&seed=${seed}`;
        setFinalImageUrl(url);
    }
  }, [step, name, gender, selectedRace, selectedClass, variacao]);

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
      // Etapa 11 (B-3): manda a MESMA imagem que a Ficha Final mostrou —
      // se o retrato IA nunca carregou, não manda nada (o servidor guarda
      // "sem imagem" em vez de salvar o retrato genérico da classe, que já
      // é o fallback natural de quem não tem imagem nenhuma).
      const imageToSend = finalImageUrl || "";

      const res = await api.post("/create_character", {
        nome: name, raca: selectedRace, classe: selectedClass,
        alinhamento: alignment, background: background, objetivo: goal,
        historia_texto: history,
        imagem: imageToSend,
        atributos: attributes,
        atributos_livre: atributosLivreEscolhidos,
      });

      const sessionId = res.data.session_id;
      if (onCharacterCreated) onCharacterCreated(sessionId);

      // Etapa 8: a lista de heróis (Home.tsx) vem do servidor via
      // GET /personagens — não existe mais save local pra escrever aqui.
      navigate(`/jogar/${sessionId}`, { state: { charImage: imageToSend || getLocalImage('classes', selectedClass) } });

    } catch (err: any) {
      const detalhe = err?.response?.data?.detail;
      alert(detalhe ? `Não deu para criar o personagem: ${detalhe}` : "Erro ao conectar com o servidor.");
    } finally {
      setLoading(false);
    }
  };

  // Etapa 14 (C-4) — "/assets/background-default.jpg" não existe mais desde
  // a reorganização de assets do B-1 (Etapa 11); o placeholder externo do
  // via.placeholder.com que o onError tentava carregar em seguida também
  // falha offline. Usa a cena de fundo local da Home, já dentro da mesma
  // regra do ADR-0017 (sem geração por IA).
  // Painel grande usa o RETRATO (arte gerada e pixelizada, ADR-0025); a lista
  // da esquerda usa o sprite do Dungeon Crawl. Ver lib/utils.ts.
  // Nada escolhido ainda mostra um "?" em moldura tracejada. Antes caía no
  // mapa de fundo, que lia como "já escolhi e o resultado é uma paisagem" em
  // vez de "falta escolher".
  const activeImage = step === 5 && finalImageUrl ? finalImageUrl : step === 2 && selectedClass ? getRetrato('classes', selectedClass) : step === 1 && selectedRace ? getRetrato('races', selectedRace) : "/assets/placeholder-selecao.png";
  const semSelecao = !(step === 5 && finalImageUrl) && !(step === 2 && selectedClass) && !(step === 1 && selectedRace);
  const activeTitle = step === 5 ? name : step === 1 ? (selectedRace || "Linhagem") : step === 2 ? (selectedClass || "Vocação") : step === 3 ? "Identidade" : "Atributos";
  const currentDetails = step === 1 ? raceData : step === 2 ? classData : null;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-black font-sans text-gray-100">
      <div className="absolute top-4 left-4 z-50 flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-gray-300 hover:text-rpg-gold flex items-center gap-2 font-rpg"><PixelIcon name="seta" className="rotate-180" /> Sair</button>
        <BotaoSom tema="aventura" />
      </div>

      <div className="w-1/3 h-full flex flex-col bg-gray-900 border-r border-gray-800 z-20 shadow-2xl relative">
        <div className="p-6 border-b border-gray-800 bg-black/40 mt-10">
           <h1 className="text-xl font-pixel-title text-rpg-gold flex items-center gap-2"><PixelIcon name="coroa" size={20} /> CRIAÇÃO</h1>
           {/* Etapa 14 (C-4) — passos em blocos discretos, mesmo espírito do
               PixelBar (Etapa 11), em vez da barra fina arredondada. */}
           <div className="flex gap-1 mt-4 px-2">{[1,2,3,4,5].map(s => (<button key={s} disabled={s > step && s !== step + 1} onClick={() => { if (step === 5 || (s < step)) setStep(s); }} className={`h-3 flex-1 transition-colors ${step >= s ? 'bg-rpg-gold cursor-pointer' : 'bg-gray-800 cursor-not-allowed'}`}/>))}</div>
           <p className="text-xs text-gray-300 mt-1 uppercase tracking-widest text-right font-rpg">{step === 5 ? "Ficha Final" : `Passo ${step}/5`}</p>
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
                        <input type="text" className="w-full bg-black/50 border-2 border-gray-600 p-3 text-white outline-none focus:border-rpg-gold" placeholder="Ex: Vorag" value={name} onChange={e => setName(e.target.value)} />
                    </div>
                    
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Gênero</label>
                        <div className="grid grid-cols-3 gap-2">
                            {["Masculino", "Feminino", "Outro"].map(g => (
                                <button key={g} onClick={() => setGender(g)} className={`p-2 border-2 text-sm transition-all ${gender === g ? 'bg-rpg-gold text-black border-rpg-gold' : 'bg-black border-gray-700 hover:border-gray-500'}`}>{g}</button>
                            ))}
                        </div>
                    </div>

                    <div className="w-full h-px bg-gray-800 my-4"></div>

                    {/* Campos de Profundidade (Novos) */}
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Alinhamento Moral</label>
                        <select className="w-full bg-black/50 border-2 border-gray-600 p-2 text-white outline-none" value={alignment} onChange={e => setAlignment(e.target.value)}>
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
                        <input type="text" className="w-full bg-black/50 border-2 border-gray-600 p-3 text-white outline-none focus:border-rpg-gold" placeholder="Ex: Soldado, Eremita, Nobre..." value={background} onChange={e => setBackground(e.target.value)} />
                        <p className="text-[10px] text-gray-500 mt-1">Isso define onde você começa o jogo.</p>
                    </div>

                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">Objetivo de Vida</label>
                        <input type="text" className="w-full bg-black/50 border-2 border-gray-600 p-3 text-white outline-none focus:border-rpg-gold" placeholder="Ex: Vingar meu clã..." value={goal} onChange={e => setGoal(e.target.value)} />
                    </div>

                    <div>
                        <label className="text-rpg-gold font-rpg block mb-1">História Extra (Opcional)</label>
                        <textarea className="w-full bg-black/50 border-2 border-gray-600 p-3 text-white h-20 outline-none resize-none focus:border-rpg-gold" placeholder="Detalhes adicionais..." value={history} onChange={e => setHistory(e.target.value)} />
                    </div>
                </div>
            )}

            {/* PASSO 4: ATRIBUTOS */}
            {step === 4 && (<div className="p-4 space-y-6 animate-fade-in"><div className="bg-black/40 p-4 border-2 border-blue-900 text-center"><span className="block text-gray-400 text-xs uppercase tracking-widest">Pontos Restantes</span><span className={`text-4xl font-rpg ${pointsRemaining === 0 ? 'text-green-500' : 'text-blue-400'}`}>{pointsRemaining}/27</span></div>{maxFreePoints > 0 && (<div className={`p-3 border-2 text-center ${usedFreePoints === maxFreePoints ? 'bg-green-900/20 border-green-700' : 'bg-rpg-gold/10 border-rpg-gold'}`}><span className="text-sm font-bold text-gray-200 block mb-1 flex items-center justify-center gap-1"><PixelIcon name="estrela" size={12}/> Bônus Racial Extra</span><span className={`text-xl font-rpg ${usedFreePoints === maxFreePoints ? 'text-green-400' : 'text-rpg-gold'}`}>{usedFreePoints}/{maxFreePoints}</span></div>)}<div className="space-y-2">{Object.keys(attributes).map(attr => { const fixedBonus = raceData?.bonus_atributos?.[attr] || 0; const isFreeSelected = freePointsAllocation[attr] === 1; const isFreeAvailable = maxFreePoints > 0 && fixedBonus === 0; return (<div key={attr} className="flex items-center justify-between bg-gray-900/50 p-2 border-2 border-gray-800 hover:border-gray-600"><div className="w-20"><span className="font-bold text-sm text-gray-300 block">{formatAttribute(attr)}</span>{fixedBonus > 0 && <span className="text-[10px] text-blue-400 font-bold">+{fixedBonus} Raça</span>}{isFreeAvailable && (<button onClick={() => handleFreeAllocation(attr)} disabled={!isFreeSelected && usedFreePoints >= maxFreePoints} className={`text-[10px] px-1 border mt-1 transition-colors ${isFreeSelected ? 'bg-green-600 text-white border-green-500' : 'bg-black text-gray-500 border-gray-700 hover:border-gray-500'}`}>{isFreeSelected ? '+1 Extra' : '+ Adicionar'}</button>)}</div><div className="flex items-center gap-3"><button onClick={() => handleAttributeChange(attr, -1)} className="w-8 h-8 bg-gray-800 hover:bg-red-900 flex items-center justify-center disabled:opacity-30" disabled={attributes[attr] <= 8}><PixelIcon name="menos" size={14}/></button><span className="text-xl w-6 text-center font-mono">{attributes[attr]}</span><button onClick={() => handleAttributeChange(attr, 1)} className="w-8 h-8 bg-gray-800 hover:bg-green-900 flex items-center justify-center disabled:opacity-30" disabled={attributes[attr] >= 15 || pointsRemaining === 0}><PixelIcon name="mais" size={14}/></button></div><div className="text-[10px] text-gray-500 w-12 text-right">{attributes[attr] >= 15 ? 'MÁX' : `-${getPointCost(attributes[attr] + 1) - getPointCost(attributes[attr])}`}</div></div>); })}</div></div>)}
            
            {/* PASSO 5: RESUMO */}
            {step === 5 && (<div className="p-6 h-full flex flex-col justify-center items-center text-center animate-fade-in"><PixelIcon name="coroa" size={48} className="mb-4 animate-pulse"/><h3 className="text-2xl font-rpg text-white mb-2">Destino Selado</h3><p className="text-gray-400 text-sm mb-8">Confirme os dados da ficha ao lado para iniciar.</p><PixelButton variant="dourado" onClick={handleFinish} disabled={loading} className="w-full py-5 text-lg flex items-center justify-center gap-3 hover:scale-105 mb-4">{loading ? "Iniciando..." : <>JOGAR AGORA <PixelIcon name="seta" /></>}</PixelButton><div className="flex flex-col items-center gap-3">
                    <button onClick={() => setVariacao(v => v + 1)} className="text-gray-300 hover:text-rpg-gold flex items-center gap-2 text-sm font-rpg border-2 border-gray-700 hover:border-rpg-gold px-3 py-2 transition-colors"><PixelIcon name="dado" size={14}/> Gerar outro retrato</button>
                    <button onClick={() => setStep(4)} className="text-gray-400 hover:text-rpg-gold flex items-center gap-2 text-sm underline decoration-gray-700 hover:decoration-rpg-gold"><PixelIcon name="seta" size={14} className="rotate-180"/> Editar Atributos</button>
                  </div></div>)}
        </div>
      </div>

      <div className="flex-1 h-full relative bg-gray-900 overflow-hidden flex items-center justify-center p-8 bg-[url('/assets/backgrounds/textura-ruido.png')] bg-repeat">
         {/* `h-[600px]` fixo cortava o conteudo: a revisao acrescentou arma,
             atributo principal e proficiencias ao painel da classe, e o bloco
             "Sabe usar" ficava clipado sem aviso. Altura passa a acompanhar a
             janela, com piso pra nao espremer em tela baixa. */}
         <PanelFrame borderWidth={16} className="relative z-30 w-full max-w-5xl h-[min(760px,90vh)] min-h-[460px] flex bg-[#121212] shadow-2xl overflow-hidden animate-scale-in">
             <div className="w-[45%] h-full relative border-r border-rpg-gold/30 bg-black">
                 {/* Revisão da Etapa 14 (ADR-0025): os retratos de raça/classe
                     deixaram de ser sprites de 16×16 e passaram a ser arte de
                     48×48 enquadrada como busto. Agora todos os passos usam
                     `object-cover`, preenchendo o painel — o `object-contain`
                     com respiro que existia aqui era muleta pro sprite
                     minúsculo de antes e só deixava a imagem menor. */}
                 {/* Tanto o retrato de raça/classe (48×48) quanto o gerado no
                     passo 5 (500×750) são bustos feitos pra preencher o
                     painel, então os dois usam `cover`. Só o placeholder,
                     que é um ícone, usa `contain`. */}
                 {step === 5 && finalImageUrl ? (
                     // Retrato gerado: passa pelo pixelizador pra não destoar
                     // do resto (ver RetratoPixelado.tsx).
                     <RetratoPixelado
                         src={finalImageUrl}
                         alt={`Retrato de ${name}`}
                         className="w-full h-full object-cover object-top"
                     />
                 ) : (
                     <img
                         src={activeImage}
                         className={
                           semSelecao
                             ? "w-full h-full object-contain p-24 opacity-70"
                             : "w-full h-full object-cover object-top"
                         }
                         alt=""
                         onError={(e) => (e.currentTarget.style.display = 'none')}
                     />
                 )}
                 <div className="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-6 pt-12">
                     <h2 className="text-3xl font-rpg text-white text-center drop-shadow-md">{activeTitle}</h2>
                     {step === 5 && <p className="text-rpg-gold text-center font-bold text-xs uppercase tracking-widest opacity-80">{selectedRace} • {selectedClass}</p>}
                 </div>
             </div>
             <div className="w-[55%] p-8 flex flex-col relative overflow-y-auto custom-scrollbar">
                 <div className="absolute top-4 right-4 opacity-10 pointer-events-none"><PixelIcon name="coroa" size={120}/></div>
                 <h3 className="text-rpg-gold font-rpg text-2xl border-b-2 border-gray-700 pb-3 mb-6 flex items-center gap-2">
                    {step === 5 ? <PixelIcon name="pergaminho" size={24}/> : step === 1 ? <PixelIcon name="coroa" size={24}/> : step === 2 ? <PixelIcon name="espada" size={24}/> : <PixelIcon name="estrela" size={24}/>}
                    {step === 5 ? "Ficha Técnica" : step === 1 ? "Detalhes da Raça" : step === 2 ? "Detalhes da Classe" : "Planejamento"}
                 </h3>
                 
                 {/* Conteúdo Dinâmico da Direita */}
                 {step === 5 ? (
                     <>
                        <div className="flex justify-around mb-8 bg-black/40 p-4 border-2 border-gray-700">
                             <div className="text-center"><div className="text-2xl font-bold text-blue-400 font-rpg">{10 + getModifierValue(getFinalAttribute('destreza'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Defesa</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-red-500 font-rpg">{getInitialHP()}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Vida</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-green-500 font-rpg">{10 + getModifierValue(getFinalAttribute('sabedoria'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Percepção</span></div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                             {Object.keys(attributes).map(attr => (
                                 <div key={attr} className="bg-gray-800/60 border-2 border-gray-700 p-2 text-center relative"><span className="block text-[10px] text-gray-300 uppercase font-bold mb-1">{formatAttribute(attr)}</span><span className="block text-xl text-white font-rpg">{getFinalAttribute(attr)}</span><div className="absolute -top-2 -right-2 w-6 h-6 bg-gray-700 flex items-center justify-center text-[10px] text-blue-200 font-bold border-2 border-gray-500">{formatModifier(getModifierValue(getFinalAttribute(attr)))}</div></div>
                             ))}
                        </div>
                        <div className="mt-6 bg-black/40 border-2 border-gray-700 p-3 text-sm text-gray-200 space-y-1">
                            <p><strong className="text-rpg-gold font-rpg">Origem:</strong> {background || <span className="text-gray-400 italic">não informada</span>}</p>
                            <p><strong className="text-rpg-gold font-rpg">Missão:</strong> {goal || <span className="text-gray-400 italic">não informada</span>}</p>
                        </div>
                     </>
                 ) : currentDetails ? (
                     <div className="space-y-5 animate-fade-in">
                        {currentDetails.quote && (
                          <p className="text-lg text-rpg-gold italic text-center px-4 font-hand">"{currentDetails.quote}"</p>
                        )}
                        <p className="text-gray-200 leading-relaxed bg-black/40 p-4 border-2 border-gray-700">{currentDetails.descricao}</p>

                        {step === 1 && currentDetails.bonus_atributos && (
                          <Bloco titulo="Bônus de Atributo">
                            <div className="flex gap-2 flex-wrap">
                              {Object.entries(currentDetails.bonus_atributos).filter(([k]) => k !== 'livre_escolha').map(([k,v]) => (
                                <Etiqueta key={k} cor="azul">+{v as number} {formatAttribute(k)}</Etiqueta>
                              ))}
                              {currentDetails.bonus_atributos.livre_escolha > 0 && (
                                <Etiqueta cor="roxo">+{currentDetails.bonus_atributos.livre_escolha} à escolha</Etiqueta>
                              )}
                            </div>
                          </Bloco>
                        )}

                        {/* Etapa 14 (revisão) — a tela de classe mostrava só a
                            descrição e o dado de vida, ficando visivelmente
                            mais pobre que a de raça. Os dados abaixo já
                            existiam em Backend/data/classes.json desde sempre;
                            faltava exibi-los. */}
                        {step === 2 && (
                          <>
                            <div className="grid grid-cols-2 gap-3">
                              <Bloco titulo="Vida por nível">
                                <span className="flex items-center gap-2 text-xl font-rpg text-red-300">
                                  <PixelIcon name="coracao" size={18}/> d{currentDetails.dado_vida}
                                </span>
                              </Bloco>
                              <Bloco titulo="Atributo principal">
                                <span className="flex items-center gap-2 text-xl font-rpg text-blue-300">
                                  <PixelIcon name="estrela" size={18}/> {(currentDetails.atributo_primario || []).join(' e ')}
                                </span>
                              </Bloco>
                            </div>

                            {currentDetails.equipamento_inicial?.length > 0 && (
                              <Bloco titulo="Começa com">
                                <div className="flex gap-2 flex-wrap">
                                  {currentDetails.equipamento_inicial.map((item: string) => (
                                    <Etiqueta key={item} cor="ouro"><PixelIcon name="espada" size={11}/> {item}</Etiqueta>
                                  ))}
                                </div>
                              </Bloco>
                            )}

                            {currentDetails.proficiencias?.length > 0 && (
                              <Bloco titulo="Sabe usar">
                                <div className="flex gap-2 flex-wrap">
                                  {currentDetails.proficiencias.map((p: string) => (
                                    <Etiqueta key={p} cor="neutro">{p}</Etiqueta>
                                  ))}
                                </div>
                              </Bloco>
                            )}
                          </>
                        )}
                     </div>
                 ) : step === 3 ? (
                     <div className="flex flex-col items-center justify-center h-full text-gray-600 text-center px-8">
                         <PixelIcon name="coroa" size={64} className="mb-4 opacity-60"/>
                         <h3 className="text-xl font-rpg text-white mb-2">Quem é você?</h3>
                         <p className="text-sm">Defina sua identidade. O nome e o passado do seu herói moldarão como o mundo reage a ele.</p>
                     </div>
                 ) : (<div className="flex flex-col items-center justify-center h-full text-gray-400"><PixelIcon name="estrela" size={48} className="mb-4 opacity-50"/><span className="text-xl font-rpg">Selecione uma opção...</span></div>)}
                 
                 {/* BOTÃO PRÓXIMO (O QUE SUMIU) */}
                 {canProceed && step < 5 && (<div className="mt-auto pt-6 flex justify-end"><PixelButton variant="dourado" onClick={() => setStep(s => s + 1)} className="py-3 px-6 flex items-center gap-2 hover:scale-105">PRÓXIMO <PixelIcon name="seta" size={20} /></PixelButton></div>)}
             </div>
         </PanelFrame>
      </div>
    </div>
  );
}

// Etapa 14 (revisão) — bloco rotulado e etiqueta, os dois padrões que se
// repetiam à mão pelo painel de detalhes (cada um com um `rounded`/borda um
// pouco diferente). Centralizar aqui é o que garante que os cantos fiquem
// retos e as cores consistentes em todos os usos, em vez de depender de
// lembrar em cada call site.
function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="bg-black/40 border-2 border-gray-700 p-3">
      <span className="text-xs text-rpg-gold uppercase tracking-widest block mb-2 font-rpg">{titulo}</span>
      {children}
    </div>
  );
}

const CORES_ETIQUETA = {
  azul: 'bg-blue-950 text-blue-200 border-blue-700',
  roxo: 'bg-purple-950 text-purple-200 border-purple-700',
  ouro: 'bg-rpg-gold/15 text-rpg-gold border-rpg-gold/60',
  neutro: 'bg-gray-800 text-gray-200 border-gray-600',
} as const;

function Etiqueta({ cor, children }: { cor: keyof typeof CORES_ETIQUETA; children: React.ReactNode }) {
  return (
    <span className={`text-xs px-2 py-1 border-2 uppercase flex items-center gap-1 font-rpg ${CORES_ETIQUETA[cor]}`}>
      {children}
    </span>
  );
}

// Etapa 14 (revisão) — a lista da esquerda destoava do painel da direita:
// borda de 1px, texto `text-gray-400` sobre fundo quase preto (baixo
// contraste) e o item selecionado se distinguindo só por um brilho sutil.
// Agora: borda grossa igual ao resto, texto legível, e o selecionado marcado
// por cor de fundo E por um cursor "▶" à esquerda, como menu de console —
// não depender só de cor também ajuda quem não distingue bem os tons.
function OptionButton({ label, active, onClick, image }: any) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`w-full text-left flex items-center gap-3 p-2 border-2 transition-colors group focus-visible:outline-none focus-visible:border-rpg-gold ${
        active
          ? 'bg-rpg-gold/20 border-rpg-gold'
          : 'bg-black/50 border-gray-700 hover:border-gray-500 hover:bg-black/70'
      }`}
    >
      {/* Cursor decorativo: `aria-hidden` porque `aria-pressed` no botão já
          diz o que está selecionado — sem isso o leitor de tela lê um "▶"
          solto antes de cada opção da lista. */}
      <span aria-hidden className={`font-rpg text-rpg-gold w-3 shrink-0 ${active ? 'opacity-100' : 'opacity-0'}`}>▶</span>
      <div className="pixel-frame w-12 h-12 bg-black shrink-0 overflow-hidden">
        {/* Sem `onError` apontando pra placeholder externo: offline (ou com o
            domínio fora do ar) o fallback falha junto e sobra o ícone de
            imagem quebrada. Escondendo, sobra o quadro preto da moldura. */}
        <img
          src={image}
          alt=""
          className="w-full h-full object-contain"
          onError={(e) => (e.currentTarget.style.display = 'none')}
        />
      </div>
      <span className={`font-rpg text-base ${active ? 'text-rpg-gold' : 'text-gray-200'}`}>{label}</span>
    </button>
  );
}