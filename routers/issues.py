"""Issues: the team list, the detail view, and the forms behind them.

URLs are built from what a thing is called rather than from its row id, so
/issue/TODO-3 is the same string you would paste into a commit message. The id
still exists, it just is not the address.

Replaces the page routes that were in routers/todos.py, which now only keeps
the old paths alive as redirects.
"""
import re
import sys

sys.path.append("..")

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status as http

import cycle_math
import deps
import models
import provisioning
import redis_cache
import summary
from templating import templates

router = APIRouter(tags=["issues"])

# TODO-3, ENG-142. Team keys are upper case and at most TEAM_KEY_MAX long;
# matching case-insensitively means a typed-in lowercase URL still resolves.
IDENTIFIER = re.compile(r"^([A-Za-z0-9]{1,%d})-(\d+)$" % provisioning.TEAM_KEY_MAX)


def team_or_none(ctx, team_key):
    """A team in the active workspace that the user belongs to."""
    return deps.team_by_key(ctx.db, ctx.user.id, ctx.workspace.id, team_key)


def issue_or_none(ctx, identifier):
    """Resolve TODO-3 to a row the user is entitled to see."""
    match = IDENTIFIER.match(identifier or "")
    if not match:
        return None
    key, number = match.group(1).upper(), int(match.group(2))
    return ctx.db.query(models.Todos)\
        .join(models.Team, models.Team.id == models.Todos.team_id)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.Team.key == key)\
        .filter(models.Todos.number == number)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.TeamMember.user_id == ctx.user.id)\
        .first()


def users_by_id(db, ids):
    """One query for every assignee on the page, rather than one per row."""
    wanted = {value for value in ids if value}
    if not wanted:
        return {}
    rows = db.query(models.Users).filter(models.Users.id.in_(wanted)).all()
    return {row.id: row for row in rows}


def group_by_status(issues):
    """Issues bucketed by status, in the order the list shows them.

    Empty statuses are dropped: a "Canceled 0" header is noise on a list that
    has never had one.
    """
    buckets = {value: [] for value in models.STATUSES}
    for issue in issues:
        buckets.setdefault(issue.status or "todo", []).append(issue)
    for bucket in buckets.values():
        # Highest priority first, then oldest first, so the order is stable
        # between renders rather than following whatever the cache held.
        bucket.sort(key=lambda issue: (issue.priority or 99, issue.number or 0))
    return [(value, buckets[value]) for value in models.STATUSES
            if buckets.get(value)]


async def load_issues(ctx, team):
    issues = await redis_cache.get_cached_issues(team.id)
    if issues is None:
        issues = ctx.db.query(models.Todos)\
            .filter(models.Todos.team_id == team.id)\
            .order_by(models.Todos.number).all()
        await redis_cache.set_cached_issues(team.id, issues)
    return issues


def issue_url(issue, team):
    return f"/issue/{team.key}-{issue.number}"


def list_url(team):
    return f"/team/{team.key}/issues"


def home_url(team):
    return f"/team/{team.key}/home"


@router.get("/", include_in_schema=False)
async def home(ctx: deps.Context = Depends(deps.require_workspace)):
    """Land on a team's list rather than on a page of its own.

    Lives here rather than in main.py because picking the team needs the
    request context, and main.py has no business knowing how that is done.
    """
    team = deps.default_team(ctx.db, ctx.user.id, ctx.workspace.id)
    if team is None:
        raise deps.Forbidden("You are not on a team in this workspace")
    return RedirectResponse(url=home_url(team), status_code=http.HTTP_302_FOUND)


