import { Link } from 'react-router-dom';
import { ALERTA_DE_ERROS_ATIVO } from '../lib/alertaDeErros';

// Pré-lançamento — termos e privacidade numa página só, em linguagem simples.
// O texto descreve o que o código faz hoje (conferido em Backend/app/infra/db.py,
// services/telemetria.py e infra/byok.py); se isso mudar, esta página muda junto.
// E-mail de contato para pedidos de dados (LGPD). Vem do ambiente da Vercel
// (VITE_EMAIL_CONTATO) para não ficar gravado no código; sem ele, a seção some.
const EMAIL_CONTATO = import.meta.env.VITE_EMAIL_CONTATO as string | undefined;
const H2 ='text-sm font-pixel-title text-rpg-gold mt-8 mb-3 leading-relaxed';

export default function Privacidade() {
  return (
    <div className="min-h-[100dvh] w-screen bg-rpg-darker px-4 py-10 font-rpg text-gray-300">
      <div className="max-w-2xl mx-auto text-left text-sm leading-relaxed">
        <Link to="/entrar" className="text-gray-400 hover:text-rpg-gold">← Voltar</Link>
        <h1 className="text-base md:text-lg font-pixel-title text-rpg-gold mt-4 leading-relaxed">
          PRIVACIDADE E TERMOS
        </h1>
        <p className="mt-2 text-gray-400">
          Mestre.IA é um projeto pessoal de portfólio, feito por uma pessoa só e oferecido de graça, sem garantias.
        </p>

        <h2 className={H2}>O que guardamos</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>E-mail e senha (a senha fica protegida por hash, nunca em texto puro), se você criar conta.</li>
          <li>Seus personagens e a história de cada partida: suas ações, o que o narrador respondeu e o estado do jogo.</li>
          <li>Um registro simples de uso, só com o tipo de evento (por exemplo, "jogou um turno"), a hora e a sua conta. Não inclui o texto que você escreveu.</li>
          {ALERTA_DE_ERROS_ATIVO && (
            <li>Relatórios de erro técnico (o que quebrou e em qual tela), enviados ao Sentry. Não incluem o texto que você escreveu, seu IP nem seus cookies.</li>
          )}
          <li>Um cookie de sessão para manter você logado. Não usamos cookies de publicidade nem de rastreamento.</li>
        </ul>

        <h2 className={H2}>Para onde vai o que você escreve</h2>
        <p>
          O texto das suas jogadas é enviado ao Google (Gemini) para gerar a narração. Não escreva dados pessoais
          sensíveis no jogo. Se você usar a sua própria chave do Gemini, ela é usada apenas durante a jogada e não é
          guardada no servidor.
        </p>
        <p className="mt-2">Não vendemos nem compartilhamos seus dados com mais ninguém.</p>

        <h2 className={H2}>Jogar sem conta</h2>
        <p>
          Quem joga como convidado fica salvo apenas neste navegador. Se limpar os dados do navegador, perde o herói.
        </p>

        <h2 className={H2}>Seus direitos</h2>
        <p>
          Você tem direito de ver, corrigir ou apagar os seus dados (LGPD).
          {EMAIL_CONTATO
            ? ' Peça pelo contato desta página e apagamos a conta e tudo o que está ligado a ela.'
            : ' Para pedir, procure o autor do projeto pelo repositório no GitHub (Bobeda12/Mestre.IA).'}
        </p>

        <h2 className={H2}>Regras de uso</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>É um jogo de ficção gerado por IA: o narrador pode errar, inventar ou se contradizer.</li>
          <li>O serviço tem limite diário de turnos e pode ficar fora do ar ou ser alterado a qualquer momento.</li>
          <li>Não use o jogo para assediar, ameaçar ou gerar conteúdo ilegal. Contas abusivas podem ser removidas.</li>
        </ul>

        {EMAIL_CONTATO && (
          <>
            <h2 className={H2}>Contato</h2>
            <p>
              <a href={`mailto:${EMAIL_CONTATO}`} className="text-rpg-gold underline">{EMAIL_CONTATO}</a>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
