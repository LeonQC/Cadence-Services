"""One shared Jinja2Templates instance, plus the helpers templates rely on.

Each router used to build its own Jinja2Templates(directory="templates"), so a
global registered in one was invisible in the others -- which is why
google_login_enabled only worked on pages rendered from routers/auth.py. With
one instance, a helper registered anywhere is available everywhere.
"""

from fastapi.templating import Jinja2Templates

import cycle_math
import models

templates = Jinja2Templates(directory="templates")


def initials(user):
    """One or two letters for the fallback avatar."""
    if user is None:
        return "?"
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    if first and last:
        return (first[0] + last[0])
    name = first or (getattr(user, "username", "") or "").strip()
    return (name[:2] or "?")


def workspace_initials(workspace):
    if workspace is None:
        return "?"
    words = (workspace.name or "").split()
    if len(words) >= 2:
        return words[0][0] + words[1][0]
    return (workspace.name or "?")[:2]


def relative_time(when, now=None):
    """"3d ago" rather than a timestamp.

    An activity feed is read for order and recency, and an exact date makes the
    reader do the subtraction themselves.
    """
    if when is None:
        return "—"
    now = now or models.utcnow()
    seconds = (now - when).total_seconds()
    if seconds < 0:
        return "just now"
    for limit, divisor, unit in ((60, 1, "s"), (3600, 60, "m"),
                                 (86400, 3600, "h"), (2592000, 86400, "d")):
        if seconds < limit:
            count = int(seconds // divisor)
            return "just now" if count < 1 and unit == "s" else f"{count}{unit} ago"
    return when.strftime("%b %d")


templates.env.globals.update(
    relative_time=relative_time,
    STATUSES=models.STATUSES,
    STATUS_LABELS=models.STATUS_LABELS,
    PROJECT_STATUSES=models.PROJECT_STATUSES,
    PROJECT_STATUS_LABELS=models.PROJECT_STATUS_LABELS,
    CYCLE_STATE_LABELS=cycle_math.STATE_LABELS,
    avatar_color=models.avatar_color_for,
    initials=initials,
    workspace_initials=workspace_initials,
)
