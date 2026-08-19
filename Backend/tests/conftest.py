"""
Isola os testes do banco de save real (rpg_save.db) e garante que os
módulos do Backend sejam importáveis independente de onde o pytest for
chamado.

api.py cria o banco com um caminho relativo (`sqlite:///./rpg_save.db`,
ver Backend/database.py:5) — relativo ao diretório de trabalho do
processo, não ao arquivo. Sem este isolamento, rodar os testes a partir
da raiz do repositório criaria (ou tocaria) o banco de verdade. A
correção definitiva — configuração tipada com caminho absoluto — é
escopo da Etapa 2 (ver PLANO_MESTRE.md, seção "Arquitetura auditável").
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.chdir(tempfile.mkdtemp(prefix="mestre_ia_test_"))
