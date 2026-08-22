"""Cliente de embeddings via `fastembed` (ONNX Runtime) — um único ponto de
carregamento do modelo, substituível em teste pelo mesmo padrão de
`llm_client.client`: os módulos que usam embeddings (services/hybrid_search.py
e consumidores) recebem `embed_fn` como parâmetro injetável, para os testes
passarem uma função determinística e barata em vez de carregar o modelo real.

Modelo multilíngue (o jogo é em português, a maioria dos modelos pequenos de
embedding do fastembed é treinada só em inglês) — ver ADR-0010 para a
comparação com `sentence-transformers` (mesma família de modelo, runtime
mais leve, sem depender de PyTorch)."""

from pathlib import Path

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Etapa 10 (A-6) — dentro de `/app` (parte normal da imagem), não em `/tmp`
# (o default do fastembed): alguns runtimes de container montam um tmpfs
# próprio sobre `/tmp`, o que apagaria um cache baixado em build time antes
# do container sequer iniciar. `fastembed_cache` (sem ponto na frente) é um
# diretório comum da imagem, sem essa armadilha — achado ao vivo: o nome
# COM ponto falha ao criar na primeira vez no Windows local, quando o
# projeto vive dentro de uma pasta sincronizada pelo OneDrive (não
# reproduz dentro do container Linux, só no host Windows local).
CACHE_DIR = str(Path(__file__).resolve().parents[2] / "fastembed_cache")

_modelo: TextEmbedding | None = None


def carregar_modelo() -> TextEmbedding:
    """Carrega (ou devolve, se já carregado) o modelo — público de
    propósito: o `lifespan` do FastAPI (`app/main.py`) chama isto no boot,
    pra pagar o custo do primeiro carregamento antes do primeiro pedido de
    um jogador, não durante ele. Com o cache já populado em build time
    (`Dockerfile`), isto vira leitura de disco, não download."""
    global _modelo
    if _modelo is None:
        _modelo = TextEmbedding(model_name=MODEL_NAME, cache_dir=CACHE_DIR)
    return _modelo


def embed(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []
    return [vetor.tolist() for vetor in carregar_modelo().embed(textos)]


def embed_um(texto: str) -> list[float]:
    return embed([texto])[0]
