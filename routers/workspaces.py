"""Creating and switching workspaces.

Both are on the workspace menu in the reference, and both are required. The
Members and Teams pages that also live off that menu land in TODO-4.
"""
import sys

sys.path.append("..")

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

import deps
import models
import provisioning
from templating import templates

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Invites get a short, top-level URL rather than living under /workspaces:
# the link is pasted into a chat or an email, so it should read like one.
invite_router = APIRouter(tags=["invites"])


def _set_active(response, slug):
    """Point the switcher cookie at a workspace.

    Not httponly-sensitive -- it names a workspace, it does not grant access
    to one; deps.load_context re-checks membership on every request. samesite
    lax so following a link from outside the app does not silently reset it.
    """
    response.set_cookie(key=deps.WORKSPACE_COOKIE, value=slug,
                        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
    return response


@router.get("/new", response_class=HTMLResponse)
async def new_workspace_form(request: Request,
                             ctx: deps.Context = Depends(deps.load_context)):
    # load_context, not require_workspace: this is the one page that has to
    # work for someone who has no workspace at all.
    return templates.TemplateResponse(
        request, "workspaces/new.html", deps.shell(ctx))


@router.post("/new", response_class=HTMLResponse)
async def create_workspace(request: Request, name: str = Form(...),
                           team_key: str = Form(provisioning.DEFAULT_TEAM_KEY),
                           ctx: deps.Context = Depends(deps.load_context)):
    if not name.strip():
        return templates.TemplateResponse(
            request, "workspaces/new.html",
            deps.shell(ctx, error="Give the workspace a name"))

    workspace = provisioning.create_workspace(
        ctx.db, ctx.user, name,
        team_name=provisioning.DEFAULT_TEAM_NAME,
        team_key=team_key or provisioning.DEFAULT_TEAM_KEY)

    # Land in the workspace that was just created, not the one that happened
    # to be active before.
    return _set_active(
        RedirectResponse(url="/", status_code=status.HTTP_302_FOUND),
        workspace.slug)


def _find_invite(db, token):
    return db.query(models.Invite)\
        .filter(models.Invite.token == token)\
        .filter(models.Invite.status == "pending").first()


def _invite_problem(invite, user):
    """Why this invite cannot be accepted, or None if it can."""
    if invite is None:
        return "That invite link is not valid, or has already been used."
    if invite.expires_at and invite.expires_at < models.utcnow():
        return "That invite has expired. Ask for a new one."
    if not provisioning.domain_allowed(invite.workspace, user.email or ""):
        return (f"{invite.workspace.name} only accepts addresses at "
                f"@{invite.workspace.allowed_email_domain}.")
    return None


@invite_router.get("/invite/{token}", response_class=HTMLResponse)
async def view_invite(request: Request, token: str,
                      ctx: deps.Context = Depends(deps.load_context)):
    """Show what is being joined before joining it.

    load_context rather than require_workspace: someone accepting an invite may
    have no workspace of their own yet, and bouncing them to the create form
    would lose the invite.
    """
    invite = _find_invite(ctx.db, token)
    already = invite is not None and ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == invite.workspace_id)\
        .filter(models.WorkspaceMember.user_id == ctx.user.id).first() is not None

    return templates.TemplateResponse(request, "workspaces/invite.html", deps.shell(
        ctx, invite=invite, token=token, already_member=already,
        problem=_invite_problem(invite, ctx.user)))


@invite_router.post("/invite/{token}")
async def accept_invite(token: str,
                        ctx: deps.Context = Depends(deps.load_context)):
    invite = _find_invite(ctx.db, token)
    if _invite_problem(invite, ctx.user) is not None:
        return RedirectResponse(url=f"/invite/{token}",
                                status_code=status.HTTP_303_SEE_OTHER)

    existing = ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == invite.workspace_id)\
        .filter(models.WorkspaceMember.user_id == ctx.user.id).first()

    if existing is None:
        ctx.db.add(models.WorkspaceMember(
            workspace_id=invite.workspace_id, user_id=ctx.user.id,
            role=invite.role))

    # Marked accepted either way: the link has done its job, and leaving it
    # pending would let it be passed on to somebody else.
    invite.status = "accepted"
    ctx.db.add(invite)
    ctx.db.commit()

    return _set_active(
        RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER),
        invite.workspace.slug)


@router.post("/switch/{slug}")
async def switch_workspace(slug: str,
                           ctx: deps.Context = Depends(deps.load_context)):
    """POST, not GET: switching changes what every later request resolves to,
    and a GET would be followed by prefetchers and crawlers."""
    membership = ctx.db.query(models.WorkspaceMember)\
        .join(models.Workspace,
              models.Workspace.id == models.WorkspaceMember.workspace_id)\
        .filter(models.WorkspaceMember.user_id == ctx.user.id)\
        .filter(models.Workspace.slug == slug).first()

    if membership is None:
        # Not this user's workspace. Say nothing about whether it exists.
        raise deps.Forbidden("That workspace is not yours to open")

    return _set_active(
        RedirectResponse(url="/", status_code=status.HTTP_302_FOUND),
        slug)
