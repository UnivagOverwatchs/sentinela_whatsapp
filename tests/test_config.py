"""Leitura do .env: comentário no fim da linha não pode mudar o valor (bug real no Docker Compose)."""
from notificador.config import Config


def test_comentario_no_fim_da_linha_e_ignorado(monkeypatch):
    monkeypatch.setenv("NOTIF_MODO_TESTE", "true      # true: resolve e registra, mas não envia")
    monkeypatch.setenv("NOTIF_JANELA_MIN", "15         # só alertas dos últimos N minutos")
    monkeypatch.setenv("WHATSAPP_SESSAO", "ABCD  # sessão")
    cfg = Config()
    assert cfg.modo_teste is True
    assert cfg.janela_min == 15
    assert cfg.sessao == "ABCD"


def test_valor_com_hash_sem_espaco_e_mantido(monkeypatch):
    monkeypatch.setenv("WHATSAPP_API_KEY", "abc#123")  # '#' faz parte do valor
    assert Config().api_key == "abc#123"
