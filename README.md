# Sistema de Restaurante

Trabalho Prático 2 de Desenvolvimento de Software para Persistência, UFC Quixadá, 2026.2. Tema 8, Sistema de Restaurante.
João Guilherme Gadelha Abreu de Souza e Pedro Henrique Sampaio de Sousa.

## Objetivo e estado atual

A API gerencia categorias, produtos, mesas, garçons e pedidos. Registra itens com preços históricos, controla o preparo, calcula a conta e encerra o atendimento com preservação dos valores vendidos.

As etapas 1 a 10 estão implementadas. A estrutura inicial é criada pelo Alembic. PostgreSQL é o banco principal, e SQLite é a alternativa configurável.

| Requisito | Situação nesta versão |
|---|---|
| F1, cadastro | Implementado para as cinco entidades principais. |
| F2, listagem | Implementado por consultas ORM. |
| F3, consulta por ID | Implementado com tratamento de inexistência. |
| F4, atualização | Implementado nos campos permitidos pelo domínio. |
| F5, exclusão/desativação | Cadastros são desativados, itens pendentes podem ser removidos e pedidos podem ser cancelados. |
| F6, relacionamentos | 1:1, 1:N e N:N mapeados e usados nas operações. |
| F7, CRUD routers | Cinco routers de recursos principais registrados. |
| F8, paginação | Implementado em `GET /pedidos/` com `offset` e `limit`, aplicados na consulta ao banco. |
| F9, filtros | Implementado em `GET /pedidos/` com seis critérios combináveis, aplicados na consulta ao banco. |
| F10, três consultas relacionadas | Implementado em `/categorias/{id}/produtos`, `/mesas/{id}/pedidos` e `/pedidos/{id}/itens`. |
| F11, duas consultas complexas | Pendente, etapa 13. |
| F12, estatísticas | Pendente, etapa 13. |
| F13, regras de negócio | Implementadas no fluxo de venda e atendimento. |
| F14, evolução com Alembic | Parcial. A versão inicial está pronta. A evolução estrutural será feita na etapa 14. |
| F15, PostgreSQL e SQLite | Implementado e conferido nos dois bancos. |
| F16, povoamento | Pendente, etapa 15. |
| F17, função específica do restaurante | Implementado o fluxo de itens, total, preparo e fechamento, descrito abaixo. |
| F18, tratamento de erros | Implementado para entrada, vínculos, regras, integridade e falhas de conexão/persistência. |

## Tecnologias e organização

Python 3.12 ou superior, FastAPI, Uvicorn, SQLModel, SQLAlchemy, Pydantic, psycopg, python-dotenv e Alembic. O desenvolvimento local foi verificado em Python 3.14.3 e PostgreSQL 18. As dependências diretas estão fixadas em `requirements.txt`.

```text
trabalho2_restaurante/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   └── routers/
│       ├── categorias.py
│       ├── produtos.py
│       ├── mesas.py
│       ├── garcons.py
│       └── pedidos.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── .env.example
├── alembic.ini
├── requirements.txt
└── README.md
```

Tabelas e schemas Base/Create/Public/Update ficam em `models.py`, seguindo as aulas de SQLModel. As operações e validações de domínio ficam nos routers, com sessões injetadas por dependência. `database.py` centraliza a configuração e o ciclo de vida das sessões. O Alembic cria e versiona a estrutura.

## Modelo relacional

| Entidade | Responsabilidade |
|---|---|
| Categoria | Organizar os produtos do cardápio. |
| Produto | Manter descrição, preço atual, disponibilidade e vínculo com categoria. |
| Mesa | Identificar número, capacidade e habilitação para atendimento. |
| Garcom | Identificar matrícula e responsável pelo atendimento. |
| Pedido | Agrupar atendimento, modalidade, situação e datas. |
| ItemPedido | Relacionar pedido e produto com quantidade, preço aplicado e preparo. |
| FechamentoConta | Consolidar o valor e a data de uma conta finalizada. |

As cinco primeiras são as entidades principais. ItemPedido é a associação com dados da venda e FechamentoConta é o registro financeiro.

```mermaid
erDiagram
    CATEGORIA ||--o{ PRODUTO : classifica
    MESA o|--o{ PEDIDO : recebe
    GARCOM ||--o{ PEDIDO : registra
    PEDIDO ||--o{ ITEM_PEDIDO : contem
    PRODUTO ||--o{ ITEM_PEDIDO : participa
    PEDIDO ||--o| FECHAMENTO_CONTA : consolida
```

