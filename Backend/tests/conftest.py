"""Isola os testes do banco de save real (rpg_save.db) e garante que o
pacote `app` seja importável independente de onde o pytest for chamado.

Antes da Etapa 2, isto exigia um `os.chdir` para um diretório temporário
(DATABASE_URL era relativo ao cwd do processo — ver Backend/database.py
na versão anterior). Agora `app.infra.settings.Settings.database_url` é
absoluto por padrão; aqui só sobrescrevemos via variável de ambiente
*antes* de qualquer módulo de app ser importado, para um arquivo sqlite
temporário — sem tocar no save de verdade nem precisar de chdir.
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_tmp_db = Path(tempfile.mkdtemp(prefix="mestre_ia_test_")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"


def pytest_configure(config):
    from app.infra.db import Base, engine

    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _usuario_autenticado():
    """A maioria dos testes (criação de personagem, chat, memória...) não é
    sobre autenticação — não faz sentido repetir registro/login em cada um.
    Por padrão, todo teste roda como um usuário já logado, via dependency
    override do FastAPI. `tests/test_auth.py` é quem desliga isto
    explicitamente, porque é o fluxo de login em si que ele testa."""
    from app.infra.db import SessionLocal, Usuario
    from app.main import app
    from app.services.auth import get_current_user

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.email == "teste@mestre.ia").first()
        if usuario is None:
            usuario = Usuario(email="teste@mestre.ia")
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
        usuario_id = usuario.id
    finally:
        db.close()

    def _usuario_atual() -> Usuario:
        db2 = SessionLocal()
        try:
            usuario = db2.get(Usuario, usuario_id)
            assert usuario is not None  # criado logo acima; só pode ter sumido se o teste apagou o banco
            return usuario
        finally:
            db2.close()

    app.dependency_overrides[get_current_user] = _usuario_atual
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _embedding_falso(texto: str) -> list[float]:
    """Hash determinístico, sem semântica real — só para nenhum teste de
    integração (ex. TestClient batendo em /chat) precisar baixar/carregar o
    modelo real de embeddings (Etapa 5). Relevância de busca é
    responsabilidade de tests/test_hybrid_search.py, que sempre passa seu
    próprio `embed_fn` explícito."""
    digest = hashlib.sha256(texto.encode("utf-8")).digest()
    return [b / 255 for b in digest[:16]]


@pytest.fixture(autouse=True)
def _embeddings_sem_rede(monkeypatch):
    from app.infra import embeddings

    monkeypatch.setattr(embeddings, "embed_um", _embedding_falso)
    monkeypatch.setattr(embeddings, "embed", lambda textos: [_embedding_falso(t) for t in textos])


@pytest.fixture(autouse=True)
def _rate_limit_zerado():
    """O `Limiter` do slowapi (Etapa 9, app/infra/rate_limit.py) guarda
    contagem em memória por todo o processo — sem isto, os ~214 testes do
    processo inteiro dividiriam o mesmo orçamento de "10/minuto" em
    `/auth/login` (todos batem do mesmo IP de teste), e testes no fim da
    suíte começariam a levar 429 por causa de testes completamente
    não relacionados no início."""
    from app.infra.rate_limit import limiter

    limiter.reset()
    yield
