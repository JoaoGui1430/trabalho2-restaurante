"""Entradas nos limites aceitos pela API e pelos dois bancos."""

import pytest

from app.models import MAXIMO_ID, MAXIMO_INTEIRO_SQL

LIMITES_QUERY = {"offset": MAXIMO_INTEIRO_SQL, "mesa_id": MAXIMO_ID, "produto_id": MAXIMO_ID}


@pytest.mark.parametrize(
    "recurso",
    [
        "/pedidos/?data_fim=9999-12-31",
        "/relatorios/produtos-mais-vendidos?data_inicio=9999-12-31&data_fim=9999-12-31",
        "/relatorios/faturamento-diario?data_inicio=9999-12-31&data_fim=9999-12-31",
    ],
)
def test_data_final_maxima(client, recurso):
    resposta = client.get(recurso)
    assert resposta.status_code == 200, resposta.text
    if recurso.startswith("/pedidos/"):
        assert resposta.json()["total"] == 0
    elif "faturamento-diario" in recurso:
        assert resposta.json() == [
            {
                "data": "9999-12-31",
                "quantidade_contas": 0,
                "faturamento_centavos": 0,
            }
        ]
    else:
        assert resposta.json() == []


@pytest.mark.parametrize("parametro", ["offset", "mesa_id", "produto_id"])
def test_query_rejeita_inteiros_acima_do_banco(client, parametro):
    for valor in (LIMITES_QUERY[parametro] + 1, 999999999999999999999999):
        resposta = client.get("/pedidos/", params={parametro: valor})
        assert resposta.status_code == 422


@pytest.mark.parametrize("parametro", ["offset", "mesa_id", "produto_id"])
def test_query_aceita_limite_inteiro_do_banco(client, parametro):
    resposta = client.get("/pedidos/", params={parametro: LIMITES_QUERY[parametro]})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["itens"] == []


@pytest.mark.parametrize(
    "recurso",
    [
        "/categorias/{id}",
        "/produtos/{id}",
        "/mesas/{id}",
        "/garcons/{id}",
        "/pedidos/{id}",
        "/categorias/{id}/produtos",
        "/mesas/{id}/pedidos",
        "/pedidos/{id}/itens",
    ],
)
def test_id_de_rota_excessivo(client, recurso):
    resposta = client.get(recurso.format(id=MAXIMO_ID + 1))
    assert resposta.status_code == 422


@pytest.mark.parametrize(
    "recurso", ["categorias", "produtos", "mesas", "garcons", "pedidos"]
)
def test_id_de_rota_maximo_inexistente(client, recurso):
    resposta = client.get(f"/{recurso}/{MAXIMO_ID}")
    assert resposta.status_code == 404, resposta.text


def test_referencias_excessivas_no_corpo(client, cenario):
    grande = MAXIMO_ID + 1
    produto_id = cenario["prato"]["id"]
    garcom_id = cenario["garcom"]["id"]
    pedido = client.post(
        "/pedidos/", json={"modalidade": "retirada", "garcom_id": garcom_id}
    ).json()
    casos = [
        (
            "POST",
            "/produtos/",
            {"nome": "Teste", "preco_centavos": 100, "categoria_id": grande},
        ),
        ("PATCH", f"/produtos/{produto_id}", {"categoria_id": grande}),
        ("POST", "/pedidos/", {"modalidade": "retirada", "garcom_id": grande}),
        (
            "POST",
            "/pedidos/",
            {"modalidade": "mesa", "mesa_id": grande, "garcom_id": garcom_id},
        ),
        ("PATCH", f'/pedidos/{pedido["id"]}', {"garcom_id": grande}),
        (
            "POST",
            f'/pedidos/{pedido["id"]}/itens',
            {"produto_id": grande, "quantidade": 1},
        ),
    ]
    for metodo, caminho, corpo in casos:
        resposta = client.request(metodo, caminho, json=corpo)
        assert resposta.status_code == 422, (metodo, caminho, resposta.text)


def test_id_excessivo_em_mutacao_de_item(client):
    resposta = client.post(f"/pedidos/1/itens/{MAXIMO_ID + 1}/iniciar-preparo")
    assert resposta.status_code == 422
