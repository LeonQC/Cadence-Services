# TodoApp API Documentation

---

## Table of Contents

- [TodoApp API Documentation](#todoapp-api-documentation)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Conventions](#conventions)
    - [Authentication](#authentication)
    - [Request and response formats](#request-and-response-formats)
    - [Error handling](#error-handling)
  - [API Endpoints](#api-endpoints)
    - [1. Authentication Endpoints](#1-authentication-endpoints)
      - [1.1. Register User (Form)](#11-register-user-form)
      - [1.2. Create User (JSON)](#12-create-user-json)
      - [1.3. Login Page](#13-login-page)
      - [1.4. Login (Form)](#14-login-form)
      - [1.5. Issue Access Token](#15-issue-access-token)
      - [1.6. Start Google Sign-in](#16-start-google-sign-in)
      - [1.7. Link Google to the Current Account](#17-link-google-to-the-current-account)
      - [1.8. Google Callback](#18-google-callback)
      - [1.9. Logout](#19-logout)
    - [2. Workspace and Invite Endpoints](#2-workspace-and-invite-endpoints)
      - [2.1. New Workspace Form](#21-new-workspace-form)
      - [2.2. Create Workspace](#22-create-workspace)
      - [2.3. Switch Workspace](#23-switch-workspace)
      - [2.4. View Invite](#24-view-invite)
      - [2.5. Accept Invite](#25-accept-invite)
    - [3. Issue Endpoints](#3-issue-endpoints)
      - [3.1. Home Redirect](#31-home-redirect)
      - [3.2. Team Issue List](#32-team-issue-list)
      - [3.3. Team Home (Summary)](#33-team-home-summary)
      - [3.4. My Issues](#34-my-issues)
      - [3.5. New Issue Form](#35-new-issue-form)
      - [3.6. Create Issue](#36-create-issue)
      - [3.7. Issue Detail](#37-issue-detail)
      - [3.8. Edit Issue Form](#38-edit-issue-form)
      - [3.9. Update Issue](#39-update-issue)
      - [3.10. Change Issue Status](#310-change-issue-status)
      - [3.11. Change Issue Priority](#311-change-issue-priority)
      - [3.12. Change Issue Project](#312-change-issue-project)
      - [3.13. Change Issue Cycle](#313-change-issue-cycle)
      - [3.14. Delete Issue](#314-delete-issue)
    - [4. Project Endpoints](#4-project-endpoints)
      - [4.1. Team Project List](#41-team-project-list)
      - [4.2. New Project Form](#42-new-project-form)
      - [4.3. Create Project](#43-create-project)
      - [4.4. Project Detail](#44-project-detail)
      - [4.5. Edit Project Form](#45-edit-project-form)
      - [4.6. Update Project](#46-update-project)
      - [4.7. Change Project Status](#47-change-project-status)
      - [4.8. Delete Project](#48-delete-project)
    - [5. Cycle Endpoints](#5-cycle-endpoints)
      - [5.1. Cycle List and Burn-up](#51-cycle-list-and-burn-up)
      - [5.2. Current Cycle](#52-current-cycle)
      - [5.3. Upcoming Cycle](#53-upcoming-cycle)
    - [6. Personal Settings Endpoints](#6-personal-settings-endpoints)
      - [6.1. Settings Root](#61-settings-root)
      - [6.2. Profile](#62-profile)
      - [6.3. Update Profile](#63-update-profile)
      - [6.4. Security and Access](#64-security-and-access)
      - [6.5. Set or Change Password](#65-set-or-change-password)
      - [6.6. Sign Out of Other Sessions](#66-sign-out-of-other-sessions)
      - [6.7. Connected Accounts](#67-connected-accounts)
      - [6.8. Disconnect Google](#68-disconnect-google)
      - [6.9. List API Keys](#69-list-api-keys)
      - [6.10. Create API Key](#610-create-api-key)
      - [6.11. Revoke API Key](#611-revoke-api-key)
    - [7. Administration Endpoints](#7-administration-endpoints)
      - [7.1. Workspace Settings](#71-workspace-settings)
      - [7.2. Update Workspace](#72-update-workspace)
      - [7.3. Delete Workspace](#73-delete-workspace)
      - [7.4. Workspace Security](#74-workspace-security)
      - [7.5. Update Workspace Security](#75-update-workspace-security)
      - [7.6. List Teams](#76-list-teams)
      - [7.7. Create Team](#77-create-team)
      - [7.8. Team Detail](#78-team-detail)
      - [7.9. Update Team](#79-update-team)
      - [7.10. Add or Remove Team Member](#710-add-or-remove-team-member)
      - [7.11. Delete Team](#711-delete-team)
      - [7.12. List Members and Invites](#712-list-members-and-invites)
      - [7.13. Invite Member](#713-invite-member)
      - [7.14. Revoke Invite](#714-revoke-invite)
      - [7.15. Change Member Role](#715-change-member-role)
      - [7.16. Remove Member](#716-remove-member)
    - [8. Legacy Redirects](#8-legacy-redirects)
    - [9. Static Assets](#9-static-assets)
  - [Settings Message Codes](#settings-message-codes)
  - [Environment Variables](#environment-variables)

---

## Overview

This document describes every HTTP route served by **TodoApp**, a Linear-style
issue tracker built on FastAPI, Jinja2, SQLAlchemy and SQLite, with Redis as an
optional cache. The application lets users:

1. **Authentication**
   1. Register with a username and password, or sign in with Google (OAuth 2.0
      authorization code flow)
   2. Hold a session as a JWT in an `httponly` cookie, with a Redis denylist for
      logout and a `token_version` column for "sign out of every session"
   3. Issue personal API keys for non-browser callers

2. **Workspaces and Teams**
   1. Work inside a workspace, chosen by a cookie and re-checked against the
      membership table on every request
   2. Belong to teams within a workspace; a team's `key` is the prefix of every
      issue identifier it owns (`TODO-3`)
   3. Invite people by link, manage roles (`owner`, `admin`, `member`) and
      restrict which sign-in methods and email domains a workspace accepts

3. **Issues**
   1. Create, edit, re-prioritise, re-status and delete issues addressed by
      identifier rather than by row id
   2. Group a team's issues by status, or see everything assigned to you across
      the workspace
   3. Attach an issue to a project (the feature it belongs to) and to a cycle
      (the time box it is scheduled in)

4. **Projects**
   1. Group issues into one deliverable, with a lead, a status and a target date
   2. Track completion as a percentage of the project's own issues
   3. Delete a project without losing its issues — they are released back to the
      team's list

5. **Cycles**
   1. Generate a team's time boxes arithmetically from an anchor date and a
      cycle length, so Current and Upcoming are never empty
   2. Read a cycle's Scope / Started / Completed burn-up
   3. Schedule and unschedule issues into a cycle

6. **Analytics**
   1. Per-team headline tiles, status and priority distributions, workload per
      assignee, and a 14-day created-vs-completed trend
   2. Per-cycle burn-up geometry computed server-side and drawn as inline SVG
   3. Per-project progress rows shared between the project list and team Home

**This application is server-rendered.** Almost every route returns HTML or a
redirect, not JSON; mutations are HTML form posts that redirect back to a page.
The two exceptions are noted where they appear ([1.2](#12-create-user-json) and
[1.5](#15-issue-access-token)), plus the JSON error bodies returned to API-key
callers.

---

## Conventions

### Authentication

Two credentials are accepted, resolved by `routers/auth.py::get_current_user`:

| Credential | How it is sent | Who uses it |
| ---------- | -------------- | ----------- |
| Session JWT | `access_token` cookie (`httponly`), HS256, 60 minute lifetime | The browser |
| API key | `Authorization: Bearer lin_api_...` | Scripts and other services |

An `Authorization: Bearer` header always wins over the cookie. The access token
carries these claims:

```json
{
  "sub": "peter",
  "id": 1,
  "jti": "9f1c2f3e-...",
  "tv": 0,
  "amr": "password",
  "exp": 1790000000
}
```

- `jti` — token id, deny-listed in Redis on logout for the token's remaining life
- `tv` — the `users.token_version` the token was minted with; bumping the column
  invalidates every outstanding token at once
- `amr` — how the user signed in (`password`, `google`, or `api_key` for keys),
  checked against the workspace's security settings

Routes declare what they need through the dependencies in `deps.py`:

| Dependency | Guarantees |
| ---------- | ---------- |
| `load_context` | Signed in; workspace may be absent |
| `require_workspace` | Signed in and inside a workspace |
| `require_admin` | The above, plus role `admin` or `owner` |
| `require_owner` | The above, plus role `owner` |

The active workspace comes from the `active_workspace` cookie, which is only a
hint — it is resolved through `workspace_members`, so pointing it at somebody
else's workspace resolves to nothing rather than granting access.

### Request and response formats

- Page routes: `GET`, respond `200 text/html`
- Mutations: `POST` with `application/x-www-form-urlencoded`, respond `302` or
  `303` to the page that should be shown next
- A `POST` that cannot find its target (a deleted issue, a project in another
  workspace) redirects to `/` rather than returning `404`
- Path-level identifiers are case-insensitive: `/issue/todo-3` resolves the same
  row as `/issue/TODO-3`

### Error handling

`deps.py` raises; `main.py` turns the exception into a response, and picks the
shape from whether the caller sent `Authorization: Bearer`.

| Exception | Browser | API-key caller |
| --------- | ------- | -------------- |
| `NotAuthenticated` | `302` → `/auth/` | `401 {"detail": "Not authenticated"}` |
| `NoWorkspace` | `302` → `/workspaces/new` | `409 {"detail": "Account has no workspace"}` |
| `Forbidden` | `403` + `errors/forbidden.html` | `403 {"detail": "<reason>"}` |

`Forbidden` is deliberately not a redirect: the user is already signed in, so
sending them to the login page would bounce them straight back.

---

## API Endpoints

### 1. Authentication Endpoints

#### 1.1. Register User (Form)

**Purpose:** Create an account, and provision the personal workspace and team
that come with it.

**Endpoint:** `/auth/register`

**Method:** `GET` (form) / `POST` (submit)

**Request Body:** `application/x-www-form-urlencoded`

| Field | Type | Notes |
| ----- | ---- | ----- |
| `email` | string | Must be unused |
| `username` | string | Must be unused |
| `firstname` | string | |
| `lastname` | string | |
| `password` | string | |
| `password2` | string | Must equal `password` |

**Response:** `200 text/html` — the login page with `msg = "User successfully
created"`, or the register page with `msg = "Invalid registration request"` if
the username or email is taken or the two passwords differ.

**Side effects:** `provisioning.provision_personal_workspace` creates
`<First>'s workspace`, a `TODO` team anchored to today, and an `owner`
membership.

---

#### 1.2. Create User (JSON)

**Purpose:** The JSON counterpart of registration, kept from the original course
project.

**Endpoint:** `/auth/create/user`

**Method:** `POST`

**Request Body:**

```json
{
  "username": "peter",
  "email": "peter@example.com",
  "first_name": "Peter",
  "last_name": "Chen",
  "password": "securepassword123"
}
```

**Response:** `200 OK`, body `null`. The route returns nothing; the account and
its workspace are created as a side effect.

> **Note:** no uniqueness check runs here, unlike [1.1](#11-register-user-form).
> A duplicate username or email reaches the unique index and raises.

---

#### 1.3. Login Page

**Endpoint:** `/auth/`

**Method:** `GET`

**Response:** `200 text/html` — `auth/login.html`. The Google button renders
only when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are both set.

---

#### 1.4. Login (Form)

**Purpose:** Exchange credentials for a session cookie.

**Endpoint:** `/auth/`

**Method:** `POST`

**Request Body:**

| Field | Type | Notes |
| ----- | ---- | ----- |
| `email` | string | Holds the **username**, not the address — the field kept its original name |
| `password` | string | |

**Response:**

- `302` → `/` with `Set-Cookie: access_token=<jwt>; HttpOnly` on success
- `200 text/html` with `msg = "Incorrect Username or Password"` on failure

Accounts created through Google have no `hashed_password` and are refused here
rather than being passed to passlib.

---

#### 1.5. Issue Access Token

**Purpose:** OAuth2 password-flow endpoint used internally by
[1.4](#14-login-form); usable directly.

**Endpoint:** `/auth/token`

**Method:** `POST`

**Request Body:** `application/x-www-form-urlencoded` with `username` and
`password` (`OAuth2PasswordRequestForm`).

**Response:** `200 OK` with body `true` and the `access_token` cookie set, or
`200 OK` with body `false` when authentication fails.

> **Note:** the failure case is `200 false`, not `401`. It predates the error
> handling in `main.py` and is kept because [1.4](#14-login-form) calls it
> directly and reads the boolean.

---

#### 1.6. Start Google Sign-in

**Purpose:** Begin the OAuth 2.0 authorization code flow.

**Endpoint:** `/auth/google`

**Method:** `GET`

**Response:** `302` → `accounts.google.com/o/oauth2/v2/auth` with
`scope=openid email profile` and `prompt=select_account`, plus a signed
`oauth_state` cookie (`httponly`, `samesite=lax`, 300 s).

The state is signed with `SECRET_KEY` rather than stored server-side, so Google
login does not depend on Redis being up. `samesite` must stay `lax`: the
callback arrives as a top-level navigation from Google, and `strict` would
withhold the cookie on exactly that request.

If Google is not configured, returns `200` with
`msg = "Google login is not configured"`.

---

#### 1.7. Link Google to the Current Account

**Purpose:** Attach a Google identity to the account already signed in.

**Endpoint:** `/auth/google/link`

**Method:** `GET`

**Response:** `302` to Google, with `mode=link` inside the signed state cookie.
`302` → `/auth/` if nobody is signed in, or
`302` → `/settings/accounts?error=unconfigured` if Google is not configured.

The mode travels in the signed cookie, not the URL, so the callback cannot be
talked into treating a link as a login.

---

#### 1.8. Google Callback

**Purpose:** Exchange the authorization code for an `id_token`, verify it, then
issue this application's own session cookie.

**Endpoint:** `/auth/google/callback`

**Method:** `GET`

**Query Parameters:**

- `code` — authorization code from Google
- `state` — must match the signed `oauth_state` cookie
- `error` — present when the user cancels

**Response:**

| Outcome | Response |
| ------- | -------- |
| Login succeeded | `302` → `/`, sets `access_token`, clears `oauth_state` |
| Link succeeded | `302` → `/settings/accounts?notice=google_linked` |
| Link hit a Google account already attached elsewhere | `302` → `/settings/accounts?error=google_taken` |
| State missing, expired or mismatched | `200` login page, `msg = "Invalid or expired login attempt"` |
| User cancelled | `200` login page, `msg = "Google login cancelled"` |
| Email already registered and unverified at Google | `200` login page, `msg = "That email is already registered, please log in with your password"` |

Identities are matched on Google's `sub` first, because it never changes. Falling
back to email is what lets an existing password account pick up Google sign-in —
but only when Google reports the address as verified, or anyone could claim
someone else's account by registering that address with Google.

---

#### 1.9. Logout

**Purpose:** Drop the cookie and stop the token from working.

**Endpoint:** `/auth/logout`

**Method:** `GET`

**Response:** `200 text/html` — the login page with `msg = "Logout Successful"`,
and `access_token` deleted.

Deleting a cookie does not invalidate a JWT, so the token's `jti` is written to
`denylist:{jti}` in Redis with a TTL equal to its remaining lifetime. If Redis
is unavailable the deny-list write is skipped and the token stays valid until it
expires — see [6.6](#66-sign-out-of-other-sessions) for the mechanism that
survives Redis being down.

---

### 2. Workspace and Invite Endpoints

#### 2.1. New Workspace Form

**Endpoint:** `/workspaces/new`

**Method:** `GET`

**Auth:** `load_context` — deliberately not `require_workspace`, because this is
the one page that has to work for an account with no workspace at all.

**Response:** `200 text/html`

---

#### 2.2. Create Workspace

**Endpoint:** `/workspaces/new`

**Method:** `POST`

**Request Body:**

| Field | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `name` | string | — | Required; blank re-renders the form with an error |
| `team_key` | string | `TODO` | Normalised to `[A-Z0-9]{1,6}` |

**Response:** `302` → `/`, with `active_workspace` set to the new slug.

A workspace is always created together with one team the creator belongs to; a
workspace with no team would render an empty sidebar and have nowhere to put an
issue.

---

#### 2.3. Switch Workspace

**Endpoint:** `/workspaces/switch/{slug}`

**Method:** `POST`

**Response:** `302` → `/` with `active_workspace={slug}`, or `403` if the caller
is not a member — which says nothing about whether the workspace exists.

`POST`, not `GET`: switching changes what every later request resolves to, and a
`GET` would be followed by prefetchers and crawlers.

---

#### 2.4. View Invite

**Purpose:** Show what is being joined before joining it.

**Endpoint:** `/invite/{token}`

**Method:** `GET`

**Auth:** `load_context` — someone accepting an invite may have no workspace of
their own yet, and bouncing them to the create form would lose the invite.

**Response:** `200 text/html`, rendering one of: the invite, "already a member",
or the reason it cannot be accepted (invalid, expired, or an email outside the
workspace's allowed domain).

---

#### 2.5. Accept Invite

**Endpoint:** `/invite/{token}`

**Method:** `POST`

**Response:** `303` → `/` with `active_workspace` pointed at the joined
workspace, or `303` back to `/invite/{token}` if the invite cannot be accepted.

The invite is marked `accepted` even when the user was already a member: the
link has done its job, and leaving it `pending` would let it be passed on.

---

### 3. Issue Endpoints

Identifiers follow `^([A-Za-z0-9]{1,6})-(\d+)$` — the team key plus the issue's
per-team number, e.g. `TODO-3`.

Every route in this section resolves the issue through `teams` → `team_members`,
so an issue in another workspace, or in a team the caller is not on, is
unreachable rather than forbidden.

#### 3.1. Home Redirect

**Endpoint:** `/`

**Method:** `GET`

**Response:** `302` → `/team/{key}/home` for the caller's first team, or `403`
if they are on no team in this workspace.

---

#### 3.2. Team Issue List

**Endpoint:** `/team/{team_key}/issues`

**Method:** `GET`

**Response:** `200 text/html` — issues grouped by status in the order
`backlog, todo, in_progress, done, canceled`, each group sorted by priority then
by issue number. Empty groups are dropped.

Reads through the Redis cache (`issues:team:{id}`, 60 s) and falls back to
SQLite on a miss or an outage.

---

#### 3.3. Team Home (Summary)

**Purpose:** The team's landing page: who they are, plus how they are doing.

**Endpoint:** `/team/{team_key}/home`

**Method:** `GET`

**Response:** `200 text/html`, containing everything `summary.build` returns:

| Block | Contents |
| ----- | -------- |
| `tiles` | Completed this week, Created this week (each with a week-on-week delta), In progress, Backlog |
| `status_rows` | Issue count per status, as bars scaled to the largest |
| `priority_rows` | Issue count per priority P1–P5 |
| `workload` | Open issues per assignee, busiest first — finished work is not a load |
| `trend` | 14-day created-vs-completed polyline geometry, as inline SVG coordinates |
| `projects` | Every project in the team with its own completion percentage |
| `recent` | The eight most recently updated issues |

`/team/{team_key}/summary` answers `308` → this page; the summary stopped being
a page of its own when it moved into Home.

---

#### 3.4. My Issues

**Endpoint:** `/my-issues`

**Method:** `GET`

**Response:** `200 text/html` — every issue assigned to the caller across every
team in the active workspace, newest update first, grouped by status.

Not team-scoped, so it reads straight from the database rather than through the
per-team cache: there is no single key that would hold it.

---

#### 3.5. New Issue Form

**Endpoint:** `/team/{team_key}/new`

**Method:** `GET`

**Response:** `200 text/html`, or `403` if the team is not one of the caller's.

---

#### 3.6. Create Issue

**Endpoint:** `/team/{team_key}/new`

**Method:** `POST`

**Request Body:**

| Field | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `title` | string | — | Required, trimmed |
| `description` | string | `""` | Trimmed |
| `priority` | integer | `3` | 1 (highest) – 5 |
| `issue_status` | string | `todo` | Anything outside `STATUSES` falls back to `todo` |

**Response:** `302` → `/issue/{KEY}-{number}`

The issue number comes from `teams.issue_counter`, which is incremented rather
than derived from a row count, so deleting an issue never causes the next one to
reuse its identifier. The creator becomes both `owner_id` and `assignee_id`, and
the team's cache entry is invalidated.

---

#### 3.7. Issue Detail

**Endpoint:** `/issue/{identifier}`

**Method:** `GET`

**Response:** `200 text/html` with the issue, its assignee and creator, the
team's projects for the project picker, and its non-completed cycles for the
cycle picker. `302` → `/` when the identifier does not resolve.

Completed cycles are left out of the picker: scheduling work into one that has
already ended would make its burn-up disagree with what actually happened.

---

#### 3.8. Edit Issue Form

**Endpoint:** `/issue/{identifier}/edit`

**Method:** `GET`

**Response:** `200 text/html`, or `302` → `/`.

---

#### 3.9. Update Issue

**Endpoint:** `/issue/{identifier}/edit`

**Method:** `POST`

**Request Body:** `title` (required), `description`, `priority`.

**Response:** `302` → `/issue/{IDENTIFIER}`

---

#### 3.10. Change Issue Status

**Purpose:** The board transition. Also derives `complete`, `completed_at` and
`started_at`.

**Endpoint:** `/issue/{identifier}/status`

**Method:** `POST`

**Request Body:**

| Field | Type | Notes |
| ----- | ---- | ----- |
| `issue_status` | string | One of `backlog`, `todo`, `in_progress`, `done`, `canceled` |

**Response:** `302` back to where the change was made — the team list if the
`Referer` names a team page, the issue otherwise. `403` if the status is not one
of the five.

`models.set_status` is the only writer of the derived columns:

- `complete` = `status == "done"`
- `completed_at` = now when moving to `done`, `NULL` otherwise
- `started_at` = now the **first** time the issue reaches `in_progress` or
  `done`, and never rewritten — it records when work began, which is what the
  cycle burn-up plots. Resetting it on a correction would make the chart rewrite
  its own history.

`POST`, not `GET`: the list renders one of these per row, and as links they
would all be prefetchable.

---

#### 3.11. Change Issue Priority

**Endpoint:** `/issue/{identifier}/priority`

**Method:** `POST`

**Request Body:** `priority` — integer, clamped to 1–5.

**Response:** `302` → `/issue/{IDENTIFIER}`

---

#### 3.12. Change Issue Project

**Purpose:** Move an issue under a feature, or out from under one.

**Endpoint:** `/issue/{identifier}/project`

**Method:** `POST`

**Request Body:**

| Field | Type | Notes |
| ----- | ---- | ----- |
| `project_id` | string | A project id, or `""` for "no project" — the picker's first entry |

**Response:** `303` → `/issue/{IDENTIFIER}`, or `403` if the project belongs to
another team, which would put an issue under a feature its own team cannot see.

---

#### 3.13. Change Issue Cycle

**Endpoint:** `/issue/{identifier}/cycle`

**Method:** `POST`

**Request Body:**

| Field | Type | Notes |
| ----- | ---- | ----- |
| `cycle_id` | string | A cycle id, or `""` to unschedule |

**Response:** `303` → `/issue/{IDENTIFIER}`, or `403` if the cycle belongs to
another team. Refused rather than ignored, so a stale form cannot silently put
an issue in a cycle nobody can see.

---

#### 3.14. Delete Issue

**Endpoint:** `/issue/{identifier}/delete`

**Method:** `POST`

**Response:** `302` → `/team/{key}/issues`

`POST`, not `GET`: the old `/todos/delete/{id}` link was one crawler away from
clearing someone's list. `teams.issue_counter` is deliberately not rolled back —
reusing a deleted issue's number would make `TODO-3` mean two different things
over time.

---

### 4. Project Endpoints

A project is a feature: one deliverable made of several issues. Projects are
scoped to a team, so a project's issues share one identifier prefix and one
cycle calendar.

#### 4.1. Team Project List

**Endpoint:** `/team/{team_key}/projects`

**Method:** `GET`

**Response:** `200 text/html` — every project in the team, newest first, each
with its issue count, completed count and percentage.

---

#### 4.2. New Project Form

**Endpoint:** `/team/{team_key}/projects/new`

**Method:** `GET`

**Response:** `200 text/html`, with the team's members available as leads.

---

#### 4.3. Create Project

**Endpoint:** `/team/{team_key}/projects/new`

**Method:** `POST`

**Request Body:**

| Field | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `name` | string | — | Blank becomes `Untitled feature` |
| `description` | string | `""` | Blank stored as `NULL` |
| `project_status` | string | `planned` | `planned`, `in_progress`, `completed`, `canceled` |
| `lead_id` | string | `""` | Non-numeric means no lead |
| `target_date` | string | `""` | `yyyy-mm-dd`; an unparseable value means "not set" rather than a 500 |

**Response:** `302` → `/project/{id}`

---

#### 4.4. Project Detail

**Endpoint:** `/project/{project_id}`

**Method:** `GET`

**Response:** `200 text/html` — the project, its lead, its issues grouped by
status, and `done / total / percent`. `302` → `/` when the project is not
reachable from the active workspace.

---

#### 4.5. Edit Project Form

**Endpoint:** `/project/{project_id}/edit`

**Method:** `GET`

**Response:** `200 text/html`

---

#### 4.6. Update Project

**Endpoint:** `/project/{project_id}/edit`

**Method:** `POST`

**Request Body:** same fields as [4.3](#43-create-project).

**Response:** `303` → `/project/{id}`

---

#### 4.7. Change Project Status

**Endpoint:** `/project/{project_id}/status`

**Method:** `POST`

**Request Body:** `project_status` — one of `PROJECT_STATUSES`.

**Response:** `303` → `/project/{id}`, or `403` for an unknown status.

---

#### 4.8. Delete Project

**Purpose:** Remove the container, keep the contents.

**Endpoint:** `/project/{project_id}/delete`

**Method:** `POST`

**Response:** `303` → `/team/{key}/projects`

The project's issues have `project_id` set to `NULL` rather than being deleted —
an issue is the unit people care about, and a feature being cancelled is not a
reason to lose the work logged under it. They land back in the team's list with
no project, and the team's cache entry is invalidated because those rows changed.

---

### 5. Cycle Endpoints

Cycles are an arithmetic series, not hand-made rows: cycle *N* runs from
`anchor + (N-1) × length` for `length` days. Rows are materialised lazily —
opening a cycle page fills in whatever is missing up to three cycles past today,
capped at 200. Which cycle is Current is read off the calendar every time and
never stored; a stored flag would be wrong the morning after.

| State | Meaning |
| ----- | ------- |
| `completed` | `ends_on < today` |
| `current` | `starts_on <= today <= ends_on` |
| `upcoming` | The first cycle that has not started |
| `planned` | Everything beyond that |

#### 5.1. Cycle List and Burn-up

**Endpoint:** `/team/{team_key}/cycles`

**Method:** `GET`

**Response:** `200 text/html` — every cycle newest first with its state, scope
and done counts, plus the burn-up for the current cycle.

The burn-up carries three daily series:

| Series | Definition |
| ------ | ---------- |
| Scope | Issues whose `created_at` falls on or before that day |
| Started | Issues whose `started_at` falls on or before that day |
| Completed | Issues whose `completed_at` falls on or before that day |

Scope uses creation date as the day an issue entered the cycle. Nothing records
when an issue was *assigned* to a cycle, so an issue moved in late shows as
having been there from the start. Actual lines stop at today — drawing the
remaining days would put flat lines where there is no data, which reads as "no
progress" rather than "not yet" — while the x axis still spans the whole cycle.

---

#### 5.2. Current Cycle

**Endpoint:** `/team/{team_key}/cycles/current`

**Method:** `GET`

**Response:** `200 text/html` — the current cycle's issues grouped by status,
with `total` and `done`.

---

#### 5.3. Upcoming Cycle

**Endpoint:** `/team/{team_key}/cycles/upcoming`

**Method:** `GET`

**Response:** `200 text/html`, same shape as [5.2](#52-current-cycle).

---

### 6. Personal Settings Endpoints

All routes in this section require a workspace but no particular role. Outcomes
are carried between a `POST` and its redirect as short codes
(`?notice=` / `?error=`), listed under
[Settings Message Codes](#settings-message-codes).

#### 6.1. Settings Root

**Endpoint:** `/settings` and `/settings/`

**Method:** `GET`

**Response:** `302` → `/settings/profile`

---

#### 6.2. Profile

**Endpoint:** `/settings/profile`

**Method:** `GET`

**Response:** `200 text/html`, including the avatar colour palette.

---

#### 6.3. Update Profile

**Endpoint:** `/settings/profile`

**Method:** `POST`

**Request Body:** `first_name`, `last_name`, `username` (required), `email`,
`avatar_color`.

**Response:** `303` → `/settings/profile` with `notice=profile_saved`, or
`error=username_taken` / `error=email_taken`. A colour outside the palette is
ignored rather than rejected.

---

#### 6.4. Security and Access

**Endpoint:** `/settings/security`

**Method:** `GET`

**Response:** `200 text/html`, telling the template whether the account has a
password at all.

---

#### 6.5. Set or Change Password

**Endpoint:** `/settings/security/password`

**Method:** `POST`

**Request Body:** `current_password`, `new_password`, `confirm_password`.

**Response:** `303` → `/settings/security` with `notice=password_changed`
(or `password_set` for an account that had none), or one of
`error=wrong_password`, `error=password_mismatch`, `error=password_short`.

A Google-only account has no current password to prove, so `current_password` is
only checked when one exists. The minimum length is 8.

---

#### 6.6. Sign Out of Other Sessions

**Endpoint:** `/settings/security/sessions`

**Method:** `POST`

**Response:** `303` → `/settings/security` with `notice=sessions_cleared`, and a
freshly minted `access_token` for the current tab.

Bumping `users.token_version` is what actually revokes the others: the Redis
deny-list only knows about tokens it watched being logged out, so it cannot
reach a session on another machine. Re-minting afterwards is why this is "other
sessions" and not a self-inflicted logout. It also works with Redis down,
because the version lives in the database.

---

#### 6.7. Connected Accounts

**Endpoint:** `/settings/accounts`

**Method:** `GET`

**Response:** `200 text/html`, showing whether Google is linked and whether it
is configured on this server.

---

#### 6.8. Disconnect Google

**Endpoint:** `/settings/accounts/google/disconnect`

**Method:** `POST`

**Response:** `303` → `/settings/accounts` with `notice=google_unlinked`, or
`error=last_credential` when the account has no password — unlinking would
strand it with no way back in.

---

#### 6.9. List API Keys

**Endpoint:** `/settings/api`

**Method:** `GET`

**Response:** `200 text/html` — the caller's keys with label, prefix, creation
and last-used timestamps. Immediately after creation the page also shows the
plaintext once, read from `?key=`.

---

#### 6.10. Create API Key

**Endpoint:** `/settings/api/keys`

**Method:** `POST`

**Request Body:** `label` (default `API key`).

**Response:** `303` → `/settings/api?key=lin_api_...`

The key is `lin_api_` plus 32 bytes of `secrets.token_urlsafe` entropy. Only its
SHA-256 and its first characters are stored, so a database leak does not hand
out working keys, and a user who misses the plaintext has to make a new key. No
salt and no bcrypt on purpose: the key is not a human-chosen password, so there
is nothing for a rainbow table or a slow hash to defend against.

**Using the key:**

```http
GET /team/TODO/issues HTTP/1.1
Authorization: Bearer lin_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Each use stamps `api_keys.last_used_at`. API-key sessions are exempt from a
workspace's sign-in method policy: the key is a separate credential the user
issued themselves, and refusing it would make the API page's own keys stop
working the moment an admin turned off password logins.

---

#### 6.11. Revoke API Key

**Endpoint:** `/settings/api/keys/{key_id}/revoke`

**Method:** `POST`

**Response:** `303` → `/settings/api` with `notice=key_revoked`. Scoped to the
caller's own keys, so another user's id deletes nothing.

---

### 7. Administration Endpoints

Every route in this section sits behind `require_admin` (or `require_owner`
where noted). Hiding the section in the sidebar is presentation; the dependency
is what refuses someone who types the URL.

#### 7.1. Workspace Settings

**Endpoint:** `/settings/workspace`

**Method:** `GET`

**Response:** `200 text/html`

---

#### 7.2. Update Workspace

**Endpoint:** `/settings/workspace`

**Method:** `POST`

**Request Body:** `name`, `slug` (slugified to `[a-z0-9-]`).

**Response:** `303` → `/settings/workspace` with `notice=workspace_saved`, or
`error=slug_taken`. The response also moves the `active_workspace` cookie,
because it holds the slug and a rename would otherwise drop the next request
into some other workspace.

---

#### 7.3. Delete Workspace

**Endpoint:** `/settings/workspace/delete`

**Auth:** `require_owner`

**Method:** `POST`

**Request Body:** `confirm_name` — must equal the workspace's name exactly.

**Response:** `303` → `/`, with the cookie repointed at a remaining workspace.
`error=last_workspace` when it is the caller's only one, `error=name_mismatch`
when the confirmation does not match.

Members, teams and invites cascade; issues do not, so they are deleted per team
first, and each affected team's cache entry is dropped.

---

#### 7.4. Workspace Security

**Endpoint:** `/settings/workspace/security`

**Method:** `GET`

**Response:** `200 text/html`

---

#### 7.5. Update Workspace Security

**Endpoint:** `/settings/workspace/security`

**Method:** `POST`

**Request Body:**

| Field | Type | Notes |
| ----- | ---- | ----- |
| `allow_password_login` | checkbox | Any value is true |
| `allow_google_login` | checkbox | Any value is true |
| `allowed_email_domain` | string | `@` and case are stripped; blank means no restriction |

**Response:** `303` → `/settings/workspace/security` with
`notice=security_saved`, `error=need_a_method` (both methods off), or
`error=would_lock_out` (the change would shut the door on the admin making it).

The policy is enforced in `deps.load_context`, not at the login form: which
workspace's rules apply is only knowable once a workspace is resolved, and a
user can belong to several with different rules. Signing in still works — the
workspace just will not open, with a message naming the method that would.

---

#### 7.6. List Teams

**Endpoint:** `/settings/teams`

**Method:** `GET`

**Response:** `200 text/html` — every team in the workspace with its member and
issue counts.

---

#### 7.7. Create Team

**Endpoint:** `/settings/teams`

**Method:** `POST`

**Request Body:** `name`, `key` (falls back to the name), `color`.

**Response:** `303` → `/settings/teams/{key}` with `notice=team_created`. The
key is normalised and de-duplicated within the workspace; the creator joins the
team, and `cycle_anchor` is set to today so the team has a Current cycle
immediately.

---

#### 7.8. Team Detail

**Endpoint:** `/settings/teams/{team_key}`

**Method:** `GET`

**Response:** `200 text/html` — the team, its current members, and everyone in
the workspace as candidates.

---

#### 7.9. Update Team

**Endpoint:** `/settings/teams/{team_key}`

**Method:** `POST`

**Request Body:** `name`, `key`, `color`, `description`.

**Response:** `303` → `/settings/teams/{newKey}` with `notice=team_saved`, or
`error=key_taken`.

> **Note:** changing the key changes every identifier in the team — `TODO-3`
> becomes `ENG-3`. The number is unaffected, so old links break but no row does.

---

#### 7.10. Add or Remove Team Member

**Endpoint:** `/settings/teams/{team_key}/members`

**Method:** `POST`

**Request Body:** `user_id`, `action` (`add` — default — or `remove`).

**Response:** `303` → `/settings/teams/{key}` with `notice=member_added` or
`notice=member_removed`.

Only people already in the workspace can be added, so a team cannot be used as a
side door into it.

---

#### 7.11. Delete Team

**Endpoint:** `/settings/teams/{team_key}/delete`

**Method:** `POST`

**Response:** `303` → `/settings/teams` with `notice=team_deleted`,
`error=last_team` (a workspace has to keep one), or `error=team_has_issues`.

Refusing while the team still has issues is deliberate rather than silent:
`todos.team_id` has no cascade, so the issues would have to go too, and an issue
is the thing people actually care about. The team's cache key is invalidated on
delete — SQLite hands the next team the rowid this one just freed, and the cache
is keyed on that id.

---

#### 7.12. List Members and Invites

**Endpoint:** `/settings/members`

**Method:** `GET`

**Response:** `200 text/html` — workspace members with their roles, plus every
pending invite and its shareable link.

---

#### 7.13. Invite Member

**Endpoint:** `/settings/members/invite`

**Method:** `POST`

**Request Body:** `email`, `role` (default `member`).

**Response:** `303` → `/settings/members` with `notice=invite_created`,
`error=bad_domain`, or `error=already_member`.

Nothing is sent: there is no mail configured, so the Members page hands the
`/invite/{token}` link over for the admin to pass on. Invites expire after 14
days.

---

#### 7.14. Revoke Invite

**Endpoint:** `/settings/invites/{invite_id}/revoke`

**Method:** `POST`

**Response:** `303` → `/settings/members` with `notice=invite_revoked`. The
invite is marked `revoked`, not deleted.

---

#### 7.15. Change Member Role

**Endpoint:** `/settings/members/{user_id}/role`

**Method:** `POST`

**Request Body:** `role` — `owner`, `admin` or `member`.

**Response:** `303` → `/settings/members` with `notice=role_changed`,
`error=not_yourself`, or `error=last_owner`.

---

#### 7.16. Remove Member

**Endpoint:** `/settings/members/{user_id}/remove`

**Method:** `POST`

**Response:** `303` → `/settings/members` with `notice=member_removed_ws`,
`error=not_yourself`, or `error=last_owner`.

Team memberships in this workspace go too, or they would be left pointing into a
workspace the user can no longer open.

---

### 8. Legacy Redirects

The original course project's `/todos/*` pages are kept alive as redirects so
bookmarks and history resolve rather than 404. They are excluded from the
OpenAPI schema.

| Old route | Methods | Redirects to |
| --------- | ------- | ------------ |
| `/todos` and `/todos/` | `GET`, `POST` | `303` → `/` |
| `/todos/add-todo` | `GET`, `POST` | `303` → `/team/{key}/new` |
| `/todos/edit-todo/{todo_id}` | `GET`, `POST` | `303` → `/issue/{KEY}-{n}/edit` |
| `/todos/complete/{todo_id}` | `GET` | `303` → `/issue/{KEY}-{n}` |
| `/todos/delete/{todo_id}` | `GET` | `303` → `/issue/{KEY}-{n}` |

`303`, not `302`: these were `POST` targets too, and a `302` would have some
clients repeat the `POST` against the new URL.

The last two are deliberately **not** carried over as state-changing `GET`s.
They used to complete or delete an issue on a plain link, which meant any
crawler or link prefetcher could do it; they now land on the issue, where the
same actions exist as `POST`s.

---

### 9. Static Assets

**Endpoint:** `/static/{path}`

**Method:** `GET`

Serves `static/` — `todo/css/linear.css` and `todo/js/app.js`. No build step,
no CDN, and no framework: the JavaScript is one plain file handling menus,
keyboard shortcuts and collapsible groups.

---

## Settings Message Codes

Redirects out of `/settings/*` carry `?notice=` or `?error=` rather than full
sentences, so the wording lives in `routers/settings.py` and the address bar
stays readable.

| Code | Kind | Message |
| ---- | ---- | ------- |
| `profile_saved` | notice | Profile updated |
| `password_set` | notice | Password set |
| `password_changed` | notice | Password changed |
| `sessions_cleared` | notice | Signed out of every other session |
| `google_linked` | notice | Google account connected |
| `google_unlinked` | notice | Google account disconnected |
| `workspace_saved` | notice | Workspace updated |
| `security_saved` | notice | Security settings updated |
| `team_created` | notice | Team created |
| `team_saved` | notice | Team updated |
| `team_deleted` | notice | Team deleted |
| `member_added` | notice | Added to the team |
| `member_removed` | notice | Removed from the team |
| `invite_created` | notice | Invite ready to share |
| `invite_revoked` | notice | Invite revoked |
| `role_changed` | notice | Role updated |
| `member_removed_ws` | notice | Member removed from the workspace |
| `key_revoked` | notice | API key revoked |
| `username_taken` | error | That username is already in use |
| `email_taken` | error | That email is already in use |
| `wrong_password` | error | That is not your current password |
| `password_mismatch` | error | The two passwords do not match |
| `password_short` | error | Use at least 8 characters |
| `google_taken` | error | That Google account is already attached to another user |
| `unconfigured` | error | Google sign-in is not configured on this server |
| `last_credential` | error | That is your only way to sign in, so it cannot be removed. Set a password first. |
| `slug_taken` | error | That URL is already taken |
| `need_a_method` | error | At least one sign-in method has to stay enabled |
| `would_lock_out` | error | That would lock you out of this workspace, since it is how you are signed in right now |
| `last_owner` | error | A workspace has to keep at least one owner |
| `not_yourself` | error | You cannot change your own role |
| `last_workspace` | error | This is your only workspace, so it cannot be deleted |
| `name_mismatch` | error | The name did not match |
| `team_has_issues` | error | Delete or move its issues first |
| `last_team` | error | A workspace has to keep at least one team |
| `key_taken` | error | Another team already uses that key |
| `bad_domain` | error | That address is outside the workspace's allowed domain |
| `already_member` | error | They are already in this workspace |

---

## Environment Variables

Read from the process environment and from `.env` (via `python-dotenv`). All of
them are optional — the application starts with none set.

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `TODOAPP_DATABASE_URL` | SQLAlchemy database URL. Overridable so a test run can point the whole application at a throwaway copy | `sqlite:///./todos.db` |
| `REDIS_URL` | Redis connection for the issue cache and the logout deny-list | `redis://localhost:6379/0` |
| `GOOGLE_CLIENT_ID` | OAuth client id from Google Cloud Console | None — unset hides the Google button |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | None — unset hides the Google button |
| `GOOGLE_REDIRECT_URI` | Must match the authorised redirect URI registered with Google, character for character | `http://localhost:8000/auth/google/callback` |

**Degradation:** if Redis is unreachable, every cache call returns as though it
were a miss and the application keeps working straight off the database. A
failure also opens a circuit for 10 seconds, because failing soft alone was not
enough — while Redis was down, each call still paid the connect-and-retry, which
turned a 40 ms page into 2 s.

**Not yet an environment variable:** `SECRET_KEY` and `ALGORITHM` in
`routers/auth.py` are literals in the source. They sign both the session JWT and
the OAuth state cookie, so a real deployment should move `SECRET_KEY` out of the
repository before going anywhere near a public host.

**Running it:**

```bash
py -3.12 -m uvicorn main:app --reload
```
