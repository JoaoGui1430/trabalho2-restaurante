from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import ConfigDict, StrictInt, field_validator, model_validator
from sqlalchemy import BigInteger, CheckConstraint, Enum as SAEnum, Index, text
from sqlmodel import Field, Relationship, SQLModel

MAXIMO_ID = 2_147_483_647
MAXIMO_INTEIRO_SQL = 9_223_372_036_854_775_807


class ModalidadePedido(str, Enum):
    MESA = "mesa"
    RETIRADA = "retirada"


class StatusPedido(str, Enum):
    ABERTO = "aberto"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class StatusPreparo(str, Enum):
    PENDENTE = "pendente"
    EM_PREPARO = "em_preparo"
    PRONTO = "pronto"


class DadosValidados(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Categoria


class CategoriaBase(DadosValidados):
    nome: str = Field(min_length=2, max_length=80, unique=True, index=True)
    descricao: str | None = Field(default=None, max_length=300)
    ativo: bool = True


class Categoria(CategoriaBase, table=True):
    __table_args__ = (
        CheckConstraint("length(trim(nome)) >= 2", name="ck_categoria_nome"),
    )

    id: int | None = Field(default=None, primary_key=True)
    produtos: list["Produto"] = Relationship(
        back_populates="categoria",
        sa_relationship_kwargs={"passive_deletes": "all"},
    )


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaPublic(CategoriaBase):
    id: int


class CategoriaUpdate(DadosValidados):
    nome: str | None = Field(default=None, min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=300)
    ativo: bool | None = None

    @field_validator("nome", "ativo", mode="before")
    @classmethod
    def rejeitar_nulo(cls, valor):
        if valor is None:
            raise ValueError("Informe um valor para este campo ou deixe de enviá-lo.")
        return valor


# Produto


class ProdutoBase(DadosValidados):
    nome: str = Field(min_length=2, max_length=120, index=True)
    descricao: str | None = Field(default=None, max_length=500)
    preco_centavos: StrictInt = Field(gt=0, le=2_147_483_647)
    disponivel: bool = True
    ativo: bool = True
    categoria_id: int = Field(
        gt=0,
        le=MAXIMO_ID,
        foreign_key="categoria.id",
        ondelete="RESTRICT",
        index=True,
    )


class Produto(ProdutoBase, table=True):
    __table_args__ = (
        CheckConstraint("length(trim(nome)) >= 2", name="ck_produto_nome"),
        CheckConstraint("preco_centavos > 0", name="ck_produto_preco"),
    )

    id: int | None = Field(default=None, primary_key=True)
    categoria: Categoria | None = Relationship(back_populates="produtos")
    itens: list["ItemPedido"] = Relationship(
        back_populates="produto",
        sa_relationship_kwargs={"passive_deletes": "all"},
    )


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoPublic(ProdutoBase):
    id: int


class ProdutoUpdate(DadosValidados):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=500)
    preco_centavos: StrictInt | None = Field(default=None, gt=0, le=2_147_483_647)
    disponivel: bool | None = None
    ativo: bool | None = None
    categoria_id: int | None = Field(default=None, gt=0, le=MAXIMO_ID)

    @field_validator(
        "nome", "preco_centavos", "disponivel", "ativo", "categoria_id", mode="before"
    )
    @classmethod
    def rejeitar_nulo(cls, valor):
        if valor is None:
            raise ValueError("Informe um valor para este campo ou deixe de enviá-lo.")
        return valor


# Mesa


class MesaBase(DadosValidados):
    numero: StrictInt = Field(gt=0, le=2_147_483_647, unique=True)
    capacidade: StrictInt = Field(gt=0, le=100)
    ativo: bool = True


