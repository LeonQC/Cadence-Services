"""Numbers and chart geometry for the team summary.

Kept out of the router because it is arithmetic, not routing: the route hands
this a team's issues and gets back everything the template draws, so the
template does no maths and there is one place to check the figures.

The coordinates are computed here too. The alternative -- a charting library --
would mean a build step and a CDN for one page, and this app has neither. What
the template renders is inline SVG for the trend and plain HTML bars for the
rest; a horizontal bar is a div with a width, and asking SVG to do that would
be more code, not less.
"""

from collections import Counter
from datetime import timedelta

import models

TREND_DAYS = 14
WEEK = 7

# The trend plot, in viewBox units. The SVG scales to its container, so these
# are proportions as much as pixels; the box is sized close to the width it
# actually renders at so text does not scale far from its nominal size.
BOX = {"width": 960, "height": 214, "left": 40, "right": 944,
       "top": 16, "bottom": 168}

# Statuses that mean "still on someone's plate". Used by the workload figures,
# where finished work is not a load.
OPEN_STATUSES = ("backlog", "todo", "in_progress")


# Axis maxima, all even so the midpoint tick is a whole number too. Without
# this the axis reads 0 / 1.5 / 3 for a peak of 3, and the reader has to do
# division to place a point.
NICE_MAXIMA = (2, 4, 6, 8, 10, 20, 30, 40, 50, 100, 200, 500, 1000)


def _nice_ceiling(value):
    for candidate in NICE_MAXIMA:
        if candidate >= value:
            return candidate
    return ((value + 999) // 1000) * 1000


def _count_between(issues, field, start, end):
    """Count issues whose timestamp falls in (start, end].

    Open at the start and closed at the end, consistently, so consecutive
    windows neither overlap nor leave a gap -- and so something that happened
    at the instant the page was rendered lands in "this week" rather than
    falling off the end of it.
    """
    total = 0
    for issue in issues:
        stamp = getattr(issue, field, None)
        if stamp is not None and start < stamp <= end:
            total += 1
    return total


def stat_tiles(issues, now):
    """The four headline numbers, each with the week-on-week change where a
    change means anything. "In progress" and "Backlog" are states, not events,
    so they carry no delta -- a delta on a standing count would invite reading
    it as a rate."""
    this_week = now - timedelta(days=WEEK)
    last_week = now - timedelta(days=WEEK * 2)

    done_now = _count_between(issues, "completed_at", this_week, now)
    done_before = _count_between(issues, "completed_at", last_week, this_week)
    made_now = _count_between(issues, "created_at", this_week, now)
    made_before = _count_between(issues, "created_at", last_week, this_week)

    statuses = Counter(issue.status or "todo" for issue in issues)

    return [
        {"label": "Completed this week", "value": done_now,
         "delta": done_now - done_before, "good": "up",
         "note": "vs previous 7 days"},
        {"label": "Created this week", "value": made_now,
         "delta": made_now - made_before, "good": None,
         "note": "vs previous 7 days"},
        {"label": "In progress", "value": statuses.get("in_progress", 0),
         "delta": None, "good": None, "note": "right now"},
        {"label": "Backlog", "value": statuses.get("backlog", 0),
         "delta": None, "good": None, "note": "not scheduled yet"},
    ]


def _bars(pairs, total):
    """Rows for a horizontal bar chart.

    One hue for every bar: the row's own label and icon carry identity, so
    colouring each bar differently would spend the only free channel on
    something the chart already says.
    """
    peak = max([count for _, count in pairs] + [1])
    return [{"key": key, "count": count,
             "percent": round(count * 100 / total) if total else 0,
             # Width is relative to the largest bar, not to the total: this is
             # a magnitude comparison, and scaling by total leaves every bar a
             # stub as soon as one status dominates.
             "width": round(count * 100 / peak, 1) if peak else 0}
            for key, count in pairs]


def status_rows(issues):
    counts = Counter(issue.status or "todo" for issue in issues)
    return _bars([(value, counts.get(value, 0)) for value in models.STATUSES],
                 len(issues))


def priority_rows(issues):
    counts = Counter(issue.priority or 3 for issue in issues)
    return _bars([(level, counts.get(level, 0)) for level in range(1, 6)],
                 len(issues))


def workload_rows(issues, people):
    """Open issues per assignee, busiest first.

    Counts only open work: a finished issue is not a load, and including it
    would make whoever cleared the most look the most burdened.
    """
    counts = Counter()
    for issue in issues:
        if (issue.status or "todo") in OPEN_STATUSES:
            counts[issue.assignee_id] += 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0] or 0))
    peak = max(list(counts.values()) + [1])
    total = sum(counts.values())

    rows = []
    for user_id, count in ordered:
        rows.append({
            "person": people.get(user_id),
            "count": count,
            "percent": round(count * 100 / total) if total else 0,
            "width": round(count * 100 / peak, 1),
        })
    return rows


