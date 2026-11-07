# SmartUrl Database Schema

---

## Table of Contents

- [Overview](#overview)
- [Database Tables](#database-tables)
  - [Table: users](#table-users)
  - [Table: projects](#table-projects)
  - [Table: sprints](#table-sprints)
  - [Table: issues](#table-issues)
  - [Table: comments](#table-comments)
  - [Table: history](#table-history)
  - [Table: attachments](#table-attachments)
  - [Table: notifications](#table-notifications)
- [Key Relationships](#key-relationships)
- [Notes on Implementation](#notes-on-implementation)

---

## Overview

This schema defines the backend structure for the Collaborative Issue Manager (CIM). It is optimized for high-performance PostgreSQL operations, utilizing pgvector for AI search and supporting a microservices-style event architecture with Kafka.

---

## Database Tables

### Table: users

| Column           | Type      | Constraints      | Description                                                        |
| ---------------- | --------- | ---------------- | ------------------------------------------------------------------ |
| id               | SERIAL    | PRIMARY KEY      | Unique identifier for each user                                    |
| username         | TEXT      | UNIQUE, NOT NULL | User's chosen username                                             |
| email            | TEXT      | UNIQUE, NOT NULL | User's email address                                               |
| password_hash    | TEXT      |                  | Hashed password (NULL for OAuth users)                             |
| auth_provider    | TEXT      |                  | Authentication provider (NULL for local auth, "google" for Google) |
| auth_provider_id | TEXT      |                  | Provider-specific user ID                                          |
| created_at       | TIMESTAMP | NOT NULL         | When the user was created                                          |
| updated_at       | TIMESTAMP | NOT NULL         | When the user was last updated                                     |

**Indexes:**

- PRIMARY KEY on `id` (automatically created)
- UNIQUE INDEX on `username` (automatically created by UNIQUE constraint)
- UNIQUE INDEX on `email` (automatically created by UNIQUE constraint)
- INDEX on `auth_provider` and `auth_provider_id` for OAuth lookups

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT, -- NULL for OAuth users
    auth_provider TEXT, -- 'google', 'github', etc.
    auth_provider_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_auth ON users (auth_provider, auth_provider_id);

CREATE TRIGGER update_users_modtime BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: projects

| Column      | Type      | Constraints          | Description                             |
| ----------- | --------- | -------------------- | --------------------------------------- |
| id          | SERIAL    | PRIMARY KEY          | Unique project ID                       |
| name        | TEXT      | NOT NULL             | Project display name                    |
| key         | TEXT      | UNIQUE, NOT NULL     | Short code prefix (e.g., "PROJ", "API") |
| lead_id     | INTEGER   | REFERENCES users(id) | Project owner/manager                   |
| is_archived | BOOLEAN   | DEFAULT FALSE        | Flag for active/archived status         |
| created_at  | TIMESTAMP | NOT NULL             | Date of project creation                |
| updated_at  | TIMESTAMP | NOT NULL             | Last configuration change               |

**Indexes:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `key`
- INDEX on `lead_id`
- GIN INDEX on `name` using pg_trgm
- PARTIAL INDEX on active projects (`is_archived = FALSE`)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    key TEXT UNIQUE NOT NULL,
    lead_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_lead ON projects (lead_id);
CREATE INDEX IF NOT EXISTS idx_projects_name_search ON projects USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_projects_active ON projects (is_archived) WHERE is_archived = FALSE;

CREATE TRIGGER update_projects_modtime BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Table: project_members

| Column     | Type      | Constraints                 | Description                          |
| ---------- | --------- | --------------------------- | ------------------------------------ |
| project_id | INTEGER   | PK, REFERENCES projects(id) | The project the user belongs to      |
| user_id    | INTEGER   | PK, REFERENCES users(id)    | The user granted access              |
| role       | TEXT      | DEFAULT 'Member'            | Access level (Admin, Member, Viewer) |
| joined_at  | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP   | When the user was added              |

```sql
CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'Member', -- 'Admin', 'Member', 'Viewer'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id)
);
```

### Table: sprints

| Column         | Type      | Constraints                       | Description                    |
| -------------- | --------- | --------------------------------- | ------------------------------ |
| id             | SERIAL    | PRIMARY KEY                       | Unique sprint identifier       |
| project_id     | INTEGER   | NOT NULL, REFERENCES projects(id) | Project the sprint belongs to  |
| name           | TEXT      | NOT NULL                          | Sprint name (e.g., "Sprint 1") |
| goal           | TEXT      | NULL                              | Sprint goal/objective          |
| start_date     | TIMESTAMP | NULL                              | Sprint start date              |
| end_date       | TIMESTAMP | NULL                              | Sprint end date                |
| completed_date | TIMESTAMP | NULL                              | Date sprint was completed      |
| status         | TEXT      | NOT NULL                          | planned, active, completed     |
| created_by     | INTEGER   | REFERENCES users(id)              | User who created the sprint    |
| created_at     | TIMESTAMP | DEFAULT NOW()                     | Creation timestamp             |
| updated_at     | TIMESTAMP | DEFAULT NOW()                     | Last update timestamp          |

### Indexes

PRIMARY KEY on id
INDEX on project_id

INDEX on status
INDEX on (project_id, status)
INDEX on (project_id, start_date)
INDEX on completed_date
OPTIONAL PARTIAL INDEX on project_id WHERE status = 'active'

**SQL for creating the table:**

```sql
CREATE TABLE sprints (
    id SERIAL PRIMARY KEY,

    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    goal TEXT,

    start_date TIMESTAMP NULL,
    end_date TIMESTAMP NULL,
    completed_date TIMESTAMP NULL,

    status TEXT NOT NULL DEFAULT 'planned',

    created_by INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_sprints_project
        FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sprints_created_by
        FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_sprints_status
        CHECK (status IN ('planned', 'active', 'completed'))
);
```

### Table: issues

| Column       | Type      | Constraints                       | Description               |
| ------------ | --------- | --------------------------------- | ------------------------- |
| id           | SERIAL    | PRIMARY KEY                       | Internal unique ID        |
| issue_key    | TEXT      | UNIQUE, NOT NULL                  | Human-readable key        |
| project_id   | INTEGER   | NOT NULL, REFERENCES projects(id) | Parent project            |
| title        | TEXT      | NOT NULL                          | Issue headline            |
| description  | TEXT      |                                   | Detailed task information |
| status       | TEXT      | NOT NULL, DEFAULT 'Backlog'       | Current workflow state    |
| priority     | TEXT      | DEFAULT 'Medium'                  | Task urgency              |
| assignee_id  | INTEGER   | REFERENCES users(id)              | Assigned user             |
| reporter_id  | INTEGER   | REFERENCES users(id)              | Issue creator             |
| story_points | INTEGER   | DEFAULT 0                         | Estimated effort          |
| created_at   | TIMESTAMP | NOT NULL                          | Creation timestamp        |
| updated_at   | TIMESTAMP | NOT NULL                          | Last activity timestamp   |

**Indexes:**

INDEX on project_id

INDEX on assignee_id

GIST/HNSW INDEX on embedding for AI search

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    issue_key TEXT UNIQUE NOT NULL, -- e.g., 'PROJ-101'
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'Backlog', -- 'Backlog', 'In Progress', 'Done'
    priority TEXT DEFAULT 'Medium',        -- 'High', 'Medium', 'Low'
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    story_points INTEGER DEFAULT 0,
    embedding VECTOR(1536),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_issues_project ON issues (project_id);
CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues (assignee_id);
CREATE INDEX IF NOT EXISTS idx_issues_embedding ON issues USING hnsw (embedding vector_cosine_ops);

CREATE TRIGGER update_issues_modtime BEFORE UPDATE ON issues
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: comments

| Column     | Type      | Constraints                     | Description                       |
| ---------- | --------- | ------------------------------- | --------------------------------- |
| id         | SERIAL    | PRIMARY KEY                     | Unique identifier for the comment |
| issue_id   | INTEGER   | NOT NULL, REFERENCES issues(id) | Parent issue                      |
| author_id  | INTEGER   | REFERENCES users(id)            | User who wrote the comment        |
| parent_id  | INTEGER   | REFERENCES comments(id)         | Parent comment for threading      |
| content    | TEXT      | NOT NULL                        | Comment body                      |
| is_edited  | BOOLEAN   | DEFAULT FALSE                   | Shows edited state in UI          |
| created_at | TIMESTAMP | NOT NULL                        | Creation timestamp                |
| updated_at | TIMESTAMP | NOT NULL                        | Last modification timestamp       |

**Indexes:**

INDEX on issue_id (To load all comments for one ticket instantly)

INDEX on author_id (To find all comments by a specific user)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_edited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comments_issue ON comments (issue_id);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments (author_id);

CREATE TRIGGER update_comments_modtime BEFORE UPDATE ON comments
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: history

| Column          | Type     | Nullable | Description                                                                |
| --------------- | -------- | -------- | -------------------------------------------------------------------------- |
| Id              | int      | No       | Primary key.                                                               |
| IssueId         | int      | No       | Foreign key referencing the associated issue.                              |
| ChangedByUserId | int      | No       | Foreign key referencing the user who made the change.                      |
| Field           | string   | No       | Name of the field that was modified (e.g., `Title`, `Status`, `Priority`). |
| OldValue        | string   | Yes      | Previous value before the change.                                          |
| NewValue        | string   | Yes      | New value after the change.                                                |
| ChangedAt       | DateTime | No       | UTC timestamp indicating when the change occurred.                         |

**Indexes:**

INDEX on issue_id (To load all comments for one ticket instantly)

INDEX on ChangedByUserId (To find all comments by a specific user)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS issue_history (
    id SERIAL PRIMARY KEY,

    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    changed_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    field TEXT NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,

    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_issue_history_issue
    ON issue_history (issue_id);

CREATE INDEX IF NOT EXISTS idx_issue_history_issue_time
    ON issue_history (issue_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_issue_history_user
    ON issue_history (changed_by_user_id);

CREATE INDEX IF NOT EXISTS idx_issue_history_changed_at
    ON issue_history (changed_at);
```

---

### Table: attachments

| Column       | Type      | Constraints                     | Description                             |
| ------------ | --------- | ------------------------------- | --------------------------------------- |
| id           | UUID      | PRIMARY KEY                     | Unique ID (usually matches S3 file key) |
| issue_id     | INTEGER   | NOT NULL, REFERENCES issues(id) | The issue this file belongs to          |
| uploader_id  | INTEGER   | REFERENCES users(id)            | The user who uploaded the file          |
| file_name    | TEXT      | NOT NULL                        | Original filename                       |
| file_url     | TEXT      | NOT NULL                        | Public/Private URL to cloud storage     |
| file_size    | BIGINT    | NOT NULL                        | Size in bytes                           |
| content_type | TEXT      | NOT NULL                        | MIME type (e.g., image/png)             |
| created_at   | TIMESTAMP | NOT NULL, DEFAULT now()         | Date of upload                          |

**Indexes:**

- INDEX on issue_id (To list all files on a ticket)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    content_type TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_issue ON attachments (issue_id);
```

---

### Table: notifications

| Column     | Type      | Constraints                    | Description                            |
| ---------- | --------- | ------------------------------ | -------------------------------------- |
| id         | SERIAL    | PRIMARY KEY                    | Unique notification ID                 |
| user_id    | INTEGER   | NOT NULL, REFERENCES users(id) | Recipient of the notification          |
| message    | TEXT      | NOT NULL                       | Notification body text                 |
| link       | TEXT      |                                | Redirect path (e.g., "/issue/API-101") |
| is_read    | BOOLEAN   | DEFAULT FALSE                  | Status for unread badges               |
| created_at | TIMESTAMP | DEFAULT now()                  | When the alert was triggered           |

**Indexes:**

- PRIMARY KEY on `id`
- INDEX on `user_id`
- PARTIAL INDEX on unread notifications (`is_read = FALSE`)

**SQL for creating the table:**

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT, -- Deep link to issue or comment
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notifications_user
ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_unread_notifications_user
ON notifications(user_id)
WHERE is_read = FALSE;
```

---

## Key Relationships

**Relationship 1: User-to-Project (Ownership)**

- Type: One-to-Many
- Description: A single user acts as the "Project Lead," possessing administrative authority over the project's settings and lifecycle.
- Implementation: Through the `lead_id` foreign key in the projects table.
- Creation requirement:
- Deletion behavior: If a user is deleted, the project remains, but the lead_id is typically SET NULL or reassigned to a system administrator to prevent project "orphaning."
- Resource persistence:

**Relationship 2: User-to-Project (Membership)**

- Type: Many-to-Many
- Description: Defines the group of users who are authorized to participate in a project (Developers, Testers, Viewers).
- Implementation: Through a join table (e.g., project_members) containing `user_id` and `project_id`.
- Deletion behavior: When a user is deleted, resources remain but user association is removed (SET NULL)
- Resource persistence: Removing a user from a project membership does not delete their historical contributions (like comments or past assignments) within that project.

**Relationship 3: Project-to-Issue**

- Type: One-to-Many
- Description: A single project acts as a container for multiple issues, tasks, and bugs.
- Implementation: Through `project_id` foreign key in the issues table.
- Creation requirement: Issues must be associated with a valid project to generate a unique `issue_key`
- Deletion behavior: When a project is deleted, all associated issues are permanently removed (ON DELETE CASCADE).

**Relationship 4:Issue-to-Comment**

- Type: One-to-Many
- Description: Each issue can have an ongoing conversation thread consisting of multiple comments.
- Implementation: Through `issue_id` foreign key in the comments table.
- Creation requirement: All resources must be created by authenticated users (enforced at application level)
- Nesting logic: Includes a self-referencing `parent_id` to support threaded replies within the same issue.
- Deletion behavior: Deleting an issue removes all related comments. Deleting a parent comment removes all nested replies (ON DELETE CASCADE).

**Relationship 5:Issue-to-Attachment**

- Type: One-to-Many
- Description: An issue can have multiple supporting files, images, or documents attached to it.
- Implementation: Through `issue_id` foreign key in the attachments table.
- Storage requirement: The database stores metadata and a pointer (file_url), while the physical file resides in cloud storage.
- Deletion behavior: Deleting an issue removes the database record and triggers a cleanup of the physical file in storage.

**Relationship 6: User-to-Notification**

- Type: One-to-Many
- Description: A single user receives multiple alerts based on mentions, assignments, or status updates.
- Implementation: Through `user_id` foreign key in the notifications table.
- Creation requirement: Entries are typically generated via a Kafka event consumer when a relevant action occurs elsewhere in the system.
- Deletion behavior: Notifications are removed if the recipient user is deleted (ON DELETE CASCADE).

---

## Notes on Implementation

1. **Foreign Key Constraints**
   - Every relationship uses hard foreign keys in PostgreSQL to ensure data integrity at the database level.

2. **Performance**
   - All "Many" sides of these relationships (e.g., issue_id in comments) are indexed to ensure that loading an issue page remains fast even with thousands of comments.

3. **Microservices Decoupling**
   - While these are DB relationships, the Notification and Search logic use an Event-Driven approach. The database stores the state, but Kafka moves the data between the "Action" and the "Alert."
