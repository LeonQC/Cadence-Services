from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        String, UniqueConstraint)
from sqlalchemy.orm import relationship
from database import Base


def utcnow():
    """Current UTC time, without a tzinfo.

    SQLite hands datetimes back naive, so storing aware ones would turn every
    later comparison into a naive-vs-aware TypeError. datetime.utcnow() would
    do the same job but is deprecated from 3.12 on.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Issue statuses, in the order the list view groups them.
STATUSES = ["backlog", "todo", "in_progress", "done", "canceled"]

STATUS_LABELS = {
    "backlog": "Backlog",
    "todo": "Todo",
    "in_progress": "In Progress",
    "done": "Done",
    "canceled": "Canceled",
}

# Workspace roles, most privileged first -- permission checks compare positions
# in this list, so the order is load-bearing.
ROLES = ["owner", "admin", "member"]


def role_at_least(role, minimum):
    """True if `role` carries at least the privileges of `minimum`."""
    if role not in ROLES or minimum not in ROLES:
        return False
    return ROLES.index(role) <= ROLES.index(minimum)


# Fallback avatar colours, in the muted range Linear uses for member chips.
AVATAR_COLORS = ["#5e6ad2", "#26b5ce", "#4cb782", "#f2c94c",
                 "#eb5757", "#bb87fc", "#f2994a", "#95a2b3"]


def avatar_color_for(user):
    """A user's avatar colour: whatever they picked, else one derived from
    their id so migrated accounts still look consistent everywhere."""
    if user is None:
        return AVATAR_COLORS[-1]
    return user.avatar_color or AVATAR_COLORS[(user.id or 0) % len(AVATAR_COLORS)]


# Project lifecycle. Separate from issue STATUSES: a project is a container,
# and "backlog" means nothing for one.
PROJECT_STATUSES = ["planned", "in_progress", "completed", "canceled"]

PROJECT_STATUS_LABELS = {
    "planned": "Planned",
    "in_progress": "In Progress",
    "completed": "Completed",
    "canceled": "Canceled",
}

# Issue statuses that count as work having begun. Used when stamping
# started_at, and by the cycle burn-up's "Started" line.
STARTED_STATUSES = ("in_progress", "done")

# Third-party services Settings -> Integrations can link a workspace to.
#
# A catalogue rather than rows: what can be connected is a property of this
# build, so only the connections themselves are data. `target` names the one
# thing a link needs in order to point somewhere, and every service names that
# differently -- a Slack channel, a GitHub repository, a Figma file.
#
# `color` is the logo tile, and has to stay clear of --bg-panel or the tile
# disappears into the card. `text` is the letter on it, defaulting to white;
# the bright tiles set it dark because white on brand orange lands under 3:1.
INTEGRATIONS = [
    {"slug": "slack", "name": "Slack", "category": "Communication",
     "color": "#4A154B", "letter": "S",
     "summary": "Post issue updates to a channel, and open issues from a "
                "message without leaving the thread.",
     "target_label": "Channel", "target_hint": "#product"},
    {"slug": "discord", "name": "Discord", "category": "Communication",
     "color": "#5865F2", "letter": "D",
     "summary": "Mirror the same updates into a Discord server.",
     "target_label": "Channel", "target_hint": "#engineering"},
    {"slug": "github", "name": "GitHub", "category": "Development",
     "color": "#30363D", "letter": "G",
     "summary": "Link pull requests to issues, and close an issue when its "
                "branch merges.",
     "target_label": "Repository", "target_hint": "acme/backend"},
    {"slug": "gitlab", "name": "GitLab", "category": "Development",
     "color": "#FC6D26", "text": "#1B1B1B", "letter": "G",
     "summary": "The same branch and merge-request links, against GitLab.",
     "target_label": "Project path", "target_hint": "acme/backend"},
    {"slug": "sentry", "name": "Sentry", "category": "Development",
     "color": "#362D59", "letter": "S",
     "summary": "Turn an unresolved error into an issue, with the stack trace "
                "attached.",
     "target_label": "Project", "target_hint": "acme/api"},
    {"slug": "figma", "name": "Figma", "category": "Design",
     "color": "#F24E1E", "text": "#1B1B1B", "letter": "F",
     "summary": "Unfurl a Figma link into a preview on the issue.",
     "target_label": "File or project URL", "target_hint": "figma.com/file/…"},
    {"slug": "notion", "name": "Notion", "category": "Productivity",
     # Notion's mark is black on white, which on this surface would be a tile
     # the same colour as the card behind it. Nudged to a warm grey so the
     # logo still separates from the panel.
     "color": "#4F4D48", "letter": "N",
     "summary": "Reference issues from a Notion page and keep their status in "
                "step.",
     "target_label": "Workspace", "target_hint": "acme"},
    {"slug": "zapier", "name": "Zapier", "category": "Productivity",
     "color": "#FF4F00", "text": "#1B1B1B", "letter": "Z",
     "summary": "Hand issue events to several thousand other tools without "
                "writing any of the glue.",
     "target_label": "Hook URL", "target_hint": "hooks.zapier.com/…"},
]

INTEGRATIONS_BY_SLUG = {entry["slug"]: entry for entry in INTEGRATIONS}

# The order the integrations page groups its cards in.
INTEGRATION_CATEGORIES = ["Communication", "Development", "Design",
                          "Productivity"]



def set_status(todo, status):
    """Move an issue to a new status.

    `complete`, `completed_at` and `started_at` are all derived from `status`,
    never set on their own, so they cannot drift apart.

    started_at is written once and then left alone. It records when work first
    began, which is what the cycle burn-up plots -- if moving an issue back to
    Todo and forward again reset it, the chart would rewrite its own history
    every time someone corrected a mis-click.
    """
    todo.status = status
    todo.complete = status == "done"
    todo.completed_at = utcnow() if status == "done" else None
    if status in STARTED_STATUSES and todo.started_at is None:
        todo.started_at = utcnow()
    todo.updated_at = utcnow()


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    # Google's stable user id ("sub" in the id_token). Null for users who only
    # ever signed up with a password. Users created via Google have no
    # hashed_password instead, so at least one of the two is always set.
    google_sub = Column(String, unique=True, index=True, nullable=True)

    # Bumped by "log out of all sessions". Every access token carries the value
    # it was minted with, so raising this invalidates all of them at once --
    # which the Redis jti denylist cannot do, since it only ever learns about
    # the one token being logged out.
    token_version = Column(Integer, default=0, nullable=False)
    # Stable colour for the fallback avatar, so a user looks the same
    # everywhere without storing an image.
    avatar_color = Column(String, nullable=True)

    todos = relationship("Todos", back_populates="owner",
                         foreign_keys="Todos.owner_id")
    memberships = relationship("WorkspaceMember", back_populates="user",
                               cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user",
                            cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", back_populates="user",
                                cascade="all, delete-orphan")

    @property
    def display_name(self):
        full = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return full or self.username


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Identifies the workspace in the switcher cookie, so it has to be unique
    # across the install rather than just readable.
    slug = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    # Written by Settings -> Administration -> Security, read by the login
    # paths in routers/auth.py.
    allow_password_login = Column(Boolean, default=True, nullable=False)
    allow_google_login = Column(Boolean, default=True, nullable=False)
    allowed_email_domain = Column(String, nullable=True)

    members = relationship("WorkspaceMember", back_populates="workspace",
                           cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="workspace",
                         cascade="all, delete-orphan")
    invites = relationship("Invite", back_populates="workspace",
                           cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="workspace",
                                cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True,
                          nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String, default="member", nullable=False)  # see ROLES
    created_at = Column(DateTime, default=utcnow)

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("Users", back_populates="memberships")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_team_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True,
                          nullable=False)
    name = Column(String, nullable=False)
    # Prefix half of an issue identifier: key "TODO" plus Todos.number 3 reads
    # as TODO-3. Unique per workspace, not globally.
    key = Column(String, nullable=False)
    color = Column(String, nullable=True)
    # Shown at the top of the team's Home page.
    description = Column(String, nullable=True)
    # Highest number handed out so far. Issue creation bumps this rather than
    # counting existing rows, so deleting an issue does not cause the next one
    # to reuse its identifier.
    issue_counter = Column(Integer, default=0, nullable=False)

    # Cycles are a arithmetic series, not hand-made rows: cycle N runs from
    # anchor + (N-1) * length for `length` days. Storing the rule rather than a
    # calendar means Current and Upcoming are always populated, with no cron
    # job to keep a table topped up.
    cycle_length_days = Column(Integer, default=14, nullable=False)
    cycle_anchor = Column(Date, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    workspace = relationship("Workspace", back_populates="teams")
    members = relationship("TeamMember", back_populates="team",
                           cascade="all, delete-orphan")
    issues = relationship("Todos", back_populates="team")
    projects = relationship("Project", back_populates="team",
                            cascade="all, delete-orphan")
    cycles = relationship("Cycle", back_populates="team",
                          cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    team = relationship("Team", back_populates="members")
    user = relationship("Users")


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True,
                          nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, default="member", nullable=False)
    # Random secret in the invite URL (/invite/{token}). Unique so a link can
    # be resolved by itself, without the recipient having to say who they are.
    token = Column(String, unique=True, index=True, nullable=False)
    invited_by_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending", nullable=False)  # pending|accepted|revoked
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime)

    workspace = relationship("Workspace", back_populates="invites")
    invited_by = relationship("Users", foreign_keys=[invited_by_id])


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    label = Column(String, nullable=False)
    # Leading characters of the plaintext, kept so the settings list can show
    # which key a row is. The rest of the key exists only in the one response
    # that created it -- everything else compares against key_hash.
    prefix = Column(String, nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("Users", back_populates="api_keys")


class OAuthToken(Base):
    """Encrypted provider refresh token owned by one application user."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True,
                     nullable=False)
    provider = Column(String, nullable=False)
    encrypted_refresh_token = Column(String, nullable=False)
    scopes = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("Users", back_populates="oauth_tokens")


