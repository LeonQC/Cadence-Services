"""Cycles: a team's time boxes, and the burn-up for the one running now.

The rows are generated from the team's anchor and cycle length -- see
cycle_math.py, which is named that rather than cycles.py so it cannot be
confused with this module. Nothing is created by hand, and Current is never
empty.

Imports the same pure helpers from routers/issues.py that the projects router
does. The dependency only goes this way.
"""
import sys

sys.path.append("..")

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status as http

import cycle_math as cycle_maths
import deps
import models
import redis_cache
from routers.issues import (group_by_status, issue_or_none, team_or_none,
                            users_by_id)
from templating import templates

router = APIRouter(tags=["cycles"])


def issues_in(db, cycle):
    return db.query(models.Todos)\
        .filter(models.Todos.cycle_id == cycle.id)\
        .order_by(models.Todos.number).all()


@router.get("/team/{team_key}/cycles", response_class=HTMLResponse)
async def team_cycles(request: Request, team_key: str,
                      ctx: deps.Context = Depends(deps.require_workspace)):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    today = models.utcnow().date()
    all_cycles = cycle_maths.ensure(ctx.db, team, today)
    states = cycle_maths.states(all_cycles, today)
    scope, done = cycle_maths.tallies(ctx.db, all_cycles)
    current = cycle_maths.pick(all_cycles, "current", today)

    chart = None
    if current is not None:
        rows = cycle_maths.burn_up(current, issues_in(ctx.db, current), today)
        chart = cycle_maths.chart(current, rows)

    # Newest first, the way the reference stacks them: what is coming sits
    # above what has been.
    ordered = sorted(all_cycles, key=lambda c: c.number, reverse=True)

    return templates.TemplateResponse(request, "cycles/list.html", deps.shell(
        ctx, active_team=team, active_view="cycles", cycles=ordered,
        states=states, scope=scope, done=done, current=current, chart=chart,
        today=today))


async def _cycle_page(request, ctx, team_key, state):
    team = team_or_none(ctx, team_key)
    if team is None:
        raise deps.Forbidden("That team is not one of yours")

    today = models.utcnow().date()
    all_cycles = cycle_maths.ensure(ctx.db, team, today)
    cycle = cycle_maths.pick(all_cycles, state, today)

    issues = issues_in(ctx.db, cycle) if cycle else []
    done = sum(1 for issue in issues if (issue.status or "todo") == "done")

    return templates.TemplateResponse(request, "cycles/detail.html", deps.shell(
        ctx, active_team=team, active_view=f"cycles-{state}", cycle=cycle,
        state=state, groups=group_by_status(issues), total=len(issues),
        done=done,
        assignees=users_by_id(ctx.db, (issue.assignee_id for issue in issues)),
        today=today))


@router.get("/team/{team_key}/cycles/current", response_class=HTMLResponse)
async def current_cycle(request: Request, team_key: str,
                        ctx: deps.Context = Depends(deps.require_workspace)):
    return await _cycle_page(request, ctx, team_key, "current")


@router.get("/team/{team_key}/cycles/upcoming", response_class=HTMLResponse)
async def upcoming_cycle(request: Request, team_key: str,
                         ctx: deps.Context = Depends(deps.require_workspace)):
    return await _cycle_page(request, ctx, team_key, "upcoming")


@router.post("/issue/{identifier}/cycle")
async def change_cycle(identifier: str, cycle_id: str = Form(""),
                       ctx: deps.Context = Depends(deps.require_workspace)):
    """Schedule an issue into a cycle, or take it out of one.

    An empty cycle_id is the picker's first entry, so scheduling and
    unscheduling go through one route.
    """
    issue = issue_or_none(ctx, identifier)
    if issue is None:
        return RedirectResponse(url="/", status_code=http.HTTP_302_FOUND)

    chosen = None
    if cycle_id.isdigit():
        chosen = ctx.db.query(models.Cycle)\
            .filter(models.Cycle.id == int(cycle_id))\
            .filter(models.Cycle.team_id == issue.team_id).first()
        if chosen is None:
            # Another team's calendar. Refused rather than ignored, so a stale
            # form cannot silently put an issue in a cycle nobody can see.
            raise deps.Forbidden("That cycle is not in this issue's team")

    issue.cycle_id = chosen.id if chosen else None
    issue.updated_at = models.utcnow()
    ctx.db.add(issue)
    ctx.db.commit()
    await redis_cache.invalidate_issues(issue.team_id)
    return RedirectResponse(url=f"/issue/{identifier.upper()}",
                            status_code=http.HTTP_303_SEE_OTHER)
