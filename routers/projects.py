"""Projects -- features, in the review's words: one deliverable made of
several issues, and the parent half of the issue hierarchy.

Scoped to a team, so a project's issues share one identifier prefix and one
cycle calendar. Deleting a project releases its issues rather than taking them
with it; see the note on Project.issues in models.py.

Imports two pure helpers from routers/issues.py (grouping and the assignee
lookup). The dependency only goes this way -- issues.py must not import from
here, or the two will not load.
"""
import sys

sys.path.append("..")

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status as http

import deps
import models
import redis_cache
import summary
from routers.issues import group_by_status, team_or_none, users_by_id
from templating import templates

router = APIRouter(tags=["projects"])


def project_or_none(ctx, project_id):
    """A project the user can reach: in a team they are on, in the workspace
    they are looking at."""
    return ctx.db.query(models.Project)\
        .join(models.Team, models.Team.id == models.Project.team_id)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.Project.id == project_id)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.TeamMember.user_id == ctx.user.id)\
        .first()


def parse_date(value):
    """A yyyy-mm-dd from a date input, or None. Never raises: an unparseable
    value means "not set" rather than a 500 on a typo."""
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def team_members(db, team):
    return db.query(models.Users)\
        .join(models.TeamMember, models.TeamMember.user_id == models.Users.id)\
        .filter(models.TeamMember.team_id == team.id)\
        .order_by(models.Users.username).all()


def projects_url(team):
    return f"/team/{team.key}/projects"


@router.get("/team/{team_key}/projects", response_class=HTMLResponse)
async def team_projects(request: Request, team_key: str,
                        ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    rows = summary.project_rows(ctx.db, team)
    leads = users_by_id(ctx.db, (row["project"].lead_id for row in rows))
    return templates.TemplateResponse(request, "projects/list.html", deps.shell(
        ctx, active_team=team, active_view="projects", rows=rows, leads=leads,
        today=models.utcnow().date()))


@router.get("/team/{team_key}/projects/new", response_class=HTMLResponse)
async def new_project_form(request: Request, team_key: str,
                           ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")
    return templates.TemplateResponse(request, "projects/form.html", deps.shell(
        ctx, active_team=team, active_view="projects", project=None,
        people=team_members(ctx.db, team)))


@router.post("/team/{team_key}/projects/new")
async def create_project(team_key: str, name: str = Form(...),
                         description: str = Form(""),
                         project_status: str = Form("planned"),
                         lead_id: str = Form(""), target_date: str = Form(""),
                         ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    project = models.Project(
        team_id=team.id,
        name=name.strip() or "Untitled feature",
        description=description.strip() or None,
        status=(project_status if project_status in models.PROJECT_STATUSES
                else "planned"),
        lead_id=int(lead_id) if lead_id.isdigit() else None,
        target_date=parse_date(target_date),
    )
    ctx.db.add(project)
    ctx.db.commit()
    ctx.db.refresh(project)
    return RedirectResponse(url=f"/project/{project.id}",
                            status_code=http.HTTP_302_FOUND)


@router.get("/project/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    project = project_or_none(ctx, project_id)
    if project is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    issues = ctx.db.query(models.Todos)\
        .filter(models.Todos.project_id == project.id)\
        .order_by(models.Todos.number).all()
    done = sum(1 for issue in issues if (issue.status or "todo") == "done")

    return templates.TemplateResponse(request, "projects/detail.html", deps.shell(
        ctx,
        active_team=project.team,
        active_view="projects",
        project=project,
        groups=group_by_status(issues),
        assignees=users_by_id(ctx.db, (issue.assignee_id for issue in issues)),
        lead=ctx.db.get(models.Users, project.lead_id) if project.lead_id else None,
        total=len(issues),
        done=done,
        percent=round(done * 100 / len(issues)) if issues else 0,
    ))


@router.get("/project/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_form(request: Request, project_id: int,
                            ctx: deps.Context = Depends(deps.require_workspace)):
    project = project_or_none(ctx, project_id)
    if project is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "projects/form.html", deps.shell(
        ctx, active_team=project.team, active_view="projects", project=project,
        people=team_members(ctx.db, project.team)))


@router.post("/project/{project_id}/edit")
async def edit_project(project_id: int, name: str = Form(...),
                       description: str = Form(""),
                       project_status: str = Form("planned"),
                       lead_id: str = Form(""), target_date: str = Form(""),
                       ctx: deps.Context = Depends(deps.require_workspace)):
    project = project_or_none(ctx, project_id)
    if project is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    project.name = name.strip() or project.name
    project.description = description.strip() or None
    if project_status in models.PROJECT_STATUSES:
        project.status = project_status
    project.lead_id = int(lead_id) if lead_id.isdigit() else None
    project.target_date = parse_date(target_date)
    project.updated_at = models.utcnow()
    ctx.db.add(project)
    ctx.db.commit()
    return RedirectResponse(url=f"/project/{project_id}",
                            status_code=http.HTTP_303_SEE_OTHER)


@router.post("/project/{project_id}/status")
async def change_project_status(project_id: int,
                                project_status: str = Form(...),
                                ctx: deps.Context = Depends(deps.require_workspace)):
    project = project_or_none(ctx, project_id)
    if project is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)
    if project_status not in models.PROJECT_STATUSES:
        raise deps.Forbidden(f"{project_status} is not a project status")

    project.status = project_status
    project.updated_at = models.utcnow()
    ctx.db.add(project)
    ctx.db.commit()
    return RedirectResponse(url=f"/project/{project_id}",
                            status_code=http.HTTP_303_SEE_OTHER)


@router.post("/project/{project_id}/delete")
async def delete_project(project_id: int,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    """Remove the container, keep the contents.

    The issues are released rather than deleted -- an issue is the unit people
    care about, and a feature being cancelled is not a reason to lose the work
    logged under it. They land back in the team's list with no project.
    """
    project = project_or_none(ctx, project_id)
    if project is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    team = project.team
    ctx.db.query(models.Todos)\
        .filter(models.Todos.project_id == project.id)\
        .update({models.Todos.project_id: None}, synchronize_session=False)
    ctx.db.delete(project)
    ctx.db.commit()
    # The released issues are cached under the team's key.
    await redis_cache.invalidate_issues(team.id)
    return RedirectResponse(url=projects_url(team),
                            status_code=http.HTTP_303_SEE_OTHER)
