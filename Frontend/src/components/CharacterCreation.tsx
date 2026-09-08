import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { getLocalImage, getRetrato } from '../lib/utils';
import { prefereMovimentoReduzido } from '../lib/acessibilidade';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import PanelFrame from './PanelFrame';
import BotaoConfig from './BotaoConfig';
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

// Remaster da criação — Passo "Mundo": as opções espelham exatamente os
// `Literal` de `Backend/app/domain/character.py` (temperamento_mestre,
// dificuldade) e o texto de cada uma vem de `narrator.TEMPERAMENTO_INSTRUCAO`
// reescrito em segunda pessoa, pro jogador saber o que está escolhendo.
const TEMPERAMENTOS = [
  { valor: 'Justo', titulo: 'Justo', descricao: 'O mundo reage às suas escolhas com equilíbrio — nem punitivo, nem condescendente.' },
  { valor: 'Implacável', titulo: 'Implacável', descricao: 'Erros custam caro e a morte é real. Duro, mas sempre justo às regras.' },
  { valor: 'Épico', titulo: 'Épico', descricao: 'Tom grandioso e dramático — cada ação sua ganha peso de lenda.' },
] as const;

const DIFICULDADES = [
  { valor: 'Normal', titulo: 'Normal', descricao: 'O desafio padrão da campanha.' },
  { valor: 'História', titulo: 'História', descricao: 'Testes mais acessíveis para explorar suas escolhas e a história.' },
  { valor: 'Difícil', titulo: 'Difícil', descricao: 'Testes mais exigentes (CD mais alta) — para quem quer sentir o risco de verdade.' },
] as const;

// Remaster da criação — Fase 3: a Matriz Clássica é fixa e pública (o
// servidor revalida de qualquer forma, ver Backend/app/services/
// rules_engine.py:MATRIZ_CLASSICA), então o front pode exibi-la sem
// round-trip nenhum. "Rolar Dados" sempre pede ao servidor (POST
// /gerar_atributos) — o valor rolado nunca nasce no cliente.
const MATRIZ_CLASSICA = [15, 14, 13, 12, 10, 8];
const ATRIBUTOS_ORDEM = ['forca', 'destreza', 'constituicao', 'inteligencia', 'sabedoria', 'carisma'] as const;

