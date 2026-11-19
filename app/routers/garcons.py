from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlmodel import Session, select

from app.database import get_session, get_write_session
from app.models import (
    Garcom,
    GarcomCreate,
    GarcomPublic,
    GarcomUpdate,
    Pedido,
    StatusPedido,
)

router = APIRouter(prefix="/garcons", tags=["Garçons"])


def validar_desativacao(garcom_id: int, session: Session) -> None:
    pedido_aberto = session.exec(
        select(Pedido.id).where(
            Pedido.garcom_id == garcom_id,
            Pedido.status == StatusPedido.ABERTO,
        )
    ).first()
    if pedido_aberto is not None:
        raise HTTPException(
            status_code=409,
            detail="Encerre os pedidos abertos antes de desativar o garçom.",
        )


@router.post("/", response_model=GarcomPublic, status_code=201)
def criar_garcom(
    dados: GarcomCreate,
    session: Session = Depends(get_write_session),
):
    garcom = Garcom.model_validate(dados)
    session.add(garcom)
    session.commit()
    session.refresh(garcom)
    return garcom


@router.get("/", response_model=list[GarcomPublic])
def listar_garcons(session: Session = Depends(get_session)):
    return session.exec(select(Garcom).order_by(Garcom.id)).all()


@router.get("/{garcom_id}", response_model=GarcomPublic)
def buscar_garcom(
    garcom_id: int = Path(gt=0),
    session: Session = Depends(get_session),
):
    garcom = session.get(Garcom, garcom_id)
    if garcom is None:
        raise HTTPException(status_code=404, detail="Garçom não encontrado.")
    return garcom


@router.patch("/{garcom_id}", response_model=GarcomPublic)
def atualizar_garcom(
    dados: GarcomUpdate,
    garcom_id: int = Path(gt=0),
    session: Session = Depends(get_write_session),
):
    garcom = session.exec(
        select(Garcom).where(Garcom.id == garcom_id).with_for_update()
    ).first()
    if garcom is None:
        raise HTTPException(status_code=404, detail="Garçom não encontrado.")

    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(
            status_code=422, detail="Informe ao menos um campo para atualizar."
        )
    if alteracoes.get("ativo") is False:
        validar_desativacao(garcom_id, session)

    garcom.sqlmodel_update(alteracoes)
    session.add(garcom)
    session.commit()
    session.refresh(garcom)
    return garcom


@router.delete("/{garcom_id}", status_code=204)
def desativar_garcom(
    garcom_id: int = Path(gt=0),
    session: Session = Depends(get_write_session),
):
    garcom = session.exec(
        select(Garcom).where(Garcom.id == garcom_id).with_for_update()
    ).first()
    if garcom is None:
        raise HTTPException(status_code=404, detail="Garçom não encontrado.")
    validar_desativacao(garcom_id, session)

    garcom.ativo = False
    session.add(garcom)
    session.commit()
    return Response(status_code=204)