def project_rows(db, team):
    """Every project in a team with how far along it is.

    Lives here rather than in the projects router because the team's Home
    shows the same figures, and two places computing "how done is this" is one
    place too many.
    """
    projects = db.query(models.Project)\
        .filter(models.Project.team_id == team.id)\
        .order_by(models.Project.created_at.desc()).all()
    if not projects:
        return []

    counts = Counter()
    done = Counter()
    for issue in db.query(models.Todos).filter(
            models.Todos.team_id == team.id,
            models.Todos.project_id.isnot(None)).all():
        counts[issue.project_id] += 1
        if (issue.status or "todo") == "done":
            done[issue.project_id] += 1

    rows = []
    for project in projects:
        total = counts.get(project.id, 0)
        finished = done.get(project.id, 0)
        rows.append({
            "project": project,
            "total": total,
            "done": finished,
            # Percent of its own issues, not of the team's: a project with two
            # of two done is finished, however small it is.
            "percent": round(finished * 100 / total) if total else 0,
        })
    return rows


def daily_counts(issues, today):
    """One bucket per day for the trend, oldest first."""
    start = today - timedelta(days=TREND_DAYS - 1)
    created, completed = Counter(), Counter()
    for issue in issues:
        if issue.created_at and start <= issue.created_at.date() <= today:
            created[issue.created_at.date()] += 1
        if issue.completed_at and start <= issue.completed_at.date() <= today:
            completed[issue.completed_at.date()] += 1

    rows = []
    for offset in range(TREND_DAYS):
        day = start + timedelta(days=offset)
        rows.append({"date": day, "created": created[day],
                     "completed": completed[day]})
    return rows


def trend_chart(rows):
    """Turn the daily buckets into drawable geometry.

    Returns points as "x,y" strings ready for a polyline, plus the gridlines,
    ticks and the endpoint labels -- so the template places what it is given
    and never does arithmetic in a Jinja expression.
    """
    peak = max([row["created"] for row in rows]
               + [row["completed"] for row in rows] + [1])
    top = _nice_ceiling(peak)

    left, right = BOX["left"], BOX["right"]
    up, down = BOX["top"], BOX["bottom"]
    step = (right - left) / (len(rows) - 1)

    def y_for(value):
        return round(down - (value / top) * (down - up), 1)

    xs = [round(left + index * step, 1) for index in range(len(rows))]

    series = []
    for name, field, role in (("Created", "created", "created"),
                              ("Completed", "completed", "completed")):
        points = [(xs[i], y_for(row[field])) for i, row in enumerate(rows)]
        series.append({
            "name": name,
            "role": role,
            "points": " ".join(f"{x},{y}" for x, y in points),
            "end": points[-1],
            "end_value": rows[-1][field],
            "total": sum(row[field] for row in rows),
        })

    # Direct end-labels only when the two lines are far enough apart to keep
    # each label attached to its own line. When they converge, the legend and
    # the table carry it -- nudging them apart would detach them from the data.
    gap = abs(series[0]["end"][1] - series[1]["end"][1])
    label_ends = gap >= 16

    ticks = sorted({0, top // 2, top})
    gridlines = [{"value": value, "y": y_for(value)} for value in ticks]

    # Five date labels across fourteen days: enough to locate a point, few
    # enough not to collide at this width. The last day is always one of them
    # -- it is the point a reader looks at first, and an evenly spaced run
    # tends to stop one short of it.
    label_every = max(1, (len(rows) - 1) // 4)
    marks = list(range(0, len(rows), label_every))
    if marks[-1] != len(rows) - 1:
        marks.append(len(rows) - 1)
        if len(marks) > 1 and marks[-1] - marks[-2] < label_every / 2:
            marks.pop(-2)  # too close to the one before it to read as separate

    dates = [{"x": xs[i], "text": rows[i]["date"].strftime("%b %d")}
             for i in marks]

    return {"box": BOX, "series": series, "gridlines": gridlines,
            "dates": dates, "label_ends": label_ends, "top": top,
            "baseline": y_for(0)}


def build(db, team, issues, now=None):
    """Everything the summary page needs, in one pass over the issues."""
    now = now or models.utcnow()

    people_ids = {issue.assignee_id for issue in issues if issue.assignee_id}
    people = {}
    if people_ids:
        people = {person.id: person for person in db.query(models.Users)
                  .filter(models.Users.id.in_(people_ids)).all()}

    rows = daily_counts(issues, now.date())

    recent = sorted(
        [issue for issue in issues if issue.updated_at],
        key=lambda issue: issue.updated_at, reverse=True)[:8]

    return {
        "tiles": stat_tiles(issues, now),
        "status_rows": status_rows(issues),
        "priority_rows": priority_rows(issues),
        "workload": workload_rows(issues, people),
        "trend_rows": rows,
        "trend": trend_chart(rows),
        "recent": [{"issue": issue, "person": people.get(issue.assignee_id)}
                   for issue in recent],
        "people": people,
        "projects": project_rows(db, team),
        "total": len(issues),
    }