class Mesa(MesaBase, table=True):
    __table_args__ = (
        CheckConstraint("numero > 0", name="ck_mesa_numero"),
        CheckConstraint("capacidade BETWEEN 1 AND 100", name="ck_mesa_capacidade"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pedidos: list["Pedido"] = Relationship(
        back_populates="mesa",
        sa_relationship_kwargs={"passive_deletes": "all"},
    )


class MesaCreate(MesaBase):
    pass


class MesaPublic(MesaBase):
    id: int


class MesaUpdate(DadosValidados):
    numero: StrictInt | None = Field(default=None, gt=0, le=2_147_483_647)
    capacidade: StrictInt | None = Field(default=None, gt=0, le=100)
    ativo: bool | None = None

    @field_validator("numero", "capacidade", "ativo", mode="before")
    @classmethod
    def rejeitar_nulo(cls, valor):
        if valor is None:
            raise ValueError("Informe um valor para este campo ou deixe de enviá-lo.")
        return valor


# Garcom


class GarcomBase(DadosValidados):
    nome: str = Field(min_length=3, max_length=120, index=True)
    matricula: str = Field(min_length=1, max_length=30, unique=True)
    ativo: bool = True


class Garcom(GarcomBase, table=True):
    __table_args__ = (
        CheckConstraint("length(trim(nome)) >= 3", name="ck_garcom_nome"),
        CheckConstraint("length(trim(matricula)) >= 1", name="ck_garcom_matricula"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pedidos: list["Pedido"] = Relationship(
        back_populates="garcom",
        sa_relationship_kwargs={"passive_deletes": "all"},
    )


class GarcomCreate(GarcomBase):
    pass


class GarcomPublic(GarcomBase):
    id: int


class GarcomUpdate(DadosValidados):
    nome: str | None = Field(default=None, min_length=3, max_length=120)
    matricula: str | None = Field(default=None, min_length=1, max_length=30)
    ativo: bool | None = None

    @field_validator("nome", "matricula", "ativo", mode="before")
    @classmethod
    def rejeitar_nulo(cls, valor):
        if valor is None:
            raise ValueError("Informe um valor para este campo ou deixe de enviá-lo.")
        return valor


# Pedido


class PedidoBase(DadosValidados):
    modalidade: ModalidadePedido = Field(
        sa_type=SAEnum(
            ModalidadePedido,
            values_callable=lambda valores: [valor.value for valor in valores],
            native_enum=False,
            create_constraint=True,
            name="modalidade_pedido",
        )
    )
    mesa_id: int | None = Field(
        default=None,
        gt=0,
        le=MAXIMO_ID,
        foreign_key="mesa.id",
        ondelete="RESTRICT",
        index=True,
    )
    garcom_id: int = Field(
        gt=0,
        le=MAXIMO_ID,
        foreign_key="garcom.id",
        ondelete="RESTRICT",
        index=True,
    )
    observacao: str | None = Field(default=None, min_length=1, max_length=300)


class Pedido(PedidoBase, table=True):
    __table_args__ = (
        CheckConstraint(
            "(modalidade = 'mesa' AND mesa_id IS NOT NULL) OR "
            "(modalidade = 'retirada' AND mesa_id IS NULL)",
            name="ck_pedido_modalidade_mesa",
        ),
        CheckConstraint(
            "(status = 'aberto' AND encerrado_em IS NULL) OR "
            "(status IN ('finalizado', 'cancelado') AND encerrado_em IS NOT NULL)",
            name="ck_pedido_encerramento",
        ),
        CheckConstraint(
            "encerrado_em IS NULL OR encerrado_em >= criado_em",
            name="ck_pedido_datas",
        ),
        Index(
            "uq_pedido_mesa_aberta",
            "mesa_id",
            unique=True,
            sqlite_where=text("status = 'aberto'"),
            postgresql_where=text("status = 'aberto'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    status: StatusPedido = Field(
        default=StatusPedido.ABERTO,
        index=True,
        sa_type=SAEnum(
            StatusPedido,
            values_callable=lambda valores: [valor.value for valor in valores],
            native_enum=False,
            create_constraint=True,
            name="status_pedido",
        ),
    )
    # UTC sem fuso no armazenamento mantém o mesmo formato nos dois bancos.
    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
    encerrado_em: datetime | None = None

    mesa: Mesa | None = Relationship(back_populates="pedidos")
    garcom: Garcom | None = Relationship(back_populates="pedidos")
    itens: list["ItemPedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"passive_deletes": "all"},
    )
    fechamento: Optional["FechamentoConta"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"uselist": False, "passive_deletes": "all"},
    )

    @property
    def total_centavos(self) -> int:
        return sum(item.subtotal_centavos for item in self.itens)


class PedidoCreate(PedidoBase):
    @model_validator(mode="after")
    def validar_mesa(self):
        if self.modalidade == ModalidadePedido.MESA and self.mesa_id is None:
            raise ValueError("Pedido de mesa exige mesa_id.")
        if self.modalidade == ModalidadePedido.RETIRADA and self.mesa_id is not None:
            raise ValueError("Pedido de retirada deve ter mesa_id nulo.")
        return self


class PedidoPublic(PedidoBase):
    id: int
    status: StatusPedido
    criado_em: datetime
    encerrado_em: datetime | None


class PedidoPagina(SQLModel):
    total: int
    offset: int
    limit: int
    itens: list[PedidoPublic]


class PedidoUpdate(DadosValidados):
    garcom_id: int | None = Field(default=None, gt=0, le=MAXIMO_ID)
    # Nulo é aceito em observacao para permitir limpar o texto.
    observacao: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("garcom_id", mode="before")
    @classmethod
    def rejeitar_nulo(cls, valor):
        if valor is None:
            raise ValueError("Informe um valor para este campo ou deixe de enviá-lo.")
        return valor


# ItemPedido


class ItemPedidoCreate(DadosValidados):
    produto_id: int = Field(gt=0, le=MAXIMO_ID)
    quantidade: StrictInt = Field(gt=0, le=10_000)


class ItemPedidoBase(ItemPedidoCreate):
    pedido_id: int = Field(
        gt=0,
        le=MAXIMO_ID,
        foreign_key="pedido.id",
        ondelete="RESTRICT",
        index=True,
    )
    produto_id: int = Field(
        gt=0,
        le=MAXIMO_ID,
        foreign_key="produto.id",
        ondelete="RESTRICT",
        index=True,
    )
    preco_unitario_centavos: StrictInt = Field(gt=0, le=2_147_483_647)


class ItemPedido(ItemPedidoBase, table=True):
    __tablename__ = "item_pedido"
    __table_args__ = (
        CheckConstraint("quantidade BETWEEN 1 AND 10000", name="ck_item_quantidade"),
        CheckConstraint("preco_unitario_centavos > 0", name="ck_item_preco"),
    )

    id: int | None = Field(default=None, primary_key=True)
    status_preparo: StatusPreparo = Field(
        default=StatusPreparo.PENDENTE,
        sa_type=SAEnum(
            StatusPreparo,
            values_callable=lambda valores: [valor.value for valor in valores],
            native_enum=False,
            create_constraint=True,
            name="status_preparo",
        ),
    )
    pedido: Pedido | None = Relationship(back_populates="itens")
    produto: Produto | None = Relationship(back_populates="itens")

    @property
    def subtotal_centavos(self) -> int:
        return self.quantidade * self.preco_unitario_centavos


class ItemPedidoPublic(ItemPedidoBase):
    id: int
    status_preparo: StatusPreparo
    subtotal_centavos: int


class ItemPedidoUpdate(DadosValidados):
    quantidade: StrictInt = Field(gt=0, le=10_000)


# FechamentoConta


class FechamentoContaBase(DadosValidados):
    pedido_id: int = Field(
        gt=0,
        le=MAXIMO_ID,
        foreign_key="pedido.id",
        ondelete="RESTRICT",
        unique=True,
    )
    total_centavos: StrictInt = Field(
        gt=0, le=9_223_372_036_854_775_807, sa_type=BigInteger
    )


class FechamentoConta(FechamentoContaBase, table=True):
    __tablename__ = "fechamento_conta"
    __table_args__ = (
        CheckConstraint("total_centavos > 0", name="ck_fechamento_total"),
    )

    id: int | None = Field(default=None, primary_key=True)
    fechado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
    pedido: Pedido | None = Relationship(back_populates="fechamento")


class FechamentoContaPublic(FechamentoContaBase):
    id: int
    fechado_em: datetime


class ItemPedidoPublicDetalhado(ItemPedidoPublic):
    produto: ProdutoPublic


class PedidoPublicDetalhado(PedidoPublic):
    mesa: MesaPublic | None
    garcom: GarcomPublic
    itens: list[ItemPedidoPublicDetalhado]
    fechamento: FechamentoContaPublic | None
    total_centavos: int


# Relatórios


class ProdutoRanking(SQLModel):
    posicao: int
    produto_id: int
    nome: str
    quantidade_vendida: int
    faturamento_centavos: int


class FaturamentoDia(SQLModel):
    data: date
    quantidade_contas: int
    faturamento_centavos: int


# Estatísticas


class PedidosPorStatus(SQLModel):
    aberto: int
    finalizado: int
    cancelado: int


class Estatisticas(SQLModel):
    total_pedidos: int
    pedidos_por_status: PedidosPorStatus
    contas_finalizadas: int
    faturamento_centavos: int
    ticket_medio_centavos: int
