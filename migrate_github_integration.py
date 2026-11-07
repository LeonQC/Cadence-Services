"""Add the GitHub App installation column to an existing database."""
from sqlalchemy import inspect, text

from database import engine

with engine.begin() as connection:
    columns = {column["name"] for column in
               inspect(engine).get_columns("integrations")}
    if "github_installation_id" not in columns:
        connection.execute(text(
            "ALTER TABLE integrations ADD COLUMN github_installation_id INTEGER"))
        print("Added integrations.github_installation_id")
    else:
        print("GitHub integration schema is already up to date")
