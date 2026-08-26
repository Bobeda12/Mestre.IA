import { useState } from 'react';
import { api } from '../lib/api';
import { useChaveGemini } from '../lib/config';

// Extraído de MenuConfiguracao.tsx pra ser reaproveitado também no banner de
// recomendação da Home (BannerChaveGemini.tsx). Só a parte mecânica do
// formulário (validar, salvar, remover) — o texto de contexto ao redor fica
// com quem usa este componente, porque o tom muda (neutro no menu de
// Opções, mais "venda" no banner).
export default function FormChaveGemini() {
  const { chave: chaveGemini, salvar: salvarChaveGemini, remover: removerChaveGemini } = useChaveGemini();
  const [campoChave, setCampoChave] = useState('');
  const [validando, setValidando] = useState(false);
  const [erroChave, setErroChave] = useState<string | null>(null);

  // Rodada de conserto — antes disto, uma chave errada só aparecia como
  // erro no meio de uma cena de jogo. `/byok/validar` é uma chamada barata
  // (lista modelos, não gera texto) só para confirmar que a chave autentica.
  const validarESalvar = async () => {
    const valor = campoChave.trim();
    if (!valor) return;
    setValidando(true);
    setErroChave(null);
    try {
      await api.post('/byok/validar', { chave: valor });
      salvarChaveGemini(valor);
      setCampoChave('');
    } catch (err) {
      const detalhe =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setErroChave(detalhe || 'Não consegui confirmar a chave — tente de novo.');
    } finally {
      setValidando(false);
    }
  };

  if (chaveGemini) {
    return (
      <div className="flex items-center justify-between gap-2 p-2 border-2 border-rpg-gold/60 bg-rpg-gold/10">
        <span className="text-xs font-rpg text-rpg-gold">Chave configurada</span>
        <button onClick={removerChaveGemini} className="text-xs text-gray-400 hover:text-red-400 underline">
          Remover
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex gap-2">
        <input
          type="password"
          placeholder="Cole sua chave aqui"
          value={campoChave}
          onChange={(e) => {
            setCampoChave(e.target.value);
            if (erroChave) setErroChave(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') validarESalvar();
          }}
          className="flex-1 min-w-0 bg-black/60 border-2 border-gray-700 px-2 py-1.5 text-white text-xs outline-none focus:border-rpg-gold"
        />
        <button
          onClick={validarESalvar}
          disabled={!campoChave.trim() || validando}
          className="shrink-0 text-xs font-bold text-black bg-rpg-gold hover:bg-white disabled:opacity-40 disabled:hover:bg-rpg-gold px-3 py-1.5"
        >
          {validando ? 'Verificando…' : 'Salvar'}
        </button>
      </div>
      {erroChave && <p className="text-[11px] text-red-400 mt-1.5">{erroChave}</p>}
    </div>
  );
}
