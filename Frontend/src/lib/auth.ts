import { useQuery, useQueryClient } from '@tanstack/react-query';
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
// GET /auth/eu. 401 não é um erro de rede, é a resposta "não autenticado"
// (retry:false já é o default global de App.tsx), então aqui ele vira
// `usuario: null` em vez de derrubar a tela com um erro.
export function useAuth() {
  const query = useQuery({
    queryKey: ['auth'],
    queryFn: async (): Promise<Usuario | null> => {
      try {
        const res = await api.get<Usuario>('/auth/eu');
        return res.data;
      } catch {
        return null;
      }
    },
  });

  return {
    usuario: query.data ?? null,
    carregando: query.isLoading,
    logado: !!query.data,
  };
}

export function useInvalidarAuth() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ['auth'] });
}
