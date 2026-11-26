import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import engine
from app.routers import (
    categorias,
    estatisticas,
    garcons,
    mesas,
    pedidos,
    produtos,
    relatorios,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Sistema de Restaurante",
    description="API do Tema 8 do Trabalho Prático 2 de Persistência.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(categorias.router)
app.include_router(produtos.router)
app.include_router(mesas.router)
app.include_router(garcons.router)
app.include_router(pedidos.router)
app.include_router(relatorios.router)
app.include_router(estatisticas.router)


@app.get("/", tags=["Início"])
def inicio():
    return {"mensagem": "Sistema de restaurante em funcionamento"}


@app.exception_handler(SQLAlchemyError)
async def tratar_erro_banco(request: Request, erro: SQLAlchemyError):
    logger.error(
        "Falha de banco em %s %s",
        request.method,
        request.url.path,
        exc_info=erro,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Não foi possível concluir a operação no banco de dados."},
    )


@app.exception_handler(IntegrityError)
async def tratar_conflito_integridade(request: Request, erro: IntegrityError):
    logger.info("Conflito de integridade em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=409,
        content={
            "detail": "A operação conflita com um registro existente ou um vínculo obrigatório."
        },
    )
