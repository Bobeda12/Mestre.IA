"""Aberturas e intenções de campanha estáveis, inclusive sem provedor de IA.

A semente seleciona pessoas e tensões uma vez. O catálogo é premissa, não
destino: os atos descrevem perguntas que podem ser resolvidas de várias formas.
"""


TEMPERAMENTOS = ["Justo", "Épico", "Implacável"]
DIFICULDADES = ["História", "Normal", "Difícil"]


def catalogo_aventura() -> dict:
    """Catálogo que a criação de personagem oferece. As 8 aberturas
    roteirizadas (`INICIOS`) e o esqueleto de Atos saíram na Fase 0 do
    plano "jogo completo" (08/09/2026, ADR-0032): toda campanha nasce da
    origem emergente (`services/emergent_start.py`) e o mundo cresce pelas
    ferramentas do Mundo Vivo, sem roteiro prévio."""
    return {"temperamentos": TEMPERAMENTOS.copy(), "dificuldades": DIFICULDADES.copy()}
