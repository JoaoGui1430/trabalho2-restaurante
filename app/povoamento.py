"""Povoamento inicial com dados de demonstração.

Uso, depois de `alembic upgrade head`:

    python -m app.povoamento

O script pode ser repetido. Cadastros já existentes (pela chave única de cada um)
são mantidos, e os pedidos só são criados se a tabela de pedidos estiver vazia.
Nada é apagado.
"""

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    Categoria,
    FechamentoConta,
    Garcom,
    ItemPedido,
    Mesa,
    ModalidadePedido,
    Pedido,
    Produto,
    StatusPedido,
    StatusPreparo,
)

CATEGORIAS = [
    ("Entradas", "Porções para começar a refeição."),
    ("Pratos principais", "Pratos quentes do dia a dia."),
    ("Bebidas", "Sucos, refrigerantes e águas."),
    ("Sobremesas", "Doces e sobremesas geladas."),
]

# nome, categoria, preço atual em centavos, disponível
PRODUTOS = [
    ("Bruschetta", "Entradas", 2200, True),
    ("Pastel de queijo", "Entradas", 1800, True),
    ("Batata frita", "Entradas", 2600, True),
    ("Bife acebolado", "Pratos principais", 4800, True),
    ("Frango grelhado", "Pratos principais", 4200, True),
    ("Macarrão ao molho", "Pratos principais", 3600, True),
    ("Feijoada", "Pratos principais", 5200, True),
    ("Suco de laranja", "Bebidas", 1200, True),
    ("Refrigerante lata", "Bebidas", 900, True),
    ("Água mineral", "Bebidas", 600, True),
    ("Cerveja long neck", "Bebidas", 1400, True),
    ("Pudim", "Sobremesas", 1500, True),
    ("Sorvete", "Sobremesas", 1300, True),
    ("Torta de limão", "Sobremesas", 1700, False),  # indisponível, para demonstração
]

# Preços praticados antes de um reajuste. Entram nos pedidos mais antigos e mostram
# que o preço aplicado em cada linha não muda quando o cardápio muda.
PRECOS_ANTIGOS = {
    "Bife acebolado": 4400,
    "Suco de laranja": 1000,
    "Cerveja long neck": 1200,
    "Feijoada": 4800,
}
DIAS_PRECO_ANTIGO = 10

# (número, capacidade, ativa)
MESAS = [(1, 2, True), (2, 4, True), (3, 4, True), (4, 6, True), (5, 6, True),
         (6, 8, True), (7, 2, True), (8, 10, True), (9, 4, False)]

# (nome, matrícula, ativo)
GARCONS = [
    ("Ana Beatriz Lima", "G001", True),
    ("Carlos Eduardo Rocha", "G002", True),
    ("Fernanda Alves", "G003", True),
    ("Marcos Vinícius Dias", "G004", False),
]

OBSERVACOES = [
    "Sem cebola.",
    "Cliente alérgico a amendoim.",
    "Trazer a sobremesa junto com o prato.",
    "Retirada às 20h.",
]

TOTAL_FINALIZADOS = 45
TOTAL_CANCELADOS = 3


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def obter_ou_criar(session: Session, modelo, chave: dict, dados: dict):
    """Retorna (registro, criado). A chave identifica o registro pela coluna única."""
    existente = session.exec(select(modelo).filter_by(**chave)).first()
    if existente is not None:
        return existente, False
    registro = modelo(**chave, **dados)
    session.add(registro)
    session.flush()
    return registro, True


def povoar_cadastros(session: Session) -> dict[str, int]:
    criados = {"categorias": 0, "produtos": 0, "mesas": 0, "garcons": 0}

    categorias = {}
    for nome, descricao in CATEGORIAS:
        categoria, novo = obter_ou_criar(session, Categoria, {"nome": nome}, {"descricao": descricao})
        categorias[nome] = categoria
        criados["categorias"] += novo

    for nome, categoria, preco, disponivel in PRODUTOS:
        _, novo = obter_ou_criar(
            session,
            Produto,
            {"nome": nome, "categoria_id": categorias[categoria].id},
            {"preco_centavos": preco, "disponivel": disponivel},
        )
        criados["produtos"] += novo

    for numero, capacidade, ativa in MESAS:
        _, novo = obter_ou_criar(session, Mesa, {"numero": numero}, {"capacidade": capacidade, "ativo": ativa})
        criados["mesas"] += novo

    for nome, matricula, ativo in GARCONS:
        _, novo = obter_ou_criar(session, Garcom, {"matricula": matricula}, {"nome": nome, "ativo": ativo})
        criados["garcons"] += novo

    return criados


def novo_pedido(modalidade, mesa, garcom, criado_em, observacao=None) -> Pedido:
    return Pedido(
        modalidade=modalidade,
        mesa_id=mesa.id if mesa else None,
        garcom_id=garcom.id,
        criado_em=criado_em,
        observacao=observacao,
    )


def adicionar_item(session, pedido, produto, quantidade, preco, status_preparo) -> int:
    session.add(
        ItemPedido(
            pedido_id=pedido.id,
            produto_id=produto.id,
            quantidade=quantidade,
            preco_unitario_centavos=preco,
            status_preparo=status_preparo,
        )
    )
    return quantidade * preco


