"""One-off migration: add users.google_sub to an existing todos.db.

models.Base.metadata.create_all() only ever CREATEs missing tables -- it never
ALTERs a table that already exists. The users table was created before
google_sub was added to the model, so the column has to be added by hand once.

Safe to run more than once: it checks first and does nothing if the column is
already there. Makes a .bak copy of the database before touching it.

    py -3.12 migrate_add_google_sub.py
"""
import os
import shutil
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todos.db")

if not os.path.exists(DB):
    print(f"找不到 {DB} —— 先启动一次应用让它建库。")
    sys.exit(1)

con = sqlite3.connect(DB)
columns = [row[1] for row in con.execute("PRAGMA table_info(users)")]

if "google_sub" in columns:
    print("users.google_sub 已存在，无需迁移。")
    con.close()
    sys.exit(0)

con.close()

backup = DB + ".bak"
shutil.copy2(DB, backup)
print(f"已备份到 {backup}")

con = sqlite3.connect(DB)
# SQLite cannot add a column with a UNIQUE constraint inline, so the column
# goes in first and the unique index follows. NULLs count as distinct in
# SQLite, so every existing password-only user keeps a NULL here happily.
con.execute("ALTER TABLE users ADD COLUMN google_sub VARCHAR")
con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)")
con.commit()

columns = [row[1] for row in con.execute("PRAGMA table_info(users)")]
users = con.execute("SELECT id, username, google_sub FROM users").fetchall()
con.close()

print("迁移完成。users 表字段:", columns)
print("现有用户:")
for uid, username, sub in users:
    print(f"  #{uid} {username:<20} google_sub={sub}")
