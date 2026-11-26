"""Regras financeiras e de atendimento: preço histórico, total, estados e ocupação."""


def abrir_pedido(client, cenario, **extra):
    corpo = {"modalidade": "mesa", "mesa_id": cenario["mesa"]["id"], "garcom_id": cenario["garcom"]["id"]}
    return client.post("/pedidos/", json={**corpo, **extra})


def incluir(client, pedido_id, produto, quantidade):
    return client.post(f"/pedidos/{pedido_id}/itens", json={"produto_id": produto["id"], "quantidade": quantidade})


def deixar_pronto(client, pedido_id, item_id):
    base = f"/pedidos/{pedido_id}/itens/{item_id}"
    assert client.post(f"{base}/iniciar-preparo").status_code == 200
    assert client.post(f"{base}/concluir-preparo").status_code == 200


def test_preco_historico_e_total_calculado_no_servidor(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    primeiro = incluir(client, pedido["id"], cenario["prato"], 2).json()

    # O cardápio muda de preço, e uma nova inclusão usa o preço novo.
    assert client.patch(f"/produtos/{cenario['prato']['id']}", json={"preco_centavos": 1800}).status_code == 200
    segundo = incluir(client, pedido["id"], cenario["prato"], 1).json()

    assert primeiro["preco_unitario_centavos"] == 1500
    assert segundo["preco_unitario_centavos"] == 1800
    detalhe = client.get(f"/pedidos/{pedido['id']}").json()
    assert detalhe["total_centavos"] == 2 * 1500 + 1 * 1800  # 4800


def test_cliente_nao_controla_preco_nem_total(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    resposta = client.post(
        f"/pedidos/{pedido['id']}/itens",
        json={"produto_id": cenario["prato"]["id"], "quantidade": 1, "preco_unitario_centavos": 1},
    )
    assert resposta.status_code == 422


def test_mesa_ocupada_rejeita_segundo_pedido_e_finalizar_libera(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    assert abrir_pedido(client, cenario).status_code == 409

    item = incluir(client, pedido["id"], cenario["suco"], 1).json()
    deixar_pronto(client, pedido["id"], item["id"])
    assert client.post(f"/pedidos/{pedido['id']}/finalizar").status_code == 200
    assert abrir_pedido(client, cenario).status_code == 201


def test_modalidade_retirada_nao_aceita_mesa(client, cenario):
    corpo = {"modalidade": "retirada", "mesa_id": cenario["mesa"]["id"], "garcom_id": cenario["garcom"]["id"]}
    assert client.post("/pedidos/", json=corpo).status_code == 422
    corpo["mesa_id"] = None
    assert client.post("/pedidos/", json=corpo).status_code == 201


def test_finalizar_exige_itens_prontos(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    assert client.post(f"/pedidos/{pedido['id']}/finalizar").status_code == 409  # sem itens

    item = incluir(client, pedido["id"], cenario["prato"], 1).json()
    assert client.post(f"/pedidos/{pedido['id']}/finalizar").status_code == 409  # pendente
    deixar_pronto(client, pedido["id"], item["id"])
    final = client.post(f"/pedidos/{pedido['id']}/finalizar")
    assert final.status_code == 200
    assert final.json()["status"] == "finalizado"
    assert final.json()["fechamento"]["total_centavos"] == 1500


def test_pedido_finalizado_fica_bloqueado(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    item = incluir(client, pedido["id"], cenario["prato"], 1).json()
    deixar_pronto(client, pedido["id"], item["id"])
    client.post(f"/pedidos/{pedido['id']}/finalizar")

    assert incluir(client, pedido["id"], cenario["suco"], 1).status_code == 409
    assert client.delete(f"/pedidos/{pedido['id']}/itens/{item['id']}").status_code == 409
    assert client.delete(f"/pedidos/{pedido['id']}").status_code == 409
    assert client.post(f"/pedidos/{pedido['id']}/finalizar").status_code == 409
    assert client.patch(f"/pedidos/{pedido['id']}", json={"observacao": "tarde demais"}).status_code == 409


def test_item_em_preparo_nao_pode_ser_removido_nem_cancelar_pedido(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    item = incluir(client, pedido["id"], cenario["prato"], 2).json()
    assert client.post(f"/pedidos/{pedido['id']}/itens/{item['id']}/iniciar-preparo").status_code == 200

    assert client.delete(f"/pedidos/{pedido['id']}/itens/{item['id']}").status_code == 409
    assert client.patch(f"/pedidos/{pedido['id']}/itens/{item['id']}", json={"quantidade": 1}).status_code == 409
    assert client.delete(f"/pedidos/{pedido['id']}").status_code == 409


def test_item_pendente_pode_reduzir_mas_nao_aumentar(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    item = incluir(client, pedido["id"], cenario["prato"], 3).json()
    reduzido = client.patch(f"/pedidos/{pedido['id']}/itens/{item['id']}", json={"quantidade": 1})
    assert reduzido.status_code == 200
    assert reduzido.json()["subtotal_centavos"] == 1500
    assert client.patch(f"/pedidos/{pedido['id']}/itens/{item['id']}", json={"quantidade": 5}).status_code == 409


def test_cancelamento_libera_a_mesa(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    incluir(client, pedido["id"], cenario["prato"], 1)
    assert client.delete(f"/pedidos/{pedido['id']}").status_code == 204
    assert client.get(f"/pedidos/{pedido['id']}").json()["status"] == "cancelado"
    assert abrir_pedido(client, cenario).status_code == 201


def test_produto_indisponivel_nao_pode_ser_vendido(client, cenario):
    client.patch(f"/produtos/{cenario['suco']['id']}", json={"disponivel": False})
    pedido = abrir_pedido(client, cenario).json()
    assert incluir(client, pedido["id"], cenario["suco"], 1).status_code == 409


def test_observacao_na_abertura_e_na_atualizacao(client, cenario):
    pedido = abrir_pedido(client, cenario, observacao="Sem cebola.").json()
    assert pedido["observacao"] == "Sem cebola."

    atualizado = client.patch(f"/pedidos/{pedido['id']}", json={"observacao": "Sem sal."})
    assert atualizado.status_code == 200
    assert atualizado.json()["observacao"] == "Sem sal."

    limpo = client.patch(f"/pedidos/{pedido['id']}", json={"observacao": None})
    assert limpo.status_code == 200 and limpo.json()["observacao"] is None
    assert client.patch(f"/pedidos/{pedido['id']}", json={"observacao": ""}).status_code == 422
    assert client.patch(f"/pedidos/{pedido['id']}", json={}).status_code == 422


def test_trocar_garcom_continua_validado(client, cenario):
    pedido = abrir_pedido(client, cenario).json()
    assert client.patch(f"/pedidos/{pedido['id']}", json={"garcom_id": 9999}).status_code == 404
    assert client.patch(f"/pedidos/{pedido['id']}", json={"garcom_id": None}).status_code == 422


def test_erros_de_identificador(client):
    assert client.get("/pedidos/999").status_code == 404
    assert client.get("/pedidos/0").status_code == 422
    assert client.get("/pedidos/abc").status_code == 422
    assert client.get("/categorias/999/produtos").status_code == 404
    assert client.get("/mesas/999/pedidos").status_code == 404


def test_duplicidade_retorna_conflito(client, cenario):
    assert client.post("/categorias/", json={"nome": "Pratos"}).status_code == 409
    assert client.post("/mesas/", json={"numero": 1, "capacidade": 2}).status_code == 409
    assert client.post("/garcons/", json={"nome": "Outra Pessoa", "matricula": "G1"}).status_code == 409
