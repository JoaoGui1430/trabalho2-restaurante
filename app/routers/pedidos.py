from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlmodel import Session, select

from app.database import get_session, get_write_session
from app.models import (
    Categoria,
    FechamentoConta,
    Garcom,
    ItemPedido,
    ItemPedidoCreate,
    ItemPedidoPublicDetalhado,
    ItemPedidoUpdate,
    Mesa,
    ModalidadePedido,
    Pedido,
    PedidoCreate,
    PedidoPublic,
    PedidoPublicDetalhado,
    PedidoUpdate,
    Produto,
    StatusPedido,
    StatusPreparo,
)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])
IdPositivo = Annotated[int, Path(gt=0)]


def buscar_garcom_ativo(garcom_id: int, session: Session) -> Garcom:
    garcom = session.exec(
        select(Garcom).where(Garcom.id == garcom_id).with_for_update()
    ).first()
    if garcom is None:
        raise HTTPException(status_code=404, detail="Garçom não encontrado.")
    if not garcom.ativo:
        raise HTTPException(status_code=409, detail="O garçom está inativo.")
    return garcom


def buscar_pedido_aberto(pedido_id: int, session: Session) -> Pedido:
    # Todas as alterações de itens e encerramentos bloqueiam primeiro o pedido.
    pedido = session.exec(
        select(Pedido).where(Pedido.id == pedido_id).with_for_update()
    ).first()
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if pedido.status != StatusPedido.ABERTO:
        raise HTTPException(status_code=409, detail="O pedido já foi encerrado.")
    return pedido


def buscar_item(pedido_id: int, item_id: int, session: Session) -> ItemPedido:
    item = session.get(ItemPedido, item_id)
    if item is None or item.pedido_id != pedido_id:
        raise HTTPException(status_code=404, detail="Item não encontrado neste pedido.")
    return item


def validar_item_pendente(item: ItemPedido) -> None:
    if item.status_preparo != StatusPreparo.PENDENTE:
        raise HTTPException(
            status_code=409,
            detail="Esta alteração exige um item que ainda não entrou em preparo.",
        )


@router.post("/", response_model=PedidoPublicDetalhado, status_code=201)
def criar_pedido(
    dados: PedidoCreate,
    session: Session = Depends(get_write_session),
):
    buscar_garcom_ativo(dados.garcom_id, session)

    if dados.modalidade == ModalidadePedido.MESA:
        mesa = session.exec(
            select(Mesa).where(Mesa.id == dados.mesa_id).with_for_update()
        ).first()
        if mesa is None:
            raise HTTPException(status_code=404, detail="Mesa não encontrada.")
        if not mesa.ativo:
            raise HTTPException(status_code=409, detail="A mesa está inativa.")

        atendimento = session.exec(
            select(Pedido).where(
                Pedido.mesa_id == dados.mesa_id,
                Pedido.status == StatusPedido.ABERTO,
            )
        ).first()
        if atendimento is not None:
            raise HTTPException(
                status_code=409, detail="A mesa já possui um pedido aberto."
            )

    pedido = Pedido.model_validate(dados)
    session.add(pedido)
    session.commit()
    session.refresh(pedido)
    return pedido


@router.get("/", response_model=list[PedidoPublic])
def listar_pedidos(session: Session = Depends(get_session)):
    consulta = select(Pedido).order_by(Pedido.criado_em.desc(), Pedido.id.desc())
    return session.exec(consulta).all()


