import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import PixelIcon from './PixelIcon';
import Carregando from './Carregando';

// Etapa 10 (A-2) — aparece no lugar do jogo/criação enquanto o e-mail não
// foi confirmado. O servidor já recusa com 403 (get_current_verified_user);
// isto é só pra não deixar o jogador travado numa tela de erro crua.
export default function ConfirmeEmail({ email }: { email: string }) {
  const [reenviado, setReenviado] = useState(false);
  const reenviar = useMutation({
    mutationFn: async () => { await api.post('/auth/confirmar/reenviar'); },
    onSuccess: () => setReenviado(true),
  });

  return (
    <div className="min-h-[100dvh] w-screen bg-rpg-darker flex flex-col items-center justify-center text-center px-4">
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
        onClick={() => reenviar.mutate()}
        disabled={reenviar.isPending || reenviado}
        className="mt-6 text-rpg-gold hover:text-white text-sm underline decoration-gray-700 disabled:opacity-50 flex items-center gap-2"
      >
        {reenviar.isPending ? <Carregando tamanho={6} rotulo="Reenviando" /> : null}
        {reenviado ? 'E-mail reenviado' : 'Reenviar e-mail'}
      </button>
      {reenviar.isError && <p className="text-red-400 text-xs mt-2">Não deu para reenviar agora. Tenta de novo em instantes.</p>}
    </div>
  );
}
