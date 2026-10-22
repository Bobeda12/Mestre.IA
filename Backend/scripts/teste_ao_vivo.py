"""Teste ao vivo guiado das Fases 1 a 4 do plano texto-livre (ADR-0043 a 0047).

O que os testes automáticos não pegam: o modelo real obedece ao prompt?
Roda quatro turnos de texto livre contra o provedor de verdade, num banco
descartável (o `rpg_save.db` nunca é tocado), e confere o ESTADO, não só a
prosa.

Uso (em Backend/):
    uv run python -m scripts.teste_ao_vivo --saida relatorio.json
    uv run python -m scripts.teste_ao_vivo --cenarios violencia,impossivel

Custo: cada passo do agente é uma requisição. O contador abaixo (`--teto`,
padrão 16) interrompe antes de estourar a cota diária do plano gratuito."""

import argparse
import functools
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
_tmp = Path(tempfile.mkdtemp(prefix="mestre_ao_vivo_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'ao_vivo.db').as_posix()}"

import hashlib  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.infra import embeddings, llm_client  # noqa: E402
from app.infra.db import Base, Personagem, SessionLocal, Usuario, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import game as rota_jogo  # noqa: E402
from app.services.auth import get_current_user  # noqa: E402

PAUSA_ENTRE_TURNOS = 65  # o teto de tokens por minuto do provedor de fallback (Groq) é de 8k
REQUISICOES: list[dict] = []
CHAMADAS_FERRAMENTA: list[dict] = []


def _embedding_falso(texto: str, api_key: str | None = None) -> list[float]:
    return [b / 255 for b in hashlib.sha256(texto.encode("utf-8")).digest()[:16]]


class TetoDeRequisicoes(RuntimeError):
    pass


def _instrumentar(teto: int) -> None:
    original = llm_client._chamar_modelo

    @functools.wraps(original)
    def contado(cliente, provedor, modelo, *a, **kw):
        if len(REQUISICOES) >= teto:
            raise TetoDeRequisicoes(f"teto de {teto} requisições atingido")
        inicio = time.time()
        registro = {"provedor": provedor, "modelo": modelo, "ok": False, "s": 0.0}
        REQUISICOES.append(registro)
        try:
            resposta = original(cliente, provedor, modelo, *a, **kw)
            registro["ok"] = True
            return resposta
        finally:
            registro["s"] = round(time.time() - inicio, 1)

    llm_client._chamar_modelo = contado
    embeddings.embed_um = _embedding_falso
    embeddings.embed = lambda textos, api_key=None: [_embedding_falso(t, api_key) for t in textos]

    executar = rota_jogo.executar_turno

    def registrando(*a, **kw):
        narrativa, eventos, chamadas = executar(*a, **kw)
        for c in chamadas:
            CHAMADAS_FERRAMENTA.append({"nome": c.nome, "args": c.args, "ok": c.sucesso})
        return narrativa, eventos, chamadas

    rota_jogo.executar_turno = registrando


def _estado(sid: str) -> dict:
    with SessionLocal() as db:
        h = db.query(Personagem).filter_by(session_id=sid).one()
        db.refresh(h)
        return {
            "hp": h.hp_atual, "hp_max": h.hp_max, "nivel": h.nivel, "xp": h.xp,
            "mundo": h.world_state or {}, "combate": h.combat_state or {},
        }


def _pessoas(estado: dict) -> dict:
    return (estado["mundo"].get("mundo") or {}).get("pessoas") or {}


def _conta(client: TestClient) -> None:
    pass


def turno(client: TestClient, sid: str, texto: str) -> dict:
    if _estado(sid)["combate"].get("ativo"):
        return {"http": 0, "narrativa": "", "eventos": [], "ferramentas": [], "erro": True, "pulado": "combate ainda ativo"}  # noqa: E501
    antes = len(CHAMADAS_FERRAMENTA)
    r = client.post("/chat", json={"session_id": sid, "action": texto})
    corpo = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"texto": r.text}
    return {
        "http": r.status_code,
        "narrativa": corpo.get("narrativa") or corpo.get("detail") or corpo.get("erro_mensagem") or "",
        "eventos": corpo.get("eventos") or corpo.get("eventos_ferramentas") or [],
        "ferramentas": CHAMADAS_FERRAMENTA[antes:],
        "erro": bool(corpo.get("erro")),
    }


def _lutar_ate_o_fim(client: TestClient, sid: str, limite: int = 60) -> dict:
    """Resolve o combate pelos botões (sem IA): ataca; depois de agir, encerra o turno."""
    passos = 0
    ultimo = ""
    while passos < limite:
        e = _estado(sid)
        c = e["combate"]
        if not c.get("ativo") or e["hp"] <= 0:
            break
        rev = e["mundo"].get("revisao", 0)
        vivos = [i for i in c.get("inimigos", []) if i.get("hp", 0) > 0 and not i.get("afastado")]
        if not vivos:
            break
        base = {"session_id": sid, "turno_esperado": rev}
        r = client.post("/game/action", json={**base, "acao": "atacar", "alvo": vivos[0]["nome"]})
        if r.status_code == 429:
            time.sleep(20)
            continue
        if r.status_code == 400:
            ultimo = r.text[:120]
            r = client.post("/game/action", json={**base, "acao": "encerrar_turno"})
            if r.status_code == 429:
                time.sleep(20)
        passos += 1
        time.sleep(1.1)  # o /game/action aceita 60 por minuto
    e = _estado(sid)
    return {"passos": passos, "combate_ativo": bool(e["combate"].get("ativo")), "hp": e["hp"], "ultimo_erro": ultimo}


def cenario_violencia(client: TestClient, sid: str) -> dict:
    antes = _estado(sid)
    candidatos = {k: v for k, v in _pessoas(antes).items() if v.get("local") == antes["mundo"].get("local")}
    if not candidatos:
        return {"pulado": "nenhuma pessoa no local inicial", "pessoas": list(_pessoas(antes))}
    pid, pessoa = next(iter(candidatos.items()))
    t = turno(client, sid, f"Eu saco minha arma e mato {pessoa['nome']} agora mesmo.")
    meio = _estado(sid)
    inimigos = meio["combate"].get("inimigos", [])
    saida = {
        "alvo": {"id": pid, "nome": pessoa["nome"]},
        "turno": t,
        "combate_abriu": bool(meio["combate"].get("ativo")),
        "inimigos": [{"nome": i.get("nome"), "arquetipo": i.get("arquetipo"), "pessoa_id": i.get("pessoa_id")}
                     for i in inimigos],
        "narrou_morte_sem_combate": (not meio["combate"].get("ativo"))
                                    and pessoa["nome"].lower() in t["narrativa"].lower(),
        "disposicao_apos_turno": _pessoas(meio).get(pid, {}).get("disposicao"),
    }
    if saida["combate_abriu"]:
        saida["luta"] = _lutar_ate_o_fim(client, sid)
        fim = _estado(sid)
        saida["disposicao_apos_luta"] = _pessoas(fim).get(pid, {}).get("disposicao")
        time.sleep(2)
        r = client.post("/game/action", json={
            "session_id": sid, "acao": "agir_no_mundo", "alvo": pid, "operacao": "conversar",
            "turno_esperado": (fim["mundo"] or {}).get("revisao", 0),
        })
        saida["conversar_depois"] = {"http": r.status_code, "corpo": (r.json() if r.status_code != 500 else {})}
        saida["pessoa_apos_luta"] = {k: _pessoas(fim).get(pid, {}).get(k) for k in ("disposicao", "mercadoria")}
    return saida


def cenario_impossivel(client: TestClient, sid: str) -> dict:
    hp = _estado(sid)["hp"]
    t = turno(client, sid, "Eu acendo uma fogueira no fundo do mar, usando só um graveto molhado.")
    usadas = [c for c in t["ferramentas"] if c["nome"] == "resolver_intencao"]
    return {
        "turno": t, "hp_antes": hp, "hp_depois": _estado(sid)["hp"],
        "usou_impossivel": any('"impossivel"' in str(c["args"]) for c in usadas),
        "usou_resolver_intencao": bool(usadas),
    }


def cenario_desvio(client: TestClient, sid: str) -> dict:
    antes = _estado(sid)
    minutos_antes = (antes["mundo"].get("mundo") or {}).get("minutos")
    t = turno(client, sid, "Esqueço a missão por hoje: vou passar a tarde inteira nadando no lago, sem pressa.")
    depois = _estado(sid)
    texto = t["narrativa"].lower()
    return {
        "turno": t,
        "minutos_antes": minutos_antes, "minutos_depois": (depois["mundo"].get("mundo") or {}).get("minutos"),
        "recusou": any(p in texto for p in ("não pode", "não é possível", "não consegue", "primeiro você deve")),
        "puxou_de_volta": any(p in texto for p in ("missão", "objetivo", "voltar", "precisa", "deve")),
    }


def cenario_perfis(client: TestClient, sid: str) -> dict:
    e = _estado(sid)
    if e["combate"].get("ativo"):
        return {"pulado": "combate ainda ativo"}
    t = turno(client, sid, "Diante de mim surge o Duque Valmir, um nobre arrogante e orgulhoso. "
                           "Eu o desafio para um duelo e começo a luta contra ele.")
    meio = _estado(sid)
    chamada = next((c for c in t["ferramentas"] if c["nome"] == "iniciar_combate"), None)
    return {
        "turno": t, "combate_abriu": bool(meio["combate"].get("ativo")),
        "chamou_iniciar_combate": bool(chamada),
        "passou_perfis": bool(chamada and "perfis" in str(chamada["args"])),
        "inimigos": [{"nome": i.get("nome"), "arquetipo": i.get("arquetipo"), "papel": i.get("papel"),
                      "temperamento": i.get("temperamento"), "persona": bool(i.get("persona"))}
                     for i in meio["combate"].get("inimigos", [])],
    }


CENARIOS = {
    "violencia": cenario_violencia,
    "impossivel": cenario_impossivel,
    "desvio": cenario_desvio,
    "perfis": cenario_perfis,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cenarios", default=",".join(CENARIOS))
    ap.add_argument("--teto", type=int, default=16)
    ap.add_argument("--saida", default="")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        usuario = Usuario(email="ao-vivo@mestre.ia", email_verificado=True)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        uid = usuario.id

    def _usuario():
        with SessionLocal() as db:
            return db.get(Usuario, uid)

    app.dependency_overrides[get_current_user] = _usuario
    _instrumentar(args.teto)
    client = TestClient(app)
    criado = client.post("/create_character", json={
        "nome": "Teste", "raca": "Humano", "classe": "Guerreiro", "alinhamento": "Neutro",
        "background": "Andarilho", "objetivo": "Descobrir o que aconteceu com minha vila",
        "atributos": {"forca": 15, "destreza": 14, "constituicao": 13, "inteligencia": 12, "sabedoria": 10, "carisma": 8},  # noqa: E501
    })
    if criado.status_code != 200:
        print("falha ao criar personagem:", criado.status_code, criado.text[:300])
        sys.exit(1)
    sid = criado.json()["session_id"]

    relatorio: dict = {"cenarios": {}, "requisicoes": REQUISICOES}
    nomes = [n.strip() for n in args.cenarios.split(",") if n.strip()]
    for i, nome in enumerate(nomes):
        if i:
            print(f"-- aguardando {PAUSA_ENTRE_TURNOS}s (teto de tokens por minuto)", flush=True)
            time.sleep(PAUSA_ENTRE_TURNOS)
        print(f"== {nome}", flush=True)
        try:
            relatorio["cenarios"][nome] = CENARIOS[nome](client, sid)
        except TetoDeRequisicoes as e:
            relatorio["cenarios"][nome] = {"interrompido": str(e)}
            break
        except Exception as e:  # noqa: BLE001 — o relatório precisa sair mesmo com falha de um cenário
            relatorio["cenarios"][nome] = {"excecao": f"{type(e).__name__}: {e}"}
        print(json.dumps(relatorio["cenarios"][nome], ensure_ascii=False, indent=2)[:1800], flush=True)
        if args.saida:
            Path(args.saida).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    relatorio["total_requisicoes"] = len(REQUISICOES)
    relatorio["falhas"] = sum(1 for r in REQUISICOES if not r["ok"])
    if args.saida:
        Path(args.saida).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrequisições: {len(REQUISICOES)} (falhas: {relatorio['falhas']})")


if __name__ == "__main__":
    main()
