"""Rate limit por IP (Etapa 9) — em memória, sem Redis: o Fly.io roda uma
única instância deste app por padrão (ver `fly.toml`), então não há estado
para sincronizar entre processos. Não sobrevive a múltiplas instâncias —
se o app crescer para mais de uma máquina, isto precisa virar um backend
compartilhado (Redis) para continuar valendo.

Existe por dois motivos, ambos citados no `PLANO_MESTRE.md` (§Etapa 9,
§7 "três armadilhas conhecidas"): força bruta em `/auth/login` (a
verificação de senha aceitava tentativas ilimitadas) e a cota da Groq —
compartilhada entre todos os jogadores — sendo drenada por uma única
pessoa martelando `/chat`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
