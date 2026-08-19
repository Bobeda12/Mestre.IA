"""Cliente de embeddings via `fastembed` (ONNX Runtime) — um único ponto de
carregamento do modelo, substituível em teste pelo mesmo padrão de
`llm_client.client`: os módulos que usam embeddings (services/hybrid_search.py
e consumidores) recebem `embed_fn` como parâmetro injetável, para os testes
passarem uma função determinística e barata em vez de carregar o modelo real.

Modelo multilíngue (o jogo é em português, a maioria dos modelos pequenos de
embedding do fastembed é treinada só em inglês) — ver ADR-0010 para a
comparação com `sentence-transformers` (mesma família de modelo, runtime
mais leve, sem depender de PyTorch)."""

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_modelo: TextEmbedding | None = None


def _carregar() -> TextEmbedding:
    global _modelo
    if _modelo is None:
        _modelo = TextEmbedding(model_name=MODEL_NAME)
    return _modelo


def embed(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []
    return [vetor.tolist() for vetor in _carregar().embed(textos)]


def embed_um(texto: str) -> list[float]:
    return embed([texto])[0]