Categoria–Produto é 1:N. Pedido–Produto é N:N por ItemPedido, que guarda os dados de cada inclusão. Pedido–FechamentoConta é 1:1, opcional até a finalização. Os detalhes do pedido usam os relacionamentos para apresentar mesa, garçom, itens, produtos e fechamento.

Chaves estrangeiras restritivas preservam referências. Há unicidade para nome de categoria, número de mesa, matrícula de garçom e pedido do fechamento. Um índice único parcial impede dois pedidos abertos na mesma mesa.

Valores monetários usam centavos inteiros. Quantidades variam de 1 a 10.000, capacidade de mesa de 1 a 100, e preço unitário positivo até 2.147.483.647 centavos. Textos têm limites definidos nos schemas. Datas são registradas em UTC sem informação de fuso na coluna, de forma uniforme nos dois bancos.

## Instalação

Abra o terminal nesta pasta, onde estão `requirements.txt` e `alembic.ini`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` com a conexão do seu ambiente. Ele é carregado por caminho relativo ao projeto. Uma variável `DATABASE_URL` definida no terminal tem precedência sobre o arquivo.

## PostgreSQL

Com o PostgreSQL em execução e um usuário autorizado a criar bancos, prepare a base pelo psql. Informe a senha quando solicitada.

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE restaurante;"
```

Configure o `.env` com usuário, senha, host, porta e banco válidos.

```dotenv
DATABASE_URL=postgresql+psycopg://usuario:senha@127.0.0.1:5432/restaurante
```

Caracteres especiais da senha precisam ser codificados para uso em URL. Use um usuário com permissão sobre o banco. A instalação local desta máquina tem uma instância isolada na porta 55432, com a conexão já registrada no `.env` local.

## SQLite

Para selecionar SQLite no terminal atual, use a configuração abaixo. Ela substitui a seleção do `.env` durante essa sessão.

```powershell
$env:DATABASE_URL = 'sqlite:///./restaurante.db'
```

Quando `DATABASE_URL` está ausente no ambiente e no `.env`, a aplicação também usa esse SQLite local. As chaves estrangeiras são habilitadas por conexão. Escritas usam transações imediatas para serializar alterações concorrentes.

Para voltar à configuração do `.env` no terminal, execute o comando abaixo e reinicie a API.

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## Migrações e execução

