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
├── docs/
│   └── guia_bigquery_parquet_alunos.pdf    # Tutorial da Etapa 2 (BigQuery)
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

> Guia completo em PDF: [`docs/guia_bigquery_parquet_alunos.pdf`](docs/guia_bigquery_parquet_alunos.pdf).
> O conteúdo abaixo resume esse guia.

O objetivo é carregar o mesmo Parquet no **Google BigQuery Sandbox** (gratuito,
sem cartão de crédito) e comparar o tempo de resposta e o volume de dados lidos
com o PostgreSQL local.

### 2.1 Configurar o BigQuery Sandbox

- Acesse o console: `console.cloud.google.com/bigquery` com sua conta Google.
- O Sandbox oferece **10 GB de armazenamento** e **1 TB de consultas/mês** grátis.
- **Criar projeto**: no seletor de projetos (topo da tela) → *Novo Projeto*
  (ex.: `telemetria-lab`).
- **Criar dataset**: no painel *Explorador*, clique nos 3 pontos ao lado do
  projeto → *Criar conjunto de dados* (ID: `telemetria_ds`, região: `US` ou
  `southamerica-east1`).

### 2.2 Importar o arquivo Parquet

O Parquet tem 89,58 MB — abaixo do limite de 100 MB do navegador — então pode ser
enviado direto pelo console:

- No painel *Explorador*, 3 pontos ao lado do dataset `telemetria_ds` → *Criar tabela*.
- *Criar tabela de*: **Upload**.
- *Selecionar arquivo*: `data/parquet/telemetria_industrial.parquet`.
- *Formato do arquivo*: **Parquet** (o esquema é detectado automaticamente pelos
  metadados).
- *Nome da tabela*: `telemetria_industrial` → *Criar tabela*.

> Alternativa via linha de comando (`bq` autenticado com `gcloud auth login`):
>
> ```bash
> bq mk --dataset <PROJETO>:telemetria_ds
> bq load --source_format=PARQUET --replace \
>   <PROJETO>:telemetria_ds.telemetria_industrial \
>   data/parquet/telemetria_industrial.parquet
> ```

### 2.3 Cuidados essenciais de sintaxe SQL

O BigQuery usa **Standard SQL**, com pequenas diferenças em relação ao PostgreSQL
e ao DuckDB:

| Recurso / Operação | PostgreSQL / DuckDB | Google BigQuery |
|---|---|---|
| Identificação da tabela | `telemetria_industrial` | `` `projeto.dataset.tabela` `` (com crases) |
| Truncamento de data | `DATE_TRUNC('day', data)` | `TIMESTAMP_TRUNC(data, DAY)` (sem aspas) |
| Valores nulos / textos | tratamento via `NULLIF` | `SAFE_CAST(coluna AS FLOAT64)` |
| Arredondamento | `ROUND(val::numeric, 2)` | `ROUND(val, 2)` |

### 2.4 Medir a performance e desativar o cache

- **Desativar cache**: no editor SQL → *Mais* (Configurações) →
  *Configurações de consulta* → desmarque **Usar resultados em cache**.
- **Tempo de execução**: após rodar a consulta, veja a aba *Informações do job*
  abaixo dos resultados e observe **Tempo decorrido** (*Elapsed time*).
- **Volume lido**: observe **Bytes processados** (*Bytes processed*) — o BigQuery
  escaneia apenas alguns MBs, evidenciando a eficiência da leitura colunar
  (*Data Pruning*).

### 2.5 Consulta SQL de benchmark

Copie e cole a consulta abaixo no editor do BigQuery (substituindo o ID do
projeto):

```sql
WITH telemetria_calculada AS (
    SELECT
        data,
        TIMESTAMP_TRUNC(data, DAY) AS dia,
        -- SAFE_CAST converte para número e transforma textos inválidos em NULL
        (SAFE_CAST(alimentacao_total_do_moinho_t_h AS FLOAT64) -
         SAFE_CAST(setpoint_alimentacao_do_moinho_t_h AS FLOAT64)) AS desvio_setpoint,
        -- Variação (Delta) de vibração (Window Function)
        SAFE_CAST(vibracao_do_moinho AS FLOAT64) -
        LAG(SAFE_CAST(vibracao_do_moinho AS FLOAT64), 1) OVER (ORDER BY data) AS delta_vibracao,
        -- Média móvel de 12 leituras da temperatura de saída
        AVG(SAFE_CAST(temperatura_de_saida_do_moinho_celsius AS FLOAT64)) OVER (
            ORDER BY data ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS media_movel_temp_saida,
        SAFE_CAST(potencia_do_motor_do_moinho_kw AS FLOAT64) AS potencia_motor,
        SAFE_CAST(temperatura_de_entrada_do_moinho_celsius AS FLOAT64) AS temp_entrada,
        SAFE_CAST(pressao_diferencial_do_moinho_mpa AS FLOAT64) AS pressao_diferencial,
        SAFE_CAST(potencia_do_exaustor_principal_kw AS FLOAT64) AS potencia_exaustor,
        SAFE_CAST(fluxo_de_ar_exaustor_principal_m3_h AS FLOAT64) AS fluxo_ar,
        SAFE_CAST(silo_argical_percentual AS FLOAT64) AS silo_argical,
        SAFE_CAST(silo_minerio_ferro_percentual AS FLOAT64) AS silo_minerio
    FROM `seu-projeto.telemetria_ds.telemetria_industrial`
)
SELECT
    dia,
    COUNT(*) AS total_amostras_dia,
    ROUND(AVG(desvio_setpoint), 4) AS media_desvio_setpoint,
    ROUND(STDDEV(desvio_setpoint), 4) AS std_desvio_setpoint,
    ROUND(AVG(delta_vibracao), 4) AS media_delta_vibracao,
    ROUND(MAX(delta_vibracao), 4) AS max_pico_vibracao,
    ROUND(AVG(media_movel_temp_saida), 2) AS media_temp_saida_filtrada,
    ROUND(AVG(temp_entrada), 2) AS media_temp_entrada,
    ROUND(AVG(pressao_diferencial), 4) AS media_pressao_diferencial,
    ROUND(AVG(potencia_motor), 2) AS media_potencia_moinho,
    ROUND(AVG(potencia_exaustor), 2) AS media_potencia_exaustor,
    ROUND(AVG(fluxo_ar), 2) AS media_fluxo_ar,
    ROUND(AVG(silo_argical), 2) AS media_silo_argical,
    ROUND(AVG(silo_minerio), 2) AS media_silo_minerio
FROM telemetria_calculada
GROUP BY dia
ORDER BY dia;
```

> Observação: o Parquet deste repositório já vem **tipado** (colunas numéricas como
> `FLOAT64`), então o `SAFE_CAST` é opcional aqui — ele consta no guia como boa
> prática para bases com dados textuais.

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
