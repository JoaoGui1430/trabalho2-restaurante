"""Paginação, filtros, relatórios e estatísticas sobre a base povoada.

Os valores esperados são recalculados em Python a partir dos registros, sem reutilizar
o SQL dos relatórios, para a conferência ser independente.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from app import povoamento
from app.database import engine
from app.models import FechamentoConta, ItemPedido, Pedido, Produto, StatusPedido

PERIODO = {"data_inicio": "2000-01-01", "data_fim": "2030-12-31"}


def periodo_do_povoamento():
    hoje = povoamento.agora_utc().date()
    return {"data_inicio": str(hoje - timedelta(days=30)), "data_fim": str(hoje)}


def pedidos_finalizados():
    with Session(engine) as session:
        pedidos = session.exec(select(Pedido).where(Pedido.status == StatusPedido.FINALIZADO)).all()
        return [
            (p, list(p.itens), p.fechamento)
            for p in pedidos
        ]


def test_povoamento_e_repetivel_e_completo(client, povoado):
    with Session(engine) as session:
        assert len(session.exec(select(Produto)).all()) >= 10
    antes = client.get("/pedidos/", params={"limit": 1}).json()["total"]
    assert povoamento.main() == 0
    assert client.get("/pedidos/", params={"limit": 1}).json()["total"] == antes == 51


def test_paginacao_percorre_todos_sem_repetir(client, povoado):
    vistos, offset = [], 0
    while True:
        pagina = client.get("/pedidos/", params={"offset": offset, "limit": 20}).json()
        vistos += [p["id"] for p in pagina["itens"]]
        assert pagina["total"] == 51
        if len(pagina["itens"]) < 20:
            break
        offset += 20
    assert len(vistos) == len(set(vistos)) == 51
    assert client.get("/pedidos/", params={"limit": 101}).status_code == 422
    assert client.get("/pedidos/", params={"offset": -1}).status_code == 422


def test_filtros_isolados_e_combinados(client, povoado):
    def total(**filtros):
        return client.get("/pedidos/", params={"limit": 100, **filtros}).json()["total"]

    assert total(status="finalizado") == 45
    assert total(status="cancelado") == 3
    assert total(status="aberto") == 3
    assert total(modalidade="retirada") == sum(1 for _ in range(45) if _ % 5 == 0) + 1  # 9 finalizadas + 1 aberta

    with Session(engine) as session:
        pedidos = session.exec(select(Pedido)).all()
        produto = session.exec(select(Produto).where(Produto.nome == "Feijoada")).one()
        esperado_produto = {p.id for p in pedidos if any(i.produto_id == produto.id for i in p.itens)}
        mesa_id = next(p.mesa_id for p in pedidos if p.mesa_id)
        esperado_mesa = {p.id for p in pedidos if p.mesa_id == mesa_id}
        esperado_combinado = {p.id for p in pedidos if p.mesa_id == mesa_id and p.status == StatusPedido.FINALIZADO}

    por_produto = client.get("/pedidos/", params={"produto_id": produto.id, "limit": 100}).json()
    ids = [p["id"] for p in por_produto["itens"]]
    assert set(ids) == esperado_produto and len(ids) == len(set(ids)) == por_produto["total"]
    assert total(mesa_id=mesa_id) == len(esperado_mesa)
    assert total(mesa_id=mesa_id, status="finalizado") == len(esperado_combinado)
    assert total(data_inicio="2000-01-01", data_fim="2000-01-02") == 0
    assert client.get("/pedidos/", params={"data_inicio": "2026-02-02", "data_fim": "2026-01-01"}).status_code == 422


def test_consultas_por_relacionamento(client, povoado):
    categorias = client.get("/categorias/").json()
    bebidas = next(c for c in categorias if c["nome"] == "Bebidas")
    produtos = client.get(f"/categorias/{bebidas['id']}/produtos").json()
    assert {p["nome"] for p in produtos} >= {"Suco de laranja", "Água mineral"}
    assert all(p["categoria_id"] == bebidas["id"] for p in produtos)

    pedido = client.get("/pedidos/", params={"status": "finalizado", "limit": 1}).json()["itens"][0]
    itens = client.get(f"/pedidos/{pedido['id']}/itens").json()
    assert itens and all(i["produto"]["id"] == i["produto_id"] for i in itens)

    historico = client.get(f"/mesas/{pedido['mesa_id']}/pedidos")
    if pedido["mesa_id"]:
        assert historico.status_code == 200
        assert pedido["id"] in [p["id"] for p in historico.json()]


def test_ranking_confere_com_contagem_manual(client, povoado):
    quantidades, valores, nomes = Counter(), Counter(), {}
    for pedido, itens, _ in pedidos_finalizados():
        for item in itens:
            quantidades[item.produto_id] += item.quantidade
            valores[item.produto_id] += item.quantidade * item.preco_unitario_centavos
    with Session(engine) as session:
        nomes = {p.id: p.nome for p in session.exec(select(Produto)).all()}
    esperado = sorted(quantidades, key=lambda pid: (-quantidades[pid], nomes[pid], pid))[:5]

    ranking = client.get("/relatorios/produtos-mais-vendidos", params={**periodo_do_povoamento(), "limite": 5}).json()
    assert [r["produto_id"] for r in ranking] == esperado
    assert [r["posicao"] for r in ranking] == [1, 2, 3, 4, 5]
    for linha in ranking:
        assert linha["quantidade_vendida"] == quantidades[linha["produto_id"]]
        assert linha["faturamento_centavos"] == valores[linha["produto_id"]]


def test_relatorios_ignoram_pedidos_abertos_e_cancelados(client, povoado):
    # Abertos e cancelados têm itens no banco, mas não podem entrar nas vendas.
    with Session(engine) as session:
        nao_finalizados = sum(
            i.quantidade
            for i in session.exec(select(ItemPedido)).all()
            if i.pedido.status != StatusPedido.FINALIZADO
        )
    assert nao_finalizados > 0
    ranking = client.get("/relatorios/produtos-mais-vendidos", params={**periodo_do_povoamento(), "limite": 100}).json()
    vendido = sum(r["quantidade_vendida"] for r in ranking)
    esperado = sum(i.quantidade for _, itens, _ in pedidos_finalizados() for i in itens)
    assert vendido == esperado


def test_faturamento_diario_confere_e_preenche_dias_sem_venda(client, povoado):
    por_dia = defaultdict(lambda: [0, 0])
    for _, _, fechamento in pedidos_finalizados():
        dia = fechamento.fechado_em.date()
        por_dia[dia][0] += 1
        por_dia[dia][1] += fechamento.total_centavos

    periodo = periodo_do_povoamento()
    linhas = client.get("/relatorios/faturamento-diario", params=periodo).json()
    assert len(linhas) == 31
    assert sum(l["faturamento_centavos"] for l in linhas) == sum(v[1] for v in por_dia.values())
    assert sum(l["quantidade_contas"] for l in linhas) == 45
    assert any(l["quantidade_contas"] == 0 and l["faturamento_centavos"] == 0 for l in linhas)
    for linha in linhas:
        contas, total = por_dia.get(date.fromisoformat(linha["data"]), [0, 0])
        assert (linha["quantidade_contas"], linha["faturamento_centavos"]) == (contas, total)


def test_relatorio_valida_periodo(client):
    assert client.get("/relatorios/faturamento-diario").status_code == 422
    assert client.get("/relatorios/faturamento-diario", params={"data_inicio": "2026-02-01", "data_fim": "2026-01-01"}).status_code == 422
    assert client.get("/relatorios/faturamento-diario", params={"data_inicio": "2020-01-01", "data_fim": "2026-01-01"}).status_code == 422


def test_estatisticas_com_base_vazia(client):
    dados = client.get("/estatisticas/").json()
    assert dados == {
        "total_pedidos": 0,
        "pedidos_por_status": {"aberto": 0, "finalizado": 0, "cancelado": 0},
        "contas_finalizadas": 0,
        "faturamento_centavos": 0,
        "ticket_medio_centavos": 0,
    }


def test_estatisticas_conferem_com_a_base_povoada(client, povoado):
    totais = [fechamento.total_centavos for _, _, fechamento in pedidos_finalizados()]
    dados = client.get("/estatisticas/").json()
    assert dados["total_pedidos"] == 51
    assert dados["pedidos_por_status"] == {"aberto": 3, "finalizado": 45, "cancelado": 3}
    assert dados["contas_finalizadas"] == len(totais) == 45
    assert dados["faturamento_centavos"] == sum(totais)
    assert dados["ticket_medio_centavos"] == round(sum(totais) / len(totais))


def test_estatisticas_acompanham_uma_nova_venda(client, cenario):
    corpo = {"modalidade": "retirada", "garcom_id": cenario["garcom"]["id"]}
    pedido = client.post("/pedidos/", json=corpo).json()
    item = client.post(f"/pedidos/{pedido['id']}/itens", json={"produto_id": cenario["prato"]["id"], "quantidade": 3}).json()
    client.post(f"/pedidos/{pedido['id']}/itens/{item['id']}/iniciar-preparo")
    client.post(f"/pedidos/{pedido['id']}/itens/{item['id']}/concluir-preparo")
    client.post(f"/pedidos/{pedido['id']}/finalizar")

    dados = client.get("/estatisticas/").json()
    assert dados["pedidos_por_status"]["finalizado"] == 1
    assert dados["faturamento_centavos"] == dados["ticket_medio_centavos"] == 4500