Com a conexão selecionada, aplique a estrutura inicial e inicie a API.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abra a [documentação Swagger](http://127.0.0.1:8000/docs), a [rota inicial](http://127.0.0.1:8000/) ou o [OpenAPI](http://127.0.0.1:8000/openapi.json). Use Ctrl+C para encerrar o servidor.

As tabelas são criadas pela migração. Novas alterações estruturais terão novas revisões Alembic. A migração inicial sozinha prepara parte de F14, cuja evolução ainda será implementada.

O povoamento automático será acrescentado na etapa 15. Nesta versão, os registros podem ser cadastrados pelo Swagger.

## Endpoints disponíveis

| Recurso | Operações |
|---|---|
| `/categorias/` | POST cadastra e GET lista. |
| `/categorias/{id}` | GET consulta, PATCH atualiza e DELETE desativa. |
| `/categorias/{id}/produtos` | GET lista os produtos da categoria. |
| `/produtos/` | POST cadastra e GET lista. |
| `/produtos/{id}` | GET consulta, PATCH atualiza e DELETE desativa. |
| `/mesas/` | POST cadastra e GET lista. |
| `/mesas/{id}` | GET consulta, PATCH atualiza e DELETE desativa. |
| `/mesas/{id}/pedidos` | GET lista o histórico de pedidos da mesa, com garçom, itens e produtos. |
| `/garcons/` | POST cadastra e GET lista. |
| `/garcons/{id}` | GET consulta, PATCH atualiza e DELETE desativa. |
| `/pedidos/` | POST abre e GET lista com paginação (`offset`, padrão 0, e `limit`, padrão 20, máximo 100). A resposta traz `total`, `offset`, `limit` e `itens`. |
| `/pedidos/{id}` | GET detalha, PATCH troca o responsável e DELETE cancela. |
| `/pedidos/{id}/itens` | POST inclui produto e quantidade, e GET lista os itens com os dados dos produtos. |
| `/pedidos/{id}/itens/{item_id}` | PATCH reduz quantidade e DELETE remove item elegível. |
| `/pedidos/{id}/itens/{item_id}/iniciar-preparo` | POST inicia o preparo. |
| `/pedidos/{id}/itens/{item_id}/concluir-preparo` | POST marca o item como pronto. |
| `/pedidos/{id}/finalizar` | POST fecha a conta e encerra o atendimento. |

As listagens retornam os registros ordenados, e a de pedidos é paginada e filtrável. Os filtros de `GET /pedidos/` podem ser combinados entre si e com a paginação, e o `total` considera os filtros aplicados.

| Filtro | Efeito |
|---|---|
| `status` | `aberto`, `finalizado` ou `cancelado`. |
| `mesa_id` | Pedidos da mesa informada. |
| `produto_id` | Pedidos com ao menos uma linha do produto, sem repetir o pedido. |
| `modalidade` | `mesa` ou `retirada`. |
| `data_inicio`, `data_fim` | Período de criação, datas inclusivas no formato AAAA-MM-DD. |

Os dois relatórios complexos e as estatísticas estão previstos na etapa 13.

## Regras e função específica do tema

1. Pedido de mesa exige mesa ativa e livre. Retirada exige mesa_id nulo. Ambas as modalidades exigem garçom ativo.
2. Produtos precisam estar ativos e disponíveis, em categoria ativa, para novas inclusões.
3. Cada inclusão registra o preço atual em uma linha própria. Mudanças no cardápio preservam os preços aplicados às linhas anteriores.
4. A API calcula o total pela soma de quantidade × preço aplicado. O cliente informa produto e quantidade ao incluir um item.
5. Apenas pedidos abertos permitem alterações. Item pendente admite redução da quantidade ou remoção. Acréscimos usam nova inclusão e preço atual.
6. O preparo segue pendente → em_preparo → pronto. Avançar o estado usa a operação correspondente.
7. Fechamento exige ao menos um item e todos os itens prontos. Pedido, total consolidado e fechamento único são persistidos na mesma transação.
8. Cancelamento exige pedido aberto com todos os itens pendentes. Pedido vazio pode ser cancelado.
9. Finalização e cancelamento liberam a mesa. Pedidos encerrados preservam o histórico e bloqueiam alterações.
10. Desativação de mesa ou garçom com pedido aberto é rejeitada. Desativação de produtos e categorias preserva as vendas anteriores.

As políticas exatas de preparo, cancelamento, responsável e ocupação são escolhas de implementação para o cenário do restaurante.

Exemplo de preço histórico. Inclua duas unidades a 1500 centavos, altere o preço atual para 1800 e inclua mais uma unidade. A conta será de 4800 centavos, com duas linhas preservando seus preços. A consulta detalhada apresenta os subtotais, o total e, após finalizar, o fechamento consolidado.

## Erros e integridade

A API retorna 201 na criação, 200 na leitura e atualização, 204 na desativação, remoção ou cancelamento, 404 para inexistência, 409 para conflitos e 422 para entradas inválidas. PATCH vazio é rejeitado e campos omitidos são preservados. Campos controlados pelo servidor são rejeitados nas entradas.

Falhas de integridade recebem resposta controlada e rollback. Falhas de conexão ou persistência recebem HTTP 500 com mensagem compreensível. No PostgreSQL, alterações de atendimento usam bloqueios de linha. No SQLite, as escritas usam BEGIN IMMEDIATE. O índice de ocupação e a unicidade do fechamento complementam essas transações.

## Referências

A organização deriva da clínica SQLModel das aulas 11 a 13 e das migrações da aula 14, consultadas no commit `04706d64181c1ad33d2ef0494f79093dc59b92fd`.

[Material de implementação do professor](https://github.com/pinheirovictor/2026.2_QXD0099_persistencia/tree/04706d64181c1ad33d2ef0494f79093dc59b92fd)

O uso de sessão por dependência e o controle de transações SQLite também seguem a documentação técnica das bibliotecas.

[Sessões no SQLModel](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/) · [Transações SQLite no SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#transactions-with-sqlite-and-the-sqlite3-driver)
