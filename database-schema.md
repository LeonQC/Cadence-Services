# TodoApp Database Schema

---

## Table of Contents

- [Overview](#overview)
- [Entity Map](#entity-map)
- [Database Tables](#database-tables)
  - [Table: users](#table-users)
  - [Table: workspaces](#table-workspaces)
  - [Table: workspace_members](#table-workspace_members)
  - [Table: teams](#table-teams)
  - [Table: team_members](#table-team_members)
  - [Table: invites](#table-invites)
  - [Table: api_keys](#table-api_keys)
  - [Table: projects](#table-projects)
  - [Table: cycles](#table-cycles)
  - [Table: todos](#table-todos)
- [Enumerations](#enumerations)
- [Derived and Generated State](#derived-and-generated-state)
- [Key Relationships](#key-relationships)
- [Redis Keyspace](#redis-keyspace)
- [Migrations](#migrations)
- [Notes on Implementation](#notes-on-implementation)

---

## Overview

This schema backs **TodoApp**, a Linear-style issue tracker. It is defined as
SQLAlchemy models in `models.py` and created by
`models.Base.metadata.create_all()` against SQLite
(`sqlite:///./todos.db` by default, overridable with `TODOAPP_DATABASE_URL`).

The DDL below is what SQLite actually holds, so it includes the columns added by
the three migration scripts as `ALTER TABLE` rather than as part of the original
`CREATE`. It is SQLite dialect: `INTEGER PRIMARY KEY` is the rowid and
autoincrements, `VARCHAR` is untyped text, `BOOLEAN` is an integer 0/1, and
`DATETIME` / `DATE` are ISO-8601 strings.

Ten tables, in four layers:

| Layer | Tables | Holds |
| ----- | ------ | ----- |
| Identity | `users`, `api_keys` | Who can sign in, and with what |
| Tenancy | `workspaces`, `workspace_members`, `invites` | Who can see what |
| Structure | `teams`, `team_members`, `projects`, `cycles` | How work is organised |
| Work | `todos` | The issues themselves |

---

## Entity Map

```
users ──< workspace_members >── workspaces ──< invites
  │                                  │
  │                                  └──< teams ──< team_members >── users
  │                                          │
  │                                          ├──< projects ──┐
  │                                          │               │
  │                                          └──< cycles ────┤
  │                                                          │
  └──< api_keys                            todos >───────────┘
        (owner_id / assignee_id ── users, team_id ── teams)
```

---

## Database Tables

### Table: users

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Unique identifier for each user |
| email | VARCHAR | UNIQUE | Email address; nullable, since a profile may clear it |
| username | VARCHAR | UNIQUE | Login name and the handle shown when no full name is set |
| first_name | VARCHAR | | Given name |
| last_name | VARCHAR | | Family name |
| hashed_password | VARCHAR | | bcrypt hash; NULL for accounts that only ever signed in with Google |
| is_active | BOOLEAN | DEFAULT TRUE | A false value refuses every session and API key |
| google_sub | VARCHAR | UNIQUE | Google's stable user id (`sub` in the id_token); NULL for password-only accounts |
| token_version | INTEGER | NOT NULL, DEFAULT 0 | Bumped by "sign out of all sessions"; every access token carries the value it was minted with |
| avatar_color | VARCHAR | | Chosen fallback-avatar colour; NULL falls back to one derived from `id` |

At least one of `hashed_password` and `google_sub` is always set — an account
with neither would have no way to sign in.

`token_version` exists because the Redis deny-list cannot do this job: it only
ever learns about the one token being logged out, so it cannot reach a session
on another machine, and it disappears when Redis does.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `username`, `email`, `google_sub`
- INDEX on `id`

**SQL for creating the table:**

```sql
CREATE TABLE users (
    id INTEGER NOT NULL,
    email VARCHAR,
    username VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    hashed_password VARCHAR,
    is_active BOOLEAN,
    google_sub VARCHAR,                       -- added by migrate_add_google_sub.py
    token_version INTEGER NOT NULL DEFAULT 0, -- added by migrate_workspaces.py
    avatar_color VARCHAR,                     -- added by migrate_workspaces.py
    PRIMARY KEY (id)
);

CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE UNIQUE INDEX ix_users_google_sub ON users (google_sub);
```

---

### Table: workspaces

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Unique workspace id |
| name | VARCHAR | NOT NULL | Display name |
| slug | VARCHAR | UNIQUE, NOT NULL | Identifies the workspace in the switcher cookie, so it is unique across the install rather than merely readable |
| created_at | DATETIME | DEFAULT utcnow | Creation timestamp |
| allow_password_login | BOOLEAN | NOT NULL, DEFAULT TRUE | Whether this workspace opens for a password session |
| allow_google_login | BOOLEAN | NOT NULL, DEFAULT TRUE | Whether this workspace opens for a Google session |
| allowed_email_domain | VARCHAR | | Restricts who may be invited; NULL means no restriction |

The three policy columns are written by Settings → Administration → Security and
read by `deps.load_context` on every request, not at the login form: a user can
belong to several workspaces with different rules, so which rules apply is only
knowable once a workspace is resolved.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `slug`

**SQL for creating the table:**

```sql
CREATE TABLE workspaces (
    id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    slug VARCHAR NOT NULL,
    created_at DATETIME,
    allow_password_login BOOLEAN NOT NULL,
    allow_google_login BOOLEAN NOT NULL,
    allowed_email_domain VARCHAR,
    PRIMARY KEY (id)
);

CREATE INDEX ix_workspaces_id ON workspaces (id);
CREATE UNIQUE INDEX ix_workspaces_slug ON workspaces (slug);
```

---

### Table: workspace_members

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Membership id |
| workspace_id | INTEGER | NOT NULL, REFERENCES workspaces(id) | The workspace |
| user_id | INTEGER | NOT NULL, REFERENCES users(id) | The member |
| role | VARCHAR | NOT NULL, DEFAULT 'member' | `owner`, `admin` or `member` |
| created_at | DATETIME | DEFAULT utcnow | When they joined |

This is the table access control actually runs on. The `active_workspace` cookie
is only a hint; every request resolves it through here, so pointing it at
somebody else's workspace resolves to nothing.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE on (`workspace_id`, `user_id`) — `uq_workspace_member`
- INDEX on `workspace_id`, on `user_id`

**SQL for creating the table:**

```sql
CREATE TABLE workspace_members (
    id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_workspace_member UNIQUE (workspace_id, user_id),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_workspace_members_id ON workspace_members (id);
CREATE INDEX ix_workspace_members_workspace_id ON workspace_members (workspace_id);
CREATE INDEX ix_workspace_members_user_id ON workspace_members (user_id);
```

---

### Table: teams

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Unique team id |
| workspace_id | INTEGER | NOT NULL, REFERENCES workspaces(id) | Owning workspace |
| name | VARCHAR | NOT NULL | Display name |
| key | VARCHAR | NOT NULL | Prefix half of an issue identifier: key `TODO` plus `todos.number` 3 reads as `TODO-3`. Unique per workspace, not globally |
| color | VARCHAR | | Team colour in the sidebar |
| description | VARCHAR | | Shown at the top of the team's Home page |
| issue_counter | INTEGER | NOT NULL, DEFAULT 0 | Highest issue number handed out so far |
| cycle_length_days | INTEGER | NOT NULL, DEFAULT 14 | Length of one cycle |
| cycle_anchor | DATE | | The day cycle 1 starts |
| created_at | DATETIME | DEFAULT utcnow | Creation timestamp |

`issue_counter` is incremented on creation rather than derived from a row count,
so deleting an issue does not cause the next one to reuse its identifier. It is
deliberately never rolled back.

`cycle_length_days` and `cycle_anchor` store the *rule* rather than a calendar —
see [cycles](#table-cycles).

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE on (`workspace_id`, `key`) — `uq_team_key`
- INDEX on `workspace_id`

**SQL for creating the table:**

```sql
CREATE TABLE teams (
    id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    "key" VARCHAR NOT NULL,
    color VARCHAR,
    issue_counter INTEGER NOT NULL,
    created_at DATETIME,
    description VARCHAR,                            -- added by migrate_projects_cycles.py
    cycle_length_days INTEGER NOT NULL DEFAULT 14,  -- added by migrate_projects_cycles.py
    cycle_anchor DATE,                              -- added by migrate_projects_cycles.py
    PRIMARY KEY (id),
    CONSTRAINT uq_team_key UNIQUE (workspace_id, "key"),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
);

CREATE INDEX ix_teams_id ON teams (id);
CREATE INDEX ix_teams_workspace_id ON teams (workspace_id);
```

---

### Table: team_members

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Membership id |
| team_id | INTEGER | NOT NULL, REFERENCES teams(id) | The team |
| user_id | INTEGER | NOT NULL, REFERENCES users(id) | The member |
| created_at | DATETIME | DEFAULT utcnow | When they joined |

No role column: privileges are held at the workspace level, and a team is about
visibility. Every issue lookup joins through here, so an issue in a team the
caller is not on is unreachable rather than forbidden.

Only people already in the workspace may be added, so a team cannot be used as a
side door into one.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE on (`team_id`, `user_id`) — `uq_team_member`
- INDEX on `team_id`, on `user_id`

**SQL for creating the table:**

```sql
CREATE TABLE team_members (
    id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_team_member UNIQUE (team_id, user_id),
    FOREIGN KEY(team_id) REFERENCES teams (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_team_members_id ON team_members (id);
CREATE INDEX ix_team_members_team_id ON team_members (team_id);
CREATE INDEX ix_team_members_user_id ON team_members (user_id);
```

---

### Table: invites

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Invite id |
| workspace_id | INTEGER | NOT NULL, REFERENCES workspaces(id) | Workspace being joined |
| email | VARCHAR | NOT NULL | Who it was addressed to, lower-cased |
| role | VARCHAR | NOT NULL, DEFAULT 'member' | Role granted on acceptance |
| token | VARCHAR | UNIQUE, NOT NULL | Random secret in the invite URL (`/invite/{token}`) |
| invited_by_id | INTEGER | REFERENCES users(id) | Who sent it |
| status | VARCHAR | NOT NULL, DEFAULT 'pending' | `pending`, `accepted` or `revoked` |
| created_at | DATETIME | DEFAULT utcnow | When it was minted |
| expires_at | DATETIME | | 14 days after creation |

The token is unique so a link can be resolved by itself, without the recipient
having to say who they are. Nothing is emailed — there is no mail configured, so
the Members page hands the link over for an admin to pass on.

An accepted or revoked invite is kept, not deleted: a used link that stayed
`pending` could be forwarded to somebody else.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `token`
- INDEX on `workspace_id`

**SQL for creating the table:**

```sql
CREATE TABLE invites (
    id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    email VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    token VARCHAR NOT NULL,
    invited_by_id INTEGER,
    status VARCHAR NOT NULL,
    created_at DATETIME,
    expires_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY(invited_by_id) REFERENCES users (id)
);

CREATE INDEX ix_invites_id ON invites (id);
CREATE UNIQUE INDEX ix_invites_token ON invites (token);
CREATE INDEX ix_invites_workspace_id ON invites (workspace_id);
```

---

### Table: api_keys

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Key id |
| user_id | INTEGER | NOT NULL, REFERENCES users(id) | Owner |
| label | VARCHAR | NOT NULL | What the user called it |
| prefix | VARCHAR | NOT NULL | Leading characters of the plaintext, so the settings list can show which key a row is |
| key_hash | VARCHAR | UNIQUE, NOT NULL | SHA-256 of the plaintext |
| created_at | DATETIME | DEFAULT utcnow | When it was issued |
| last_used_at | DATETIME | | Stamped on every authenticated call |

The plaintext (`lin_api_` + 32 bytes of `secrets.token_urlsafe`) is shown once,
at creation, and never stored — a database leak does not hand out working keys.
No salt and no bcrypt on purpose: the key is machine-generated entropy, not a
human-chosen password, so there is nothing for a rainbow table or a slow hash to
defend against. The unique index on `key_hash` is what makes the lookup a single
indexed read.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `key_hash` (the authentication lookup)
- INDEX on `user_id`

**SQL for creating the table:**

```sql
CREATE TABLE api_keys (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    label VARCHAR NOT NULL,
    prefix VARCHAR NOT NULL,
    key_hash VARCHAR NOT NULL,
    created_at DATETIME,
    last_used_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_api_keys_id ON api_keys (id);
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);
CREATE UNIQUE INDEX ix_api_keys_key_hash ON api_keys (key_hash);
```

---

### Table: projects

A feature: one deliverable, made of several issues — the parent half of the
issue hierarchy.

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Project id |
| team_id | INTEGER | NOT NULL, REFERENCES teams(id) | Owning team |
| name | VARCHAR | NOT NULL | Display name |
| description | VARCHAR | | What the feature is |
| status | VARCHAR | NOT NULL, DEFAULT 'planned' | `planned`, `in_progress`, `completed`, `canceled` |
| lead_id | INTEGER | REFERENCES users(id) | Who is driving it |
| target_date | DATE | | When it is meant to land |
| created_at | DATETIME | DEFAULT utcnow | Creation timestamp |
| updated_at | DATETIME | DEFAULT utcnow, ON UPDATE utcnow | Last change |

Scoped to a team rather than to the workspace, so a project's issues all share
one identifier prefix and one cycle calendar.

Project status is its own enumeration rather than a reuse of the issue
statuses: a project is a container, and `backlog` means nothing for one.

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `team_id`

**SQL for creating the table:**

```sql
CREATE TABLE projects (
    id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    status VARCHAR NOT NULL,
    lead_id INTEGER,
    target_date DATE,
    created_at DATETIME,
    updated_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(team_id) REFERENCES teams (id),
    FOREIGN KEY(lead_id) REFERENCES users (id)
);

CREATE INDEX ix_projects_id ON projects (id);
CREATE INDEX ix_projects_team_id ON projects (team_id);
```

---

### Table: cycles

A team's time box — Cycle 1, Cycle 2, and so on.

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Cycle id |
| team_id | INTEGER | NOT NULL, REFERENCES teams(id) | Owning team |
| number | INTEGER | NOT NULL | 1-based, gapless within the team |
| starts_on | DATE | NOT NULL | First day, inclusive |
| ends_on | DATE | NOT NULL | Last day, inclusive |
| created_at | DATETIME | DEFAULT utcnow | When the row was materialised |

Rows are generated from `teams.cycle_anchor` and `teams.cycle_length_days`
rather than created by hand, so the numbering is gapless and the dates
contiguous by construction:

```
starts_on(N) = cycle_anchor + (N - 1) × cycle_length_days
ends_on(N)   = starts_on(N) + cycle_length_days - 1
```

Rows still exist because an issue has to point at one, and they are materialised
lazily: opening a cycle page fills in whatever is missing up to three cycles
past today, capped at 200 so a long-dormant team does not bulk-insert hundreds
of rows on first view. The operation is idempotent.

**There is no `is_current` column, on purpose.** Which cycle is current is
computed from the calendar on every request — a stored flag would be wrong the
morning after.

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE on (`team_id`, `number`) — `uq_cycle_number`
- INDEX on `team_id`

**SQL for creating the table:**

```sql
CREATE TABLE cycles (
    id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_cycle_number UNIQUE (team_id, number),
    FOREIGN KEY(team_id) REFERENCES teams (id)
);

CREATE INDEX ix_cycles_id ON cycles (id);
CREATE INDEX ix_cycles_team_id ON cycles (team_id);
```

---

### Table: todos

An issue. Still called `todos` because the table predates the rename, and
renaming it would mean rewriting every existing row's home.

| Column | Type | Constraints | Description |
| ------ | ---- | ----------- | ----------- |
| id | INTEGER | PRIMARY KEY | Internal row id — not the address |
| title | VARCHAR | | Issue headline |
| description | VARCHAR | | Detail |
| priority | INTEGER | | 1 (P1, highest) – 5; default 3 |
| complete | BOOLEAN | DEFAULT FALSE | Redundant with `status = 'done'`, and deliberately so |
| owner_id | INTEGER | REFERENCES users(id) | Who created it |
| team_id | INTEGER | REFERENCES teams(id) | Owning team; with `number` it forms the identifier |
| number | INTEGER | | Per-team sequence number from `teams.issue_counter` |
| status | VARCHAR | NOT NULL, DEFAULT 'todo' | `backlog`, `todo`, `in_progress`, `done`, `canceled` |
| assignee_id | INTEGER | REFERENCES users(id) | Who is working on it |
| project_id | INTEGER | REFERENCES projects(id) | The feature it belongs to; NULL is allowed |
| cycle_id | INTEGER | REFERENCES cycles(id) | The time box it is scheduled in; NULL is allowed |
| created_at | DATETIME | DEFAULT utcnow | Creation timestamp |
| updated_at | DATETIME | DEFAULT utcnow, ON UPDATE utcnow | Last activity |
| completed_at | DATETIME | | Set when the status becomes `done`, cleared otherwise |
| started_at | DATETIME | | When work first began; written once and never rewritten |

`project_id` and `cycle_id` are both optional — an issue can exist with neither,
which is what the backlog is.

`complete` is kept in step with `status` rather than dropped because the
original routes and the Redis cache still read it. It is only ever written
through `models.set_status`, so the two cannot drift apart.

**No `identifier` column:** `TODO-3` is a Python property composed from
`teams.key` and `number`. Storing it would duplicate the team key into every
row and go stale the moment a team is renamed.

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `team_id` (the list view's query), `project_id`, `cycle_id`

`assignee_id` and `owner_id` carry no index. My Issues filters on `assignee_id`,
but only after joining through `team_members`, so the candidate set is already
small; at SQLite scale the scan costs nothing. Worth revisiting first if the
table ever grows.

**SQL for creating the table:**

```sql
CREATE TABLE todos (
    id INTEGER NOT NULL,
    title VARCHAR,
    description VARCHAR,
    priority INTEGER,
    complete BOOLEAN,
    owner_id INTEGER,
    team_id INTEGER REFERENCES teams(id),          -- added by migrate_workspaces.py
    number INTEGER,                                -- added by migrate_workspaces.py
    status VARCHAR NOT NULL DEFAULT 'todo',        -- added by migrate_workspaces.py
    assignee_id INTEGER REFERENCES users(id),      -- added by migrate_workspaces.py
    created_at DATETIME,                           -- added by migrate_workspaces.py
    updated_at DATETIME,                           -- added by migrate_workspaces.py
    completed_at DATETIME,                         -- added by migrate_workspaces.py
    project_id INTEGER REFERENCES projects(id),    -- added by migrate_projects_cycles.py
    cycle_id INTEGER REFERENCES cycles(id),        -- added by migrate_projects_cycles.py
    started_at DATETIME,                           -- added by migrate_projects_cycles.py
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_todos_id ON todos (id);
CREATE INDEX ix_todos_team_id ON todos (team_id);
CREATE INDEX ix_todos_project_id ON todos (project_id);
CREATE INDEX ix_todos_cycle_id ON todos (cycle_id);
```

---

## Enumerations

Stored as text rather than as lookup tables or SQLite `CHECK` constraints; the
canonical lists live in `models.py` and every write path validates against them
before it reaches the database.

**Issue status** — `models.STATUSES`, in the order the list view groups them:

| Value | Label | Counts as started | Counts as open |
| ----- | ----- | ----------------- | -------------- |
| `backlog` | Backlog | no | yes |
| `todo` | Todo | no | yes |
| `in_progress` | In Progress | yes | yes |
| `done` | Done | yes | no |
| `canceled` | Canceled | no | no |

**Project status** — `models.PROJECT_STATUSES`: `planned`, `in_progress`,
`completed`, `canceled`.

**Workspace role** — `models.ROLES`, most privileged first: `owner`, `admin`,
`member`. The order is load-bearing: `role_at_least` compares positions in this
list, so reordering it would change who can do what.

**Invite status:** `pending`, `accepted`, `revoked`.

**Priority:** integers 1–5, displayed as P1–P5, where 1 is the most urgent. The
list view sorts on `priority or 99`, so an issue with no priority sinks rather
than leading.

**Cycle state:** not stored at all — `completed`, `current`, `upcoming` and
`planned` are derived from the dates. See
[Derived and Generated State](#derived-and-generated-state).

---

## Derived and Generated State

Four pieces of state are computed rather than stored independently, each with a
single writer.

**1. `models.set_status()` owns four columns.** `status` is the input;
`complete`, `completed_at` and `started_at` are all derived from it and are
never set on their own, so they cannot drift apart:

| Column | Rule |
| ------ | ---- |
| `complete` | `status == 'done'` |
| `completed_at` | now when moving to `done`, `NULL` otherwise |
| `started_at` | now the **first** time the issue reaches `in_progress` or `done`; never rewritten afterwards |
| `updated_at` | now |

`started_at` is written once on purpose. It records when work first began, which
is what the cycle burn-up plots — if moving an issue back to Todo and forward
again reset it, the chart would rewrite its own history every time someone
corrected a mis-click.

**2. Issue identifiers.** `teams.issue_counter` is incremented to reserve the
next `todos.number`, rather than counting existing rows. Deleting an issue does
not roll the counter back: reusing a deleted issue's number would make `TODO-3`
mean two different things over time.

**3. Cycle rows.** Generated from the team's anchor and length, materialised
lazily, never created by hand. Current is therefore never empty and needs no
cron job keeping a table topped up.

**4. Timestamps.** `models.utcnow()` returns UTC with `tzinfo` stripped. SQLite
hands datetimes back naive, so storing aware ones would turn every later
comparison into a naive-vs-aware `TypeError`.

---

## Key Relationships

**Relationship 1: User-to-Workspace (Membership)**

- Type: Many-to-Many, through `workspace_members`
- Description: Who may open a workspace, and with what privileges. This is the
  table every access check runs on.
- Creation requirement: every signup path provisions a personal workspace with
  an `owner` membership, so no account ever exists without one.
- Deletion behaviour: removing a member also removes their `team_members` rows
  in that workspace, which would otherwise point into a workspace the user can
  no longer open. Their issues, as owner or assignee, stay.
- Invariant: a workspace must keep at least one `owner`; the last one can be
  neither demoted nor removed.

**Relationship 2: Workspace-to-Team**

- Type: One-to-Many, through `teams.workspace_id`
- Description: A workspace is a tenancy boundary; a team is a unit of work
  inside it, and the owner of an identifier prefix.
- Creation requirement: a workspace is always created together with one team —
  a workspace with no team would render an empty sidebar and have nowhere to put
  an issue.
- Deletion behaviour: `Workspace.teams` cascades in the ORM. Issues do not
  cascade, so they are deleted per team first.
- Invariant: a workspace must keep at least one team.

**Relationship 3: User-to-Team (Membership)**

- Type: Many-to-Many, through `team_members`
- Description: Visibility. Every issue, project and cycle lookup joins through
  this table, so work in a team you are not on is unreachable rather than
  forbidden.
- Creation requirement: the user must already be a workspace member.
- Deletion behaviour: removing someone from a team leaves their issues and
  assignments untouched.

**Relationship 4: Team-to-Issue**

- Type: One-to-Many, through `todos.team_id`
- Description: A team owns its issues and the numbering they are addressed by.
- Creation requirement: an issue must have a team to have an identifier —
  `Todos.identifier` is `None` until it does.
- Deletion behaviour: **no cascade.** Deleting a team with issues is refused at
  the route; the explicit delete path removes the issues first, because leaving
  them would produce rows pointing at a team that is not there — invisible to
  every view and impossible to reach.

**Relationship 5: Team-to-Project, Project-to-Issue**

- Type: One-to-Many at both levels (`projects.team_id`, `todos.project_id`)
- Description: A project is a feature; the issues under it are the work that
  makes it up. Progress is a percentage of the project's own issues, not of the
  team's — a project with two of two done is finished, however small it is.
- Creation requirement: an issue may only be attached to a project in its own
  team, or it would sit under a feature its own team cannot see.
- Deletion behaviour: deleting a project sets its issues' `project_id` to NULL
  rather than deleting them. An issue is the unit people care about, and a
  feature being cancelled is not a reason to lose the work logged under it.

**Relationship 6: Team-to-Cycle, Cycle-to-Issue**

- Type: One-to-Many at both levels (`cycles.team_id`, `todos.cycle_id`)
- Description: A cycle is a time box; the issues in it are what was scheduled
  for those dates.
- Creation requirement: an issue may only be scheduled into a cycle in its own
  team, and only into one that has not already completed — scheduling work into
  a finished cycle would make its burn-up disagree with what happened.
- Deletion behaviour: cycles cascade with their team in the ORM. Nothing else
  deletes one; a cycle in the past is history.

**Relationship 7: User-to-Issue (Owner and Assignee)**

- Type: Two separate One-to-Many links, `todos.owner_id` and `todos.assignee_id`
- Description: Who filed it, and who is doing it. On creation both are the
  creator.
- Deletion behaviour: there is no user-deletion path in the application. Were
  one added, these would have to be nulled rather than cascaded, or deleting a
  departing colleague would take the team's history with them.

**Relationship 8: User-to-API-Key**

- Type: One-to-Many, through `api_keys.user_id`
- Description: Credentials the user issued themselves, for non-browser callers.
- Deletion behaviour: cascades with the user (`delete-orphan`). Revoking deletes
  the row — there is no `revoked` flag, because a key that cannot be used again
  has nothing left to say.

**Relationship 9: Workspace-to-Invite**

- Type: One-to-Many, through `invites.workspace_id`
- Description: Pending and historical offers of membership.
- Deletion behaviour: cascades with the workspace.

---

## Redis Keyspace

Not part of the database, but part of the data model: Redis is a cache and a
deny-list, never a source of truth. Everything here can be lost without losing
state, which is what lets every call fail soft.

| Key | Type | TTL | Contents |
| --- | ---- | --- | -------- |
| `issues:team:{team_id}` | string (JSON) | 60 s | A team's issue list, one object per issue |
| `denylist:{jti}` | string | Remaining token lifetime | Marks a logged-out access token |

The issue cache is keyed by team, not by user: an issue belongs to a team, and
once a team has more than one member a per-user key would hand each of them a
separate copy that the others' writes never invalidate. The write paths
invalidate explicitly, so the TTL is only a safety net.

Cached rows carry `id, title, description, priority, complete, owner_id,
team_id, number, status, assignee_id, project_id, cycle_id` plus the four
timestamps, and come back as `SimpleNamespace` objects so templates can use
`issue.title` exactly as they do with an ORM row.

`is_denylisted` returns `False` when Redis is unavailable, meaning a logged-out
token stays usable until it expires on its own. Failing open is the deliberate
trade-off — failing closed would sign every user out whenever Redis blinks — and
`users.token_version` covers the case this cannot, because it lives in the
database.

---

## Migrations

`models.Base.metadata.create_all()` CREATEs missing tables but never ALTERs an
existing one, so new columns on existing tables are added by hand. Each script
checks first and does nothing if it has already run, and copies the database to
a timestamped `.bak` before touching it.

| Script | Adds | Backfills |
| ------ | ---- | --------- |
| `migrate_add_google_sub.py` | `users.google_sub` | — |
| `migrate_workspaces.py` | The workspace / team / membership / invite / api-key tables, plus `users.token_version`, `users.avatar_color` and the team and status columns on `todos` | A personal workspace and a `TODO` team for every existing user, so no todo is left in a team-less limbo the new views cannot reach |
| `migrate_projects_cycles.py` | `projects`, `cycles`, `todos.project_id`, `todos.cycle_id`, `todos.started_at`, `teams.description`, `teams.cycle_length_days`, `teams.cycle_anchor` | `started_at` as an approximation — `completed_at` where the issue is done, `updated_at` otherwise; issues that never started stay NULL, which is correct |

Run them from the application directory:

```bash
py -3.12 migrate_add_google_sub.py
py -3.12 migrate_workspaces.py
py -3.12 migrate_projects_cycles.py
```

> The `started_at` backfill has a consequence worth knowing: a burn-up over a
> cycle that predates the migration plots an approximation, not history.

---

## Notes on Implementation

1. **Foreign keys are declarative, not enforced.**
   SQLite does not enforce foreign keys unless `PRAGMA foreign_keys = ON` is set
   per connection, and nothing here sets it. The constraints document intent and
   drive SQLAlchemy's relationships; integrity is maintained by the write paths,
   which validate every reference against the caller's workspace before saving.

2. **Access control is a join, not a column.**
   There is no `visible_to` or ACL table. Every read resolves through
   `teams → team_members` and `workspaces → workspace_members`, so the worst
   outcome of a forged cookie or a guessed id is an empty result.

3. **Deletion is asymmetric on purpose.**
   Containers release their contents (a project frees its issues), while a
   tenancy boundary takes them (deleting a workspace deletes its issues). The
   rule is that an issue survives anything that is merely a way of organising
   it, and does not survive the removal of the place it lived.

4. **Cache invalidation is an obligation the code hands back.**
   `provisioning.delete_team` and `delete_workspace` return the team ids whose
   cache must be dropped rather than clearing them, which keeps those functions
   synchronous while making the obligation hard to miss. It matters because
   SQLite hands a new team the rowid a deleted one just freed, and the cache is
   keyed on that id — without the invalidation a brand new team would inherit
   the deleted one's issue list until the entry expired.

5. **Chart geometry is computed in Python, not in the database or the browser.**
   `summary.py` and `cycle_math.py` turn rows into SVG coordinates, so the
   templates place what they are given and there is one place to check the
   figures. The alternative — a charting library — would mean a build step and a
   CDN for two pages, and this application has neither.

6. **Portability.**
   Nothing here is SQLite-specific except the DDL spelling: no triggers, no
   stored procedures, no dialect-only types. Moving to PostgreSQL would mean
   `SERIAL`/`IDENTITY` for the primary keys, real `BOOLEAN` and `TIMESTAMP`,
   turning the enumerations into `CHECK` constraints, and adding the
   `ON DELETE` behaviours that the write paths currently implement by hand.
