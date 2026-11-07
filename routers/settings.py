"""The settings area: three personal pages, six administration pages, and
team management.

The navigation is data rather than markup so that what is routed and what is
linked cannot drift apart -- an entry without an href renders greyed out, and
those are only ever features this rebuild does not cover.

Every administration route sits behind deps.require_admin. Hiding a link in a
template is presentation; that dependency is the part that actually refuses
someone who types the URL.
"""
import sys

sys.path.append("..")

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

import deps
import github_integration
import models
import provisioning
import redis_cache
from database import SessionLocal
from routers import auth as auth_module
from templating import templates
from jose import JWTError, jwt
from routers.auth import SECRET_KEY
from uuid import uuid4

router = APIRouter(prefix="/settings", tags=["settings"])


def _item(label, href=None, planned=False):
    """One settings navigation entry.

    href None means there is no page. `planned` is left over from when these
    were all unbuilt; what remains without an href is out of scope for this
    rebuild, and renders inert because a link that 404s is a worse lie than a
    visibly disabled one.
    """
    return {"label": label, "href": href, "planned": planned}


SETTINGS_NAV = [
    ("Personal", [
        _item("Preferences"),
        _item("Profile", "/settings/profile"),
        _item("Notifications"),
        _item("Code & reviews"),
        _item("Security & access", "/settings/security"),
        _item("Connected accounts", "/settings/accounts"),
        _item("Agent personalization"),
    ]),
    ("Administration", [
        _item("Workspace", "/settings/workspace"),
        _item("Teams", "/settings/teams"),
        _item("Members", "/settings/members"),
        _item("Security", "/settings/workspace/security"),
        _item("API", "/settings/api"),
        _item("Integrations", "/settings/integrations"),
        _item("Applications"),
        _item("Billing"),
        _item("Import & export"),
    ]),
]

# Sections only workspace admins see. Presentation only -- each page below is
# separately guarded.
ADMIN_SECTIONS = {"Administration"}

# Messages are carried between a POST and its redirect as short codes rather
# than as text in the URL, so the wording lives here and the address bar stays
# readable.
MESSAGES = {
    "profile_saved": "Profile updated",
    "password_set": "Password set",
    "password_changed": "Password changed",
    "sessions_cleared": "Signed out of every other session",
    "google_linked": "Google account connected",
    "google_unlinked": "Google account disconnected",
    "workspace_saved": "Workspace updated",
    "security_saved": "Security settings updated",
    "team_created": "Team created",
    "team_saved": "Team updated",
    "team_deleted": "Team deleted",
    "member_added": "Added to the team",
    "member_removed": "Removed from the team",
    "invite_created": "Invite ready to share",
    "invite_revoked": "Invite revoked",
    "role_changed": "Role updated",
    "member_removed_ws": "Member removed from the workspace",
    "key_revoked": "API key revoked",
    "integration_connected": "Integration connected",
    "integration_updated": "Integration updated",
    "integration_disconnected": "Integration disconnected",
    "integration_paused": "Integration paused",
    "integration_resumed": "Integration resumed",

    "username_taken": "That username is already in use",
    "email_taken": "That email is already in use",
    "wrong_password": "That is not your current password",
    "password_mismatch": "The two passwords do not match",
    "password_short": "Use at least 8 characters",
    "google_taken": "That Google account is already attached to another user",
    "unconfigured": "Google sign-in is not configured on this server",
    "last_credential": "That is your only way to sign in, so it cannot be "
                       "removed. Set a password first.",
    "slug_taken": "That URL is already taken",
    "need_a_method": "At least one sign-in method has to stay enabled",
    "would_lock_out": "That would lock you out of this workspace, since it is "
                      "how you are signed in right now",
    "last_owner": "A workspace has to keep at least one owner",
    "not_yourself": "You cannot change your own role",
    "last_workspace": "This is your only workspace, so it cannot be deleted",
    "name_mismatch": "The name did not match",
    "team_has_issues": "Delete or move its issues first",
    "last_team": "A workspace has to keep at least one team",
    "key_taken": "Another team already uses that key",
    "bad_domain": "That address is outside the workspace's allowed domain",
    "already_member": "They are already in this workspace",
    "unknown_integration": "This build does not offer that integration",
    "target_required": "Say where the integration should point",
    "github_unconfigured": "GitHub App is not configured on this server",
    "github_connected": "GitHub App connected",
    "github_failed": "GitHub App connection failed",
    "github_repo_invalid": "That repository is not available to this GitHub App installation",
}