@router.get("/team/{team_key}/issues", response_class=HTMLResponse)
async def team_issues(request: Request, team_key: str,
                      ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    issues = await load_issues(ctx, team)
    return templates.TemplateResponse(request, "issues/list.html", deps.shell(
        ctx,
        active_team=team,
        active_view="issues",
        groups=group_by_status(issues),
        total=len(issues),
        assignees=users_by_id(ctx.db, (issue.assignee_id for issue in issues)),
    ))


@router.get("/team/{team_key}/home", response_class=HTMLResponse)
async def team_home(request: Request, team_key: str,
                    ctx: deps.Context = Depends(deps.require_workspace)):
    """The team's landing page: who they are, plus how they are doing.

    The reference puts a description, a member list and a set of shortcuts
    here. This app has no documents to link to, so the space below that header
    carries the charts instead of standing empty -- which is also where the
    summary went when the top-right tabs were removed.
    """
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    issues = await load_issues(ctx, team)
    members = ctx.db.query(models.Users)\
        .join(models.TeamMember, models.TeamMember.user_id == models.Users.id)\
        .filter(models.TeamMember.team_id == team.id)\
        .order_by(models.Users.username).all()

    return templates.TemplateResponse(request, "issues/home.html", deps.shell(
        ctx, active_team=team, active_view="home", team_members=members,
        **summary.build(ctx.db, team, issues)))


@router.get("/team/{team_key}/summary", include_in_schema=False)
async def team_summary(team_key: str):
    # The summary stopped being its own page when it moved into Home.
    return RedirectResponse(url=f"/team/{team_key}/home",
                            status_code=http.HTTP_308_PERMANENT_REDIRECT)


@router.get("/my-issues", response_class=HTMLResponse)
async def my_issues(request: Request,
                    ctx: deps.Context = Depends(deps.require_workspace)):
    """Everything assigned to me, across every team in this workspace.

    Not team-scoped, so it reads straight from the database rather than
    through the per-team cache -- there is no single key that would hold it.
    """
    rows = ctx.db.query(models.Todos)\
        .join(models.Team, models.Team.id == models.Todos.team_id)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.TeamMember.user_id == ctx.user.id)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.Todos.assignee_id == ctx.user.id)\
        .order_by(models.Todos.updated_at.desc()).all()

    teams_by_id = {team.id: team for team in
                   deps.teams_for(ctx.db, ctx.user.id, ctx.workspace.id)}

    return templates.TemplateResponse(request, "issues/my_issues.html", deps.shell(
        ctx, active_view="my-issues", groups=group_by_status(rows),
        teams_by_id=teams_by_id, total=len(rows),
        assignees={ctx.user.id: ctx.user}))