def povoar_pedidos(session: Session) -> dict[str, int]:
    if session.exec(select(Pedido.id).limit(1)).first() is not None:
        return {}

    produtos = session.exec(
        select(Produto)
        .join(Categoria, Produto.categoria_id == Categoria.id)
        .where(Produto.ativo, Produto.disponivel, Categoria.ativo)
        .order_by(Produto.id)
    ).all()
    mesas = session.exec(select(Mesa).where(Mesa.ativo).order_by(Mesa.numero)).all()
    garcons = session.exec(select(Garcom).where(Garcom.ativo).order_by(Garcom.matricula)).all()
    if not produtos:
        raise ValueError("Disponibilize ao menos um produto ativo em uma categoria ativa.")
    if len(mesas) < 2:
        raise ValueError("Ative ao menos duas mesas para os atendimentos de demonstração.")
    if not garcons:
        raise ValueError("Ative ao menos um garçom para os atendimentos de demonstração.")
    agora = agora_utc()
    criados = {"finalizados": 0, "cancelados": 0, "abertos": 0}

    # Contas finalizadas espalhadas pelos últimos 21 dias, com mesa e retirada.
    for i in range(TOTAL_FINALIZADOS):
        dias_atras = 1 + (i % 21)
        criado_em = (agora - timedelta(days=dias_atras)).replace(
            hour=11 + (i * 7) % 10, minute=(i * 13) % 60, second=0, microsecond=0
        )
        retirada = i % 5 == 0
        observacao = OBSERVACOES[i % len(OBSERVACOES)] if i % 6 == 0 else None
        pedido = novo_pedido(
            ModalidadePedido.RETIRADA if retirada else ModalidadePedido.MESA,
            None if retirada else mesas[i % len(mesas)],
            garcons[i % len(garcons)],
            criado_em,
            observacao,
        )
        pedido.status = StatusPedido.FINALIZADO
        pedido.encerrado_em = criado_em + timedelta(minutes=35 + (i * 3) % 40)
        session.add(pedido)
        session.flush()

        total = 0
        for k in range(1 + i % 4):
            produto = produtos[(i * 3 + k * 5) % len(produtos)]
            preco = produto.preco_centavos
            if dias_atras > DIAS_PRECO_ANTIGO:
                preco = PRECOS_ANTIGOS.get(produto.nome, preco)
            total += adicionar_item(session, pedido, produto, 1 + (i + k) % 3, preco, StatusPreparo.PRONTO)

        session.add(FechamentoConta(pedido_id=pedido.id, total_centavos=total, fechado_em=pedido.encerrado_em))
        criados["finalizados"] += 1

    # Pedidos cancelados: só podem ter itens ainda pendentes (ou nenhum).
    for i in range(TOTAL_CANCELADOS):
        criado_em = agora - timedelta(days=2 + i, hours=1)
        pedido = novo_pedido(ModalidadePedido.MESA, mesas[i % len(mesas)], garcons[i % len(garcons)], criado_em)
        pedido.status = StatusPedido.CANCELADO
        pedido.encerrado_em = criado_em + timedelta(minutes=10)
        session.add(pedido)
        session.flush()
        if i > 0:
            produto = produtos[i % len(produtos)]
            adicionar_item(session, pedido, produto, 2, produto.preco_centavos, StatusPreparo.PENDENTE)
        criados["cancelados"] += 1

    # Atendimentos em andamento: duas mesas ocupadas e uma retirada.
    em_andamento = [
        (mesas[0], [StatusPreparo.PRONTO, StatusPreparo.EM_PREPARO, StatusPreparo.PENDENTE]),
        (mesas[1], [StatusPreparo.PENDENTE, StatusPreparo.PENDENTE]),
        (None, [StatusPreparo.PRONTO]),
    ]
    for i, (mesa, estados) in enumerate(em_andamento):
        pedido = novo_pedido(
            ModalidadePedido.MESA if mesa else ModalidadePedido.RETIRADA,
            mesa,
            garcons[i % len(garcons)],
            agora - timedelta(minutes=20 + 10 * i),
            "Retirada às 20h." if mesa is None else None,
        )
        session.add(pedido)
        session.flush()
        for k, estado in enumerate(estados):
            produto = produtos[(i * 4 + k * 3) % len(produtos)]
            adicionar_item(session, pedido, produto, 1 + k, produto.preco_centavos, estado)
        criados["abertos"] += 1

    return criados


def main() -> int:
    try:
        inspetor = inspect(engine)
        colunas = {c["name"] for c in inspetor.get_columns("pedido")} if inspetor.has_table("pedido") else set()
        if "observacao" not in colunas:
            print("O banco não está na versão atual. Execute `python -m alembic upgrade head` antes.")
            return 1
        with Session(engine) as session:
            cadastros = povoar_cadastros(session)
            pedidos = povoar_pedidos(session)
            session.commit()
    except ValueError as erro:
        print(f"Não foi possível povoar o banco: {erro} Nada foi gravado.")
        return 1
    except SQLAlchemyError as erro:
        print(f"Falha ao povoar o banco: {type(erro).__name__}. Nada foi gravado.")
        return 1

    print("Cadastros criados:", cadastros)
    print("Pedidos criados:", pedidos or "nenhum (a tabela de pedidos já tinha registros)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