def nav_for(ctx):
    """The navigation as the current user should see it."""
    return [(title, items) for title, items in SETTINGS_NAV
            if title not in ADMIN_SECTIONS or ctx.is_admin]


def page(request, ctx, template, current, **extra):
    """Render a settings page with the shell context it needs."""
    codes = request.query_params
    return templates.TemplateResponse(request, template, deps.shell(
        ctx,
        nav=nav_for(ctx),
        current=current,
        notice=MESSAGES.get(codes.get("notice")),
        error=MESSAGES.get(codes.get("error")),
        **extra))


def back(path, **codes):
    return RedirectResponse(
        url=path + ("?" + "&".join(f"{k}={v}" for k, v in codes.items())
                    if codes else ""),
        status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
async def settings_home():
    return RedirectResponse(url="/settings/profile",
                            status_code=status.HTTP_302_FOUND)


@router.get("", include_in_schema=False)
async def settings_home_no_slash():
    return RedirectResponse(url="/settings/profile",
                            status_code=status.HTTP_302_FOUND)


# Personal -------------------------------------------------------------------


@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request,
                  ctx: deps.Context = Depends(deps.require_workspace)):
    return page(request, ctx, "settings/profile.html", "Profile",
                palette=models.AVATAR_COLORS)


@router.post("/profile")
async def save_profile(first_name: str = Form(""), last_name: str = Form(""),
                       username: str = Form(...), email: str = Form(""),
                       avatar_color: str = Form(""),
                       ctx: deps.Context = Depends(deps.require_workspace)):
    username = username.strip()
    email = email.strip()

    clash = ctx.db.query(models.Users)\
        .filter(models.Users.username == username)\
        .filter(models.Users.id != ctx.user.id).first()
    if clash is not None:
        return back("/settings/profile", error="username_taken")

    if email:
        clash = ctx.db.query(models.Users)\
            .filter(models.Users.email == email)\
            .filter(models.Users.id != ctx.user.id).first()
        if clash is not None:
            return back("/settings/profile", error="email_taken")

    ctx.user.first_name = first_name.strip()
    ctx.user.last_name = last_name.strip()
    ctx.user.username = username
    ctx.user.email = email or None
    if avatar_color in models.AVATAR_COLORS:
        ctx.user.avatar_color = avatar_color
    ctx.db.add(ctx.user)
    ctx.db.commit()
    return back("/settings/profile", notice="profile_saved")


@router.get("/security", response_class=HTMLResponse)
async def security(request: Request,
                   ctx: deps.Context = Depends(deps.require_workspace)):
    return page(request, ctx, "settings/security.html", "Security & access",
                has_password=bool(ctx.user.hashed_password))


@router.post("/security/password")
async def change_password(current_password: str = Form(""),
                          new_password: str = Form(...),
                          confirm_password: str = Form(...),
                          ctx: deps.Context = Depends(deps.require_workspace)):
    had_password = bool(ctx.user.hashed_password)

    # A Google-only account has no current password to prove, so only ask for
    # one when there is one.
    if had_password and not auth_module.verify_password(
            current_password, ctx.user.hashed_password):
        return back("/settings/security", error="wrong_password")
    if new_password != confirm_password:
        return back("/settings/security", error="password_mismatch")
    if len(new_password) < 8:
        return back("/settings/security", error="password_short")

    ctx.user.hashed_password = auth_module.get_password_hash(new_password)
    ctx.db.add(ctx.user)
    ctx.db.commit()
    return back("/settings/security",
                notice="password_changed" if had_password else "password_set")


