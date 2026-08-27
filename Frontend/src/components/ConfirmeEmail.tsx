import PixelIcon from './PixelIcon';
import Carregando from './Carregando';

// Etapa 10 (A-2, revisão registro-sem-estado) — aparece no lugar do
// jogo/criação enquanto o e-mail não foi confirmado. Não existe mais sessão
// nem conta gravada nesse momento (nada foi persistido até o link ser
// clicado), então "reenviar" não é uma rota própria: quem chama este
// componente reenvia repetindo o próprio POST original (registrar ou
// reivindicar) com os mesmos dados, e passa o resultado via props.
//
// Sem wrapper de página própria (nem `min-h-screen` nem cor de fundo): quem
// usa decide o container — `Login.tsx` mostra em tela cheia, `GameChat.tsx`
// mostra dentro de um modal por cima do jogo.
export default function ConfirmeEmail({
  email,
  aoReenviar,
  reenviando,
  reenviado,
  erroAoReenviar,
}: {
  email: string;
  aoReenviar: () => void;
  reenviando: boolean;
  reenviado: boolean;
  erroAoReenviar: boolean;
}) {
  return (
    <div className="flex flex-col items-center text-center px-4">
      <PixelIcon name="pergaminho" size={48} className="mb-4" />
      <h1 className="text-sm md:text-base font-pixel-title text-rpg-gold mb-4 leading-relaxed">Confirme seu e-mail</h1>
      <p className="text-gray-200 text-sm max-w-sm">
        Mandamos um link de confirmação para <span className="text-gray-200">{email}</span>. Clique nele para
        continuar jogando.
      </p>
      <p className="text-gray-400 text-xs max-w-sm mt-3">
        Não achou? Dá uma olhada na caixa de spam/lixo eletrônico — e-mail automático de conta nova costuma
        cair lá. Encontrando, marque como "não é spam" pra facilitar da próxima vez.
      </p>
      <button
        onClick={aoReenviar}
        disabled={reenviando || reenviado}
        className="mt-6 text-rpg-gold hover:text-white text-sm underline decoration-gray-700 disabled:opacity-50 flex items-center gap-2"
      >
        {reenviando ? <Carregando tamanho={6} rotulo="Reenviando" /> : null}
        {reenviado ? 'E-mail reenviado' : 'Reenviar e-mail'}
      </button>
      {erroAoReenviar && <p className="text-red-400 text-xs mt-2">Não deu para reenviar agora. Tenta de novo em instantes.</p>}
    </div>
  );
}
