# Sistema de Restaurante

Trabalho Prático 2 de Desenvolvimento de Software para Persistência, UFC Quixadá, 2026.2. Tema 8, Sistema de Restaurante.
João Guilherme Gadelha Abreu de Souza e Pedro Henrique Sampaio de Sousa.

## Objetivo e estado atual

A API gerencia categorias, produtos, mesas, garçons e pedidos. Registra itens com preços históricos, controla o preparo, calcula a conta e encerra o atendimento com preservação dos valores vendidos.

Todos os requisitos F1 a F18 estão implementados. A estrutura é criada e evoluída pelo Alembic, e o povoamento de demonstração é feito por script. PostgreSQL é o banco principal, e SQLite é a alternativa configurável.

| Requisito | Situação nesta versão |
|---|---|
| F1, cadastro | Implementado para as cinco entidades principais. |
| F2, listagem | Implementado por consultas ORM. |
| F3, consulta por ID | Implementado com tratamento de inexistência. |
| F4, atualização | Implementado nos campos permitidos pelo domínio. |
| F5, exclusão/desativação | Cadastros são desativados, itens pendentes podem ser removidos e pedidos podem ser cancelados. |
| F6, relacionamentos | 1:1, 1:N e N:N mapeados e usados nas operações. |
| F7, CRUD routers | Cinco routers de recursos principais registrados, além dos routers de relatórios e estatísticas. |
| F8, paginação | Implementado em `GET /pedidos/` com `offset` e `limit`, aplicados na consulta ao banco. |
| F9, filtros | Implementado em `GET /pedidos/` com seis critérios combináveis, aplicados na consulta ao banco. |
| F10, três consultas relacionadas | Implementado em `/categorias/{id}/produtos`, `/mesas/{id}/pedidos` e `/pedidos/{id}/itens`. |
| F11, duas consultas complexas | Implementado em `/relatorios/produtos-mais-vendidos` e `/relatorios/faturamento-diario`. |
| F12, estatísticas | Implementado em `GET /estatisticas/`, com agregações feitas no banco. |
| F13, regras de negócio | Implementadas no fluxo de venda e atendimento. |
| F14, evolução com Alembic | Implementado. A revisão `0002` adiciona `observacao` a `pedido` sobre um banco já povoado, sem perder registros. |
| F15, PostgreSQL e SQLite | Implementado e conferido nos dois bancos. |
| F16, povoamento | Implementado em `python -m app.povoamento`, repetível e sem apagar dados. |
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
│   ├── povoamento.py
│   └── routers/
│       ├── categorias.py
│       ├── produtos.py
│       ├── mesas.py
│       ├── garcons.py
│       ├── pedidos.py
│       ├── relatorios.py
│       └── estatisticas.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
├── .env.example
├── alembic.ini
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
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
| Pedido | Agrupar atendimento, modalidade, situação, datas e uma observação opcional. |
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

IDs recebidos pela API vão de 1 a 2.147.483.647, compatíveis com as chaves INTEGER do PostgreSQL. O offset vai de zero a 9.223.372.036.854.775.807. Valores acima desses limites recebem HTTP 422.

## Instalação

### Pré-requisitos

As instruções abaixo usam **Windows e PowerShell**. No VS Code, selecione PowerShell no menu do terminal. O ambiente de desenvolvimento foi conferido com Python 3.14.3 e PostgreSQL 18.6.