@router.post("/security/sessions")
async def clear_sessions(ctx: deps.Context = Depends(deps.require_workspace)):
    """Invalidate every outstanding token, then re-issue one for this tab.

    Bumping token_version is what actually revokes them: the Redis denylist
    only knows about tokens it watched being logged out, so it cannot reach a
    session on another machine. Re-minting afterwards is why this is "other
    sessions" and not a self-inflicted logout.
    """
    ctx.user.token_version = (ctx.user.token_version or 0) + 1
    ctx.db.add(ctx.user)
    ctx.db.commit()

    response = back("/settings/security", notice="sessions_cleared")
    response.set_cookie(
        key="access_token",
        value=auth_module.create_access_token(
            ctx.user.username, ctx.user.id,
            expires_delta=timedelta(minutes=60),
            token_version=ctx.user.token_version,
            method=ctx.auth_method),
        httponly=True)
    return response


@router.get("/accounts", response_class=HTMLResponse)
async def accounts(request: Request,
                   ctx: deps.Context = Depends(deps.require_workspace)):
    return page(request, ctx, "settings/accounts.html", "Connected accounts",
                has_password=bool(ctx.user.hashed_password),
                google_enabled=auth_module.google_login_enabled())


@router.post("/accounts/google/disconnect")
async def disconnect_google(ctx: deps.Context = Depends(deps.require_workspace)):
    if not ctx.user.hashed_password:
        # Google is the only thing this account can sign in with; unlinking it
        # would strand them with no way back.
        return back("/settings/accounts", error="last_credential")
    ctx.user.google_sub = None
    ctx.db.add(ctx.user)
    ctx.db.commit()
    return back("/settings/accounts", notice="google_unlinked")


@router.get("/api", response_class=HTMLResponse)
async def api_keys(request: Request,
                   ctx: deps.Context = Depends(deps.require_workspace)):
    keys = ctx.db.query(models.ApiKey)\
        .filter(models.ApiKey.user_id == ctx.user.id)\
        .order_by(models.ApiKey.created_at.desc()).all()
    # The plaintext of a key just created is handed back through the session
    # cookie-free route below; nothing stores it.
    return page(request, ctx, "settings/api.html", "API", keys=keys,
                fresh_key=request.query_params.get("key"),
                base_url=str(request.base_url).rstrip("/"))


@router.post("/api/keys")
async def create_api_key(label: str = Form("API key"),
                         ctx: deps.Context = Depends(deps.require_workspace)):
    raw, prefix, key_hash = auth_module.generate_api_key()
    ctx.db.add(models.ApiKey(user_id=ctx.user.id, label=label.strip() or "API key",
                             prefix=prefix, key_hash=key_hash))
    ctx.db.commit()
    # Carried once, in the redirect, and never written down: the row holds only
    # the SHA-256. If the user misses it here, they make a new key.
    return back("/settings/api", key=raw)


