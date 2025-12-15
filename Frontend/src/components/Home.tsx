import { useNavigate } from 'react-router-dom';
import { Sword, Scroll, Crown } from 'lucide-react';

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center relative overflow-hidden">
      
      {/* Background com efeito Parallax simples */}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent z-10" />
        <img 
          src="https://image.pollinations.ai/prompt/dark%20fantasy%20rpg%20table%20dnd%20mood%20lighting%20candle?width=1920&height=1080&nologo=true" 
          alt="Mesa de RPG" 
          className="w-full h-full object-cover opacity-60"
        />
      </div>

      {/* Conteúdo */}
      <div className="z-20 text-center space-y-8 animate-fade-in p-6 max-w-4xl">
        <div className="mb-4 flex justify-center">
            <Crown size={80} className="text-rpg-gold animate-pulse-slow drop-shadow-[0_0_15px_rgba(197,160,89,0.5)]" />
        </div>
        
        <h1 className="text-7xl font-rpg text-white drop-shadow-lg tracking-wider">
          MESTRE<span className="text-red-600">.IA</span>
        </h1>
        
        <p className="text-xl text-gray-300 font-hand max-w-2xl mx-auto leading-relaxed">
          "Em um mundo onde o destino é escrito por algoritmos e dados, apenas os mais corajosos ousam desafiar a aleatoriedade. Crie seu herói, enfrente a escuridão e escreva sua lenda."
        </p>

        <div className="flex flex-col md:flex-row gap-6 justify-center mt-12">
          <button 
            onClick={() => navigate('/criar')}
            className="group relative px-8 py-4 bg-red-800 hover:bg-red-700 text-white font-bold rounded border-2 border-red-600 shadow-lg hover:shadow-red-900/50 transition-all transform hover:-translate-y-1"
          >
            <div className="flex items-center gap-3 text-xl font-rpg">
              <Sword size={24} className="group-hover:rotate-45 transition-transform"/>
              NOVA AVENTURA
            </div>
          </button>

          <button 
            onClick={() => alert("Em breve: Continuar campanha salva!")}
            className="group px-8 py-4 bg-gray-900 hover:bg-gray-800 text-gray-400 hover:text-white font-bold rounded border-2 border-gray-700 transition-all"
          >
            <div className="flex items-center gap-3 text-xl font-rpg">
              <Scroll size={24} />
              CARREGAR JOGO
            </div>
          </button>
        </div>
      </div>

      <footer className="absolute bottom-6 text-gray-600 text-sm font-sans">
        v1.0 • Desenvolvido com React & Python
      </footer>
    </div>
  );
}