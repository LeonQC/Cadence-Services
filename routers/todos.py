"""Compatibility redirects for the old /todos/* URLs.

Everything here used to be a page; the pages now live in routers/issues.py
under names built from the issue identifier. Bookmarks, the browser history of
anyone who has been using this, and the four RedirectResponse targets that
were scattered through routers/auth.py all still point at these paths, so they
resolve rather than 404.

The two state-changing GETs are deliberately not carried over as GETs. They
used to complete or delete an issue on a plain link, which meant any crawler
or link prefetcher could do it; they now land on the issue, where the same
actions exist as POSTs.
"""
import sys

sys.path.append("..")

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from starlette import status

import deps
import models
from routers.issues import issue_url

router = APIRouter(prefix="/todos", tags=["todos"], include_in_schema=False)


def _seen_other(url):
    # 303: these were POST targets too, and a 302 would have some clients
    # repeat the POST against the new URL.
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _issue_by_row_id(ctx, todo_id):
    return ctx.db.query(models.Todos)\
        .join(models.Team, models.Team.id == models.Todos.team_id)\
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)\
        .filter(models.Todos.id == todo_id)\
        .filter(models.Team.workspace_id == ctx.workspace.id)\
        .filter(models.TeamMember.user_id == ctx.user.id)\
        .first()


@router.api_route("/", methods=["GET", "POST"])
@router.api_route("", methods=["GET", "POST"])
async def old_list():
    return _seen_other("/")


@router.api_route("/add-todo", methods=["GET", "POST"])
async def old_add(ctx: deps.Context = Depends(deps.require_workspace)):
    team = deps.default_team(ctx.db, ctx.user.id, ctx.workspace.id)
    return _seen_other(f"/team/{team.key}/new" if team else "/")


@router.api_route("/edit-todo/{todo_id}", methods=["GET", "POST"])
async def old_edit(todo_id: int,
                   ctx: deps.Context = Depends(deps.require_workspace)):
    issue = _issue_by_row_id(ctx, todo_id)
    if issue is None:
        return _seen_other("/")
    return _seen_other(f"{issue_url(issue, issue.team)}/edit")


@router.get("/complete/{todo_id}")
@router.get("/delete/{todo_id}")
async def old_mutating_link(todo_id: int,
                            ctx: deps.Context = Depends(deps.require_workspace)):
    issue = _issue_by_row_id(ctx, todo_id)
    if issue is None:
        return _seen_other("/")
    return _seen_other(issue_url(issue, issue.team))
