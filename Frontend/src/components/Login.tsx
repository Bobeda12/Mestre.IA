import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useInvalidarAuth } from '../lib/auth';
import ConfirmeEmail from './ConfirmeEmail';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import { PIXEL_BUTTON_CLASS, pixelButtonBorderStyle } from '../lib/pixelButtonEstilo';
import Carregando from './Carregando';
import MapaDeFundo from './MapaDeFundo';
import BotaoConfig from './BotaoConfig';

// Etapa 14 (revisão) — a tela de login tinha passado inteira por fora do
// sistema pixel: `font-sans` (Geist), cantos arredondados e ícones
// lucide-react de traço fino. O layout já estava certo, então aqui muda só a
// pele. Os ícones dos campos (envelope/cadeado) saíram em vez de virarem
// pixel: jogo 8-bit não põe ícone dentro de campo de texto, e o rótulo em
// maiúscula acima do campo já diz o que é.
const CAMPO =
  'w-full bg-black/60 border-2 border-gray-600 px-3 py-3 text-white outline-none focus:border-rpg-gold transition-colors';
const ROTULO = 'text-left text-xs text-rpg-gold uppercase tracking-widest font-rpg';

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
    <div className="min-h-[100dvh] w-screen bg-rpg-darker flex flex-col items-center justify-center relative overflow-hidden px-4 py-10">
      <MapaDeFundo />

      <div className="z-10 w-full max-w-sm text-center">
        <Link to="/" className="absolute top-4 left-4 text-gray-400 hover:text-rpg-gold flex items-center gap-2 text-sm font-rpg">
          <PixelIcon name="seta" size={16} className="rotate-180" /> Voltar
        </Link>
        <div className="absolute top-4 right-4"><BotaoConfig tema="aventura" mostrarVoltar={false} /></div>

        <PixelIcon name="coroa" size={48} className="mx-auto mb-4" />
        <h1 className="text-base md:text-lg font-pixel-title text-rpg-gold mb-6 leading-relaxed">
          {modo === 'entrar' ? 'ENTRAR' : 'CRIAR CONTA'}
        </h1>

        {confirmado === '1' && (
          <p className="text-emerald-400 text-sm mb-4 font-rpg">E-mail confirmado! Pode entrar.</p>
        )}
        {confirmado === '0' && (
          <p className="text-red-400 text-sm mb-4 font-rpg">Esse link de confirmação expirou ou já foi usado.</p>
        )}

        <PixelButton
          type="button"
          variant="vermelho"
          onClick={() => jogarComoConvidado.mutate()}
          disabled={jogarComoConvidado.isPending}
          className="w-full py-4 text-[10px] md:text-xs"
        >
          {jogarComoConvidado.isPending ? <Carregando rotulo="Entrando" /> : 'JOGAR AGORA'}
        </PixelButton>
        <p className="text-gray-400 text-xs mt-2 font-rpg">
          Seu progresso fica salvo neste navegador. Limpou os dados, perdeu o herói.
        </p>
        {jogarComoConvidado.isError && (
          <p className="text-red-400 text-sm mt-2 font-rpg">Não deu para começar agora. Tenta de novo em alguns minutos.</p>
        )}

        <Divisor>{modo === 'entrar' ? 'ou entre com e-mail' : 'ou crie uma conta'}</Divisor>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            entrar.mutate();
          }}
          className="flex flex-col gap-2 text-left"
        >
          <label className={ROTULO} htmlFor="campo-email">E-mail</label>
          <input
            id="campo-email"
            type="email"
            required
            autoFocus
            placeholder="seu@email.com"
            className={CAMPO}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label className={`${ROTULO} mt-2`} htmlFor="campo-senha">Senha</label>
          <input
            id="campo-senha"
            type="password"
            required
            minLength={modo === 'criar' ? 8 : undefined}
            placeholder={modo === 'criar' ? 'Mínimo 8 caracteres' : 'Sua senha'}
            className={CAMPO}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />

          {modo === 'criar' && (
            <>
              <label className={`${ROTULO} mt-2`} htmlFor="campo-confirmar">Confirmar senha</label>
              <input
                id="campo-confirmar"
                type="password"
                required
                minLength={8}
                placeholder="Digite a senha de novo"
                className={`${CAMPO} ${confirmarSenha && !senhasConferem ? 'border-red-600' : ''}`}
                value={confirmarSenha}
                onChange={(e) => setConfirmarSenha(e.target.value)}
              />
              {confirmarSenha && !senhasConferem && (
                <p className="text-red-400 text-xs font-rpg">As senhas não são iguais.</p>
              )}
            </>
          )}

          <PixelButton
            type="submit"
            variant="dourado"
            disabled={entrar.isPending || !email || !senha || !senhasConferem}
            className="w-full py-4 text-[10px] md:text-xs mt-4"
          >
            {entrar.isPending ? <Carregando /> : modo === 'entrar' ? 'ENTRAR' : 'CRIAR CONTA'}
          </PixelButton>
          {entrar.isError && <p className="text-red-400 text-sm font-rpg text-center">{mensagemErro}</p>}
        </form>

        <button
          onClick={() => {
            entrar.reset();
            setSenha('');
            setConfirmarSenha('');
            setModo(modo === 'entrar' ? 'criar' : 'entrar');
          }}
          className="mt-5 text-gray-400 hover:text-rpg-gold text-sm font-rpg underline decoration-gray-700 hover:decoration-rpg-gold"
        >
          {modo === 'entrar' ? 'Não tem conta? Criar uma' : 'Já tem conta? Entrar'}
        </button>

        {opcoes.isLoading ? (
          <>
            <Divisor>ou</Divisor>
            <div className="w-full h-[52px] flex items-center justify-center border-2 border-gray-700 bg-black/30 text-gray-500">
              <Carregando tamanho={6} rotulo="Carregando opções de login" />
            </div>
          </>
        ) : opcoes.data?.google_disponivel ? (
          <>
            <Divisor>ou</Divisor>
            <a
              href={`${API_URL}/auth/google/iniciar`}
              className={`${PIXEL_BUTTON_CLASS} w-full flex items-center justify-center gap-2 py-3 text-[10px] md:text-xs no-underline`}
              style={pixelButtonBorderStyle('dourado')}
            >
              Entrar com Google
            </a>
          </>
        ) : null}
      </div>
    </div>
  );
}

function Divisor({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 my-6 text-gray-400 text-[10px] uppercase tracking-widest font-rpg">
      <div className="flex-1 h-0.5 bg-gray-700" />
      {children}
      <div className="flex-1 h-0.5 bg-gray-700" />
    </div>
  );
}
