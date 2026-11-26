from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import get_session, get_write_session
from app.models import (
    MAXIMO_ID,
    ItemPedido,
    Mesa,
    MesaCreate,
    MesaPublic,
    MesaUpdate,
    Pedido,
    PedidoPublicDetalhado,
    StatusPedido,
)

router = APIRouter(prefix="/mesas", tags=["Mesas"])


def validar_desativacao(mesa_id: int, session: Session) -> None:
    pedido_aberto = session.exec(
        select(Pedido.id).where(
            Pedido.mesa_id == mesa_id,
            Pedido.status == StatusPedido.ABERTO,
        )
    ).first()
    if pedido_aberto is not None:
        raise HTTPException(
            status_code=409,
            detail="Encerre o pedido aberto antes de desativar a mesa.",
        )


@router.post("/", response_model=MesaPublic, status_code=201)
def criar_mesa(
    dados: MesaCreate,
    session: Session = Depends(get_write_session),
):
    mesa = Mesa.model_validate(dados)
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.get("/", response_model=list[MesaPublic])
def listar_mesas(session: Session = Depends(get_session)):
    return session.exec(select(Mesa).order_by(Mesa.id)).all()


@router.get("/{mesa_id}", response_model=MesaPublic)
def buscar_mesa(
    mesa_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_session),
):
    mesa = session.get(Mesa, mesa_id)
    if mesa is None:
        raise HTTPException(status_code=404, detail="Mesa não encontrada.")
    return mesa


@router.get("/{mesa_id}/pedidos", response_model=list[PedidoPublicDetalhado])
def listar_pedidos_da_mesa(
    mesa_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_session),
):
    # Histórico da mesa, do mais recente ao mais antigo, com garçom, itens e produtos.
    if session.get(Mesa, mesa_id) is None:
        raise HTTPException(status_code=404, detail="Mesa não encontrada.")
    consulta = (
        select(Pedido)
        .where(Pedido.mesa_id == mesa_id)
        .options(
            selectinload(Pedido.mesa),
            selectinload(Pedido.garcom),
            selectinload(Pedido.itens).selectinload(ItemPedido.produto),
            selectinload(Pedido.fechamento),
        )
        .order_by(Pedido.criado_em.desc(), Pedido.id.desc())
    )
    return session.exec(consulta).all()


@router.patch("/{mesa_id}", response_model=MesaPublic)
def atualizar_mesa(
    dados: MesaUpdate,
    mesa_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    mesa = session.exec(
        select(Mesa).where(Mesa.id == mesa_id).with_for_update()
    ).first()
    if mesa is None:
        raise HTTPException(status_code=404, detail="Mesa não encontrada.")

    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(
            status_code=422, detail="Informe ao menos um campo para atualizar."
        )
    if alteracoes.get("ativo") is False:
        validar_desativacao(mesa_id, session)

    mesa.sqlmodel_update(alteracoes)
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.delete("/{mesa_id}", status_code=204)
def desativar_mesa(
    mesa_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    mesa = session.exec(
        select(Mesa).where(Mesa.id == mesa_id).with_for_update()
    ).first()
    if mesa is None:
        raise HTTPException(status_code=404, detail="Mesa não encontrada.")
    validar_desativacao(mesa_id, session)

    mesa.ativo = False
    session.add(mesa)
    session.commit()
    return Response(status_code=204)
