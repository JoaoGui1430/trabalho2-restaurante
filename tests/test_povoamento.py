"""Povoamento sobre cadastros preexistentes, sem alterar sua situação."""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, select

from app import povoamento
from app.database import engine
from app.models import Categoria, Garcom, ItemPedido, Mesa, Pedido, Produto


def contagens():
    with Session(engine) as session:
        return {
            tabela.name: len(session.execute(tabela.select()).all())
            for tabela in SQLModel.metadata.sorted_tables
        }


@pytest.mark.parametrize(
    "categoria_ativa,produto_ativo", [(True, False), (False, True)]
)
def test_povoamento_respeita_produto_e_categoria_inativos(
    categoria_ativa, produto_ativo
):
    with Session(engine) as session:
        categoria = Categoria(nome="Entradas", ativo=categoria_ativa)
        session.add(categoria)
        session.flush()
        produto = Produto(
            nome="Bruschetta",
            categoria_id=categoria.id,
            preco_centavos=2200,
            ativo=produto_ativo,
            disponivel=True,
        )
        session.add(produto)
        session.commit()
        categoria_id, produto_id = categoria.id, produto.id

    assert povoamento.main() == 0
    with Session(engine) as session:
        assert session.get(Categoria, categoria_id).ativo == categoria_ativa
        assert session.get(Produto, produto_id).ativo == produto_ativo
        itens = session.exec(select(ItemPedido)).all()
        assert itens
        assert all(
            item.produto.ativo
            and item.produto.disponivel
            and item.produto.categoria.ativo
            for item in itens
        )
        assert len(session.exec(select(Pedido)).all()) == 51


@pytest.mark.parametrize("tipo", ["mesas", "garcons", "categorias"])
def test_povoamento_informa_falta_de_cadastros_ativos_e_reverte(tipo, capsys):
    with Session(engine) as session:
        if tipo == "mesas":
            session.add_all(
                [
                    Mesa(numero=n, capacidade=c, ativo=False)
                    for n, c, _ in povoamento.MESAS
                ]
            )
        elif tipo == "garcons":
            session.add_all(
                [
                    Garcom(nome=n, matricula=m, ativo=False)
                    for n, m, _ in povoamento.GARCONS
                ]
            )
        else:
            session.add_all(
                [
                    Categoria(nome=n, descricao=d, ativo=False)
                    for n, d in povoamento.CATEGORIAS
                ]
            )
        session.commit()
    antes = contagens()
    assert povoamento.main() == 1
    assert "Nada foi gravado" in capsys.readouterr().out
    assert contagens() == antes


def test_povoamento_com_duas_mesas_ativas():
    with Session(engine) as session:
        session.add_all(
            [
                Mesa(numero=n, capacidade=c, ativo=n in (1, 2))
                for n, c, _ in povoamento.MESAS
            ]
        )
        session.commit()
    assert povoamento.main() == 0
    antes = contagens()
    assert antes["pedido"] == 51
    assert povoamento.main() == 0
    assert contagens() == antes


def test_povoamento_com_um_produto_vendavel():
    with Session(engine) as session:
        povoamento.povoar_cadastros(session)
        produtos = session.exec(select(Produto).order_by(Produto.id)).all()
        produto_id = produtos[0].id
        for produto in produtos[1:]:
            produto.ativo = False
            session.add(produto)
        session.commit()
    assert povoamento.main() == 0
    with Session(engine) as session:
        assert len(session.exec(select(Pedido)).all()) == 51
        assert all(item.produto_id == produto_id for item in session.exec(select(ItemPedido)).all())


def test_povoamento_sem_conexao_retorna_erro_controlado():
    with socket.socket() as conexao:
        conexao.bind(("127.0.0.1", 0))
        porta = conexao.getsockname()[1]
    ambiente = {
        **os.environ,
        "DATABASE_URL": f"postgresql+psycopg://teste:senha@127.0.0.1:{porta}/indisponivel",
    }
    resultado = subprocess.run(
        [sys.executable, "-m", "app.povoamento"],
        cwd=Path(__file__).resolve().parents[1],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert resultado.returncode == 1
    assert "Falha ao povoar o banco" in resultado.stdout
    assert "Traceback" not in resultado.stderr
