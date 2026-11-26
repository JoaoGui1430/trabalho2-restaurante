from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import BigInteger, cast, desc, func
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    FaturamentoDia,
    FechamentoConta,
    ItemPedido,
    Pedido,
    Produto,
    ProdutoRanking,
    StatusPedido,
)

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])

MAXIMO_DIAS = 366


class Periodo:
    """Intervalo inclusivo de datas, comparado com a data de fechamento da conta."""

    def __init__(
        self,
        data_inicio: date = Query(description="Primeiro dia, inclusive (AAAA-MM-DD)."),
        data_fim: date = Query(description="Último dia, inclusive (AAAA-MM-DD)."),
    ):
        if data_fim < data_inicio:
            raise HTTPException(
                status_code=422, detail="data_fim não pode ser anterior a data_inicio."
            )
        if (data_fim - data_inicio).days >= MAXIMO_DIAS:
            raise HTTPException(
                status_code=422,
                detail=f"O período deve ter no máximo {MAXIMO_DIAS} dias.",
            )
        self.data_inicio = data_inicio
        self.data_fim = data_fim

    def filtros(self):
        return [
            FechamentoConta.fechado_em >= datetime.combine(self.data_inicio, time.min),
            FechamentoConta.fechado_em <= datetime.combine(self.data_fim, time.max),
        ]


@router.get("/produtos-mais-vendidos", response_model=list[ProdutoRanking])
def produtos_mais_vendidos(
    periodo: Periodo = Depends(),
    limite: int = Query(10, ge=1, le=100, description="Tamanho do ranking."),
    session: Session = Depends(get_session),
):
    # Considera só contas finalizadas no período. Usa o preço aplicado em cada linha.
    quantidade = func.sum(ItemPedido.quantidade)
    faturamento = func.sum(
        cast(ItemPedido.quantidade, BigInteger) * ItemPedido.preco_unitario_centavos
    )
    consulta = (
        select(Produto.id, Produto.nome, quantidade, faturamento)
        .select_from(ItemPedido)
        .join(Pedido, ItemPedido.pedido_id == Pedido.id)
        .join(FechamentoConta, FechamentoConta.pedido_id == Pedido.id)
        .join(Produto, ItemPedido.produto_id == Produto.id)
        .where(Pedido.status == StatusPedido.FINALIZADO, *periodo.filtros())
        .group_by(Produto.id, Produto.nome)
        .order_by(desc(quantidade), Produto.nome, Produto.id)
        .limit(limite)
    )
    linhas = session.exec(consulta).all()
    return [
        ProdutoRanking(
            posicao=posicao,
            produto_id=produto_id,
            nome=nome,
            quantidade_vendida=int(qtd),
            faturamento_centavos=int(valor),
        )
        for posicao, (produto_id, nome, qtd, valor) in enumerate(linhas, start=1)
    ]


@router.get("/faturamento-diario", response_model=list[FaturamentoDia])
def faturamento_diario(
    periodo: Periodo = Depends(),
    session: Session = Depends(get_session),
):
    # Soma os fechamentos, não as linhas de itens, para não multiplicar valores no JOIN.
    dia = func.date(FechamentoConta.fechado_em)
    consulta = (
        select(dia, func.count(FechamentoConta.id), func.sum(FechamentoConta.total_centavos))
        .where(*periodo.filtros())
        .group_by(dia)
    )
    por_dia = {}
    for valor_dia, contas, total in session.exec(consulta).all():
        # SQLite devolve o dia como texto e PostgreSQL como date.
        chave = date.fromisoformat(valor_dia) if isinstance(valor_dia, str) else valor_dia
        por_dia[chave] = (int(contas), int(total))

    # Dias sem vendas aparecem com zero para o período ficar completo.
    resultado = []
    total_dias = (periodo.data_fim - periodo.data_inicio).days + 1
    for deslocamento in range(total_dias):
        atual = periodo.data_inicio + timedelta(days=deslocamento)
        contas, total = por_dia.get(atual, (0, 0))
        resultado.append(
            FaturamentoDia(
                data=atual, quantidade_contas=contas, faturamento_centavos=total
            )
        )
    return resultado
