import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Mail, Lock, Crown, ArrowLeft, Loader2 } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useInvalidarAuth } from '../lib/auth';
import ConfirmeEmail from './ConfirmeEmail';

export default function Login() {
  const [modo, setModo] = useState<'entrar' | 'criar'>('entrar');
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');
  // Etapa 10 (A-2) — depois de criar conta, mostra a tela de confirmação
  // na hora, em vez de navegar pro jogo pra só então travar em /criar.
  const [emailRecemRegistrado, setEmailRecemRegistrado] = useState<string | null>(null);
  const navigate = useNavigate();
  const invalidarAuth = useInvalidarAuth();
  // Etapa 10 (A-2) — quem clicou o link de confirmação chega aqui via
  // redirect do backend (`GET /auth/confirmar`). Se essa aba já estava
  // logada, `invalidarAuth` refaz a query e `RotaProtegida` libera na hora.
  const [searchParams] = useSearchParams();
  const confirmado = searchParams.get('confirmado');
  // eslint-disable-next-line react-hooks/exhaustive-deps -- só na 1ª renderização, `invalidarAuth` é estável
  useEffect(() => { if (confirmado === '1') invalidarAuth(); }, []);

  // Sem GOOGLE_CLIENT_ID/SECRET configurados no backend, o fluxo OAuth não
  // tem como funcionar — o botão simplesmente não aparece, em vez de levar
  // a um erro no meio do caminho (ver ADR-0014).
  const opcoes = useQuery({
    queryKey: ['auth-opcoes'],
    queryFn: async () => (await api.get<{ google_disponivel: boolean }>('/auth/opcoes')).data,
  });

  const senhasConferem = modo === 'entrar' || senha === confirmarSenha;

  const entrar = useMutation({
    mutationFn: async () => {
      const rota = modo === 'entrar' ? '/auth/login' : '/auth/registrar';
      await api.post(rota, { email, senha });
    },
    onSuccess: () => {
      invalidarAuth();
      if (modo === 'criar') {
        setEmailRecemRegistrado(email);
      } else {
        navigate('/', { replace: true });
      }
    },
  });

  // Etapa 10 (A-1) — joga sem e-mail. O convidado vai direto pra criação de
  // personagem, não pro menu: o objetivo é tirar o máximo de atrito antes
  // do primeiro turno, não mostrar uma lista de heróis vazia.
  const jogarComoConvidado = useMutation({
    mutationFn: async () => { await api.post('/auth/convidado'); },
    onSuccess: () => {
      invalidarAuth();
      navigate('/criar', { replace: true });
    },
  });

  const detalheServidor =
    entrar.error && isAxiosError<{ detail?: string }>(entrar.error) ? entrar.error.response?.data?.detail : undefined;
  const mensagemErro =
    detalheServidor ??
    (modo === 'entrar'
      ? 'E-mail ou senha incorretos.'
      : 'Não deu para criar a conta. Confira o e-mail e a senha (mínimo 8 caracteres).');

  if (emailRecemRegistrado) {
    return <ConfirmeEmail email={emailRecemRegistrado} />;
  }

  return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center relative overflow-hidden font-sans px-4">
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/90 to-black/60 z-0" />

      <div className="z-10 w-full max-w-sm text-center">
        <Link to="/" className="absolute top-4 left-4 text-gray-500 hover:text-white flex items-center gap-2 text-sm">
          <ArrowLeft size={18} /> Voltar
        </Link>

        <Crown size={48} className="text-rpg-gold mx-auto mb-4 drop-shadow-[0_0_15px_rgba(197,160,89,0.5)]" />
        <h1 className="text-3xl font-rpg text-white mb-2">{modo === 'entrar' ? 'Entrar' : 'Criar conta'}</h1>

        {confirmado === '1' && (
          <p className="text-emerald-400 text-sm mb-4">E-mail confirmado! Pode entrar.</p>
        )}
        {confirmado === '0' && (
          <p className="text-red-500 text-sm mb-4">Esse link de confirmação expirou ou já foi usado.</p>
        )}

        <button
          type="button"
          onClick={() => jogarComoConvidado.mutate()}
          disabled={jogarComoConvidado.isPending}
          className="w-full bg-transparent hover:bg-gray-900 text-rpg-gold border border-rpg-gold/50 hover:border-rpg-gold font-bold py-3 rounded flex items-center justify-center gap-2 transition-all disabled:opacity-50"
        >
          {jogarComoConvidado.isPending ? <Loader2 size={18} className="animate-spin" /> : 'Jogar agora'}
        </button>
        <p className="text-gray-600 text-xs mt-2">
          Seu progresso fica salvo neste navegador — limpou os dados, perdeu o herói.
        </p>
        {jogarComoConvidado.isError && (
          <p className="text-red-500 text-sm mt-2">Não deu para começar agora. Tenta de novo em alguns minutos.</p>
        )}

        <div className="flex items-center gap-3 my-6 text-gray-600 text-xs uppercase tracking-widest">
          <div className="flex-1 h-px bg-gray-800" />
          {modo === 'entrar' ? 'ou entre com e-mail e senha' : 'ou crie uma conta'}
          <div className="flex-1 h-px bg-gray-800" />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            entrar.mutate();
          }}
          className="mt-8 flex flex-col gap-4"
        >
          <label className="text-left text-xs text-gray-500 uppercase tracking-wide -mb-2">E-mail</label>
          <div className="flex items-center bg-gray-900/80 border border-gray-700 rounded px-3 focus-within:border-rpg-gold">
            <Mail size={18} className="text-gray-500" />
            <input
              type="email"
              required
              autoFocus
              placeholder="seu@email.com"
              aria-label="E-mail"
              className="bg-transparent text-white px-3 py-3 outline-none w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <label className="text-left text-xs text-gray-500 uppercase tracking-wide -mb-2">Senha</label>
          <div className="flex items-center bg-gray-900/80 border border-gray-700 rounded px-3 focus-within:border-rpg-gold">
            <Lock size={18} className="text-gray-500" />
            <input
              type="password"
              required
              minLength={modo === 'criar' ? 8 : undefined}
              placeholder={modo === 'criar' ? 'Mínimo 8 caracteres' : 'Sua senha'}
              aria-label="Senha"
              className="bg-transparent text-white px-3 py-3 outline-none w-full"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>

          {modo === 'criar' && (
            <>
              <label className="text-left text-xs text-gray-500 uppercase tracking-wide -mb-2">Confirmar senha</label>
              <div className={`flex items-center bg-gray-900/80 border rounded px-3 focus-within:border-rpg-gold ${
                confirmarSenha && !senhasConferem ? 'border-red-700' : 'border-gray-700'
              }`}>
                <Lock size={18} className="text-gray-500" />
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="Digite a senha de novo"
                  aria-label="Confirmar senha"
                  className="bg-transparent text-white px-3 py-3 outline-none w-full"
                  value={confirmarSenha}
                  onChange={(e) => setConfirmarSenha(e.target.value)}
                />
              </div>
              {confirmarSenha && !senhasConferem && (
                <p className="text-red-500 text-xs text-left -mt-2">As senhas não são iguais.</p>
              )}
            </>
          )}

          <button
            type="submit"
            disabled={entrar.isPending || !email || !senha || !senhasConferem}
            className="bg-rpg-gold hover:bg-white text-black font-bold py-3 rounded flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
          >
            {entrar.isPending ? <Loader2 size={18} className="animate-spin" /> : modo === 'entrar' ? 'Entrar' : 'Criar conta'}
          </button>
          {entrar.isError && <p className="text-red-500 text-sm">{mensagemErro}</p>}
        </form>

        <button
          onClick={() => {
            entrar.reset();
            setSenha('');
            setConfirmarSenha('');
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
