"""Isola os testes do banco de save real (rpg_save.db) e garante que o
pacote `app` seja importável independente de onde o pytest for chamado.

Antes da Etapa 2, isto exigia um `os.chdir` para um diretório temporário
(DATABASE_URL era relativo ao cwd do processo — ver Backend/database.py
na versão anterior). Agora `app.infra.settings.Settings.database_url` é
absoluto por padrão; aqui só sobrescrevemos via variável de ambiente
*antes* de qualquer módulo de app ser importado, para um arquivo sqlite
temporário — sem tocar no save de verdade nem precisar de chdir.
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_tmp_db = Path(tempfile.mkdtemp(prefix="mestre_ia_test_")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"


def pytest_configure(config):
    from app.infra.db import Base, SessionLocal, engine, garantir_usuario_local

    Base.metadata.create_all(bind=engine)
    # O TestClient só roda o lifespan (que faria isso) dentro de um `with`;
    # os testes usam a forma direta, então garantimos aqui.
    db = SessionLocal()
    try:
        garantir_usuario_local(db)
    finally:
        db.close()
