"""One-off migration: turn the single-user TodoApp into a multi-tenant one.

Adds the workspace / team / membership / invite / api-key tables plus the
columns they need on users and todos, then backfills a personal workspace and
a "TODO" team for every existing user -- without that last step every existing
todo would be left in a team-less limbo the new views cannot reach.

models.Base.metadata.create_all() CREATEs missing tables but never ALTERs an
existing one, which is why the new columns on users and todos have to be added
by hand. Same reason migrate_add_google_sub.py exists.

Safe to run more than once: it checks first and does nothing if the migration
has already happened. Copies the database to a timestamped .bak before
touching it (timestamped so it cannot clobber an earlier migration's backup).

    py -3.12 migrate_workspaces.py
"""
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# database.py points at ./todos.db, i.e. relative to the working directory, so
# make sure that is this folder no matter where the script was invoked from.
os.chdir(HERE)

DB = os.path.join(HERE, "todos.db")

# Matches the task prefix used across this project, so the first issue in a
# freshly migrated database reads as TODO-1.
DEFAULT_TEAM_KEY = "TODO"
DEFAULT_TEAM_NAME = "Todo"
DEFAULT_TEAM_COLOR = "#5e6ad2"


def naive_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def slugify(value):
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return cleaned or "workspace"


def unique_slug(base, taken):
    slug, suffix = base, 1
    while slug in taken:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


if not os.path.exists(DB):
    print(f"找不到 {DB} —— 先启动一次应用让它建库。")
    sys.exit(1)

con = sqlite3.connect(DB)
todo_columns = [row[1] for row in con.execute("PRAGMA table_info(todos)")]
con.close()

if "team_id" in todo_columns:
    print("todos.team_id 已存在，无需迁移。")
    sys.exit(0)

backup = f"{DB}.{naive_utcnow():%Y%m%d-%H%M%S}.bak"
shutil.copy2(DB, backup)
print(f"已备份到 {backup}")


# 1. New tables, created straight from the models so the two cannot drift.

from database import engine  # noqa: E402  (imported late, after the backup)
import models  # noqa: E402

models.Base.metadata.create_all(bind=engine)
print("新表已创建: workspaces, workspace_members, teams, team_members, "
      "invites, api_keys")


# 2. New columns on the two tables that already existed.

con = sqlite3.connect(DB)


def add_column(table, name, ddl):
    columns = [row[1] for row in con.execute(f"PRAGMA table_info({table})")]
    if name in columns:
        return False
    # SQLite only accepts ADD COLUMN when the column is nullable or carries a
    # non-null default, which is why every NOT NULL below has a DEFAULT.
    con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    return True


add_column("users", "token_version", "token_version INTEGER NOT NULL DEFAULT 0")
add_column("users", "avatar_color", "avatar_color VARCHAR")

add_column("todos", "team_id", "team_id INTEGER REFERENCES teams(id)")
add_column("todos", "number", "number INTEGER")
add_column("todos", "status", "status VARCHAR NOT NULL DEFAULT 'todo'")
add_column("todos", "assignee_id", "assignee_id INTEGER REFERENCES users(id)")
add_column("todos", "created_at", "created_at DATETIME")
add_column("todos", "updated_at", "updated_at DATETIME")
add_column("todos", "completed_at", "completed_at DATETIME")
con.execute("CREATE INDEX IF NOT EXISTS ix_todos_team_id ON todos (team_id)")
con.commit()
print("users / todos 新字段已添加。")


# 3. Backfill: a personal workspace and team per user, and every one of their
#    todos moved into it with a gapless number.

now = naive_utcnow().isoformat(sep=" ", timespec="seconds")
taken_slugs = {row[0] for row in con.execute("SELECT slug FROM workspaces")}
report = []

users = con.execute(
    "SELECT id, username, first_name FROM users ORDER BY id").fetchall()

for user_id, username, first_name in users:
    if con.execute("SELECT 1 FROM workspace_members WHERE user_id = ?",
                   (user_id,)).fetchone():
        continue  # already has a workspace, e.g. a half-finished earlier run

    owner_label = (first_name or username or "Personal").strip()
    slug = unique_slug(slugify(username or f"user{user_id}"), taken_slugs)
    taken_slugs.add(slug)

    workspace_id = con.execute(
        "INSERT INTO workspaces (name, slug, created_at, allow_password_login,"
        " allow_google_login, allowed_email_domain) VALUES (?, ?, ?, 1, 1, NULL)",
        (f"{owner_label}'s workspace", slug, now)).lastrowid

    con.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, created_at)"
        " VALUES (?, ?, 'owner', ?)", (workspace_id, user_id, now))

    team_id = con.execute(
        "INSERT INTO teams (workspace_id, name, key, color, issue_counter,"
        " created_at) VALUES (?, ?, ?, ?, 0, ?)",
        (workspace_id, DEFAULT_TEAM_NAME, DEFAULT_TEAM_KEY,
         DEFAULT_TEAM_COLOR, now)).lastrowid

    con.execute(
        "INSERT INTO team_members (team_id, user_id, created_at) VALUES (?, ?, ?)",
        (team_id, user_id, now))

    todos = con.execute(
        "SELECT id, complete FROM todos WHERE owner_id = ? ORDER BY id",
        (user_id,)).fetchall()

    for number, (todo_id, complete) in enumerate(todos, start=1):
        # There is no history to recover a real creation time from, so
        # everything gets stamped now; COALESCE keeps a re-run from moving a
        # timestamp that has since become real.
        con.execute(
            "UPDATE todos SET team_id = ?, number = ?, status = ?,"
            " assignee_id = COALESCE(assignee_id, ?),"
            " created_at = COALESCE(created_at, ?),"
            " updated_at = COALESCE(updated_at, ?), completed_at = ?"
            " WHERE id = ?",
            (team_id, number, "done" if complete else "todo", user_id,
             now, now, now if complete else None, todo_id))

    con.execute("UPDATE teams SET issue_counter = ? WHERE id = ?",
                (len(todos), team_id))
    report.append((username, slug, f"{DEFAULT_TEAM_KEY}-1..{len(todos)}"
                   if todos else "无 issue"))

con.commit()

orphans = con.execute(
    "SELECT COUNT(*) FROM todos WHERE team_id IS NULL").fetchone()[0]

print("\n迁移完成。")
for username, slug, issues in report:
    print(f"  {username:<20} workspace={slug:<20} {issues}")

if orphans:
    # Rows whose owner_id is NULL or points at a user that no longer exists.
    # Left alone rather than guessed at, but they will not show up in any team
    # view, so say so.
    print(f"\n注意: {orphans} 条 todo 没有归属用户，未分配团队，新视图中不可见。")

con.close()
