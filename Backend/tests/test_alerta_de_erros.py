from app.infra import erros


def test_sem_dsn_nao_liga_nada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(erros.settings, "sentry_dsn", None)
    monkeypatch.setattr(erros.sentry_sdk, "init", lambda **kw: chamadas.append(kw))
    assert erros.iniciar_alerta_de_erros() is False
    assert chamadas == []


def test_com_dsn_liga_sem_vazar_texto_do_jogador(monkeypatch):
    chamadas = []
    monkeypatch.setattr(erros.settings, "sentry_dsn", "https://chave@exemplo.ingest.sentry.io/1")
    monkeypatch.setattr(erros.sentry_sdk, "init", lambda **kw: chamadas.append(kw))
    assert erros.iniciar_alerta_de_erros() is True
    assert chamadas[0]["send_default_pii"] is False
    assert chamadas[0]["max_request_body_size"] == "never"
    assert chamadas[0]["traces_sample_rate"] == 0.0
