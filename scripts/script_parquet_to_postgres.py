from pathlib import Path
import sys

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import schema

PARQUET = RAIZ / "data" / "parquet" / "telemetria_industrial.parquet"
PG_CONNINFO = "dbname=telemetria_db user=postgres password=123 host=localhost port=5433"
PG_TABLE = "pg.telemetria_industrial"


def main():
    if not PARQUET.exists():
        raise SystemExit(f"Parquet não encontrado: {PARQUET}")

    caminho = str(PARQUET).replace("\\", "/")

    conn = duckdb.connect()
    try:
        conn.execute("INSTALL postgres; LOAD postgres;")
        conn.execute(f"ATTACH '{PG_CONNINFO}' AS pg (TYPE POSTGRES);")

        conn.execute(f"DROP TABLE IF EXISTS {PG_TABLE};")
        conn.execute(schema.sql_create_table(PG_TABLE, caminho))
        conn.execute(
            f"INSERT INTO {PG_TABLE} SELECT * FROM read_parquet('{caminho}');"
        )
    finally:
        conn.close()

    print("PostgreSQL populado com sucesso a partir do Parquet!")


if __name__ == "__main__":
    main()
