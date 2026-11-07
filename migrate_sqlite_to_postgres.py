"""Copy the existing TodoApp SQLite data into PostgreSQL.

Example:
  python migrate_sqlite_to_postgres.py --source todos.db \
    --target postgresql+psycopg://todoapp:password@localhost:5432/todoapp

Run this against a new or empty PostgreSQL database. Existing target rows are
not deleted or overwritten.
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="todos.db")
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        raise SystemExit(f"SQLite database not found: {source_path}")
    if not args.target.startswith(("postgresql://", "postgresql+")):
        raise SystemExit("--target must be a PostgreSQL SQLAlchemy URL")

    # models imports the shared metadata. Set the target before importing it.
    os.environ["TODOAPP_DATABASE_URL"] = args.target
    import models
    from database import engine as target_engine

    source_engine = create_engine(
        f"sqlite:///{source_path.resolve().as_posix()}",
        connect_args={"check_same_thread": False},
    )
    models.Base.metadata.create_all(bind=target_engine)
    source_tables = set(inspect(source_engine).get_table_names())
    copied = 0

    with source_engine.connect() as source, target_engine.begin() as target:
        for table in models.Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            rows = source.execute(select(table)).mappings().all()
            if not rows:
                continue
            target.execute(table.insert(), [dict(row) for row in rows])
            copied += len(rows)
            print(f"{table.name}: {len(rows)} rows")

        # Explicitly copied SQLite IDs do not advance PostgreSQL sequences.
        for table in models.Base.metadata.sorted_tables:
            if table.name not in source_tables or table.c.get("id") is None:
                continue
            table_name = table.name.replace('"', '""')
            sequence = target.execute(text(
                "SELECT pg_get_serial_sequence(:table_name, 'id')"),
                {"table_name": table.name}).scalar()
            if not sequence:
                continue
            maximum = target.execute(text(
                f'SELECT MAX(id) FROM "{table_name}"')).scalar()
            target.execute(text(
                "SELECT setval(:sequence_name, :value, :called)"),
                {"sequence_name": sequence, "value": maximum or 1,
                 "called": bool(maximum)})

    print(f"Migration complete: {copied} rows copied.")


if __name__ == "__main__":
    main()
