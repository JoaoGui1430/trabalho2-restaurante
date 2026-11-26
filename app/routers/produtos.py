from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlmodel import Session, select

from app.database import get_session, get_write_session
from app.models import (
    MAXIMO_ID,
    Categoria,
    Produto,
    ProdutoCreate,
    ProdutoPublic,
    ProdutoUpdate,
)

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def obter_categoria_ativa(categoria_id: int, session: Session) -> Categoria:
    categoria = session.exec(
        select(Categoria).where(Categoria.id == categoria_id).with_for_update()
    ).first()
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    if not categoria.ativo:
        raise HTTPException(status_code=409, detail="A categoria está desativada.")
    return categoria


@router.post("/", response_model=ProdutoPublic, status_code=201)
def criar_produto(
    dados: ProdutoCreate,
    session: Session = Depends(get_write_session),
):
    categoria = obter_categoria_ativa(dados.categoria_id, session)
    produto = Produto.model_validate(dados)
    produto.categoria = categoria
    session.add(produto)
    session.commit()
    session.refresh(produto)
    return produto


@router.get("/", response_model=list[ProdutoPublic])
def listar_produtos(session: Session = Depends(get_session)):
    return session.exec(select(Produto).order_by(Produto.id)).all()


@router.get("/{produto_id}", response_model=ProdutoPublic)
def buscar_produto(
    produto_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_session),
):
    produto = session.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return produto


@router.patch("/{produto_id}", response_model=ProdutoPublic)
def atualizar_produto(
    dados: ProdutoUpdate,
    produto_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    produto = session.exec(
        select(Produto).where(Produto.id == produto_id).with_for_update()
    ).first()
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(
            status_code=422, detail="Informe ao menos um campo para atualizar."
        )

    if "categoria_id" in alteracoes:
        produto.categoria = obter_categoria_ativa(alteracoes["categoria_id"], session)

    produto.sqlmodel_update(alteracoes)
    session.add(produto)
    session.commit()
    session.refresh(produto)
    return produto


@router.delete("/{produto_id}", status_code=204)
def desativar_produto(
    produto_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    produto = session.exec(
        select(Produto).where(Produto.id == produto_id).with_for_update()
    ).first()
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    produto.ativo = False
    session.add(produto)
    session.commit()
    return Response(status_code=204)
