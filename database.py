import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Overridable so a test run can point the whole app at a throwaway copy of the
# database. Without this the checks exercise the real one, and a single
# mistake in a cleanup routine costs real rows -- which is exactly what
# happened before this existed.
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("TODOAPP_DATABASE_URL",
                                    "sqlite:///./todos.db")

engine_options = {"pool_pre_ping": True}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_compatibility_columns():
    """Apply tiny additive changes needed by an existing SQLite database.

    SQLAlchemy's create_all does not alter an already-created table. Keeping
    this additive check here lets an existing local TodoApp database start
    after the GitHub integration is added.
    """
    columns = {column["name"] for column in
               inspect(engine).get_columns("integrations")}
    if "github_installation_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE integrations ADD COLUMN github_installation_id INTEGER"))
