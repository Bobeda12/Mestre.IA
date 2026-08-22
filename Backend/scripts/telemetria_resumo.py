"""Resumo de telemetria de produto (Etapa 9) a partir de `eventos_telemetria`
— sessões criadas, turnos por sessão, retenção D1/D7 e ponto de abandono.
Granularidade mínima por design (ver `app/infra/db.py:EventoTelemetria`):
isto é uma consulta, não um dashboard.

Custo por sessão não está aqui — já vive no Langfuse (Etapa 9, Fase F) por
trace, com `personagem_id` como metadata; filtre por lá em vez de duplicar
tokens/custo numa segunda tabela.

Uso: `uv run python scripts/telemetria_resumo.py` (lê o `DATABASE_URL` de
`app/infra/settings.py`, o mesmo banco do app — passe `DATABASE_URL=...` na
frente do comando para mirar outro banco, ex. o de produção)."""

import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra.db import EventoTelemetria, SessionLocal, Usuario  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        eventos = db.query(EventoTelemetria).order_by(EventoTelemetria.criado_em).all()
        usuarios = {u.id: u for u in db.query(Usuario).all()}

        sessoes_criadas = [e for e in eventos if e.tipo == "sessao_criada"]
        turnos = [e for e in eventos if e.tipo == "turno"]
        arquivados = [e for e in eventos if e.tipo == "personagem_arquivado"]

        print(f"Sessões (personagens) criadas: {len(sessoes_criadas)}")
        print(f"Turnos jogados: {len(turnos)}")
        print(f"Personagens arquivados: {len(arquivados)}")

        turnos_por_personagem: dict[int, int] = defaultdict(int)
        for e in turnos:
            if e.personagem_id is not None:
                turnos_por_personagem[e.personagem_id] += 1
        if turnos_por_personagem:
            media = sum(turnos_por_personagem.values()) / len(turnos_por_personagem)
            print(f"Turnos por sessão (média, só quem jogou >=1): {media:.1f}")

        print("\nPonto de abandono — última atividade por personagem que já jogou:")
        ultimo_turno: dict[int, EventoTelemetria] = {}
        for e in turnos:
            if e.personagem_id is not None:
                ultimo_turno[e.personagem_id] = e
        for personagem_id, evento in sorted(ultimo_turno.items(), key=lambda kv: kv[1].criado_em):
            n_turnos = turnos_por_personagem[personagem_id]
            print(f"  personagem {personagem_id}: {n_turnos} turnos, último em {evento.criado_em}")

        print("\nRetenção — por usuário, jogou algum turno pelo menos 1/7 dias após criar a conta:")
        d1 = d7 = 0
        turnos_por_usuario: dict[int, list[EventoTelemetria]] = defaultdict(list)
        for e in turnos:
            turnos_por_usuario[e.usuario_id].append(e)
        for usuario_id, usuario in usuarios.items():
            eventos_usuario = turnos_por_usuario.get(usuario_id, [])
            voltou_d1 = any(e.criado_em - usuario.criado_em >= timedelta(days=1) for e in eventos_usuario)
            voltou_d7 = any(e.criado_em - usuario.criado_em >= timedelta(days=7) for e in eventos_usuario)
            d1 += voltou_d1
            d7 += voltou_d7
        total_usuarios = len(usuarios) or 1
        print(f"  D1: {d1}/{len(usuarios)} ({d1 / total_usuarios:.0%})")
        print(f"  D7: {d7}/{len(usuarios)} ({d7 / total_usuarios:.0%})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