@router.post("/api/keys/{key_id}/revoke")
async def revoke_api_key(key_id: int,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    ctx.db.query(models.ApiKey)\
        .filter(models.ApiKey.id == key_id)\
        .filter(models.ApiKey.user_id == ctx.user.id).delete()
    ctx.db.commit()
    return back("/settings/api", notice="key_revoked")


# Administration -------------------------------------------------------------


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_settings(request: Request,
                             ctx: deps.Context = Depends(deps.require_admin)):
    return page(request, ctx, "settings/workspace.html", "Workspace",
                is_owner=ctx.can("owner"),
                workspace_count=len(deps.workspaces_for(ctx.db, ctx.user.id)))


@router.post("/workspace")
async def save_workspace(name: str = Form(...), slug: str = Form(...),
                         ctx: deps.Context = Depends(deps.require_admin)):
    slug = provisioning.slugify(slug)
    clash = ctx.db.query(models.Workspace)\
        .filter(models.Workspace.slug == slug)\
        .filter(models.Workspace.id != ctx.workspace.id).first()
    if clash is not None:
        return back("/settings/workspace", error="slug_taken")

    ctx.workspace.name = name.strip() or ctx.workspace.name
    ctx.workspace.slug = slug
    ctx.db.add(ctx.workspace)
    ctx.db.commit()

    # The switcher cookie holds the slug, so a rename has to move it or the
    # next request falls back to some other workspace.
    response = back("/settings/workspace", notice="workspace_saved")
    response.set_cookie(key=deps.WORKSPACE_COOKIE, value=slug, httponly=True,
                        samesite="lax", max_age=60 * 60 * 24 * 365)
    return response


@router.post("/workspace/delete")
async def delete_workspace(confirm_name: str = Form(""),
                           ctx: deps.Context = Depends(deps.require_owner)):
    if len(deps.workspaces_for(ctx.db, ctx.user.id)) < 2:
        # Deleting the last one would leave the account with nowhere to work.
        return back("/settings/workspace", error="last_workspace")
    if confirm_name.strip() != ctx.workspace.name:
        return back("/settings/workspace", error="name_mismatch")

    for team_id in provisioning.delete_workspace(ctx.db, ctx.workspace):
        await redis_cache.invalidate_issues(team_id)

    remaining = deps.workspaces_for(ctx.db, ctx.user.id)
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    if remaining:
        response.set_cookie(key=deps.WORKSPACE_COOKIE, value=remaining[0].slug,
                            httponly=True, samesite="lax")
    return response


@router.get("/workspace/security", response_class=HTMLResponse)
async def workspace_security(request: Request,
                             ctx: deps.Context = Depends(deps.require_admin)):
    return page(request, ctx, "settings/workspace_security.html", "Security")


@router.post("/workspace/security")
async def save_workspace_security(
        allow_password_login: str = Form(""), allow_google_login: str = Form(""),
        allowed_email_domain: str = Form(""),
        ctx: deps.Context = Depends(deps.require_admin)):
    password_ok = bool(allow_password_login)
    google_ok = bool(allow_google_login)

    if not password_ok and not google_ok:
        return back("/settings/workspace/security", error="need_a_method")

    # Refuse the change that would shut the door on the admin making it. They
    # could otherwise disable their own method and have no way back in.
    would_be = models.Workspace(allow_password_login=password_ok,
                                allow_google_login=google_ok)
    if not deps.method_allowed(would_be, ctx.auth_method):
        return back("/settings/workspace/security", error="would_lock_out")

    ctx.workspace.allow_password_login = password_ok
    ctx.workspace.allow_google_login = google_ok
    ctx.workspace.allowed_email_domain = \
        allowed_email_domain.strip().lstrip("@").lower() or None
    ctx.db.add(ctx.workspace)
    ctx.db.commit()
    return back("/settings/workspace/security", notice="security_saved")


def _integration(ctx, provider):
    """The workspace's row for one provider, or None.

    Scoped to the workspace on the way in rather than checked afterwards, so a
    provider slug from the URL can never reach another workspace's row.
    """
    return ctx.db.query(models.Integration)        .filter(models.Integration.workspace_id == ctx.workspace.id)        .filter(models.Integration.provider == provider).first()


@router.get("/integrations", response_class=HTMLResponse)
async def integrations(request: Request,
                       ctx: deps.Context = Depends(deps.require_admin)):
    """The catalogue, with each workspace's connections folded in.

    The page is built from models.INTEGRATIONS rather than from the table, so
    a service this build offers but nobody has connected still has a card.
    """
    connected = {row.provider: row for row in ctx.db.query(models.Integration)
                 .filter(models.Integration.workspace_id == ctx.workspace.id)}
    groups = []
    for category in models.INTEGRATION_CATEGORIES:
        cards = [{"entry": entry, "link": connected.get(entry["slug"])}
                 for entry in models.INTEGRATIONS
                 if entry["category"] == category]
        if cards:
            groups.append((category, cards))
    return page(request, ctx, "settings/integrations.html", "Integrations",
                groups=groups, connected_count=len(connected),
                total_count=len(models.INTEGRATIONS),
                github_configured=github_integration.configured())


@router.get("/integrations/github/install")
async def install_github(ctx: deps.Context = Depends(deps.require_admin)):
    if not github_integration.configured():
        return back("/settings/integrations", error="github_unconfigured")
    state = jwt.encode(
        {"workspace_id": ctx.workspace.id, "user_id": ctx.user.id,
         "nonce": str(uuid4()),
         "exp": models.utcnow().timestamp() + 600},
        SECRET_KEY, algorithm="HS256")
    return RedirectResponse(github_integration.install_url(state),
                            status_code=status.HTTP_302_FOUND)


@router.get("/integrations/github/callback")
async def github_callback(installation_id: int = 0, state: str = ""):
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return back("/settings/integrations", error="github_failed")
    if not installation_id or payload.get("user_id") is None:
        return back("/settings/integrations", error="github_failed")
    try:
        if not await github_integration.verify_installation(installation_id):
            return back("/settings/integrations", error="github_failed")
    except Exception:
        return back("/settings/integrations", error="github_failed")

    db = SessionLocal()
    try:
        user = db.query(models.Users).filter(
            models.Users.id == payload["user_id"]).first()
        workspace = db.query(models.Workspace).filter(
            models.Workspace.id == payload["workspace_id"]).first()
        membership = db.query(models.WorkspaceMember).filter(
            models.WorkspaceMember.workspace_id == payload["workspace_id"],
            models.WorkspaceMember.user_id == payload["user_id"]).first()
        if not user or not workspace or not membership or not models.role_at_least(
                membership.role, "admin"):
            return back("/settings/integrations", error="github_failed")

        link = db.query(models.Integration).filter(
            models.Integration.workspace_id == workspace.id,
            models.Integration.provider == "github").first()
        if link is None:
            link = models.Integration(workspace_id=workspace.id,
                                      provider="github")
        link.github_installation_id = installation_id
        link.enabled = True
        link.connected_by_id = user.id
        link.connected_at = models.utcnow()
        db.add(link)
        db.commit()
    finally:
        db.close()
    return back("/settings/integrations", notice="github_connected")


@router.post("/integrations/{provider}/connect")
async def connect_integration(provider: str, target: str = Form(""),
                              ctx: deps.Context = Depends(deps.require_admin)):
    """Connect a service, or repoint one that is already connected.

    One handler for both because the form is the same either way, and a
    separate edit route would differ only in whether the row existed.
    """
    if provider not in models.INTEGRATIONS_BY_SLUG:
        return back("/settings/integrations", error="unknown_integration")
    target = target.strip()
    if not target:
        return back("/settings/integrations", error="target_required")

    link = _integration(ctx, provider)
    if provider == "github":
        if link is None or not link.github_installation_id:
            return back("/settings/integrations", error="github_failed")
        try:
            repository = await github_integration.get_repository(
                link.github_installation_id, target)
            target = repository["full_name"]
        except Exception:
            return back("/settings/integrations", error="github_repo_invalid")
    existed = link is not None
    if link is None:
        link = models.Integration(workspace_id=ctx.workspace.id,
                                  provider=provider)
    link.target = target
    link.enabled = True
    link.connected_by_id = ctx.user.id
    link.connected_at = models.utcnow()
    ctx.db.add(link)
    ctx.db.commit()
    return back("/settings/integrations",
                notice="integration_updated" if existed
                       else "integration_connected")


@router.post("/integrations/{provider}/toggle")
async def toggle_integration(provider: str,
                             ctx: deps.Context = Depends(deps.require_admin)):
    """Pause or resume, keeping the target.

    Disconnecting would drop the channel or repository someone had to go and
    look up, which is the wrong cost for turning something off for a week.
    """
    link = _integration(ctx, provider)
    if link is None:
        return back("/settings/integrations", error="unknown_integration")
    link.enabled = not link.enabled
    ctx.db.add(link)
    ctx.db.commit()
    return back("/settings/integrations",
                notice="integration_resumed" if link.enabled
                       else "integration_paused")


@router.post("/integrations/{provider}/disconnect")
async def disconnect_integration(provider: str,
                                 ctx: deps.Context = Depends(deps.require_admin)):
    ctx.db.query(models.Integration)        .filter(models.Integration.workspace_id == ctx.workspace.id)        .filter(models.Integration.provider == provider).delete()
    ctx.db.commit()
    return back("/settings/integrations", notice="integration_disconnected")


@router.get("/teams", response_class=HTMLResponse)
async def teams(request: Request,
                ctx: deps.Context = Depends(deps.require_admin)):
    rows = ctx.db.query(models.Team)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .order_by(models.Team.name).all()
    counts = {team.id: ctx.db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team.id).count() for team in rows}
    issues = {team.id: ctx.db.query(models.Todos).filter(
        models.Todos.team_id == team.id).count() for team in rows}
    return page(request, ctx, "settings/teams.html", "Teams",
                team_rows=rows, member_counts=counts, issue_counts=issues,
                palette=models.AVATAR_COLORS)


