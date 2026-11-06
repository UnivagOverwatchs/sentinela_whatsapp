"""
banco.py - Acesso ao PostgreSQL do Sentinela.

Lê: alerta, evento, camera, contato_emergencia (tabelas do Sentinela; não altera nenhuma delas).
Escreve: notificacao_whatsapp (tabela própria deste serviço, criada se não existir).

notificacao_whatsapp tem UNIQUE(alerta_id, contato_id): cada contato recebe no máximo uma
mensagem por alerta, mesmo se o serviço reiniciar ou houver duas instâncias rodando.

Status:
    ENVIADO          mensagem entregue à API do WhatsApp
    ERRO             falhou (rede, API fora do ar...) -> tenta de novo até NOTIF_MAX_TENTATIVAS
    SEM_WHATSAPP     o número não tem WhatsApp (definitivo)
    NUMERO_INVALIDO  telefone não pôde ser normalizado, ex.: 192 (definitivo)
    TESTE            modo teste: tudo foi resolvido, mas nada foi enviado
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

ESQUEMA = """
CREATE TABLE IF NOT EXISTS notificacao_whatsapp (
    id            SERIAL PRIMARY KEY,
    alerta_id     INTEGER NOT NULL REFERENCES alerta(id) ON DELETE CASCADE,
    contato_id    INTEGER NOT NULL REFERENCES contato_emergencia(id) ON DELETE CASCADE,
    chat_id       VARCHAR(40),
    status        VARCHAR(16) NOT NULL
                  CHECK (status IN ('ENVIADO', 'ERRO', 'SEM_WHATSAPP', 'NUMERO_INVALIDO', 'TESTE')),
    tentativas    INTEGER NOT NULL DEFAULT 1,
    erro          TEXT,
    atualizado_em TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (alerta_id, contato_id)
)
"""

# Para cada alerta PENDENTE recente x cada contato: o que ainda não foi tratado
# ou falhou com tentativas restantes. Alerta resolvido no painel deixa de ser enviado.
_SQL_PENDENCIAS = """
SELECT a.id AS alerta_id, e.tipo, e.ocorrido_em, e.imagem,
       c.nome AS camera_nome, c.local AS camera_local,
       ct.id AS contato_id, ct.nome AS contato_nome, ct.telefone,
       COALESCE(n.tentativas, 0) AS tentativas
  FROM alerta a
  JOIN evento e  ON e.id = a.evento_id
  JOIN camera c  ON c.id = e.camera_id
 CROSS JOIN contato_emergencia ct
  LEFT JOIN notificacao_whatsapp n ON n.alerta_id = a.id AND n.contato_id = ct.id
 WHERE a.status = 'PENDENTE'
   AND e.ocorrido_em >= %s
   AND (n.id IS NULL OR (n.status = 'ERRO' AND n.tentativas < %s))
 ORDER BY a.id, ct.id
"""

_SQL_REGISTRAR = """
INSERT INTO notificacao_whatsapp (alerta_id, contato_id, chat_id, status, erro)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (alerta_id, contato_id) DO UPDATE
   SET chat_id = EXCLUDED.chat_id,
       status = EXCLUDED.status,
       erro = EXCLUDED.erro,
       tentativas = notificacao_whatsapp.tentativas + 1,
       atualizado_em = now()
"""


class Banco:
    def __init__(self, conninfo: str = ""):
        # conninfo vazio: o psycopg usa PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD do ambiente.
        self._conninfo = conninfo
        self._con: Optional[psycopg.Connection] = None
        self._conectar()
        self._con.execute(ESQUEMA)

    def _conectar(self) -> None:
        self._con = psycopg.connect(self._conninfo, autocommit=True, row_factory=dict_row, connect_timeout=10)

    def _executar(self, sql: str, params: tuple = ()):
        """Executa reconectando uma vez se a conexão com o servidor tiver caído."""
        for tentativa in (1, 2):
            try:
                return self._con.execute(sql, params)
            except (psycopg.OperationalError, psycopg.InterfaceError):
                if tentativa == 2:
                    raise
                self._conectar()

    @property
    def descricao(self) -> str:
        return f"{self._con.info.host}/{self._con.info.dbname}"

    def pendencias(self, janela_min: int, max_tentativas: int) -> List[Dict[str, Any]]:
        # Horário de corte calculado aqui: o Sentinela grava ocorrido_em no horário local desta máquina,
        # e o relógio/fuso do servidor do banco pode ser outro.
        corte = datetime.now() - timedelta(minutes=janela_min)
        return self._executar(_SQL_PENDENCIAS, (corte, max_tentativas)).fetchall()

    def registrar(self, alerta_id: int, contato_id: int, status: str,
                  chat_id: Optional[str] = None, erro: Optional[str] = None) -> None:
        self._executar(_SQL_REGISTRAR, (alerta_id, contato_id, chat_id, status, (erro or "")[:500] or None))

    def fechar(self) -> None:
        if self._con:
            self._con.close()