1. Instale [Python para Windows](https://www.python.org/downloads/windows/), versão 3.12 ou superior. No instalador tradicional, habilite a opção de adicionar Python ao PATH. Abra um terminal novo depois da instalação e confira `python --version`. Se a instalação disponibilizar apenas `py`, use `py -m venv .venv` na criação do ambiente abaixo.
2. Para usar o banco principal, instale [PostgreSQL para Windows](https://www.postgresql.org/download/windows/). A versão 18 foi usada no desenvolvimento. Inclua o servidor e as ferramentas de linha de comando (`psql`); o pgAdmin pode ser usado como alternativa gráfica. Anote a senha definida para o usuário `postgres` e a porta escolhida, normalmente `5432`.
3. Deixe o servidor PostgreSQL em execução. Se ele estiver parado, abra o aplicativo Serviços do Windows e inicie o serviço da instalação PostgreSQL. É possível verificar sua situação no PowerShell com `Get-Service *postgres*`.
4. Tenha acesso à internet para baixar as dependências. SQLite já é disponibilizado pelo Python e pode ser escolhido como alternativa, sem instalar o servidor PostgreSQL.

### Obter o projeto

Baixe e extraia o ZIP do repositório, ou, se tiver Git instalado, execute:

```powershell
git clone https://github.com/JoaoGui1430/trabalho2-restaurante.git
cd trabalho2-restaurante
```

Abra o terminal na raiz do projeto, onde estão `requirements.txt` e `alembic.ini`. Os arquivos `.venv`, `.env` e os bancos locais são preparados em cada máquina.

### Criar o ambiente e instalar as dependências

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Os comandos de execução deste README usam diretamente o Python da `.venv`, então a ativação do ambiente é opcional.

### Preparar a configuração

Na primeira instalação, crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Edite `.env` conforme o banco escolhido nas próximas seções. Ele é carregado a partir da raiz do projeto. Uma variável `DATABASE_URL` definida no terminal tem precedência sobre o arquivo. O exemplo contém marcadores de usuário e senha, que devem ser substituídos pelos dados reais da instalação.

## PostgreSQL

Com o PostgreSQL em execução, crie o banco vazio pelo `psql`, usando o usuário administrativo `postgres` criado na instalação. Informe a senha quando solicitada. O comando usa a porta padrão `5432`; ajuste-a se escolheu outra porta.

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE restaurante;"
```

Se `psql` não for reconhecido, execute pelo caminho completo. Para PostgreSQL 18 instalado no diretório padrão:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE restaurante;"
```

Ajuste o diretório se instalou outra versão ou escolheu outro local. Como alternativa, no pgAdmin conecte ao servidor com o usuário `postgres`, abra o Query Tool do banco administrativo `postgres` e execute separadamente, com Auto-commit habilitado:

```sql
CREATE DATABASE restaurante;
```

Escolha uma das formas acima para criar o banco. Se `restaurante` já existir por uma configuração anterior deste projeto, use esse banco e continue para as migrações.

Configure o `.env` com os dados da mesma instalação. O exemplo abaixo usa o usuário `postgres`, que criou o banco, e a porta padrão. Substitua `SUA_SENHA` pela senha desse usuário:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:SUA_SENHA@127.0.0.1:5432/restaurante
```

Caracteres especiais da senha precisam ser codificados para uso em URL. Por exemplo, `@` vira `%40`, `#` vira `%23` e `%` vira `%25`. A senha `Minha@Senha` seria escrita como `Minha%40Senha` na URL; no pedido de senha do `psql`, informe a senha original.

Se preferir outro usuário, ele deve ter permissão para conectar ao banco, criar e alterar tabelas, índices e restrições pelas migrações, e consultar e modificar os dados da aplicação. A porta `55432` usada em uma instância isolada do desenvolvimento é específica daquele ambiente. Em outra máquina, use a porta da própria instalação.

O `CREATE DATABASE` cria a base vazia. As tabelas serão criadas por `alembic upgrade head`; não é necessário criá-las manualmente.

## SQLite

Para usar SQLite, substitua a linha ativa de `DATABASE_URL` no `.env` por:

```dotenv
DATABASE_URL=sqlite:///./restaurante.db
```

Mantenha apenas uma definição ativa de `DATABASE_URL` no arquivo. O arquivo `restaurante.db` será criado na raiz quando as migrações forem aplicadas. Não é necessário criar um banco previamente ou instalar um servidor SQLite.

Para selecionar SQLite apenas no terminal atual, use a configuração abaixo. Ela substitui a seleção do `.env` durante essa sessão.

```powershell
$env:DATABASE_URL = 'sqlite:///./restaurante.db'
```

Quando `DATABASE_URL` está ausente no ambiente e no `.env`, a aplicação também usa esse SQLite local. As chaves estrangeiras são habilitadas por conexão. Escritas usam transações imediatas para serializar alterações concorrentes.

A reversão da migração `0002` usa `ALTER TABLE DROP COLUMN` e requer SQLite 3.35 ou superior. A conferência local foi realizada com SQLite 3.50.4 e PostgreSQL 18.6.

Para remover a seleção temporária e voltar à configuração do `.env`, execute o comando abaixo e reinicie a API. Se também alterou o arquivo, restaure nele a URL do PostgreSQL quando quiser retornar a esse banco.

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## Migrações e execução

Depois de configurar o banco escolhido, execute na raiz do projeto, nesta ordem:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m app.povoamento
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

O `current` deve indicar `0002 (head)`. O povoamento prepara os dados antes de iniciar o servidor. Aguarde a mensagem `Application startup complete` e abra a [documentação Swagger](http://127.0.0.1:8000/docs), a [rota inicial](http://127.0.0.1:8000/) ou o [OpenAPI](http://127.0.0.1:8000/openapi.json). O terminal fica ocupado pelo Uvicorn enquanto o servidor estiver rodando. Use Ctrl+C para encerrá-lo.

As tabelas são criadas pela migração. Novas alterações estruturais terão novas revisões Alembic. Em um banco já atualizado, `upgrade head` não reaplica as revisões concluídas. Ao trocar PostgreSQL por SQLite, ou o contrário, execute as migrações e o povoamento também no banco selecionado. A troca da URL não transfere dados entre os bancos.

| Revisão | Alteração |
|---|---|
| `0001` | Estrutura inicial com as sete tabelas, restrições e índices. |
| `0002` | Adiciona a coluna opcional `observacao` (até 300 caracteres) a `pedido`. Os pedidos existentes ficam com o valor nulo. |

A `0002` foi aplicada sobre um banco da `0001` que já tinha registros, e eles foram preservados. Seu `upgrade` usa `op.add_column`, e seu `downgrade` usa `op.drop_column`, com `ALTER TABLE` nativo nos dois bancos. O `alembic downgrade 0001` remove a coluna `observacao`, perdendo os textos armazenados nela e preservando os demais registros e vínculos. Para demonstrar a reversão, use um banco separado de demonstração.

## Povoamento

Com a estrutura aplicada (`alembic upgrade head`), carregue os dados de demonstração.

```powershell
.\.venv\Scripts\python.exe -m app.povoamento
```

O povoamento preserva a situação dos cadastros existentes. Para criar os pedidos de demonstração, precisa de ao menos duas mesas ativas, um garçom ativo e um produto ativo e disponível em categoria ativa. Se esses cadastros não estiverem disponíveis, retorna uma mensagem de orientação e reverte a execução.

| Entidade | Dados criados |
|---|---|
| Categoria | 4 (entradas, pratos principais, bebidas e sobremesas). |
| Produto | 14, com um indisponível (torta de limão). |
| Mesa | 9, com uma inativa. |
| Garçom | 4, com um inativo. |
| Pedido | 51: 45 finalizados em 21 dias (com 45 fechamentos), 3 cancelados e 3 abertos (duas mesas e uma retirada). |
| ItemPedido | Cerca de 120 linhas, com itens pendentes, em preparo e prontos. |

Os pedidos mais antigos usam os preços anteriores de alguns produtos (por exemplo, bife acebolado e cerveja), o que mostra o preço histórico nas consultas e nos relatórios. Parte dos pedidos tem observação.

O script não apaga nada. Cadastros existentes são encontrados pelos critérios de identificação do povoamento: nome da categoria, nome e categoria do produto, número da mesa e matrícula do garçom. Nome e categoria do produto são um critério de busca do script, sem uma restrição UNIQUE composta no banco. Os pedidos só são criados quando a tabela de pedidos está vazia. Repetir o comando não duplica os dados de demonstração. Se o banco ainda não estiver na última revisão, o script avisa e não grava nada. Os dados são gravados em uma única transação.

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
| `/pedidos/{id}` | GET detalha, PATCH troca o responsável ou altera a observação (`null` limpa o texto) e DELETE cancela. |
| `/pedidos/{id}/itens` | POST inclui produto e quantidade, e GET lista os itens com os dados dos produtos. |
| `/pedidos/{id}/itens/{item_id}` | PATCH reduz quantidade e DELETE remove item elegível. |
| `/pedidos/{id}/itens/{item_id}/iniciar-preparo` | POST inicia o preparo. |
| `/pedidos/{id}/itens/{item_id}/concluir-preparo` | POST marca o item como pronto. |
| `/pedidos/{id}/finalizar` | POST fecha a conta e encerra o atendimento. |
| `/relatorios/produtos-mais-vendidos` | GET ranking de produtos por quantidade vendida no período. |
| `/relatorios/faturamento-diario` | GET faturamento e quantidade de contas por dia no período. |
| `/estatisticas/` | GET estatísticas gerais: pedidos por situação, faturamento e ticket médio. |

As listagens retornam os registros ordenados, e a de pedidos é paginada e filtrável. Os filtros de `GET /pedidos/` podem ser combinados entre si e com a paginação, e o `total` considera os filtros aplicados.

| Filtro | Efeito |
|---|---|
| `status` | `aberto`, `finalizado` ou `cancelado`. |
| `mesa_id` | Pedidos da mesa informada. |
| `produto_id` | Pedidos com ao menos uma linha do produto, sem repetir o pedido. |
| `modalidade` | `mesa` ou `retirada`. |
| `data_inicio`, `data_fim` | Período de criação, datas inclusivas no formato AAAA-MM-DD. |

## Relatórios

Os dois relatórios usam apenas contas finalizadas. Pedidos abertos e cancelados ficam de fora. O período é obrigatório (`data_inicio` e `data_fim`, inclusivas, AAAA-MM-DD, máximo de 366 dias) e é comparado com a data de fechamento da conta.

| Relatório | Cálculo |
|---|---|
| `produtos-mais-vendidos` | Soma a quantidade por produto e o valor pelos preços aplicados em cada linha. Ordena da maior para a menor quantidade, desempatando por nome. `limite` define o tamanho do ranking, de 1 a 100, com padrão 10. |
| `faturamento-diario` | Soma o total dos fechamentos por dia, sem passar pelos itens, para não multiplicar valores. Dias sem vendas aparecem com zero. |

## Estatísticas

`GET /estatisticas/` consolida toda a base e não recebe parâmetros. As contagens e somas são feitas no banco.

| Campo | Cálculo |
|---|---|
| `total_pedidos` | Soma dos pedidos de todas as situações. |
| `pedidos_por_status` | Quantidade de `aberto`, `finalizado` e `cancelado`, com zero quando não há pedidos na situação. |
| `contas_finalizadas` | Quantidade de fechamentos de conta. |
| `faturamento_centavos` | Soma dos totais dos fechamentos. Pedidos abertos e cancelados não entram. |
| `ticket_medio_centavos` | Faturamento dividido pelas contas finalizadas, arredondado para o centavo mais próximo. Vale zero sem contas. |

Com a base povoada, a resposta tem 51 pedidos (45 finalizados, 3 cancelados e 3 abertos).

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Os testes criam um SQLite temporário com as migrações do Alembic e não tocam no banco do `.env`. Cobrem o preço histórico, o total, o fechamento e o cancelamento, a ocupação de mesa, o bloqueio de pedidos encerrados, a paginação, os filtros, os relatórios e as estatísticas conferidos contra cálculos independentes, a repetição do povoamento e a evolução da migração `0002` sobre dados existentes.

Para repetir a suíte em PostgreSQL, informe um banco **exclusivo para testes** em `TESTE_DATABASE_URL`. Cada teste apaga todos os registros ao terminar, então nunca aponte para o banco de uso real.

```powershell
$env:TESTE_DATABASE_URL = 'postgresql+psycopg://usuario:senha@127.0.0.1:5432/restaurante_teste'
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:TESTE_DATABASE_URL
```

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

O uso de sessão por dependência e o controle de transações SQLite também seguem a documentação técnica das bibliotecas.

[Sessões no SQLModel](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/) · [Transações SQLite no SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#transactions-with-sqlite-and-the-sqlite3-driver)
