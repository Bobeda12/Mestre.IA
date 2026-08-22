"""Testa app/services/guardrail.py — a checagem heurística de item fora do
inventário, inimigo morto tratado como vivo e local errado, mais o reprompt
único de correção. Não é um teste de qualidade de prosa (isso seria
LLM-as-judge, Etapa 6) — só confere que os três gatilhos disparam e que a
correção usa o resultado do modelo quando disponível."""

from app.domain.state import CombatState, Inimigo, WorldState
from app.infra.db import Personagem
from app.infra.llm_client import ErroMestre
from app.services import guardrail


def _heroi(inventario=None) -> Personagem:
    return Personagem(
        nome="TesteGuardrail", hp_atual=10, hp_max=10, defesa=15, ouro=10, atributos={}, inventario=inventario or []
    )


class TestValidarNarrativa:
    def test_narrativa_limpa_nao_gera_violacao(self):
        heroi = _heroi(inventario=["Cimitarra"])
        c_state = CombatState(ativo=True, inimigos=[Inimigo(nome="Goblin", hp=5, max_hp=7, ca=15)])
        w_state = WorldState(local="Vila de Phandalin")
        violacoes = guardrail.validar_narrativa(
            "Você avança pela vila com a cimitarra em punho, atento ao goblin ferido.", heroi, c_state, w_state
        )
        assert violacoes == []

    def test_item_fora_do_inventario_e_detectado(self):
        heroi = _heroi(inventario=["Cimitarra"])
        c_state = CombatState()
        w_state = WorldState(local="Vila de Phandalin")
        violacoes = guardrail.validar_narrativa(
            "Você ergue sua espada longa e ataca.", heroi, c_state, w_state
        )
        assert any("Espada Longa" in v for v in violacoes)

    def test_inimigo_morto_tratado_como_vivo_e_detectado(self):
        heroi = _heroi()
        c_state = CombatState(ativo=True, inimigos=[Inimigo(nome="Goblin", hp=0, max_hp=7, ca=15)])
        w_state = WorldState(local="Vila de Phandalin")
        violacoes = guardrail.validar_narrativa(
            "O goblin ataca mais uma vez, furioso.", heroi, c_state, w_state
        )
        assert any("Goblin" in v for v in violacoes)

    def test_local_errado_e_detectado(self):
        heroi = _heroi()
        c_state = CombatState()
        w_state = WorldState(local="Vila de Phandalin")
        violacoes = guardrail.validar_narrativa(
            "Você chega a Floresta das Sombras, entre árvores retorcidas.", heroi, c_state, w_state
        )
        assert any("Floresta das Sombras" in v for v in violacoes)


class TestLimparFormatacao:
    """Etapa 10 (A-7) — o prompt já pede prosa sem markdown; isto é a
    segunda linha de defesa, determinística, aplicada antes de persistir."""

    def test_texto_sem_markdown_passa_intacto(self):
        texto = "Você avança pela vila, atento ao goblin ferido."
        assert guardrail.limpar_formatacao(texto) == texto

    def test_remove_negrito(self):
        assert guardrail.limpar_formatacao("O golpe é **certeiro** e brutal.") == "O golpe é certeiro e brutal."

    def test_remove_italico(self):
        assert guardrail.limpar_formatacao("Um *sussurro* ecoa nas pedras.") == "Um sussurro ecoa nas pedras."

    def test_remove_titulo(self):
        assert guardrail.limpar_formatacao("# A Emboscada\nVocês avançam.") == "A Emboscada\nVocês avançam."

    def test_remove_lista(self):
        texto = "Você vê:\n- uma tocha\n- um baú\n2. um cadáver"
        assert guardrail.limpar_formatacao(texto) == "Você vê:\numa tocha\num baú\num cadáver"

    def test_remove_bloco_de_codigo_mantendo_o_texto(self):
        assert guardrail.limpar_formatacao("```\nregras\n```") == "\nregras\n"

    def test_remove_codigo_inline(self):
        assert guardrail.limpar_formatacao("Ele sussurra `a senha`.") == "Ele sussurra a senha."

    def test_nao_apaga_asterisco_isolado_sem_par(self):
        # Heurística, não parser de markdown de verdade — um `*` solto
        # (não é marcação, é só um caractere) não deveria sumir do texto.
        assert guardrail.limpar_formatacao("3 * 4 = 12") == "3 * 4 = 12"


class _MensagemFalsa:
    def __init__(self, content: str) -> None:
        self.content = content


class _RespostaFalsa:
    def __init__(self, content: str) -> None:
        self.choices = [type("Choice", (), {"message": _MensagemFalsa(content)})()]


class TestCorrigirNarrativa:
    def test_usa_a_narrativa_corrigida_do_modelo(self, monkeypatch):
        monkeypatch.setattr(guardrail, "chamar_com_fallback", lambda msgs: _RespostaFalsa("Versão corrigida."))
        resultado = guardrail.corrigir_narrativa("Versão original.", ["item fora do inventário"], [])
        assert resultado == "Versão corrigida."

    def test_erro_mestre_mantem_a_narrativa_original(self, monkeypatch):
        def _levanta(msgs):
            raise ErroMestre("indisponível")

        monkeypatch.setattr(guardrail, "chamar_com_fallback", _levanta)
        resultado = guardrail.corrigir_narrativa("Versão original.", ["item fora do inventário"], [])
        assert resultado == "Versão original."
