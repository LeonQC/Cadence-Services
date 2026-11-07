"""Shared request dependencies: who is signed in, which workspace they are
looking at, and whether they are allowed to be there.

Every route used to repeat the same four lines of get_current_user plus a
redirect. With workspaces and roles in play that would have become a dozen
copies of the same check, each one an opportunity to forget the membership
half, so the checks live here once and routes declare what they need:

    @router.get("/settings/members")
    async def members(ctx: Context = Depends(require_admin)):
        ...

The failures are raised, not returned, so a route can never accidentally carry
on past one. main.py turns them into a redirect for browsers and a JSON 401 or
403 for API-key callers.
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from routers.auth import get_current_user

# Name of the cookie holding the slug of the workspace being viewed. Only ever
# trusted after the membership lookup in load_context confirms it.
WORKSPACE_COOKIE = "active_workspace"


class NotAuthenticated(Exception):
    """No usable session. Handled in main.py as a redirect to the login page."""


class Forbidden(Exception):
    """Signed in, but not entitled to this. Deliberately distinct from
    NotAuthenticated: sending someone back to a login page they are already
    past just loops them."""

    def __init__(self, detail="You do not have access to that"):
        self.detail = detail
        super().__init__(detail)


class NoWorkspace(Exception):
    """Signed in, but with nowhere to work.

    Its own type rather than a Forbidden, because the fix is to create a
    workspace, not to ask someone for access. main.py sends these to the
    create-workspace form.
    """


@dataclass
class Context:
    """Everything a signed-in page needs about the caller.

    Passed around as one object so adding, say, the team later does not mean
    changing thirty route signatures.
    """

    db: Session
    user: models.Users
    workspace: Optional[models.Workspace] = None
    membership: Optional[models.WorkspaceMember] = None
    # How this session was authenticated: password, google or api_key. Read by
    # the workspace security policy.
    auth_method: str = "password"

    @property
    def role(self):
        return self.membership.role if self.membership else None

    def can(self, minimum):
        return models.role_at_least(self.role, minimum)

    @property
    def is_admin(self):
        """Whether the Administration section applies to this user."""
        return self.can("admin")


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def workspaces_for(db, user_id):
    """Every workspace the user belongs to, for the switcher."""
    return db.query(models.Workspace)\
        .join(models.WorkspaceMember,
              models.WorkspaceMember.workspace_id == models.Workspace.id)\
        .filter(models.WorkspaceMember.user_id == user_id)\
        .order_by(models.Workspace.name).all()


def teams_for(db, user_id, workspace_id):
    """The user's teams inside one workspace, for the sidebar."""
    return db.query(models.Team)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.TeamMember.user_id == user_id)\
        .filter(models.Team.workspace_id == workspace_id)\
        .order_by(models.Team.name).all()


def team_by_key(db, user_id, workspace_id, team_key):
    """A team the user belongs to, named by its key.

    Scoped to one workspace as well as to the membership: keys are unique per
    workspace, not globally, so the same key means different teams elsewhere.
    """
    return db.query(models.Team)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.Team.key == (team_key or "").upper())\
        .filter(models.Team.workspace_id == workspace_id)\
        .filter(models.TeamMember.user_id == user_id)\
        .first()


def default_team(db, user_id, workspace_id=None):
    """The team to land on when the URL does not name one."""
    query = db.query(models.Team)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.TeamMember.user_id == user_id)
    if workspace_id is not None:
        query = query.filter(models.Team.workspace_id == workspace_id)
    return query.order_by(models.Team.id).first()


async def identity(request: Request, db: Session = Depends(get_db)):
    """Who the caller is, as get_current_user reports them.

    Its own dependency so that require_user and load_context share one lookup:
    FastAPI caches a dependency's result for the request, so the token is
    decoded once no matter how many guards a route stacks.
    """
    who = await get_current_user(request, db)
    if who is None:
        raise NotAuthenticated()
    return who


async def require_user(db: Session = Depends(get_db),
                       who: dict = Depends(identity)):
    """The signed-in user as an ORM row. Raises rather than returning None."""
    user = db.query(models.Users).filter(models.Users.id == who["id"]).first()
    if user is None:
        raise NotAuthenticated()
    return user


