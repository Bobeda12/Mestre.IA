import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from './api';

interface Usuario {
  // `null` é o convidado (Etapa 10, A-1) — `Usuario.email` é opcional no
  // backend desde a Etapa 8, convidado só usa esse caminho que já existia.
  email: string | null;
  // Etapa 10 (A-2) — só importa quando `email !== null`; convidado e conta
  // Google (já verificada no OAuth) nunca ficam presos nisso.
  email_verificado: boolean;
}

// Etapa 8: fonte única de verdade sobre "estou logado?" — uma query contra
// GET /auth/eu. Só 401/403 significam "não autenticado" e viram `usuario: null`.
//
// Qualquer outra falha (500, rede, o Render acordando de um sono de 30 a 60 s)
// NÃO é "deslogado": antes, o `catch` engolia tudo como `null` e a rota
// protegida jogava a pessoa no login por causa de um soluço do servidor. Agora
// o erro sobe, a query tenta de novo com espera crescente (até ~35 s, o tempo de
// o Render acordar) e `carregando` fica verdadeiro durante as tentativas.
export function useAuth() {
  const query = useQuery({
    queryKey: ['auth'],
    queryFn: async (): Promise<Usuario | null> => {
      try {
        const res = await api.get<Usuario>('/auth/eu');
        return res.data;
      } catch (erro) {
        if (isAxiosError(erro) && (erro.response?.status === 401 || erro.response?.status === 403)) return null;
        throw erro;
      }
    },
    retry: 6,
    retryDelay: (tentativa) => Math.min(1000 * 2 ** tentativa, 10000),
  });

  return {
    usuario: query.data ?? null,
    carregando: query.isLoading,
    logado: !!query.data,
    // Esgotou as tentativas: o servidor não respondeu. Diferente de "deslogado".
    servidorIndisponivel: query.isError,
    tentarDeNovo: () => query.refetch(),
  };
}

export function useInvalidarAuth() {
  const queryClient = useQueryClient();
  // `refetchType: 'all'`: a tela de entrada não observa esta query, e o
  // padrão ('active') só marcaria o dado como velho sem buscar de novo — a
  // promessa resolvia na hora e quem navegasse em seguida ainda era visto
  // como "não logado" pela rota protegida.
  return () => queryClient.invalidateQueries({ queryKey: ['auth'], refetchType: 'all' });
}