@router.post("/teams")
async def create_team(name: str = Form(...), key: str = Form(""),
                      color: str = Form(provisioning.DEFAULT_TEAM_COLOR),
                      ctx: deps.Context = Depends(deps.require_admin)):
    team = provisioning.create_team(
        ctx.db, ctx.workspace, name.strip() or "Team",
        key=key or name, color=color, members=[ctx.user])
    ctx.db.commit()
    return back(f"/settings/teams/{team.key}", notice="team_created")


def team_or_none(ctx, team_key):
    return ctx.db.query(models.Team)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.Team.key == (team_key or "").upper()).first()


@router.get("/teams/{team_key}", response_class=HTMLResponse)
async def team_detail(request: Request, team_key: str,
                      ctx: deps.Context = Depends(deps.require_admin)):
    team = team_or_none(ctx, team_key)
    if team is None:
        return back("/settings/teams")

    member_ids = {row.user_id for row in ctx.db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team.id).all()}
    workspace_people = ctx.db.query(models.Users)\
        .join(models.WorkspaceMember,
              models.WorkspaceMember.user_id == models.Users.id)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .order_by(models.Users.username).all()

    return page(request, ctx, "settings/team_detail.html", team.name,
                team=team, member_ids=member_ids, people=workspace_people,
                issue_count=ctx.db.query(models.Todos).filter(
                    models.Todos.team_id == team.id).count(),
                team_total=ctx.db.query(models.Team).filter(
                    models.Team.workspace_id == ctx.workspace.id).count(),
                palette=models.AVATAR_COLORS)