// O modelo de imagem foi treinado majoritariamente em inglês — mandar o
// nome da raça/classe em português ("Draconato", "Meio-Orc") não significa
// nada pra ele, e é a causa mais provável da arte não bater com o
// personagem. Estes descritores existem só para o prompt de imagem; o
// resto do app continua em português (ver Backend/data/races.json).
const RACE_VISUAL_EN: Record<string, string> = {
  "Anão": "dwarf, short and stocky build",
  "Elfo": "elf, tall and slender, pointed ears, elegant features",
  "Halfling": "halfling, very short stature, curly hair, cheerful round face",
  "Humano": "human",
  "Draconato": "dragonborn, reptilian scaled skin, dragon-like head, no hair",
  "Gnomo": "gnome, tiny stature, large expressive eyes, pointed ears",
  "Meio-Elfo": "half-elf, slightly pointed ears, human build with elven grace",
  "Meio-Orc": "half-orc, greenish-gray skin, prominent lower tusks, sturdy build",
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

  // Passo "Mundo" (remaster da criação, Fase 1)
  const [temperamentoMestre, setTemperamentoMestre] = useState<string>("Justo");
  const [dificuldade, setDificuldade] = useState<string>("Normal");

  // Oráculo (remaster da criação, Fase 2) — origem guiada por IA, alternativa
  // à escolha manual de raça/classe no mesmo passo.
  const [oraculoAtivo, setOraculoAtivo] = useState(false);
  const [oraculoConceito, setOraculoConceito] = useState("");
  const [oraculoCarregando, setOraculoCarregando] = useState(false);
  const [oraculoErro, setOraculoErro] = useState("");
  const [oraculoPerguntas, setOraculoPerguntas] = useState<string[]>([]);
  const [oraculoRespostas, setOraculoRespostas] = useState<string[]>(["", ""]);
  const [oraculoPistaVisual, setOraculoPistaVisual] = useState("");
  const [oraculoConfirmado, setOraculoConfirmado] = useState(false);
  const [resumoHistoria, setResumoHistoria] = useState("");

  // Atributos (remaster, Fase 3) — sem point-buy: ou a Matriz Clássica fixa,
  // ou seis valores rolados pelo servidor (nunca no cliente, ver ADR-0002).
  // `alocacao` mapeia atributo -> um dos valores de `atributosDisponiveis`
  // (ou null enquanto não escolhido); a validação de unicidade acontece em
  // `opcoesParaAtributo` (só oferece valores ainda não consumidos por outro
  // atributo) e o servidor confere o multiset de novo no fim.
  const [modoAtributos, setModoAtributos] = useState<'classica' | 'dados'>('classica');
  const [atributosDisponiveis, setAtributosDisponiveis] = useState<number[]>(MATRIZ_CLASSICA);
  const [atributosToken, setAtributosToken] = useState<string | null>(null);
  const [atributosRolando, setAtributosRolando] = useState(false);
  const [alocacao, setAlocacao] = useState<Record<string, number | null>>(
    { forca: null, destreza: null, constituicao: null, inteligencia: null, sabedoria: null, carisma: null }
  );
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
    // Passo 5 E 6 (Atributos, Resumo — steps deslocaram +1 com o novo Passo
    // 1 "Mundo"): o retrato nasce ao fechar os atributos (5), mas o botão
    // "gerar outro" vive na ficha final (6). Com o guard só em `step === 5`
    // o clique mudava `variacao` e nada regerava — a condição precisa cobrir
    // a tela onde o botão está.
    if ((step === 5 || step === 6) && name && gender && selectedRace && selectedClass) {
        const genderEn = gender === "Feminino" ? "woman" : gender === "Masculino" ? "man" : "person";
        const raceVisual = RACE_VISUAL_EN[selectedRace] || selectedRace;
        const classVisual = CLASS_VISUAL_EN[selectedClass] || selectedClass;
        // Remaster da criação (Fase 4) — quando a origem veio do Oráculo,
        // `pista_visual_en` (aparência específica do conceito do jogador,
        // ex: "blind elf with pale scarred eyes") entra no prompt pra dar
        // retratos mais únicos do que só raça+classe.
        const pista = oraculoPistaVisual ? `, ${oraculoPistaVisual}` : '';
        const prompt = `fantasy rpg character portrait of a ${genderEn}, race is ${raceVisual}, class is ${classVisual}${pista}, highly detailed face, looking at camera, dnd art style, masterpiece, sharp focus, dark fantasy background`;
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
  }, [step, name, gender, selectedRace, selectedClass, variacao, oraculoPistaVisual]);

  // Lógica de Atributos (remaster, Fase 3 — sem point-buy)
  // Devolve os valores de `atributosDisponiveis` ainda livres para `attr`:
  // o pool inteiro menos o que já foi consumido por OUTROS atributos (o
  // valor já escolhido pelo próprio `attr` continua na lista, pra dar pra
  // manter a escolha atual no <select>). Trata duplicatas (a rolagem pode
  // dar dois valores iguais) por contagem, não por Set, senão dois "13"
  // rolados só apareceriam disponíveis uma vez no total.
  const opcoesParaAtributo = (attr: string): number[] => {
      const pool = [...atributosDisponiveis];
      for (const outro of ATRIBUTOS_ORDEM) {
          if (outro === attr) continue;
          const usado = alocacao[outro];
          if (usado === null || usado === undefined) continue;
          const idx = pool.indexOf(usado);
          if (idx !== -1) pool.splice(idx, 1);
      }
      return [...new Set(pool)].sort((a, b) => b - a);
  };

  // Visão geral do pool inteiro pro topo do Passo 5 ("Valores Disponíveis") —
  // um chip por posição do pool (não deduplicado), marcando como "usado"
  // tantas ocorrências de cada valor quantas já estão em `alocacao`. Mesmo
  // cuidado com duplicatas de `opcoesParaAtributo`: dois "14" rolados viram
  // dois chips "14" independentes.
  const chipsDisponiveis = () => {
      const usados: Record<number, number> = {};
      for (const v of Object.values(alocacao)) {
          if (v === null || v === undefined) continue;
          usados[v] = (usados[v] ?? 0) + 1;
      }
      const contador: Record<number, number> = {};
      return [...atributosDisponiveis].sort((a, b) => b - a).map((valor, idx) => {
          contador[valor] = (contador[valor] ?? 0) + 1;
          return { valor, usado: contador[valor] <= (usados[valor] ?? 0), key: `${valor}-${idx}` };
      });
  };

  const handleAlocacaoChange = (attr: string, valor: string) => {
      setAlocacao(prev => ({ ...prev, [attr]: valor === '' ? null : Number(valor) }));
  };

  const escolherMatrizClassica = () => {
      setModoAtributos('classica');
      setAtributosDisponiveis(MATRIZ_CLASSICA);
      setAtributosToken(null);
      setAlocacao({ forca: null, destreza: null, constituicao: null, inteligencia: null, sabedoria: null, carisma: null });
  };

  const rolarAtributos = async () => {
      setAtributosRolando(true);
      try {
          const res = await api.post('/gerar_atributos', { modo: 'dados' });
          const aplicar = () => {
              setModoAtributos('dados');
              setAtributosDisponiveis(res.data.valores);
              setAtributosToken(res.data.token);
              setAlocacao({ forca: null, destreza: null, constituicao: null, inteligencia: null, sabedoria: null, carisma: null });
              setAtributosRolando(false);
          };
          // "Fator cassino" (RollCard.tsx) — mesma duração de espera, pulada
          // inteira quando o sistema pede menos movimento.
          if (prefereMovimentoReduzido()) aplicar();
          else setTimeout(aplicar, 1000);
      } catch {
          setAtributosRolando(false);
          alert("Não deu para rolar os atributos. Tente de novo.");
      }
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
      return (alocacao[attr] ?? 0) + (raceData?.bonus_atributos?.[attr] || 0) + (freePointsAllocation[attr] || 0);
  };

  const getModifierValue = (score: number) => Math.floor((score - 10) / 2);
  const formatModifier = (mod: number) => mod >= 0 ? `+${mod}` : `${mod}`;
  const getInitialHP = () => (classData?.dado_vida || 0) + getModifierValue(getFinalAttribute('constituicao'));

  const maxFreePoints = raceData?.bonus_atributos?.['livre_escolha'] || 0;
  const usedFreePoints = Object.values(freePointsAllocation).reduce((a, b) => a + b, 0);
  const atributosCompletos = ATRIBUTOS_ORDEM.every(attr => alocacao[attr] !== null);

  // --- ORÁCULO (remaster, Fase 2) ---
  const consultarOraculo = async () => {
      if (!oraculoConceito.trim()) return;
      setOraculoCarregando(true);
      setOraculoErro("");
      try {
          const res = await api.post('/oraculo_origem', { conceito: oraculoConceito });
          setSelectedRace(res.data.raca);
          setSelectedClass(res.data.classe);
          setOraculoPerguntas(res.data.perguntas);
          setOraculoRespostas(["", ""]);
          setOraculoPistaVisual(res.data.pista_visual_en || "");
          setOraculoConfirmado(false);
      } catch {
          setOraculoErro("O Oráculo não respondeu. Tente de novo, ou escolha manualmente.");
      } finally {
          setOraculoCarregando(false);
      }
  };

  const confirmarOraculoHistoria = async () => {
      setOraculoCarregando(true);
      setOraculoErro("");
      try {
          const res = await api.post('/oraculo_origem/historia', {
              conceito: oraculoConceito, raca: selectedRace, classe: selectedClass,
              perguntas: oraculoPerguntas, respostas: oraculoRespostas,
          });
          setBackground(res.data.background);
          setHistory(res.data.historia_texto);
          setResumoHistoria(res.data.resumo_historia);
          setGoal(res.data.objetivo);
          setAlignment(res.data.alinhamento);
          setOraculoConfirmado(true);
      } catch {
          setOraculoErro("O Oráculo não conseguiu escrever a história agora. Tente de novo.");
      } finally {
          setOraculoCarregando(false);
      }
  };

  // --- VALIDAÇÃO DO BOTÃO "PRÓXIMO" ---
  // Passos deslocaram +1 com o novo Passo 1 "Mundo" (era 1..5, agora 1..6:
  // Mundo, Raça/Origem, Classe, Identidade, Atributos, Resumo).
  const canProceed =
    (step === 1) ||
    (step === 2 && !!selectedRace && (!oraculoAtivo || oraculoConfirmado)) ||
    (step === 3 && !!selectedClass) ||
    // AGORA O PASSO 4 EXIGE NOME, GÊNERO E OS NOVOS CAMPOS
    (step === 4 && !!name && !!gender && !!background && !!goal) ||
    (step === 5 && atributosCompletos && usedFreePoints === maxFreePoints);

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

      // Remaster da criação — os seis valores finais vêm de `alocacao`
      // (Matriz Clássica ou rolagem), não mais de um point-buy incremental.
      // `token_atributos` só existe (e só é exigido pelo servidor) no modo
      // "dados" — é a prova de que os valores vieram de POST /gerar_atributos.
      const atributosFinais = Object.fromEntries(
        ATRIBUTOS_ORDEM.map(attr => [attr, alocacao[attr] as number])
      );

      const res = await api.post("/create_character", {
        nome: name, raca: selectedRace, classe: selectedClass,
        alinhamento: alignment, background: background, objetivo: goal,
        historia_texto: history,
        resumo_historia: resumoHistoria,
        temperamento_mestre: temperamentoMestre,
        dificuldade: dificuldade,
        imagem: imageToSend,
        atributos: atributosFinais,
        atributos_livre: atributosLivreEscolhidos,
        modo_atributos: modoAtributos,
        token_atributos: atributosToken,
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
  // Passos deslocaram +1 com o novo Passo 1 "Mundo": 1=Mundo, 2=Raça/Origem,
  // 3=Classe, 4=Identidade, 5=Atributos, 6=Resumo.
  const activeImage = step === 6 && finalImageUrl ? finalImageUrl : step === 3 && selectedClass ? getRetrato('classes', selectedClass) : step === 2 && selectedRace ? getRetrato('races', selectedRace) : "/assets/placeholder-selecao.png";
  const semSelecao = !(step === 6 && finalImageUrl) && !(step === 3 && selectedClass) && !(step === 2 && selectedRace);
  const activeTitle = step === 6 ? name : step === 1 ? "O Mundo" : step === 2 ? (selectedRace || "Linhagem") : step === 3 ? (selectedClass || "Vocação") : "Atributos";
  const currentDetails = step === 2 ? raceData : step === 3 ? classData : null;

  return (
    <div className="flex flex-col md:flex-row min-h-[100dvh] w-screen md:overflow-hidden bg-black text-gray-100">
      <div className="absolute top-4 left-4 z-50 flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-gray-300 hover:text-rpg-gold flex items-center gap-2 font-rpg"><PixelIcon name="seta" className="rotate-180" /> Sair</button>
        <BotaoConfig tema="aventura" />
      </div>

      <div className="w-full md:w-1/3 md:h-full flex flex-col bg-gray-900 border-b-2 md:border-b-0 md:border-r border-gray-800 z-20 shadow-2xl relative">
        <div className="p-6 border-b border-gray-800 bg-black/40 mt-10">
           <h1 className="text-xl font-pixel-title text-rpg-gold flex items-center gap-2"><PixelIcon name="coroa" size={20} /> CRIAÇÃO</h1>
           {/* Etapa 14 (C-4) — passos em blocos discretos, mesmo espírito do
               PixelBar (Etapa 11), em vez da barra fina arredondada. */}
           <div className="flex gap-1 mt-4 px-2">{[1,2,3,4,5,6].map(s => (<button key={s} disabled={s > step && s !== step + 1} onClick={() => { if (step === 6 || (s < step)) setStep(s); }} className={`h-3 flex-1 transition-colors ${step >= s ? 'bg-rpg-gold cursor-pointer' : 'bg-gray-800 cursor-not-allowed'}`}/>))}</div>
           <p className="text-xs text-gray-300 mt-1 uppercase tracking-widest text-right font-rpg">{step === 6 ? "Ficha Final" : `Passo ${step}/6`}</p>
        </div>

        <div className="flex-1 max-h-[45vh] md:max-h-none overflow-y-auto p-4 space-y-2 custom-scrollbar pb-6 md:pb-24">
            
            {/* PASSO 1: MUNDO (temperamento do mestre + dificuldade) */}
            {step === 1 && (
                <div className="p-2 space-y-6 animate-fade-in">
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-2">Temperamento do Mestre</label>
                        <div className="space-y-2">
                            {TEMPERAMENTOS.map(t => (
                                <button
                                    key={t.valor}
                                    onClick={() => setTemperamentoMestre(t.valor)}
                                    aria-pressed={temperamentoMestre === t.valor}
                                    className={`w-full text-left p-3 border-2 transition-colors ${temperamentoMestre === t.valor ? 'bg-rpg-gold/20 border-rpg-gold' : 'bg-black/50 border-gray-700 hover:border-gray-500'}`}
                                >
                                    <span className={`font-rpg block ${temperamentoMestre === t.valor ? 'text-rpg-gold' : 'text-gray-200'}`}>{t.titulo}</span>
                                    <span className="text-xs text-gray-400">{t.descricao}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-rpg-gold font-rpg block mb-2">Dificuldade</label>
                        <div className="space-y-2">
                            {DIFICULDADES.map(d => (
                                <button
                                    key={d.valor}
                                    onClick={() => setDificuldade(d.valor)}
                                    aria-pressed={dificuldade === d.valor}
                                    className={`w-full text-left p-3 border-2 transition-colors ${dificuldade === d.valor ? 'bg-rpg-gold/20 border-rpg-gold' : 'bg-black/50 border-gray-700 hover:border-gray-500'}`}
                                >
                                    <span className={`font-rpg block ${dificuldade === d.valor ? 'text-rpg-gold' : 'text-gray-200'}`}>{d.titulo}</span>
                                    <span className="text-xs text-gray-400">{d.descricao}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* PASSO 2: ORIGEM (raça/classe manual, ou Oráculo guiado por IA) */}
            {step === 2 && (
                <div className="space-y-3 animate-fade-in">
                    <div className="grid grid-cols-2 gap-2 p-2">
                        <button onClick={() => setOraculoAtivo(false)} className={`p-2 border-2 font-rpg text-sm transition-colors ${!oraculoAtivo ? 'bg-rpg-gold/20 border-rpg-gold text-rpg-gold' : 'bg-black/50 border-gray-700 text-gray-300 hover:border-gray-500'}`}>Escolha Manual</button>
                        <button onClick={() => setOraculoAtivo(true)} className={`p-2 border-2 font-rpg text-sm transition-colors flex items-center justify-center gap-1 ${oraculoAtivo ? 'bg-rpg-gold/20 border-rpg-gold text-rpg-gold' : 'bg-black/50 border-gray-700 text-gray-300 hover:border-gray-500'}`}><PixelIcon name="estrela" size={12} /> Oráculo (IA)</button>
                    </div>

                    {oraculoAtivo ? (
                        <div className="p-2 space-y-3">
                            <label className="text-rpg-gold font-rpg block mb-1 text-sm">Descreva o conceito do seu herói</label>
                            <textarea
                                className="w-full bg-black/50 border-2 border-gray-600 p-3 text-white h-20 outline-none resize-none focus:border-rpg-gold text-sm"
                                placeholder="Ex: Um elfo cego que odeia magia..."
                                value={oraculoConceito}
                                onChange={e => setOraculoConceito(e.target.value)}
                                disabled={oraculoCarregando}
                                maxLength={300}
                            />
                            {oraculoErro && <p className="text-red-400 text-xs">{oraculoErro}</p>}
                            {!selectedRace && !oraculoCarregando && (
                                <PixelButton variant="dourado" onClick={consultarOraculo} disabled={!oraculoConceito.trim()} className="w-full py-2 text-sm">Consultar o Oráculo</PixelButton>
                            )}
                            {oraculoCarregando && (
                                <div className="flex items-center justify-center gap-2 text-gray-400 text-sm py-3">
                                    <PixelIcon name="dado" size={16} className="animate-spin [animation-duration:0.6s]" /> O Oráculo está pensando...
                                </div>
                            )}
                            {!oraculoCarregando && selectedRace && selectedClass && oraculoPerguntas.length === 2 && !oraculoConfirmado && (
                                <div className="space-y-3 border-t-2 border-gray-800 pt-3">
                                    <p className="text-xs text-gray-400">
                                        O Oráculo sugere <span className="text-rpg-gold">{selectedRace}</span> / <span className="text-rpg-gold">{selectedClass}</span>. Não gostou? Troque na aba "Escolha Manual" antes de confirmar.
                                    </p>
                                    {oraculoPerguntas.map((pergunta, i) => (
                                        <div key={i}>
                                            <label className="text-gray-300 text-sm block mb-1">{pergunta}</label>
                                            <input
                                                type="text"
                                                className="w-full bg-black/50 border-2 border-gray-600 p-2 text-white text-sm outline-none focus:border-rpg-gold"
                                                value={oraculoRespostas[i]}
                                                onChange={e => setOraculoRespostas(prev => prev.map((r, idx) => idx === i ? e.target.value : r))}
                                                maxLength={500}
                                            />
                                        </div>
                                    ))}
                                    <PixelButton
                                        variant="dourado"
                                        onClick={confirmarOraculoHistoria}
                                        disabled={oraculoRespostas.some(r => !r.trim())}
                                        className="w-full py-2 text-sm"
                                    >Confirmar Origem</PixelButton>
                                </div>
                            )}
                            {oraculoConfirmado && (
                                <div className="border-t-2 border-gray-800 pt-3 text-sm text-emerald-400 flex items-center gap-2">
                                    <PixelIcon name="estrela" size={14} /> Origem escrita pelo Oráculo — veja no Passo 4.
                                </div>
                            )}
                        </div>
                    ) : (
                        races.map(r => <OptionButton key={r} label={r} active={selectedRace === r} image={getLocalImage('races', r)} onClick={() => setSelectedRace(r)} />)
                    )}
                </div>
            )}

            {/* PASSO 3: CLASSE */}
            {step === 3 && classes.map(c => <OptionButton key={c} label={c} active={selectedClass === c} image={getLocalImage('classes', c)} onClick={() => setSelectedClass(c)} />)}

            {/* PASSO 4: IDENTIDADE (CORRIGIDO) */}
            {step === 4 && (
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

            {/* PASSO 5: ATRIBUTOS (remaster — Matriz Clássica ou Rolar Dados, sem point-buy) */}
            {step === 5 && (
                <div className="p-4 space-y-4 animate-fade-in">
                    {!atributosRolando && (
                        <div>
                            <label className="text-rpg-gold font-rpg block mb-1">Valores Disponíveis</label>
                            <div className="flex flex-wrap gap-2 justify-center bg-gray-900/50 p-2 border-2 border-gray-800">
                                {chipsDisponiveis().map(c => (
                                    <div key={c.key}
                                        className={`w-10 h-10 flex items-center justify-center border-2 font-mono text-lg font-bold transition-colors ${
                                            c.usado ? 'bg-black/40 border-gray-800 text-gray-600 line-through opacity-50'
                                                     : 'bg-rpg-gold/10 border-rpg-gold text-rpg-gold'}`}>
                                        {c.valor}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                        <button onClick={escolherMatrizClassica} className={`p-2 border-2 font-rpg text-sm transition-colors ${modoAtributos === 'classica' ? 'bg-rpg-gold/20 border-rpg-gold text-rpg-gold' : 'bg-black/50 border-gray-700 text-gray-300 hover:border-gray-500'}`}>Matriz Clássica</button>
                        <button onClick={rolarAtributos} disabled={atributosRolando} className={`p-2 border-2 font-rpg text-sm transition-colors flex items-center justify-center gap-1 ${modoAtributos === 'dados' ? 'bg-rpg-gold/20 border-rpg-gold text-rpg-gold' : 'bg-black/50 border-gray-700 text-gray-300 hover:border-gray-500'}`}>
                            <PixelIcon name="dado" size={12} className={atributosRolando ? 'animate-spin [animation-duration:0.45s]' : ''} /> Rolar Dados
                        </button>
                    </div>
                    <p className="text-[10px] text-gray-500">
                        {modoAtributos === 'classica'
                            ? 'Valores fixos [15, 14, 13, 12, 10, 8] — aloque livremente entre os atributos.'
                            : 'Seis valores rolados (4d6, descarta o menor) — pode rolar de novo quantas vezes quiser.'}
                    </p>
                    {maxFreePoints > 0 && (<div className={`p-3 border-2 text-center ${usedFreePoints === maxFreePoints ? 'bg-green-900/20 border-green-700' : 'bg-rpg-gold/10 border-rpg-gold'}`}><span className="text-sm font-bold text-gray-200 block mb-1 flex items-center justify-center gap-1"><PixelIcon name="estrela" size={12}/> Bônus Racial Extra</span><span className={`text-xl font-rpg ${usedFreePoints === maxFreePoints ? 'text-green-400' : 'text-rpg-gold'}`}>{usedFreePoints}/{maxFreePoints}</span></div>)}
                    <div className="space-y-2">
                        {atributosRolando ? (
                            <div className="flex items-center justify-center gap-2 text-gray-400 text-sm py-6">
                                <PixelIcon name="dado" size={22} className="animate-spin [animation-duration:0.45s]" /> Rolando...
                            </div>
                        ) : ATRIBUTOS_ORDEM.map(attr => {
                            const fixedBonus = raceData?.bonus_atributos?.[attr] || 0;
                            const isFreeSelected = freePointsAllocation[attr] === 1;
                            const isFreeAvailable = maxFreePoints > 0 && fixedBonus === 0;
                            const opcoes = opcoesParaAtributo(attr);
                            return (
                                <div key={attr} className="flex items-center justify-between bg-gray-900/50 p-2 border-2 border-gray-800 hover:border-gray-600">
                                    <div className="w-24">
                                        <span className="font-bold text-sm text-gray-300 block">{formatAttribute(attr)}</span>
                                        {fixedBonus > 0 && <span className="text-[10px] text-blue-400 font-bold">+{fixedBonus} Raça</span>}
                                        {isFreeAvailable && (<button onClick={() => handleFreeAllocation(attr)} disabled={!isFreeSelected && usedFreePoints >= maxFreePoints} className={`text-[10px] px-1 border mt-1 transition-colors ${isFreeSelected ? 'bg-green-600 text-white border-green-500' : 'bg-black text-gray-500 border-gray-700 hover:border-gray-500'}`}>{isFreeSelected ? '+1 Extra' : '+ Adicionar'}</button>)}
                                    </div>
                                    <select
                                        className="bg-black border-2 border-gray-700 text-white text-lg font-mono px-3 py-1 outline-none focus:border-rpg-gold"
                                        value={alocacao[attr] ?? ''}
                                        onChange={e => handleAlocacaoChange(attr, e.target.value)}
                                    >
                                        <option value="">—</option>
                                        {opcoes.map(v => <option key={v} value={v}>{v}</option>)}
                                    </select>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* PASSO 6: RESUMO */}
            {step === 6 && (<div className="p-6 h-full flex flex-col justify-center items-center text-center animate-fade-in"><PixelIcon name="coroa" size={48} className="mb-4 animate-pulse"/><h3 className="text-2xl font-rpg text-white mb-2">Destino Selado</h3><p className="text-gray-400 text-sm mb-8">Confirme os dados da ficha ao lado para iniciar.</p><PixelButton variant="dourado" onClick={handleFinish} disabled={loading} className="w-full py-5 text-lg flex items-center justify-center gap-3 hover:scale-105 mb-4">{loading ? "Iniciando..." : <>JOGAR AGORA <PixelIcon name="seta" /></>}</PixelButton><div className="flex flex-col items-center gap-3">
                    <div className="flex flex-col items-center gap-1">
                        <button onClick={() => setVariacao(v => v + 1)} className="text-gray-300 hover:text-rpg-gold flex items-center gap-2 text-sm font-rpg border-2 border-gray-700 hover:border-rpg-gold px-3 py-2 transition-colors"><PixelIcon name="dado" size={14}/> Gerar outro retrato</button>
                        <span className="text-[10px] text-gray-500">Pode levar alguns segundos para carregar</span>
                    </div>
                    <button onClick={() => setStep(5)} className="text-gray-400 hover:text-rpg-gold flex items-center gap-2 text-sm underline decoration-gray-700 hover:decoration-rpg-gold"><PixelIcon name="seta" size={14} className="rotate-180"/> Editar Atributos</button>
                  </div></div>)}
        </div>
      </div>

      <div className="flex-1 md:h-full relative bg-gray-900 overflow-hidden flex items-center justify-center p-3 md:p-8 bg-[url('/assets/backgrounds/textura-ruido.png')] bg-repeat">
         {/* `h-[600px]` fixo cortava o conteudo: a revisao acrescentou arma,
             atributo principal e proficiencias ao painel da classe, e o bloco
             "Sabe usar" ficava clipado sem aviso. Altura passa a acompanhar a
             janela, com piso pra nao espremer em tela baixa. */}
         <PanelFrame borderWidth={16} className="relative z-30 w-full max-w-5xl md:h-[min(760px,90vh)] md:min-h-[460px] flex flex-col md:flex-row bg-[#121212] shadow-2xl overflow-hidden animate-scale-in">
             <div className="w-full h-52 md:h-full md:w-[45%] relative border-b md:border-b-0 md:border-r border-rpg-gold/30 bg-black shrink-0">
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
                 {step === 6 && finalImageUrl ? (
                     // Retrato gerado: passa pelo pixelizador pra não destoar
                     // do resto (ver RetratoPixelado.tsx).
                     <RetratoPixelado
                         src={finalImageUrl}
                         alt={`Retrato de ${name}`}
                         grade={120}
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
                     {step === 6 && <p className="text-rpg-gold text-center font-bold text-xs uppercase tracking-widest opacity-80">{selectedRace} • {selectedClass}</p>}
                 </div>
             </div>
             <div className="w-full md:w-[55%] p-4 md:p-8 flex flex-col relative overflow-y-auto custom-scrollbar">
                 <div className="absolute top-4 right-4 opacity-10 pointer-events-none"><PixelIcon name="coroa" size={120}/></div>
                 <h3 className="text-rpg-gold font-rpg text-2xl border-b-2 border-gray-700 pb-3 mb-6 flex items-center gap-2">
                    {step === 6 ? <PixelIcon name="pergaminho" size={24}/> : step === 2 ? <PixelIcon name="coroa" size={24}/> : step === 3 ? <PixelIcon name="espada" size={24}/> : <PixelIcon name="estrela" size={24}/>}
                    {step === 6 ? "Ficha Técnica" : step === 2 ? "Detalhes da Raça" : step === 3 ? "Detalhes da Classe" : "Planejamento"}
                 </h3>

                 {/* Conteúdo Dinâmico da Direita */}
                 {step === 6 ? (
                     <>
                        <div className="flex justify-around mb-8 bg-black/40 p-4 border-2 border-gray-700">
                             <div className="text-center"><div className="text-2xl font-bold text-blue-400 font-rpg">{10 + getModifierValue(getFinalAttribute('destreza'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Defesa</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-red-500 font-rpg">{getInitialHP()}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Vida</span></div>
                             <div className="w-px bg-gray-700 mx-2"></div>
                             <div className="text-center"><div className="text-2xl font-bold text-green-500 font-rpg">{10 + getModifierValue(getFinalAttribute('sabedoria'))}</div><span className="text-[10px] text-gray-500 uppercase font-bold">Percepção</span></div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                             {ATRIBUTOS_ORDEM.map(attr => (
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

                        {step === 2 && currentDetails.bonus_atributos && (
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
                        {step === 3 && (
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
                 ) : step === 4 ? (
                     <div className="flex flex-col items-center justify-center h-full text-gray-600 text-center px-8">
                         <PixelIcon name="coroa" size={64} className="mb-4 opacity-60"/>
                         <h3 className="text-xl font-rpg text-white mb-2">Quem é você?</h3>
                         <p className="text-sm">Defina sua identidade. O nome e o passado do seu herói moldarão como o mundo reage a ele.</p>
                     </div>
                 ) : (<div className="flex flex-col items-center justify-center h-full text-gray-400"><PixelIcon name="estrela" size={48} className="mb-4 opacity-50"/><span className="text-xl font-rpg">Selecione uma opção...</span></div>)}

                 {/* BOTÃO PRÓXIMO (O QUE SUMIU) */}
                 {canProceed && step < 6 && (<div className="mt-auto pt-6 flex justify-end"><PixelButton variant="dourado" onClick={() => setStep(s => s + 1)} className="py-3 px-6 flex items-center gap-2 hover:scale-105">PRÓXIMO <PixelIcon name="seta" size={20} /></PixelButton></div>)}
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