@router.get("/{pedido_id}", response_model=PedidoPublicDetalhado)
def consultar_pedido(pedido_id: IdPositivo, session: Session = Depends(get_session)):
    pedido = session.get(Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return pedido


@router.patch("/{pedido_id}", response_model=PedidoPublicDetalhado)
def atualizar_pedido(
    pedido_id: IdPositivo,
    dados: PedidoUpdate,
    session: Session = Depends(get_write_session),
):
    valores = dados.model_dump(exclude_unset=True)
    if not valores:
        raise HTTPException(
            status_code=422, detail="Informe ao menos um campo para atualizar."
        )

    buscar_garcom_ativo(valores["garcom_id"], session)
    pedido = buscar_pedido_aberto(pedido_id, session)
    pedido.sqlmodel_update(valores)
    session.add(pedido)
    session.commit()
    session.refresh(pedido)
    return pedido


@router.post(
    "/{pedido_id}/itens", response_model=ItemPedidoPublicDetalhado, status_code=201
)
def adicionar_item(
    pedido_id: IdPositivo,
    dados: ItemPedidoCreate,
    session: Session = Depends(get_write_session),
):
    produto = session.exec(
        select(Produto).where(Produto.id == dados.produto_id).with_for_update()
    ).first()
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    categoria = session.exec(
        select(Categoria).where(Categoria.id == produto.categoria_id).with_for_update()
    ).first()
    if (
        not produto.ativo
        or not produto.disponivel
        or categoria is None
        or not categoria.ativo
    ):
        raise HTTPException(
            status_code=409, detail="O produto está indisponível para venda."
        )

    pedido = buscar_pedido_aberto(pedido_id, session)
    item = ItemPedido(
        pedido_id=pedido.id,
        produto_id=produto.id,
        quantidade=dados.quantidade,
        preco_unitario_centavos=produto.preco_centavos,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch("/{pedido_id}/itens/{item_id}", response_model=ItemPedidoPublicDetalhado)
def reduzir_quantidade(
    pedido_id: IdPositivo,
    item_id: IdPositivo,
    dados: ItemPedidoUpdate,
    session: Session = Depends(get_write_session),
):
    buscar_pedido_aberto(pedido_id, session)
    item = buscar_item(pedido_id, item_id, session)
    validar_item_pendente(item)
    if dados.quantidade > item.quantidade:
        raise HTTPException(
            status_code=409,
            detail="Para acrescentar unidades, inclua um novo item com o preço atual.",
        )

    item.quantidade = dados.quantidade
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{pedido_id}/itens/{item_id}", status_code=204)
def remover_item(
    pedido_id: IdPositivo,
    item_id: IdPositivo,
    session: Session = Depends(get_write_session),
):
    buscar_pedido_aberto(pedido_id, session)
    item = buscar_item(pedido_id, item_id, session)
    validar_item_pendente(item)
    session.delete(item)
    session.commit()
    return Response(status_code=204)


@router.post(
    "/{pedido_id}/itens/{item_id}/iniciar-preparo",
    response_model=ItemPedidoPublicDetalhado,
)
def iniciar_preparo(
    pedido_id: IdPositivo,
    item_id: IdPositivo,
    session: Session = Depends(get_write_session),
):
    buscar_pedido_aberto(pedido_id, session)
    item = buscar_item(pedido_id, item_id, session)
    validar_item_pendente(item)
    item.status_preparo = StatusPreparo.EM_PREPARO
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post(
    "/{pedido_id}/itens/{item_id}/concluir-preparo",
    response_model=ItemPedidoPublicDetalhado,
)
def concluir_preparo(
    pedido_id: IdPositivo,
    item_id: IdPositivo,
    session: Session = Depends(get_write_session),
):
    buscar_pedido_aberto(pedido_id, session)
    item = buscar_item(pedido_id, item_id, session)
    if item.status_preparo != StatusPreparo.EM_PREPARO:
        raise HTTPException(status_code=409, detail="O item precisa estar em preparo.")
    item.status_preparo = StatusPreparo.PRONTO
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/{pedido_id}/finalizar", response_model=PedidoPublicDetalhado)
def finalizar_pedido(
    pedido_id: IdPositivo,
    session: Session = Depends(get_write_session),
):
    pedido = buscar_pedido_aberto(pedido_id, session)
    if not pedido.itens:
        raise HTTPException(
            status_code=409, detail="O pedido deve possuir ao menos um item."
        )
    if any(item.status_preparo != StatusPreparo.PRONTO for item in pedido.itens):
        raise HTTPException(
            status_code=409, detail="Todos os itens precisam estar prontos."
        )

    total = pedido.total_centavos
    if total > 9_223_372_036_854_775_807:
        raise HTTPException(
            status_code=409, detail="O total excede o limite de armazenamento."
        )

    encerramento = datetime.now(timezone.utc).replace(tzinfo=None)
    pedido.status = StatusPedido.FINALIZADO
    pedido.encerrado_em = encerramento
    fechamento = FechamentoConta(
        pedido_id=pedido.id,
        fechado_em=encerramento,
        total_centavos=total,
    )
    session.add(pedido)
    session.add(fechamento)
    session.commit()
    session.refresh(pedido)
    return pedido


@router.delete("/{pedido_id}", status_code=204, summary="Cancelar pedido")
def cancelar_pedido(
    pedido_id: IdPositivo,
    session: Session = Depends(get_write_session),
):
    pedido = buscar_pedido_aberto(pedido_id, session)
    if any(item.status_preparo != StatusPreparo.PENDENTE for item in pedido.itens):
        raise HTTPException(
            status_code=409,
            detail="O pedido só pode ser cancelado antes de iniciar o preparo dos itens.",
        )
    pedido.status = StatusPedido.CANCELADO
    pedido.encerrado_em = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(pedido)
    session.commit()
    return Response(status_code=204)
