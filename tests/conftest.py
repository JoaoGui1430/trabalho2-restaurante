import os
import tempfile
from pathlib import Path

import pytest

# O banco precisa ser escolhido antes de importar a aplicação. Por padrão os testes usam
# um SQLite temporário. TESTE_DATABASE_URL seleciona outro banco (por exemplo, um
# PostgreSQL EXCLUSIVO para testes), pois cada teste apaga todos os registros ao terminar.
_pasta = tempfile.mkdtemp(prefix="restaurante_testes_")
os.environ["DATABASE_URL"] = os.getenv("TESTE_DATABASE_URL") or (
    f"sqlite:///{Path(_pasta, 'teste.db').as_posix()}"
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel, Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def banco_migrado():
    # O esquema dos testes vem das migrações, o mesmo caminho usado em produção.
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    command.upgrade(config, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def banco_limpo():
    yield
    with Session(engine) as session:
        for tabela in reversed(SQLModel.metadata.sorted_tables):
            session.execute(tabela.delete())
        session.commit()


@pytest.fixture
def client():
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def cenario(client):
    """Cadastros mínimos: uma categoria, dois produtos, duas mesas e um garçom."""

    def criar(caminho, corpo):
        resposta = client.post(caminho, json=corpo)
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    categoria = criar("/categorias/", {"nome": "Pratos"})
    return {
        "categoria": categoria,
        "prato": criar(
            "/produtos/",
            {"nome": "Prato feito", "preco_centavos": 1500, "categoria_id": categoria["id"]},
        ),
        "suco": criar(
            "/produtos/",
            {"nome": "Suco", "preco_centavos": 800, "categoria_id": categoria["id"]},
        ),
        "mesa": criar("/mesas/", {"numero": 1, "capacidade": 4}),
        "mesa2": criar("/mesas/", {"numero": 2, "capacidade": 4}),
        "garcom": criar("/garcons/", {"nome": "Ana Lima", "matricula": "G1"}),
    }


@pytest.fixture
def povoado():
    from app import povoamento

    assert povoamento.main() == 0
