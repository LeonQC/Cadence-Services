"""Creating workspaces and teams.

Three separate paths need a user to end up with somewhere to work -- password
signup, Google signup, and the "create a workspace" form -- so the shape of a
new workspace is defined once here instead of three times. It matches what
migrate_workspaces.py backfilled onto existing accounts, so a migrated user
and a fresh one are indistinguishable afterwards.

Imports models only, so both routers/auth.py and routers/workspaces.py can use
it without an import cycle.
"""

import re
import secrets
from datetime import timedelta

import models

# Matches the task prefix used across this project, so a new workspace's first
# issue reads as TODO-1.
DEFAULT_TEAM_KEY = "TODO"
DEFAULT_TEAM_NAME = "Todo"
DEFAULT_TEAM_COLOR = "#5e6ad2"

# Team keys are the visible half of an issue identifier, so they are kept
# short and shouty the way Linear does it.
TEAM_KEY_MAX = 6


def slugify(value):
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return cleaned or "workspace"


def unique_slug(db, preferred):
    """Free workspace slug closest to `preferred`, e.g. acme -> acme-2."""
    base = slugify(preferred)
    slug, suffix = base, 1
    while db.query(models.Workspace).filter(
            models.Workspace.slug == slug).first():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


def teamify(value, fallback=DEFAULT_TEAM_KEY):
    """Turn free text into a team key: TODO, ENG, DESIGN."""
    cleaned = re.sub(r"[^A-Z0-9]", "", (value or "").upper())[:TEAM_KEY_MAX]
    return cleaned or fallback


def unique_team_key(db, workspace_id, preferred):
    """Free team key within one workspace. Keys are unique per workspace, not
    globally, so two workspaces can each have their own TODO team."""
    base = teamify(preferred)
    key, suffix = base, 1
    while db.query(models.Team).filter(
            models.Team.workspace_id == workspace_id,
            models.Team.key == key).first():
        suffix += 1
        key = f"{base[:TEAM_KEY_MAX - len(str(suffix))]}{suffix}"
    return key


def create_team(db, workspace, name, key=None, color=DEFAULT_TEAM_COLOR,
                members=()):
    """Add a team to a workspace, with `members` joined to it.

    Does not commit -- the caller decides where the transaction ends, so a
    half-built workspace never reaches the database.
    """
    team = models.Team(
        workspace_id=workspace.id,
        name=name,
        key=unique_team_key(db, workspace.id, key or name),
        color=color,
        issue_counter=0,
        # Cycle 1 starts the day the team does. Everything after it is
        # arithmetic from here, so a team always has a Current cycle.
        cycle_anchor=models.utcnow().date(),
    )
    db.add(team)
    db.flush()  # assigns team.id, needed for the memberships below

    for user in members:
        db.add(models.TeamMember(team_id=team.id, user_id=user.id))
    return team


def create_workspace(db, owner, name, slug=None, team_name=DEFAULT_TEAM_NAME,
                     team_key=DEFAULT_TEAM_KEY):
    """Create a workspace owned by `owner`, with one team they belong to.

    A workspace with no team would render an empty sidebar and have nowhere to
    put an issue, so the two are always created together.
    """
    workspace = models.Workspace(
        name=name.strip() or "Workspace",
        slug=unique_slug(db, slug or name),
    )
    db.add(workspace)
    db.flush()

    db.add(models.WorkspaceMember(
        workspace_id=workspace.id, user_id=owner.id, role="owner"))
    create_team(db, workspace, team_name, key=team_key, members=[owner])

    db.commit()
    db.refresh(workspace)
    return workspace


def provision_personal_workspace(db, user):
    """Give a brand new account somewhere to work.

    Called from every signup path. Without it a user could sign in and land on
    an app with no workspace, no team and nowhere to put an issue.
    """
    label = (user.first_name or user.username or "Personal").strip()
    return create_workspace(db, user, f"{label}'s workspace",
                            slug=user.username or f"user{user.id}")


INVITE_TTL_DAYS = 14


def email_domain(address):
    return (address or "").rsplit("@", 1)[-1].strip().lower()


def domain_allowed(workspace, address):
    """Whether an address may join this workspace.

    An empty allowed_email_domain means no restriction, which is the default;
    the setting only ever narrows.
    """
    required = (workspace.allowed_email_domain or "").strip().lower()
    if not required:
        return True
    return email_domain(address) == required.lstrip("@")


def create_invite(db, workspace, inviter, email, role="member"):
    """Mint an invite. Does not send anything -- there is no mail configured,
    so the Members page hands the link over for the admin to pass on."""
    invite = models.Invite(
        workspace_id=workspace.id,
        email=(email or "").strip().lower(),
        role=role if role in models.ROLES else "member",
        token=secrets.token_urlsafe(24),
        invited_by_id=inviter.id,
        status="pending",
        expires_at=models.utcnow() + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def delete_team(db, team):
    """Remove a team, its memberships and its issues.

    The issues go too rather than being orphaned: Todos.team_id has no
    cascade, so leaving them would produce rows pointing at a team that is not
    there, invisible to every view and impossible to reach.

    Returns the ids whose issue cache the caller has to drop. SQLite hands the
    next team the rowid this one just freed, and the cache is keyed on that id
    -- so without the invalidation a brand new team inherits the deleted one's
    issue list until the entry expires. Returning the ids rather than clearing
    them here keeps this function synchronous while making the obligation hard
    to miss.
    """
    team_id = team.id
    db.query(models.Todos).filter(models.Todos.team_id == team_id).delete(
        synchronize_session=False)
    db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id).delete(synchronize_session=False)
    db.delete(team)
    db.commit()
    return [team_id]


def delete_workspace(db, workspace):
    """Remove a workspace and everything under it.

    Members, teams and invites cascade from the model; issues do not, so they
    are taken down per team first. Returns the team ids to invalidate, for the
    same reason delete_team does.
    """
    team_ids = [team.id for team in workspace.teams]
    for team_id in team_ids:
        db.query(models.Todos).filter(models.Todos.team_id == team_id).delete(
            synchronize_session=False)
    db.delete(workspace)
    db.commit()
    return team_ids


def next_issue_number(db, team):
    """Reserve the next number in a team's sequence.

    Counts up from issue_counter rather than from the existing rows, so
    deleting an issue does not cause the next one to reuse its identifier.
    """
    team.issue_counter = (team.issue_counter or 0) + 1
    db.add(team)
    return team.issue_counter
