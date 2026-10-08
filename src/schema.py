"""Camada trusted: schema central e geracao de SQL tipado.

Fonte unica da verdade para os scripts de ingestao. A ideia e ler os CSV
cru (que misturam numeros com tokens de qualidade do historiador) e devolver
um SELECT tipado, onde:

- a coluna de tempo vira TIMESTAMP;
- a coluna categorica vira BOOLEAN;
- todas as demais viram DOUBLE via TRY_CAST, o que converte qualquer token
  de status (No Data, Bad Input, Intf Shut, ...) em NULL automaticamente.
"""

import duckdb

TIMESTAMP_COL = "data"

BOOL_COL = "desviadora_de_alimentacao_do_moinho_dg01"
BOOL_TRUE = "Active"
BOOL_FALSE = "Inactive"

RENAMES = {
    "finura_peneira_#170": "finura_peneira_170",
}

STATUS_TOKENS = [
    "No Data",
    "Active",
    "Inactive",
    "Intf Shut",
    "Bad Input",
    "Bad",
    "Pt Created",
    "Arc Off-line",
    "Calc Failed",
    "I/O Timeout",
    "Configure",
    "Not Connect",
]

_DUCK_TO_PG = {
    "TIMESTAMP": "timestamp",
    "DOUBLE": "double precision",
    "BOOLEAN": "boolean",
    "VARCHAR": "text",
    "BIGINT": "bigint",
    "INTEGER": "integer",
}


def _quote(ident):
    return '"' + ident.replace('"', '""') + '"'


def _sql_str(valor):
    return "'" + valor.replace("'", "''") + "'"


def _alias(nome):
    return RENAMES.get(nome, nome)


def colunas_csv(origem):
    con = duckdb.connect()
    cur = con.execute(f"SELECT * FROM read_csv_auto({_sql_str(origem)}) LIMIT 0")
    return [d[0] for d in cur.description]


def sql_select_tipado(origem):
    """SELECT tipado que le o CSV cru e devolve colunas limpas."""
    partes = []
    for col in colunas_csv(origem):
        alvo = _quote(_alias(col))
        if col == TIMESTAMP_COL:
            partes.append(f"CAST({_quote(col)} AS TIMESTAMP) AS {alvo}")
        elif col == BOOL_COL:
            partes.append(
                f"CASE WHEN {_quote(col)} = {_sql_str(BOOL_TRUE)} THEN true "
                f"WHEN {_quote(col)} = {_sql_str(BOOL_FALSE)} THEN false "
                f"ELSE NULL END AS {alvo}"
            )
        else:
            partes.append(f"TRY_CAST({_quote(col)} AS DOUBLE) AS {alvo}")
    return "SELECT\n  " + ",\n  ".join(partes)


def colunas_parquet(caminho):
    con = duckdb.connect()
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet({_sql_str(caminho)})"
    ).fetchall()
    return [(r[0], _DUCK_TO_PG.get(r[1], r[1])) for r in rows]


def sql_create_table(tabela, caminho_parquet, pk=TIMESTAMP_COL):
    """DDL explicita e tipada, com chave primaria, derivada do Parquet."""
    linhas = []
    for nome, tipo in colunas_parquet(caminho_parquet):
        linha = f"{_quote(nome)} {tipo}"
        if nome == pk:
            linha += " PRIMARY KEY"
        linhas.append(linha)
    corpo = ",\n  ".join(linhas)
    return f"CREATE TABLE {tabela} (\n  {corpo}\n)"