class Project(Base):
    """A feature: one deliverable, made of several issues.

    The parent half of the issue hierarchy -- Team owns Projects, a Project
    owns Issues. Scoped to a team rather than to the workspace, so a project's
    issues all share one identifier prefix and one cycle calendar.
    """

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="planned", nullable=False)  # PROJECT_STATUSES
    lead_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    team = relationship("Team", back_populates="projects")
    lead = relationship("Users", foreign_keys=[lead_id])
    # No cascade: deleting a project releases its issues rather than taking
    # them with it. An issue is the unit people care about, and a container
    # going away is not a reason to lose one.
    issues = relationship("Todos", back_populates="project")


class Cycle(Base):
    """A team's time box -- Cycle 1, Cycle 2, and so on.

    Rows are generated from the team's anchor date and cycle length rather
    than being created by hand, so the numbering is gapless and the dates are
    contiguous by construction. Which one is Current is read off the calendar
    and never stored: a stored flag would be wrong the morning after.
    """

    __tablename__ = "cycles"
    __table_args__ = (
        UniqueConstraint("team_id", "number", name="uq_cycle_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    number = Column(Integer, nullable=False)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)   # inclusive
    created_at = Column(DateTime, default=utcnow)

    team = relationship("Team", back_populates="cycles")
    issues = relationship("Todos", back_populates="cycle")

    def contains(self, day):
        return self.starts_on <= day <= self.ends_on

    @property
    def name(self):
        return f"Cycle {self.number}"


class Todos(Base):
    """An issue. Still called Todos because the table predates the rename and
    renaming it would mean rewriting every existing row's home."""

    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(Integer)
    # Redundant with status == "done", and deliberately so: the original routes
    # and the Redis cache still read it. Only ever written via set_status().
    complete = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))

    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    # Per-team sequence number; with the team's key this makes the identifier.
    number = Column(Integer)
    status = Column(String, default="todo", nullable=False)  # see STATUSES
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # The feature this task belongs to, and the time box it is scheduled in.
    # Both optional: an issue can exist without either, which is what the
    # backlog is.
    project_id = Column(Integer, ForeignKey("projects.id"), index=True,
                        nullable=True)
    cycle_id = Column(Integer, ForeignKey("cycles.id"), index=True,
                      nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)
    # When work first began. Written once by set_status; the cycle burn-up's
    # "Started" line cannot be reconstructed from the other columns.
    started_at = Column(DateTime, nullable=True)

    owner = relationship("Users", back_populates="todos",
                         foreign_keys=[owner_id])
    assignee = relationship("Users", foreign_keys=[assignee_id])
    team = relationship("Team", back_populates="issues")
    project = relationship("Project", back_populates="issues")
    cycle = relationship("Cycle", back_populates="issues")
    github_commits = relationship("GitHubCommit", back_populates="issue",
                                   cascade="all, delete-orphan")

    @property
    def identifier(self):
        """The TODO-3 form. None until the issue has been given a team."""
        if self.team is None or self.number is None:
            return None
        return f"{self.team.key}-{self.number}"


