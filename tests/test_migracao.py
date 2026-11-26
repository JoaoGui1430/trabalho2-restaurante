"""F14: a revisão 0002 evolui um banco que já tem dados, sem perdê-los."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_revisao_0002_preserva_registros_existentes(tmp_path):
    banco = tmp_path / "evolucao.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{banco.as_posix()}"}

    def alembic(*args):
        resultado = subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=RAIZ, env=env, capture_output=True, text=True
        )
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    alembic("upgrade", "0001")
    conexao = sqlite3.connect(banco)
    conexao.execute("insert into garcom(nome, matricula, ativo) values ('Maria Souza', 'G1', 1)")
    conexao.execute(
        "insert into pedido(modalidade, garcom_id, status, criado_em) "
        "values ('retirada', 1, 'aberto', '2026-11-01 10:00:00')"
    )
    conexao.commit()
    colunas_antes = {linha[1] for linha in conexao.execute("pragma table_info(pedido)")}
    conexao.close()
    assert "observacao" not in colunas_antes

    alembic("upgrade", "head")
    conexao = sqlite3.connect(banco)
    colunas = {linha[1] for linha in conexao.execute("pragma table_info(pedido)")}
    pedido = conexao.execute("select id, status, observacao from pedido").fetchall()
    conexao.close()
    assert "observacao" in colunas
    assert pedido == [(1, "aberto", None)]

    # O modelo e o banco migrado não podem divergir.
    alembic("check")
    alembic("downgrade", "0001")
    alembic("upgrade", "head")
