"""F14: evolução e retorno de versão preservam pedidos e seus vínculos."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


RAIZ = Path(__file__).resolve().parents[1]
TABELAS = (
    "categoria", "produto", "mesa", "garcom", "pedido", "item_pedido", "fechamento_conta",
)


@pytest.fixture
def banco_evolucao(tmp_path):
    configuracao = os.getenv("TESTE_DATABASE_URL")
    administrador = None
    esquema = None
    if configuracao and make_url(configuracao).get_backend_name() == "postgresql":
        administrador = create_engine(configuracao, hide_parameters=True)
        esquema = "verificacao_migracao_" + uuid4().hex
        with administrador.begin() as conexao:
            conexao.execute(CreateSchema(esquema))
        url = make_url(configuracao).update_query_dict({"options": "-csearch_path=" + esquema})
    else:
        url = make_url(f"sqlite:///{(tmp_path / 'evolucao.db').as_posix()}")

    engine = create_engine(url, hide_parameters=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def ativar_chaves_estrangeiras(conexao, registro):
            cursor = conexao.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    try:
        yield engine
    finally:
        engine.dispose()
        if administrador is not None:
            with administrador.begin() as conexao:
                conexao.execute(DropSchema(esquema, cascade=True))
            administrador.dispose()


def executar_alembic(url, *argumentos):
    ambiente = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", *argumentos],
        cwd=RAIZ,
        env=ambiente,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def registrar_venda(engine):
    with engine.begin() as conexao:
        conexao.execute(text(
            "INSERT INTO categoria (id, nome, ativo) VALUES (1, 'Pratos', :ativo)"
        ), {"ativo": True})
        conexao.execute(text(
            "INSERT INTO produto "
            "(id, nome, preco_centavos, disponivel, ativo, categoria_id) "
            "VALUES (1, 'Prato feito', 1500, :disponivel, :ativo, 1)"
        ), {"disponivel": True, "ativo": True})
        conexao.execute(text(
            "INSERT INTO mesa (id, numero, capacidade, ativo) VALUES (1, 1, 4, :ativo)"
        ), {"ativo": True})
        conexao.execute(text(
            "INSERT INTO garcom (id, nome, matricula, ativo) "
            "VALUES (1, 'Maria Souza', 'G1', :ativo)"
        ), {"ativo": True})
        conexao.execute(text(
            "INSERT INTO pedido "
            "(id, modalidade, mesa_id, garcom_id, status, criado_em, encerrado_em) "
            "VALUES (1, 'mesa', 1, 1, 'finalizado', "
            "'2026-11-01 10:00:00', '2026-11-01 11:00:00')"
        ))
        conexao.execute(text(
            "INSERT INTO item_pedido "
            "(id, pedido_id, produto_id, quantidade, preco_unitario_centavos, status_preparo) "
            "VALUES (1, 1, 1, 2, 1500, 'pronto')"
        ))
        conexao.execute(text(
            "INSERT INTO fechamento_conta (id, pedido_id, fechado_em, total_centavos) "
            "VALUES (1, 1, '2026-11-01 11:00:00', 3000)"
        ))


def consultar_registros(engine):
    with engine.connect() as conexao:
        registros = {
            tabela: [dict(linha) for linha in conexao.execute(
                text(f"SELECT * FROM {tabela} ORDER BY id")
            ).mappings()]
            for tabela in TABELAS
        }
        if engine.dialect.name == "sqlite":
            assert conexao.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert conexao.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    for pedido in registros["pedido"]:
        pedido.pop("observacao", None)
    return registros


def test_revisao_0002_preserva_registros_existentes(banco_evolucao):
    engine = banco_evolucao
    url = engine.url
    executar_alembic(url, "upgrade", "0001")
    registrar_venda(engine)
    anteriores = consultar_registros(engine)
    assert all(len(registros) == 1 for registros in anteriores.values())
    assert "observacao" not in {coluna["name"] for coluna in inspect(engine).get_columns("pedido")}

    executar_alembic(url, "upgrade", "0002")
    assert consultar_registros(engine) == anteriores
    with engine.begin() as conexao:
        assert conexao.execute(text("SELECT observacao FROM pedido WHERE id = 1")).scalar_one() is None
        conexao.execute(text(
            "UPDATE pedido SET observacao = :observacao WHERE id = 1"
        ), {"observacao": "Mesa perto da janela"})
    with engine.connect() as conexao:
        assert conexao.execute(text("SELECT observacao FROM pedido WHERE id = 1")).scalar_one() == "Mesa perto da janela"
    executar_alembic(url, "check")

    executar_alembic(url, "downgrade", "0001")
    assert "observacao" not in {coluna["name"] for coluna in inspect(engine).get_columns("pedido")}
    assert consultar_registros(engine) == anteriores

    executar_alembic(url, "upgrade", "0002")
    atuais = consultar_registros(engine)
    assert atuais == anteriores
    with engine.connect() as conexao:
        assert conexao.execute(text("SELECT observacao FROM pedido WHERE id = 1")).scalar_one() is None
    assert atuais["item_pedido"][0]["quantidade"] * atuais["item_pedido"][0]["preco_unitario_centavos"] == 3000
    assert atuais["fechamento_conta"][0]["total_centavos"] == 3000
    executar_alembic(url, "check")
