from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Estatisticas,
    FechamentoConta,
    Pedido,
    PedidosPorStatus,
    StatusPedido,
)

router = APIRouter(prefix="/estatisticas", tags=["Estatísticas"])


@router.get("/", response_model=Estatisticas)
def obter_estatisticas(session: Session = Depends(get_session)):
    # Contagem por situação, feita pelo banco com GROUP BY.
    contagens = dict(
        session.exec(select(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status)).all()
    )
    por_status = PedidosPorStatus(
        aberto=contagens.get(StatusPedido.ABERTO, 0),
        finalizado=contagens.get(StatusPedido.FINALIZADO, 0),
        cancelado=contagens.get(StatusPedido.CANCELADO, 0),
    )

    # Faturamento vem dos fechamentos: só contas finalizadas têm fechamento.
    contas, faturamento = session.exec(
        select(func.count(FechamentoConta.id), func.coalesce(func.sum(FechamentoConta.total_centavos), 0))
    ).one()
    contas, faturamento = int(contas), int(faturamento)

    # Ticket médio em centavos inteiros, arredondado para o centavo mais próximo.
    ticket_medio = (faturamento * 2 + contas) // (contas * 2) if contas else 0

    return Estatisticas(
        total_pedidos=por_status.aberto + por_status.finalizado + por_status.cancelado,
        pedidos_por_status=por_status,
        contas_finalizadas=contas,
        faturamento_centavos=faturamento,
        ticket_medio_centavos=ticket_medio,
    )