def method_allowed(workspace, method):
    """Whether a workspace accepts a session signed in this way.

    API keys are exempt: they are a separate credential the user issued
    themselves, and refusing them here would make the API page's own keys
    stop working the moment an admin turned off password logins.
    """
    if workspace is None or method == "api_key":
        return True
    if method == "google":
        return bool(workspace.allow_google_login)
    return bool(workspace.allow_password_login)


def refusal_message(workspace, method):
    """Why a workspace will not open, and what to do about it.

    Naming the method that would work is the whole point: "not allowed" on its
    own leaves someone staring at a page with no idea that signing out and
    coming back the other way fixes it.
    """
    used = "Google" if method == "google" else "a password"
    instead = []
    if workspace.allow_password_login:
        instead.append("a password")
    if workspace.allow_google_login:
        instead.append("Google")

    if not instead:
        return (f"{workspace.name} has no sign-in method enabled. "
                f"An admin has to turn one back on.")
    return (f"{workspace.name} does not accept signing in with {used}. "
            f"Sign out and use {' or '.join(instead)} instead.")


async def load_context(request: Request, db: Session = Depends(get_db),
                       user: models.Users = Depends(require_user),
                       who: dict = Depends(identity)):
    """require_user, plus the workspace the cookie points at.

    The cookie is only a hint: the workspace is resolved through the
    membership table, so pointing the cookie at someone else's workspace
    resolves to nothing rather than granting access to it.
    """
    slug = request.cookies.get(WORKSPACE_COOKIE)

    membership = None
    if slug:
        membership = db.query(models.WorkspaceMember)\
            .join(models.Workspace,
                  models.Workspace.id == models.WorkspaceMember.workspace_id)\
            .filter(models.WorkspaceMember.user_id == user.id)\
            .filter(models.Workspace.slug == slug).first()

    if membership is None:
        # No cookie, or one naming a workspace this user cannot see. Fall back
        # to their first membership so the app is never stuck with nowhere to
        # go; the caller is expected to reset the cookie.
        membership = db.query(models.WorkspaceMember)\
            .filter(models.WorkspaceMember.user_id == user.id)\
            .order_by(models.WorkspaceMember.id).first()

    workspace = membership.workspace if membership else None
    method = who.get("method", "password")

    # Settings -> Administration -> Security is enforced here rather than at
    # the login form, because which workspace's rules apply is only knowable
    # once one is resolved -- a user can belong to several with different
    # rules. Signing in still works; this workspace just will not open.
    if not method_allowed(workspace, method):
        raise Forbidden(refusal_message(workspace, method))

    return Context(db=db, user=user, workspace=workspace,
                   membership=membership, auth_method=method)


async def require_workspace(ctx: Context = Depends(load_context)):
    """A context that is guaranteed to have a workspace.

    Signup provisions one, so reaching here without a membership means an
    account that predates that or has had its last workspace removed. Either
    way the answer is the same: go and make one.
    """
    if ctx.workspace is None:
        raise NoWorkspace()
    return ctx


def shell(ctx: Context, **extra):
    """The context every page rendered inside the app shell needs.

    The sidebar reads workspace, workspaces and teams on every single page, so
    gathering them here keeps thirty routes from each remembering to.
    """
    context = {
        "user": ctx.user,
        "ctx": ctx,
        "workspace": ctx.workspace,
        "workspaces": workspaces_for(ctx.db, ctx.user.id),
        "teams": teams_for(ctx.db, ctx.user.id, ctx.workspace.id)
                 if ctx.workspace else [],
        "active_team": None,
        # Which sidebar entry to mark as current. Passed by the route rather
        # than worked out from the URL in a template, so renaming a path does
        # not silently unhighlight a link.
        "active_view": None,
    }
    context.update(extra)
    return context


async def require_admin(ctx: Context = Depends(require_workspace)):
    """Guard for the Administration settings pages.

    Hiding the section in the template is presentation, not access control --
    this is the part that actually stops a member from opening the URL.
    """
    if not ctx.is_admin:
        raise Forbidden("Only workspace admins can change these settings")
    return ctx


async def require_owner(ctx: Context = Depends(require_workspace)):
    if not ctx.can("owner"):
        raise Forbidden("Only the workspace owner can do that")
    return ctx
