# Telemetria Industrial — Postgres x BigQuery

Atividade prática de comparação de desempenho: os alunos carregam o mesmo
conjunto de dados (um arquivo Parquet já limpo e tipado) em **PostgreSQL** e no
**BigQuery** e comparam o tempo de execução das mesmas consultas.

Os dados vêm de um processo industrial de moagem, coletados a cada **5 minutos**
entre **2015 e 2021** (710.412 linhas, 51 colunas).

---

## Estrutura do repositório

```
.
├── docker-compose.yml              # Sobe o Postgres local (porta 5433)
├── requirements.txt                # Dependências Python (duckdb)
├── README.md
├── data/
│   └── parquet/
│       └── telemetria_industrial.parquet   # Base pronta (tipada) para carregar
├── scripts/
│   └── script_parquet_to_postgres.py       # Popula o Postgres a partir do Parquet
└── src/
    ├── __init__.py
    └── schema.py                   # Schema central / geração do DDL tipado
```

---

## Pré-requisitos

- **Docker** + **Docker Compose**
- **Python 3.10+** (testado com 3.14)
- Opcional: cliente **`psql`** instalado na máquina
- Opcional: **Google Cloud SDK** (`gcloud`/`bq`) para a Etapa 2
- Conexão com a internet (na primeira execução o DuckDB baixa a extensão `postgres`)

---

## Etapa 1 — PostgreSQL

### 1.1 Subir o banco

Na raiz do projeto:

```bash
docker compose up -d
```

Isso cria o container `postgres_telemetria` com o banco `telemetria_db` na porta
**5433** (mapeada para a 5432 do container).

### 1.2 Instalar as dependências Python

```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 1.3 Popular o banco a partir do Parquet

```bash
python scripts/script_parquet_to_postgres.py
```

Saída esperada: `PostgreSQL populado com sucesso a partir do Parquet!`

> O script é **idempotente**: ele recria a tabela `telemetria_industrial` a cada
> execução, então pode ser rodado quantas vezes quiser.

### 1.4 Conectar no psql e medir as consultas

Entre no banco pelo terminal:

```bash
docker exec -it -e PGPASSWORD=123 postgres_telemetria psql -U postgres -d telemetria_db
```

> Alternativa: se você tem o `psql` instalado na máquina, conecte direto no host:
> `psql "host=localhost port=5433 dbname=telemetria_db user=postgres password=123"`

Ative a medição de tempo e rode as consultas:

```sql
\timing on

-- 1) Contagem total
SELECT count(*) FROM telemetria_industrial;

-- 2) Média anual de alimentação do moinho
SELECT date_trunc('year', data) AS ano,
       avg(alimentacao_total_do_moinho_t_h) AS media
FROM telemetria_industrial
GROUP BY 1
ORDER BY 1;

-- 3) Potência média do motor do moinho quando a desviadora está ativa
SELECT avg(potencia_do_motor_do_moinho_kw)
FROM telemetria_industrial
WHERE desviadora_de_alimentacao_do_moinho_dg01 IS TRUE;
```

Anote o tempo de cada consulta para comparar com o BigQuery.

---

## Etapa 2 — BigQuery

### 2.1 Criar o dataset e carregar o Parquet

Com o `gcloud`/`bq` autenticado (`gcloud auth login`), crie um dataset e carregue
o arquivo:

```bash
bq mk --dataset <PROJETO>:telemetria
bq load --source_format=PARQUET --replace \
  <PROJETO>:telemetria.telemetria_industrial \
  data/parquet/telemetria_industrial.parquet
```

> Pelo **console do BigQuery** também funciona: *Criar tabela → Fonte: Upload →
> formato Parquet* e aponte para `data/parquet/telemetria_industrial.parquet`.

### 2.2 Rodar as mesmas consultas

```sql
-- 1) Contagem total
SELECT count(*) FROM `PROJETO.telemetria.telemetria_industrial`;

-- 2) Média anual de alimentação do moinho
SELECT DATE_TRUNC(data, YEAR) AS ano,
       AVG(alimentacao_total_do_moinho_t_h) AS media
FROM `PROJETO.telemetria.telemetria_industrial`
GROUP BY 1
ORDER BY 1;

-- 3) Potência média do motor do moinho quando a desviadora está ativa
SELECT AVG(potencia_do_motor_do_moinho_kw)
FROM `PROJETO.telemetria.telemetria_industrial`
WHERE desviadora_de_alimentacao_do_moinho_dg01 IS TRUE;
```

O console do BigQuery mostra o tempo e os **bytes processados** de cada consulta.

---

## Sobre os dados

- **Coluna `data`**: `timestamp`, chave primária, uma linha a cada 5 minutos.
- **49 colunas numéricas**: `double precision` / `FLOAT64` (alimentação, pressão,
  temperatura, potência, vibração, níveis de silo, etc.).
- **`desviadora_de_alimentacao_do_moinho_dg01`**: `boolean`
  (`Active` → `true`, `Inactive` → `false`).
- **Valores ausentes**: no histórico original, falhas e ausência de leitura
  apareciam como textos (`No Data`, `Bad Input`, `Intf Shut`, `Pt Created`, ...).
  Esses tokens foram convertidos em **`NULL`**. Ao calcular médias, considere usar
  `WHERE <coluna> IS NOT NULL` (a função `AVG` já ignora `NULL` automaticamente).

---

## Observações

- As credenciais e a porta (`localhost:5433`, usuário `postgres`, senha `123`) são
  apenas para o ambiente local da atividade.
- Para encerrar o banco: `docker compose down`
  (use `docker compose down -v` para também apagar os dados do container).
- O arquivo `data/parquet/telemetria_industrial.parquet` já está limpo e tipado —
  não é necessário baixar ou tratar os CSV originais.