@router.get("/team/{team_key}/new", response_class=HTMLResponse)
async def new_issue_form(request: Request, team_key: str,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")
    return templates.TemplateResponse(
        request, "issues/new.html", deps.shell(ctx, active_team=team))


@router.post("/team/{team_key}/new")
async def create_issue(team_key: str, title: str = Form(...),
                       description: str = Form(""), priority: int = Form(3),
                       issue_status: str = Form("todo"),
                       ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    issue = models.Todos(
        title=title.strip(),
        description=description.strip(),
        priority=priority,
        owner_id=ctx.user.id,
        assignee_id=ctx.user.id,
        team_id=team.id,
        number=provisioning.next_issue_number(ctx.db, team),
    )
    models.set_status(issue, issue_status if issue_status in models.STATUSES
                      else "todo")
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(team.id)
    return RedirectResponse(url=issue_url(issue, team),
                            status_code=http.HTTP_302_FOUND)


@router.get("/issue/{identifier}", response_class=HTMLResponse)
async def issue_detail(request: Request, identifier: str,
                       ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    people = users_by_id(ctx.db, (issue.assignee_id, issue.owner_id))
    return templates.TemplateResponse(request, "issues/detail.html", deps.shell(
        ctx,
        active_team=issue.team,
        active_view="issues",
        issue=issue,
        assignee=people.get(issue.assignee_id),
        creator=people.get(issue.owner_id),
        # For the Project picker: only this team's, since a project belongs to
        # one team and so does the issue.
        team_projects=ctx.db.query(models.Project)
            .filter(models.Project.team_id == issue.team_id)
            .order_by(models.Project.name).all(),
        # For the Cycle picker. Closed cycles are left out: scheduling work
        # into one that has already ended would make its burn-up disagree with
        # what actually happened.
        open_cycles=open_cycles_for(ctx.db, issue.team),
        github_commits=ctx.db.query(models.GitHubCommit).filter(
            models.GitHubCommit.issue_id == issue.id).order_by(
                models.GitHubCommit.committed_at.desc(),
                models.GitHubCommit.id.desc()).all(),
    ))


def open_cycles_for(db, team):
    """Current and later cycles, each with the state to label it by."""
    series = cycle_math.ensure(db, team)
    state_by_id = cycle_math.states(series)
    return [{"cycle": cycle, "state": state_by_id[cycle.id]}
            for cycle in series if state_by_id[cycle.id] != "completed"]


@router.post("/issue/{identifier}/project")
async def change_project(identifier: str, project_id: str = Form(""),
                         ctx: deps.Context = Depends(deps.require_workspace)):
    """Move an issue under a feature, or out from under one.

    An empty project_id means "no project" -- the picker's first entry -- so
    detaching goes through the same route as attaching.
    """
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    chosen = None
    if project_id.isdigit():
        chosen = ctx.db.query(models.Project)\
            .filter(models.Project.id == int(project_id))\
            .filter(models.Project.team_id == issue.team_id).first()
        if chosen is None:
            # A project from another team would put an issue under a feature
            # its own team cannot see.
            raise deps.Forbidden("That project is not in this issue's team")

    issue.project_id = chosen.id if chosen else None
    issue.updated_at = models.utcnow()
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(issue.team_id)
    return RedirectResponse(url=f"/issue/{identifier.upper()}",
                            status_code=http.HTTP_303_SEE_OTHER)


@router.get("/issue/{identifier}/edit", response_class=HTMLResponse)
async def edit_issue_form(request: Request, identifier: str,
                          ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "issues/edit.html", deps.shell(
        ctx, active_team=issue.team, issue=issue))


@router.post("/issue/{identifier}/edit")
async def edit_issue(identifier: str, title: str = Form(...),
                     description: str = Form(""), priority: int = Form(3),
                     ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    issue.title = title.strip()
    issue.description = description.strip()
    issue.priority = priority
    issue.updated_at = models.utcnow()
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(issue.team_id)
    return RedirectResponse(url=f"/issue/{identifier.upper()}",
                            status_code=http.HTTP_302_FOUND)


@router.post("/issue/{identifier}/status")
async def change_status(request: Request, identifier: str,
                        issue_status: str = Form(...),
                        ctx: deps.Context = Depends(deps.require_workspace)):
    """Change one issue's status.

    POST because it writes, and because the list renders one of these per row
    -- as links they would all be prefetchable.
    """
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)
    if issue_status not in models.STATUSES:
        raise deps.Forbidden(f"{issue_status} is not a status")

    models.set_status(issue, issue_status)
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(issue.team_id)

    # Back where the change was made: the list if it came from a row, the
    # detail view if it came from there.
    referer = request.headers.get("referer") or ""
    target = f"/issue/{identifier.upper()}"
    if "/team/" in referer:
        target = list_url(issue.team)
    return RedirectResponse(url=target, status_code=http.HTTP_302_FOUND)


@router.post("/issue/{identifier}/priority")
async def change_priority(identifier: str, priority: int = Form(...),
                          ctx: deps.Context = Depends(deps.require_workspace)):
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    issue.priority = min(max(priority, 1), 5)
    issue.updated_at = models.utcnow()
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(issue.team_id)
    return RedirectResponse(url=f"/issue/{identifier.upper()}",
                            status_code=http.HTTP_302_FOUND)


@router.post("/issue/{identifier}/delete")
async def delete_issue(identifier: str,
                       ctx: deps.Context = Depends(deps.require_workspace)):
    """POST, not GET: the old /todos/delete/{id} link was one crawler away
    from clearing someone's list."""
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    team = issue.team
    ctx.db.delete(issue)
    ctx.db.commit()
    # issue_counter is deliberately not rolled back: reusing a deleted issue's
    # number would make TODO-3 mean two different things over time.
    await redis_cache.invalidate_issues(team.id)
    return RedirectResponse(url=list_url(team), status_code=http.HTTP_302_FOUND)