class Integration(Base):
    """A workspace's link to one third-party service.

    The row is the connection: no row means not connected, which keeps
    INTEGRATIONS the single list of what exists and leaves this table holding
    only what somebody actually set up. `enabled` is separate from deleting the
    row so that pausing an integration does not throw away the target its owner
    had to look up.

    Provider credentials stay in environment variables. GitHub stores only its
    installation id here; short-lived installation tokens are minted on demand.
    """

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider",
                         name="uq_workspace_integration"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True,
                          nullable=False)
    # A slug from INTEGRATIONS. Stored rather than a foreign key because the
    # catalogue is code, not a table.
    provider = Column(String, nullable=False)
    # Where the link points, in whatever shape the service uses.
    target = Column(String, nullable=True)
    github_installation_id = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    connected_at = Column(DateTime, default=utcnow)
    connected_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    workspace = relationship("Workspace", back_populates="integrations")
    connected_by = relationship("Users")

    @property
    def catalog(self):
        """The catalogue entry this row connects, or None if the build no
        longer offers it."""
        return INTEGRATIONS_BY_SLUG.get(self.provider)


class GitHubCommit(Base):
    """A GitHub commit associated with a TodoApp issue identifier."""

    __tablename__ = "github_commits"
    __table_args__ = (
        UniqueConstraint("repository", "sha", "issue_id",
                         name="uq_github_repository_sha_issue"),
    )

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("todos.id"), index=True,
                      nullable=False)
    repository = Column(String, nullable=False)
    sha = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    message = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    url = Column(String, nullable=False)
    author_name = Column(String, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    issue = relationship("Todos", back_populates="github_commits")
