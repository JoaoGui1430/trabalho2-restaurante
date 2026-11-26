from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlmodel import Session, select

from app.database import get_session, get_write_session
from app.models import (
    MAXIMO_ID,
    Categoria,
    CategoriaCreate,
    CategoriaPublic,
    CategoriaUpdate,
    Produto,
    ProdutoPublic,
)

router = APIRouter(prefix="/categorias", tags=["Categorias"])


@router.post("/", response_model=CategoriaPublic, status_code=201)
def criar_categoria(
    dados: CategoriaCreate,
    session: Session = Depends(get_write_session),
):
    categoria = Categoria.model_validate(dados)
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria


@router.get("/", response_model=list[CategoriaPublic])
def listar_categorias(session: Session = Depends(get_session)):
    return session.exec(select(Categoria).order_by(Categoria.id)).all()


@router.get("/{categoria_id}", response_model=CategoriaPublic)
def buscar_categoria(
    categoria_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_session),
):
    categoria = session.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return categoria


@router.get("/{categoria_id}/produtos", response_model=list[ProdutoPublic])
def listar_produtos_da_categoria(
    categoria_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_session),
):
    # Relacionamento 1:N: os produtos são os registros que apontam para a categoria.
    if session.get(Categoria, categoria_id) is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    consulta = (
        select(Produto)
        .join(Categoria, Produto.categoria_id == Categoria.id)
        .where(Categoria.id == categoria_id)
        .order_by(Produto.nome, Produto.id)
    )
    return session.exec(consulta).all()


@router.patch("/{categoria_id}", response_model=CategoriaPublic)
def atualizar_categoria(
    dados: CategoriaUpdate,
    categoria_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    categoria = session.exec(
        select(Categoria).where(Categoria.id == categoria_id).with_for_update()
    ).first()
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(
            status_code=422, detail="Informe ao menos um campo para atualizar."
        )

    categoria.sqlmodel_update(alteracoes)
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}", status_code=204)
def desativar_categoria(
    categoria_id: int = Path(gt=0, le=MAXIMO_ID),
    session: Session = Depends(get_write_session),
):
    categoria = session.exec(
        select(Categoria).where(Categoria.id == categoria_id).with_for_update()
    ).first()
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    categoria.ativo = False
    session.add(categoria)
    session.commit()
    return Response(status_code=204)
