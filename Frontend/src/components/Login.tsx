import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useInvalidarAuth } from '../lib/auth';
import ConfirmeEmail from './ConfirmeEmail';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import PanelFrame from './PanelFrame';
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
  // Revisão registro-sem-estado — "reenviar" na tela de confirmação é só
  // repetir o próprio POST /auth/registrar com os mesmos dados (nada foi
  // gravado no banco ainda, então não esbarra na checagem de duplicidade).
  const [reenviouConfirmacao, setReenviouConfirmacao] = useState(false);
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
      if (modo === 'entrar') {
        invalidarAuth();
        navigate('/', { replace: true });
        return;
      }
      // Registrar não grava nada no banco nem seta sessão (só acontece
      // quando o link do e-mail é clicado) — não há o que invalidar aqui.
      // Este branch só é alcançado pelo formulário de criação de conta (o
      // reenvio, inclusive vindo de um login que falhou, usa
      // `reenviarConfirmacao` abaixo).
      setEmailRecemRegistrado(email);
    },
  });

  // Revisão "motivo de erro no login" — reenviar precisa sempre bater em
  // `/auth/registrar`, nunca em `/auth/login`. Reusar `entrar.mutate()`
  // aqui quebraria se o usuário chegasse em `ConfirmeEmail` vindo do modo
  // 'entrar' (a rota dela depende de `modo`, e nesse ponto `modo` ainda
  // seria 'entrar'). Como `/auth/registrar` agora espelha o pendente em
  // `RegistroPendente` (backend), chamar de novo com o mesmo e-mail é
  // exatamente o reenvio, sem esbarrar em duplicidade.
  const reenviarConfirmacao = useMutation({
    mutationFn: async () => { await api.post('/auth/registrar', { email, senha }); },
    onSuccess: () => {
      if (emailRecemRegistrado) {
        setReenviouConfirmacao(true);
      } else {
        setEmailRecemRegistrado(email);
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

  const statusServidor = entrar.error && isAxiosError(entrar.error) ? entrar.error.response?.status : undefined;
  const detalheServidor =
    entrar.error && isAxiosError<{ detail?: string }>(entrar.error) ? entrar.error.response?.data?.detail : undefined;
  // Revisão "motivo de erro no login" — `/auth/login` agora devolve um
  // `motivo` (senha_incorreta | pendente_confirmacao | conta_nao_encontrada
  // | conta_google) ao lado do `detail`, para oferecer a ação certa em vez
  // de um texto único e genérico (troca deliberada da proteção
  // anti-enumeração original, ver `Backend/app/routers/auth.py:ErroLogin`).
  const motivoServidor =
    entrar.error && isAxiosError<{ detail?: string; motivo?: string }>(entrar.error)
      ? entrar.error.response?.data?.motivo
      : undefined;
  const mensagemErro =
    detalheServidor ??
    (modo === 'entrar'
      ? 'E-mail ou senha incorretos, ou você ainda não confirmou o link enviado para o seu e-mail.'
      : 'Não deu para criar a conta. Confira o e-mail e a senha (mínimo 8 caracteres).');
  const emailJaExiste = modo === 'criar' && statusServidor === 409;
  const statusReenvio =
    reenviarConfirmacao.error && isAxiosError(reenviarConfirmacao.error)
      ? reenviarConfirmacao.error.response?.status
      : undefined;

  if (emailRecemRegistrado) {
    return (
      <div className="min-h-[100dvh] w-screen bg-rpg-darker flex items-center justify-center">
        <ConfirmeEmail
          email={emailRecemRegistrado}
          aoReenviar={() => reenviarConfirmacao.mutate()}
          reenviando={reenviarConfirmacao.isPending}
          reenviado={reenviouConfirmacao}
          erroAoReenviar={reenviarConfirmacao.isError}
        />
      </div>
    );
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
          <PanelFrame borderWidth={6} className="bg-emerald-950/80 mb-4 p-3 flex items-center justify-center gap-2">
            <PixelIcon name="estrela" size={18} className="shrink-0" />
            <p className="text-emerald-300 text-sm font-rpg">E-mail confirmado! Você já está logado.</p>
          </PanelFrame>
        )}
        {confirmado === '0' && (
          <PanelFrame borderWidth={6} className="bg-red-950/80 mb-4 p-3">
            <p className="text-red-400 text-sm font-rpg">Esse link de confirmação expirou ou já foi usado.</p>
          </PanelFrame>
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
          {entrar.isError && (
            <p className="text-red-400 text-sm font-rpg text-center">
              {mensagemErro}
              {emailJaExiste && (
                <>
                  {' '}
                  <button
                    type="button"
                    onClick={() => {
                      entrar.reset();
                      reenviarConfirmacao.reset();
                      setSenha('');
                      setConfirmarSenha('');
                      setModo('entrar');
                    }}
                    className="text-rpg-gold hover:text-white underline decoration-gray-700 hover:decoration-rpg-gold"
                  >
                    Entrar com essa conta
                  </button>
                </>
              )}
            </p>
          )}

          {entrar.isError && modo === 'entrar' && motivoServidor === 'pendente_confirmacao' && (
            <div className="text-center">
              <button
                type="button"
                onClick={() => reenviarConfirmacao.mutate()}
                disabled={reenviarConfirmacao.isPending}
                className="text-rpg-gold hover:text-white text-xs font-rpg underline decoration-gray-700 hover:decoration-rpg-gold disabled:opacity-50 inline-flex items-center gap-2"
              >
                {reenviarConfirmacao.isPending && <Carregando tamanho={6} rotulo="Reenviando" />}
                Reenviar e-mail de confirmação
              </button>
              {reenviarConfirmacao.isError && (
                <p className="text-red-400 text-xs font-rpg mt-1">
                  {statusReenvio === 409
                    ? 'Essa conta já existe e está confirmada — confira a senha.'
                    : 'Não deu para reenviar agora. Tenta de novo em instantes.'}
                </p>
              )}
            </div>
          )}

          {entrar.isError && modo === 'entrar' && motivoServidor === 'conta_nao_encontrada' && (
            <p className="text-center">
              <button
                type="button"
                onClick={() => {
                  entrar.reset();
                  reenviarConfirmacao.reset();
                  setSenha('');
                  setConfirmarSenha('');
                  setModo('criar');
                }}
                className="text-rpg-gold hover:text-white text-xs font-rpg underline decoration-gray-700 hover:decoration-rpg-gold"
              >
                Criar uma conta
              </button>
            </p>
          )}

          {entrar.isError && modo === 'entrar' && motivoServidor === 'conta_google' && opcoes.data?.google_disponivel && (
            <p className="text-center">
              <a
                href={`${API_URL}/auth/google/iniciar`}
                className="text-rpg-gold hover:text-white text-xs font-rpg underline decoration-gray-700 hover:decoration-rpg-gold"
              >
                Entrar com Google
              </a>
            </p>
          )}
        </form>

        <button
          disabled={entrar.isPending}
          onClick={() => {
            entrar.reset();
            reenviarConfirmacao.reset();
            setSenha('');
            setConfirmarSenha('');
            setModo(modo === 'entrar' ? 'criar' : 'entrar');
          }}
          className="mt-5 text-gray-400 hover:text-rpg-gold text-sm font-rpg underline decoration-gray-700 hover:decoration-rpg-gold disabled:opacity-50 disabled:pointer-events-none"
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