@router.post("/teams/{team_key}")
async def save_team(team_key: str, name: str = Form(...), key: str = Form(...),
                    color: str = Form(provisioning.DEFAULT_TEAM_COLOR),
                    description: str = Form(""),
                    ctx: deps.Context = Depends(deps.require_admin)):
    team = team_or_none(ctx, team_key)
    if team is None:
        return back("/settings/teams")

    new_key = provisioning.teamify(key, fallback=team.key)
    clash = ctx.db.query(models.Team)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.Team.key == new_key)\
        .filter(models.Team.id != team.id).first()
    if clash is not None:
        return back(f"/settings/teams/{team.key}", error="key_taken")

    team.name = name.strip() or team.name
    team.key = new_key  # every identifier in this team changes with it
    team.color = color
    team.description = description.strip() or None  # shown on the team's Home
    ctx.db.add(team)
    ctx.db.commit()
    return back(f"/settings/teams/{team.key}", notice="team_saved")


@router.post("/teams/{team_key}/members")
async def toggle_team_member(team_key: str, user_id: int = Form(...),
                             action: str = Form("add"),
                             ctx: deps.Context = Depends(deps.require_admin)):
    team = team_or_none(ctx, team_key)
    if team is None:
        return back("/settings/teams")

    # Only people already in the workspace, so a team cannot be used as a side
    # door into it.
    in_workspace = ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .filter(models.WorkspaceMember.user_id == user_id).first()
    if in_workspace is None:
        return back(f"/settings/teams/{team.key}")

    existing = ctx.db.query(models.TeamMember)\
        .filter(models.TeamMember.team_id == team.id)\
        .filter(models.TeamMember.user_id == user_id).first()

    if action == "remove":
        if existing:
            ctx.db.delete(existing)
            ctx.db.commit()
        return back(f"/settings/teams/{team.key}", notice="member_removed")

    if existing is None:
        ctx.db.add(models.TeamMember(team_id=team.id, user_id=user_id))
        ctx.db.commit()
    return back(f"/settings/teams/{team.key}", notice="member_added")


@router.post("/teams/{team_key}/delete")
async def remove_team(team_key: str,
                      ctx: deps.Context = Depends(deps.require_admin)):
    team = team_or_none(ctx, team_key)
    if team is None:
        return back("/settings/teams")

    total = ctx.db.query(models.Team).filter(
        models.Team.workspace_id == ctx.workspace.id).count()
    if total < 2:
        return back(f"/settings/teams/{team.key}", error="last_team")

    issues = ctx.db.query(models.Todos).filter(
        models.Todos.team_id == team.id).count()
    if issues:
        # Deleting would take the issues with it. Made explicit rather than
        # silent, because an issue is the thing people actually care about.
        return back(f"/settings/teams/{team.key}", error="team_has_issues")

    for team_id in provisioning.delete_team(ctx.db, team):
        await redis_cache.invalidate_issues(team_id)
    return back("/settings/teams", notice="team_deleted")


