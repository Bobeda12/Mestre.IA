import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Mail, Lock, Crown, ArrowLeft, Loader2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useInvalidarAuth } from '../lib/auth';

export default function Login() {
  const [modo, setModo] = useState<'entrar' | 'criar'>('entrar');
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const navigate = useNavigate();
  const invalidarAuth = useInvalidarAuth();

  // Sem GOOGLE_CLIENT_ID/SECRET configurados no backend, o fluxo OAuth não
  // tem como funcionar — o botão simplesmente não aparece, em vez de levar
  // a um erro no meio do caminho (ver ADR-0014).
  const opcoes = useQuery({
    queryKey: ['auth-opcoes'],
    queryFn: async () => (await api.get<{ google_disponivel: boolean }>('/auth/opcoes')).data,
  });

  const entrar = useMutation({
    mutationFn: async () => {
      const rota = modo === 'entrar' ? '/auth/login' : '/auth/registrar';
      await api.post(rota, { email, senha });
    },
    onSuccess: () => {
      invalidarAuth();
      navigate('/', { replace: true });
    },
  });

  const detalheServidor =
    entrar.error && isAxiosError<{ detail?: string }>(entrar.error) ? entrar.error.response?.data?.detail : undefined;
  const mensagemErro =
    detalheServidor ??
    (modo === 'entrar'
      ? 'E-mail ou senha incorretos.'
      : 'Não deu para criar a conta. Confira o e-mail e a senha (mínimo 8 caracteres).');

  return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center relative overflow-hidden font-sans px-4">
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/90 to-black/60 z-0" />

      <div className="z-10 w-full max-w-sm text-center">
        <Link to="/" className="absolute top-4 left-4 text-gray-500 hover:text-white flex items-center gap-2 text-sm">
          <ArrowLeft size={18} /> Voltar
        </Link>

        <Crown size={48} className="text-rpg-gold mx-auto mb-4 drop-shadow-[0_0_15px_rgba(197,160,89,0.5)]" />
        <h1 className="text-3xl font-rpg text-white mb-2">{modo === 'entrar' ? 'Entrar' : 'Criar conta'}</h1>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            entrar.mutate();
          }}
          className="mt-8 flex flex-col gap-4"
        >
          <div className="flex items-center bg-gray-900/80 border border-gray-700 rounded px-3 focus-within:border-rpg-gold">
            <Mail size={18} className="text-gray-500" />
            <input
              type="email"
              required
              autoFocus
              placeholder="seu@email.com"
              className="bg-transparent text-white px-3 py-3 outline-none w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex items-center bg-gray-900/80 border border-gray-700 rounded px-3 focus-within:border-rpg-gold">
            <Lock size={18} className="text-gray-500" />
            <input
              type="password"
              required
              minLength={modo === 'criar' ? 8 : undefined}
              placeholder={modo === 'criar' ? 'Mínimo 8 caracteres' : 'Sua senha'}
              className="bg-transparent text-white px-3 py-3 outline-none w-full"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={entrar.isPending || !email || !senha}
            className="bg-rpg-gold hover:bg-white text-black font-bold py-3 rounded flex items-center justify-center gap-2 transition-all disabled:opacity-50"
          >
            {entrar.isPending ? <Loader2 size={18} className="animate-spin" /> : modo === 'entrar' ? 'Entrar' : 'Criar conta'}
          </button>
          {entrar.isError && <p className="text-red-500 text-sm">{mensagemErro}</p>}
        </form>

        <button
          onClick={() => {
            entrar.reset();
            setModo(modo === 'entrar' ? 'criar' : 'entrar');
          }}
          className="mt-4 text-gray-500 hover:text-rpg-gold text-sm underline decoration-gray-700"
        >
          {modo === 'entrar' ? 'Não tem conta? Criar uma' : 'Já tem conta? Entrar'}
        </button>

        {opcoes.data?.google_disponivel && (
          <>
            <div className="flex items-center gap-3 my-6 text-gray-600 text-xs uppercase tracking-widest">
              <div className="flex-1 h-px bg-gray-800" /> ou <div className="flex-1 h-px bg-gray-800" />
            </div>
            <a
              href={`${API_URL}/auth/google/iniciar`}
              className="w-full flex items-center justify-center gap-2 bg-white hover:bg-gray-200 text-gray-900 font-bold py-3 rounded transition-all"
            >
              Entrar com Google
            </a>
          </>
        )}
      </div>
    </div>
  );
}
