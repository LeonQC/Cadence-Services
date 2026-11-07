"""One-off migration: add projects and cycles, and the columns they hang off.

    py -3.12 migrate_projects_cycles.py

Adds the projects and cycles tables, the project/cycle/started_at columns on
todos, and the description plus cycle settings on teams.

models.Base.metadata.create_all() CREATEs missing tables but never ALTERs an
existing one, so the new columns have to be added by hand -- same reason
migrate_workspaces.py and migrate_add_google_sub.py exist.

Safe to run more than once: it checks first and does nothing if the migration
has already happened. Copies the database to a timestamped .bak before
touching it.

ON started_at: it records when an issue first moved into In Progress, which is
what the cycle burn-up's "Started" line plots. There is no history to recover
it from, so this backfills an approximation -- completed_at where the issue is
done, updated_at otherwise. Issues that never started stay NULL, which is
correct. The consequence is that a burn-up over a period that predates this
migration will show Started and Completed on top of each other; anything
created afterwards is real.
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# database.py points at ./todos.db, i.e. relative to the working directory.
os.chdir(HERE)

def database_path():
    """The file to migrate.

    Follows TODOAPP_DATABASE_URL when it is set, so a test run migrates its
    throwaway copy rather than the real database.
    """
    url = os.getenv("TODOAPP_DATABASE_URL")
    if url and url.startswith("sqlite:///"):
        return os.path.abspath(url[len("sqlite:///"):])
    return os.path.join(HERE, "todos.db")


DB = database_path()
DEFAULT_CYCLE_LENGTH = 14


def naive_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


if not os.path.exists(DB):
    print(f"找不到 {DB} —— 先启动一次应用让它建库。")
    sys.exit(1)

con = sqlite3.connect(DB)
todo_columns = [row[1] for row in con.execute("PRAGMA table_info(todos)")]
con.close()

if "project_id" in todo_columns:
    print("todos.project_id 已存在，无需迁移。")
    sys.exit(0)

backup = f"{DB}.{naive_utcnow():%Y%m%d-%H%M%S}.bak"
shutil.copy2(DB, backup)
print(f"已备份到 {backup}")


# 1. New tables, straight from the models so the two cannot drift.

from database import engine  # noqa: E402  (imported late, after the backup)
import models  # noqa: E402

models.Base.metadata.create_all(bind=engine)
print("新表已创建: projects, cycles")


# 2. New columns on the tables that already existed.

con = sqlite3.connect(DB)


def add_column(table, name, ddl):
    columns = [row[1] for row in con.execute(f"PRAGMA table_info({table})")]
    if name in columns:
        return False
    # SQLite only accepts ADD COLUMN when the column is nullable or carries a
    # non-null default, which is why every NOT NULL below has a DEFAULT.
    con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    return True


add_column("todos", "project_id", "project_id INTEGER REFERENCES projects(id)")
add_column("todos", "cycle_id", "cycle_id INTEGER REFERENCES cycles(id)")
add_column("todos", "started_at", "started_at DATETIME")
con.execute("CREATE INDEX IF NOT EXISTS ix_todos_project_id ON todos (project_id)")
con.execute("CREATE INDEX IF NOT EXISTS ix_todos_cycle_id ON todos (cycle_id)")

add_column("teams", "description", "description VARCHAR")
add_column("teams", "cycle_length_days",
           f"cycle_length_days INTEGER NOT NULL DEFAULT {DEFAULT_CYCLE_LENGTH}")
add_column("teams", "cycle_anchor", "cycle_anchor DATE")
con.commit()
print("todos / teams 新字段已添加。")


# 3. Backfill.

# started_at: approximate, and only for issues that have actually started.
# Anything still in backlog/todo/canceled never began, so it stays NULL.
started = con.execute(
    "UPDATE todos SET started_at = COALESCE(completed_at, updated_at)"
    " WHERE status IN ('in_progress', 'done') AND started_at IS NULL").rowcount

# cycle_anchor: the day the team was created, so Cycle 1 starts there and the
# series reaches today without a gap.
anchored = con.execute(
    "UPDATE teams SET cycle_anchor = DATE(created_at)"
    " WHERE cycle_anchor IS NULL AND created_at IS NOT NULL").rowcount
# Teams with no created_at at all (none expected, but the column is nullable).
orphan_anchor = con.execute(
    "UPDATE teams SET cycle_anchor = DATE('now')"
    " WHERE cycle_anchor IS NULL").rowcount
con.commit()

teams = con.execute(
    "SELECT key, name, cycle_length_days, cycle_anchor FROM teams"
    " ORDER BY id").fetchall()
never_started = con.execute(
    "SELECT COUNT(*) FROM todos WHERE started_at IS NULL").fetchone()[0]
con.close()

print("\n迁移完成。")
print(f"  started_at 回填 {started} 条（近似值，见本文件开头的说明）")
print(f"  仍为 NULL 的 {never_started} 条是从未开始过的 issue，属正常")
print(f"  cycle_anchor 设定 {anchored + orphan_anchor} 个团队")
for key, name, length, anchor in teams:
    print(f"    {key:<6} {name:<14} 周期 {length} 天，自 {anchor} 起")