@router.get("/members", response_class=HTMLResponse)
async def members(request: Request,
                  ctx: deps.Context = Depends(deps.require_admin)):
    rows = ctx.db.query(models.WorkspaceMember, models.Users)\
        .join(models.Users, models.Users.id == models.WorkspaceMember.user_id)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .order_by(models.Users.username).all()
    invites = ctx.db.query(models.Invite)\
        .filter(models.Invite.workspace_id == ctx.workspace.id)\
        .filter(models.Invite.status == "pending")\
        .order_by(models.Invite.created_at.desc()).all()
    return page(request, ctx, "settings/members.html", "Members",
                member_rows=rows, invites=invites, roles=models.ROLES,
                base_url=str(request.base_url).rstrip("/"))


def owner_count(ctx):
    return ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .filter(models.WorkspaceMember.role == "owner").count()


@router.post("/members/invite")
async def invite_member(email: str = Form(...), role: str = Form("member"),
                        ctx: deps.Context = Depends(deps.require_admin)):
    email = email.strip().lower()
    if not provisioning.domain_allowed(ctx.workspace, email):
        return back("/settings/members", error="bad_domain")

    already = ctx.db.query(models.WorkspaceMember)\
        .join(models.Users, models.Users.id == models.WorkspaceMember.user_id)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .filter(models.Users.email == email).first()
    if already is not None:
        return back("/settings/members", error="already_member")

    provisioning.create_invite(ctx.db, ctx.workspace, ctx.user, email, role)
    return back("/settings/members", notice="invite_created")


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(invite_id: int,
                        ctx: deps.Context = Depends(deps.require_admin)):
    invite = ctx.db.query(models.Invite)\
        .filter(models.Invite.id == invite_id)\
        .filter(models.Invite.workspace_id == ctx.workspace.id).first()
    if invite is not None:
        invite.status = "revoked"
        ctx.db.add(invite)
        ctx.db.commit()
    return back("/settings/members", notice="invite_revoked")


@router.post("/members/{user_id}/role")
async def change_role(user_id: int, role: str = Form(...),
                      ctx: deps.Context = Depends(deps.require_admin)):
    if user_id == ctx.user.id:
        return back("/settings/members", error="not_yourself")
    if role not in models.ROLES:
        return back("/settings/members")

    membership = ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .filter(models.WorkspaceMember.user_id == user_id).first()
    if membership is None:
        return back("/settings/members")
    if membership.role == "owner" and role != "owner" and owner_count(ctx) < 2:
        return back("/settings/members", error="last_owner")

    membership.role = role
    ctx.db.add(membership)
    ctx.db.commit()
    return back("/settings/members", notice="role_changed")


@router.post("/members/{user_id}/remove")
async def remove_member(user_id: int,
                        ctx: deps.Context = Depends(deps.require_admin)):
    if user_id == ctx.user.id:
        return back("/settings/members", error="not_yourself")

    membership = ctx.db.query(models.WorkspaceMember)\
        .filter(models.WorkspaceMember.workspace_id == ctx.workspace.id)\
        .filter(models.WorkspaceMember.user_id == user_id).first()
    if membership is None:
        return back("/settings/members")
    if membership.role == "owner" and owner_count(ctx) < 2:
        return back("/settings/members", error="last_owner")

    # Team memberships go too, or they would be left pointing into a workspace
    # the user can no longer open.
    team_ids = [team.id for team in ctx.db.query(models.Team).filter(
        models.Team.workspace_id == ctx.workspace.id).all()]
    if team_ids:
        ctx.db.query(models.TeamMember)\
            .filter(models.TeamMember.team_id.in_(team_ids))\
            .filter(models.TeamMember.user_id == user_id)\
            .delete(synchronize_session=False)
    ctx.db.delete(membership)
    ctx.db.commit()
    return back("/settings/members", notice="member_removed_ws")
