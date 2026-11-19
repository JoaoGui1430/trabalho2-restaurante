import os
from collections.abc import Generator
from pathlib import Path
from sqlite3 import Connection

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./restaurante.db")
backend = make_url(DATABASE_URL).get_backend_name()

if backend not in {"sqlite", "postgresql"}:
    raise ValueError("DATABASE_URL deve selecionar PostgreSQL ou SQLite.")

connect_args = {"connect_timeout": 5}
if backend == "sqlite":
    connect_args = {"check_same_thread": False, "timeout": 10}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    hide_parameters=True,
)


if backend == "sqlite":

    @event.listens_for(engine, "connect")
    def ativar_chaves_estrangeiras(conexao: Connection, registro_conexao):
        # SQLAlchemy inicia as transações explicitamente, inclusive as de escrita.
        conexao.isolation_level = None
        cursor = conexao.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def iniciar_transacao(conexao):
        if conexao.get_execution_options().get("sqlite_write", False):
            conexao.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conexao.exec_driver_sql("BEGIN")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def get_write_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        try:
            if backend == "sqlite":
                session.connection(execution_options={"sqlite_write": True})
            yield session
        except Exception:
            session.rollback()
            raise
