"""JSON API consumed by the React application.

The original server-rendered routes remain available for backwards
compatibility.  New clients should use this versioned API instead of parsing
HTML pages.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

import deps
import models
import provisioning
import redis_cache
import cycle_math
import summary
from routers import auth as auth_module
from routers.issues import issue_or_none

router = APIRouter(prefix="/api", tags=["api"])


class IssueCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    issue_status: str = "todo"


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    issue_status: Optional[str] = None
    project_id: Optional[int] = None
    cycle_id: Optional[int] = None


class ProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    email: Optional[str] = None


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    key: Optional[str] = None
    color: str = models.AVATAR_COLORS[0]


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)


class SecurityUpdate(BaseModel):
    allow_password_login: bool = True
    allow_google_login: bool = True
    allowed_email_domain: Optional[str] = None


class PasswordUpdate(BaseModel):
    current_password: str = ""
    new_password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


class ApiKeyCreate(BaseModel):
    label: str = Field(default="API key", min_length=1, max_length=100)


class IntegrationUpdate(BaseModel):
    target: str = Field(min_length=1, max_length=300)


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    role: str = "member"


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    team_key: Optional[str] = None


class ProjectPayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    project_status: str = "planned"
    lead_id: Optional[int] = None
    target_date: Optional[str] = None


class RoleUpdate(BaseModel):
    role: str


def user_json(user):
    return {"id": user.id, "username": user.username,
            "email": user.email, "name": user.display_name}


def owner_count(ctx):
    return ctx.db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == ctx.workspace.id,
        models.WorkspaceMember.role == "owner").count()


def team_json(team):
    return {"id": team.id, "name": team.name, "key": team.key,
            "description": team.description, "color": team.color}


def set_workspace_cookie(response, slug):
    response.set_cookie(key=deps.WORKSPACE_COOKIE, value=slug,
                        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)


def issue_json(issue):
    return {
        "id": issue.id,
        "identifier": issue.identifier,
        "title": issue.title,
        "description": issue.description or "",
        "priority": issue.priority or 3,
        "status": issue.status or "todo",
        "complete": bool(issue.complete),
        "team_key": issue.team.key if issue.team else None,
        "assignee_id": issue.assignee_id,
        "project_id": issue.project_id,
        "cycle_id": issue.cycle_id,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
    }


@router.get("/me")
async def me(ctx: deps.Context = Depends(deps.require_workspace)):
    return {
        "user": user_json(ctx.user),
        "workspace": {"id": ctx.workspace.id, "name": ctx.workspace.name,
                       "slug": ctx.workspace.slug, "role": ctx.role},
        "workspaces": [{"id": workspace.id, "name": workspace.name,
                         "slug": workspace.slug}
                        for workspace in deps.workspaces_for(ctx.db, ctx.user.id)],
        "teams": [team_json(team) for team in
                  deps.teams_for(ctx.db, ctx.user.id, ctx.workspace.id)],
        "statuses": models.STATUSES,
    }


@router.post("/workspaces/switch/{slug}")
async def switch_workspace_api(slug: str, response: Response,
                               ctx: deps.Context = Depends(deps.require_workspace)):
    workspace = next((item for item in deps.workspaces_for(ctx.db, ctx.user.id)
                      if item.slug == slug), None)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Workspace is not yours")
    set_workspace_cookie(response, workspace.slug)
    return {"id": workspace.id, "name": workspace.name, "slug": workspace.slug}


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, response: Response,
                           who: dict = Depends(deps.identity),
                           db=Depends(deps.get_db)):
    workspace = provisioning.create_workspace(
        db, db.query(models.Users).filter(models.Users.id == who["id"]).first(),
        payload.name.strip(), team_key=payload.team_key or provisioning.DEFAULT_TEAM_KEY)
    set_workspace_cookie(response, workspace.slug)
    return {"id": workspace.id, "name": workspace.name, "slug": workspace.slug}


@router.get("/invites/{token}")
async def get_invite(token: str, who: dict = Depends(deps.identity),
                     db=Depends(deps.get_db)):
    invite = db.query(models.Invite).filter(
        models.Invite.token == token, models.Invite.status == "pending").first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    already = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == invite.workspace_id,
        models.WorkspaceMember.user_id == who["id"]).first() is not None
    return {"workspace": {"id": invite.workspace.id, "name": invite.workspace.name},
            "email": invite.email, "role": invite.role, "already_member": already}


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, response: Response,
                        who: dict = Depends(deps.identity),
                        db=Depends(deps.get_db)):
    invite = db.query(models.Invite).filter(
        models.Invite.token == token, models.Invite.status == "pending").first()
    if invite is None or (invite.expires_at and invite.expires_at < models.utcnow()):
        raise HTTPException(status_code=404, detail="Invite is invalid or expired")
    user = db.query(models.Users).filter(models.Users.id == who["id"]).first()
    if not provisioning.domain_allowed(invite.workspace, user.email or ""):
        raise HTTPException(status_code=403, detail="Your email is not allowed")
    existing = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == invite.workspace_id,
        models.WorkspaceMember.user_id == who["id"]).first()
    if existing is None:
        db.add(models.WorkspaceMember(workspace_id=invite.workspace_id,
                                      user_id=who["id"], role=invite.role))
    invite.status = "accepted"; db.add(invite); db.commit()
    set_workspace_cookie(response, invite.workspace.slug)
    return {"workspace": {"id": invite.workspace.id, "name": invite.workspace.name,
                           "slug": invite.workspace.slug}}


@router.get("/settings/profile")
async def profile(ctx: deps.Context = Depends(deps.require_workspace)):
    return user_json(ctx.user)


@router.patch("/settings/profile")
async def update_profile(payload: ProfileUpdate,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    ctx.user.first_name = payload.first_name.strip()
    ctx.user.last_name = payload.last_name.strip()
    if payload.email is not None:
        ctx.user.email = payload.email.strip() or None
    ctx.db.add(ctx.user)
    ctx.db.commit()
    ctx.db.refresh(ctx.user)
    return user_json(ctx.user)


@router.get("/settings/workspace")
async def workspace_settings(ctx: deps.Context = Depends(deps.require_workspace)):
    return {"id": ctx.workspace.id, "name": ctx.workspace.name,
            "slug": ctx.workspace.slug, "role": ctx.role,
            "is_owner": ctx.can("owner")}


@router.get("/settings/security")
async def security_settings(ctx: deps.Context = Depends(deps.require_workspace)):
    return {"allow_password_login": ctx.workspace.allow_password_login,
            "allow_google_login": ctx.workspace.allow_google_login,
            "allowed_email_domain": ctx.workspace.allowed_email_domain,
            "has_password": bool(ctx.user.hashed_password)}


@router.patch("/settings/security")
async def update_security(payload: SecurityUpdate,
                          ctx: deps.Context = Depends(deps.require_admin)):
    if not payload.allow_password_login and not payload.allow_google_login:
        raise HTTPException(status_code=422, detail="At least one sign-in method must stay enabled")
    if not deps.method_allowed(models.Workspace(
            allow_password_login=payload.allow_password_login,
            allow_google_login=payload.allow_google_login), ctx.auth_method):
        raise HTTPException(status_code=422, detail="You cannot disable your current sign-in method")
    ctx.workspace.allow_password_login = payload.allow_password_login
    ctx.workspace.allow_google_login = payload.allow_google_login
    ctx.workspace.allowed_email_domain = (payload.allowed_email_domain or "").strip().lstrip("@").lower() or None
    ctx.db.add(ctx.workspace)
    ctx.db.commit()
    return await security_settings(ctx)


@router.post("/settings/security/password")
async def update_password(payload: PasswordUpdate,
                          ctx: deps.Context = Depends(deps.require_workspace)):
    if ctx.user.hashed_password and not auth_module.verify_password(
            payload.current_password, ctx.user.hashed_password):
        raise HTTPException(status_code=422, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match")
    ctx.user.hashed_password = auth_module.get_password_hash(payload.new_password)
    ctx.db.add(ctx.user); ctx.db.commit()
    return {"message": "Password updated"}


@router.post("/settings/security/sessions")
async def clear_sessions(response: Response,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    ctx.user.token_version = (ctx.user.token_version or 0) + 1
    ctx.db.add(ctx.user); ctx.db.commit()
    token = auth_module.create_access_token(
        ctx.user.username, ctx.user.id, expires_delta=timedelta(minutes=60),
        token_version=ctx.user.token_version, method=ctx.auth_method)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return {"message": "Other sessions cleared"}


@router.get("/settings/api-keys")
async def api_keys(ctx: deps.Context = Depends(deps.require_workspace)):
    keys = ctx.db.query(models.ApiKey).filter(
        models.ApiKey.user_id == ctx.user.id).order_by(
        models.ApiKey.created_at.desc()).all()
    return {"keys": [{"id": key.id, "label": key.label, "prefix": key.prefix,
                      "created_at": key.created_at.isoformat() if key.created_at else None,
                      "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None}
                     for key in keys]}


@router.post("/settings/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    raw, prefix, key_hash = auth_module.generate_api_key()
    ctx.db.add(models.ApiKey(user_id=ctx.user.id, label=payload.label.strip(),
                             prefix=prefix, key_hash=key_hash))
    ctx.db.commit()
    return {"key": raw, "label": payload.label.strip(), "prefix": prefix}


@router.delete("/settings/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: int,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    ctx.db.query(models.ApiKey).filter(models.ApiKey.id == key_id,
                                       models.ApiKey.user_id == ctx.user.id).delete()
    ctx.db.commit()


@router.get("/settings/accounts")
async def connected_accounts(ctx: deps.Context = Depends(deps.require_workspace)):
    return {"google_connected": bool(ctx.user.google_sub),
            "google_enabled": auth_module.google_login_enabled(),
            "email": ctx.user.email,
            "has_password": bool(ctx.user.hashed_password),
            "username": ctx.user.username}


@router.delete("/settings/accounts/google", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google(ctx: deps.Context = Depends(deps.require_workspace)):
    if not ctx.user.hashed_password:
        raise HTTPException(status_code=422, detail="Set a password before disconnecting Google")
    ctx.user.google_sub = None
    ctx.db.add(ctx.user); ctx.db.commit()


@router.get("/settings/integrations")
async def integrations(ctx: deps.Context = Depends(deps.require_admin)):
    connected = {row.provider: row for row in ctx.db.query(models.Integration).filter(
        models.Integration.workspace_id == ctx.workspace.id).all()}
    return {"integrations": [{**entry,
        "connected": entry["slug"] in connected,
        "enabled": connected[entry["slug"]].enabled if entry["slug"] in connected else False,
        "target": connected[entry["slug"]].target if entry["slug"] in connected else None}
        for entry in models.INTEGRATIONS]}


@router.post("/settings/integrations/{provider}")
async def connect_integration(provider: str, payload: IntegrationUpdate,
                              ctx: deps.Context = Depends(deps.require_admin)):
    if provider not in models.INTEGRATIONS_BY_SLUG:
        raise HTTPException(status_code=404, detail="Unknown integration")
    link = ctx.db.query(models.Integration).filter(
        models.Integration.workspace_id == ctx.workspace.id,
        models.Integration.provider == provider).first()
    if link is None:
        link = models.Integration(workspace_id=ctx.workspace.id, provider=provider)
    link.target = payload.target.strip(); link.enabled = True
    link.connected_by_id = ctx.user.id; link.connected_at = models.utcnow()
    ctx.db.add(link); ctx.db.commit()
    return {"provider": provider, "connected": True, "enabled": True,
            "target": link.target}


@router.patch("/settings/integrations/{provider}")
async def toggle_integration(provider: str,
                             ctx: deps.Context = Depends(deps.require_admin)):
    link = ctx.db.query(models.Integration).filter(
        models.Integration.workspace_id == ctx.workspace.id,
        models.Integration.provider == provider).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Integration is not connected")
    link.enabled = not link.enabled; ctx.db.add(link); ctx.db.commit()
    return {"provider": provider, "connected": True, "enabled": link.enabled,
            "target": link.target}


@router.delete("/settings/integrations/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(provider: str,
                                 ctx: deps.Context = Depends(deps.require_admin)):
    ctx.db.query(models.Integration).filter(
        models.Integration.workspace_id == ctx.workspace.id,
        models.Integration.provider == provider).delete()
    ctx.db.commit()


@router.patch("/settings/workspace")
async def update_workspace(payload: WorkspaceUpdate,
                           ctx: deps.Context = Depends(deps.require_admin)):
    slug = provisioning.slugify(payload.slug)
    clash = ctx.db.query(models.Workspace).filter(
        models.Workspace.slug == slug,
        models.Workspace.id != ctx.workspace.id).first()
    if clash is not None:
        raise HTTPException(status_code=409, detail="Workspace slug already exists")
    ctx.workspace.name = payload.name.strip() or ctx.workspace.name
    ctx.workspace.slug = slug
    ctx.db.add(ctx.workspace)
    ctx.db.commit()
    ctx.db.refresh(ctx.workspace)
    return {"id": ctx.workspace.id, "name": ctx.workspace.name,
            "slug": ctx.workspace.slug, "role": ctx.role,
            "is_owner": ctx.can("owner")}


@router.get("/settings/teams")
async def admin_teams(ctx: deps.Context = Depends(deps.require_admin)):
    teams = deps.teams_for(ctx.db, ctx.user.id, ctx.workspace.id)
    return {"teams": [{**team_json(team),
                       "members": len(team.members),
                       "issues": len(team.issues)} for team in teams]}


@router.post("/settings/teams", status_code=status.HTTP_201_CREATED)
async def admin_create_team(payload: TeamCreate,
                            ctx: deps.Context = Depends(deps.require_admin)):
    team = provisioning.create_team(ctx.db, ctx.workspace, payload.name.strip(),
                                    key=payload.key or payload.name,
                                    color=payload.color, members=[ctx.user])
    ctx.db.commit()
    return team_json(team)


@router.get("/settings/members")
async def admin_members(ctx: deps.Context = Depends(deps.require_admin)):
    rows = ctx.db.query(models.WorkspaceMember, models.Users).join(
        models.Users, models.Users.id == models.WorkspaceMember.user_id
    ).filter(models.WorkspaceMember.workspace_id == ctx.workspace.id).order_by(
        models.Users.username).all()
    invites = ctx.db.query(models.Invite).filter(
        models.Invite.workspace_id == ctx.workspace.id,
        models.Invite.status == "pending").order_by(
        models.Invite.created_at.desc()).all()
    return {"members": [{**user_json(user), "role": membership.role,
                         "is_current": user.id == ctx.user.id}
                        for membership, user in rows],
            "invites": [{"id": invite.id, "email": invite.email,
                         "role": invite.role, "token": invite.token}
                        for invite in invites]}


@router.post("/settings/members/invite", status_code=status.HTTP_201_CREATED)
async def admin_invite(payload: InviteCreate,
                       ctx: deps.Context = Depends(deps.require_admin)):
    email = payload.email.strip().lower()
    if payload.role not in models.ROLES:
        raise HTTPException(status_code=422, detail="Invalid role")
    if not provisioning.domain_allowed(ctx.workspace, email):
        raise HTTPException(status_code=422, detail="Email domain is not allowed")
    already = ctx.db.query(models.WorkspaceMember).join(models.Users).filter(
        models.WorkspaceMember.workspace_id == ctx.workspace.id,
        models.Users.email == email).first()
    if already is not None:
        raise HTTPException(status_code=409, detail="User is already a member")
    invite = provisioning.create_invite(ctx.db, ctx.workspace, ctx.user, email, payload.role)
    ctx.db.commit()
    return {"id": invite.id, "email": invite.email, "role": invite.role,
            "token": invite.token}


@router.delete("/settings/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_revoke_invite(invite_id: int,
                              ctx: deps.Context = Depends(deps.require_admin)):
    invite = ctx.db.query(models.Invite).filter(
        models.Invite.id == invite_id,
        models.Invite.workspace_id == ctx.workspace.id).first()
    if invite:
        invite.status = "revoked"; ctx.db.add(invite); ctx.db.commit()


@router.patch("/settings/members/{user_id}")
async def admin_change_role(user_id: int, payload: RoleUpdate,
                            ctx: deps.Context = Depends(deps.require_admin)):
    if user_id == ctx.user.id or payload.role not in models.ROLES:
        raise HTTPException(status_code=422, detail="Invalid member change")
    membership = ctx.db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == ctx.workspace.id,
        models.WorkspaceMember.user_id == user_id).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner" and payload.role != "owner" and owner_count(ctx) < 2:
        raise HTTPException(status_code=422, detail="Workspace needs an owner")
    membership.role = payload.role; ctx.db.add(membership); ctx.db.commit()
    return {"user_id": user_id, "role": membership.role}


@router.delete("/settings/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_remove_member(user_id: int,
                              ctx: deps.Context = Depends(deps.require_admin)):
    if user_id == ctx.user.id:
        raise HTTPException(status_code=422, detail="You cannot remove yourself")
    membership = ctx.db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == ctx.workspace.id,
        models.WorkspaceMember.user_id == user_id).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner" and owner_count(ctx) < 2:
        raise HTTPException(status_code=422, detail="Workspace needs an owner")
    team_ids = [team.id for team in ctx.db.query(models.Team).filter(
        models.Team.workspace_id == ctx.workspace.id).all()]
    if team_ids:
        ctx.db.query(models.TeamMember).filter(
            models.TeamMember.team_id.in_(team_ids),
            models.TeamMember.user_id == user_id).delete(synchronize_session=False)
    ctx.db.delete(membership); ctx.db.commit()


@router.get("/teams/{team_key}/issues")
async def list_team_issues(team_key: str,
                           ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    # API responses use ORM rows so the serializer can include relationships.
    # The HTML view may use the Redis cache, whose lightweight objects are
    # intentionally optimized for templates rather than API serialization.
    issues = ctx.db.query(models.Todos).filter(
        models.Todos.team_id == team.id
    ).order_by(models.Todos.number).all()
    return {"team": team_json(team), "issues": [issue_json(item) for item in issues]}


@router.get("/teams/{team_key}/home")
async def team_home_data(team_key: str,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    issues = ctx.db.query(models.Todos).filter(models.Todos.team_id == team.id).all()
    members = ctx.db.query(models.Users).join(
        models.TeamMember, models.TeamMember.user_id == models.Users.id
    ).filter(models.TeamMember.team_id == team.id).order_by(models.Users.username).all()
    data = summary.build(ctx.db, team, issues)
    return {"team": team_json(team), "members": [user_json(member) for member in members],
            "total": len(issues), "summary": data}


@router.get("/my-issues")
async def my_issues(ctx: deps.Context = Depends(deps.require_workspace)):
    issues = ctx.db.query(models.Todos).join(models.Team).join(
        models.TeamMember, models.TeamMember.team_id == models.Team.id).filter(
        models.TeamMember.user_id == ctx.user.id,
        models.Team.workspace_id == ctx.workspace.id,
        models.Todos.assignee_id == ctx.user.id).order_by(
        models.Todos.updated_at.desc()).all()
    return {"issues": [issue_json(issue) for issue in issues]}


@router.get("/teams/{team_key}/projects")
async def team_projects(team_key: str,
                        ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    projects = ctx.db.query(models.Project).filter(
        models.Project.team_id == team.id
    ).order_by(models.Project.updated_at.desc()).all()
    return {"team": team_json(team), "projects": [
        {"id": project.id, "name": project.name,
         "description": project.description or "", "status": project.status,
         "target_date": project.target_date.isoformat() if project.target_date else None,
         "total_issues": len(project.issues),
         "done_issues": sum(1 for issue in project.issues if issue.status == "done")}
        for project in projects
    ]}


@router.get("/issues/{identifier}")
async def get_issue(identifier: str,
                    ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue_json(issue)


@router.get("/projects/{project_id}")
async def get_project(project_id: int,
                      ctx: deps.Context = Depends(deps.require_workspace)):
    project = ctx.db.query(models.Project).join(models.Team).filter(
        models.Project.id == project_id,
        models.Team.workspace_id == ctx.workspace.id,
    ).first()
    if project is None or deps.team_by_key(ctx.db, ctx.user.id,
                                           ctx.workspace.id, project.team.key) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "name": project.name,
            "description": project.description or "", "status": project.status,
            "team": team_json(project.team),
            "issues": [issue_json(issue) for issue in project.issues]}


@router.post("/teams/{team_key}/projects", status_code=status.HTTP_201_CREATED)
async def create_project_api(team_key: str, payload: ProjectPayload,
                             ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    project = models.Project(team_id=team.id, name=payload.name.strip(),
                             description=payload.description.strip() or None,
                             status=payload.project_status if payload.project_status in models.PROJECT_STATUSES else "planned",
                             lead_id=payload.lead_id,
                             target_date=date.fromisoformat(payload.target_date) if payload.target_date else None)
    ctx.db.add(project); ctx.db.commit(); ctx.db.refresh(project)
    return {"id": project.id, "name": project.name,
            "description": project.description or "", "status": project.status}


@router.patch("/projects/{project_id}")
async def update_project_api(project_id: int, payload: ProjectPayload,
                             ctx: deps.Context = Depends(deps.require_workspace)):
    project = ctx.db.query(models.Project).join(models.Team).filter(
        models.Project.id == project_id,
        models.Team.workspace_id == ctx.workspace.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.name = payload.name.strip()
    project.description = payload.description.strip() or None
    if payload.project_status in models.PROJECT_STATUSES:
        project.status = payload.project_status
    project.lead_id = payload.lead_id
    project.target_date = date.fromisoformat(payload.target_date) if payload.target_date else None
    project.updated_at = models.utcnow()
    ctx.db.add(project); ctx.db.commit()
    return {"id": project.id, "name": project.name,
            "description": project.description or "", "status": project.status}


@router.get("/teams/{team_key}/cycles")
async def team_cycles(team_key: str,
                      ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    series = cycle_math.ensure(ctx.db, team)
    states = cycle_math.states(series)
    current = cycle_math.pick(series, "current")
    chart = None
    if current is not None:
        cycle_issues = ctx.db.query(models.Todos).filter(
            models.Todos.cycle_id == current.id).order_by(models.Todos.number).all()
        rows = cycle_math.burn_up(current, cycle_issues)
        chart = cycle_math.chart(current, rows) if rows else None
    return {"team": team_json(team), "cycles": [
        {"id": cycle.id, "number": cycle.number, "name": cycle.name,
         "starts_on": cycle.starts_on.isoformat(), "ends_on": cycle.ends_on.isoformat(),
         "state": states[cycle.id],
         "total_issues": len(cycle.issues),
         "done_issues": sum(1 for issue in cycle.issues if issue.status == "done")}
        for cycle in sorted(series, key=lambda item: item.number, reverse=True)
    ], "chart": chart}


@router.get("/teams/{team_key}/cycles/{state}")
async def cycle_detail(team_key: str, state: str,
                       ctx: deps.Context = Depends(deps.require_workspace)):
    if state not in ("current", "upcoming"):
        raise HTTPException(status_code=422, detail="Invalid cycle state")
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    series = cycle_math.ensure(ctx.db, team)
    selected = cycle_math.pick(series, state)
    issues = [] if selected is None else ctx.db.query(models.Todos).filter(
        models.Todos.cycle_id == selected.id).order_by(models.Todos.number).all()
    chart = None
    if selected is not None and state == "current":
        rows = cycle_math.burn_up(selected, issues)
        chart = cycle_math.chart(selected, rows) if rows else None
    return {"team": team_json(team), "state": state,
            "cycle": None if selected is None else {
                "id": selected.id, "name": selected.name,
                "starts_on": selected.starts_on.isoformat(),
                "ends_on": selected.ends_on.isoformat()},
            "issues": [issue_json(issue) for issue in issues],
            "chart": chart}


@router.post("/teams/{team_key}/issues", status_code=status.HTTP_201_CREATED)
async def create_team_issue(team_key: str, payload: IssueCreate,
                            ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    issue = models.Todos(
        title=payload.title.strip(), description=payload.description.strip(),
        priority=payload.priority, owner_id=ctx.user.id, assignee_id=ctx.user.id,
        team_id=team.id, number=provisioning.next_issue_number(ctx.db, team),
    )
    models.set_status(issue, payload.issue_status if payload.issue_status in models.STATUSES else "todo")
    ctx.db.add(issue)
    ctx.db.commit()
    ctx.db.refresh(issue)
    await redis_cache.invalidate_issues(team.id)
    return issue_json(issue)


@router.patch("/issues/{identifier}")
async def update_issue(identifier: str, payload: IssueUpdate,
                       ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if payload.title is not None:
        issue.title = payload.title.strip()
    if payload.description is not None:
        issue.description = payload.description.strip()
    if payload.priority is not None:
        issue.priority = payload.priority
    if payload.issue_status is not None:
        if payload.issue_status not in models.STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status")
        models.set_status(issue, payload.issue_status)
    if "project_id" in payload.model_fields_set:
        issue.project_id = payload.project_id
    if "cycle_id" in payload.model_fields_set:
        issue.cycle_id = payload.cycle_id
    issue.updated_at = models.utcnow()
    ctx.db.add(issue)
    ctx.db.commit()
    ctx.db.refresh(issue)
    await redis_cache.invalidate_issues(issue.team_id)
    return issue_json(issue)


@router.delete("/issues/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_issue(identifier: str,
                       ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    team_id = issue.team_id
    ctx.db.delete(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(team_id)

