"""Cycle arithmetic and the burn-up geometry.

A team's cycles are a series, not a set of hand-made rows: cycle N runs from
`anchor + (N-1) * length` for `length` days. Storing the rule rather than a
calendar means Current is always populated with no cron job keeping a table
topped up, and the numbering is gapless and the dates contiguous by
construction.

Rows still exist, because an issue has to point at one. They are materialised
lazily -- opening the Cycles page fills in whatever is missing up to a couple
of cycles ahead of today.

Which cycle is Current is read off the calendar every time and never stored: a
stored flag would be wrong the morning after.
"""

from collections import Counter
from datetime import timedelta

import models

# How far past today to materialise, so Upcoming and the ones after it exist.
CYCLES_AHEAD = 3

# A team created years ago with a short cycle would otherwise bulk-insert
# hundreds of rows the first time anyone opens the page.
MAX_CYCLES = 200

# The burn-up plot, in viewBox units -- same box as the Home trend so the two
# charts share the .trend styling rather than growing a second set.
BOX = {"width": 960, "height": 214, "left": 40, "right": 944,
       "top": 16, "bottom": 168}

STATE_LABELS = {
    "completed": "Completed",
    "current": "Current",
    "upcoming": "Upcoming",
    "planned": "Planned",
}


def length_of(team):
    return team.cycle_length_days or 14


def bounds(team, number):
    """(starts_on, ends_on) for cycle `number`. Both ends inclusive."""
    length = length_of(team)
    start = team.cycle_anchor + timedelta(days=(number - 1) * length)
    return start, start + timedelta(days=length - 1)


def number_for(team, day):
    """The cycle number containing `day`, never below 1.

    A team whose anchor is in the future has no cycle 0 to speak of, so the
    series simply starts at 1 rather than counting backwards.
    """
    delta = (day - team.cycle_anchor).days
    return max(1, delta // length_of(team) + 1)


def ensure(db, team, today=None):
    """Create whatever rows are missing, and return the team's cycles in order.

    Idempotent: it only inserts numbers that are not already there, so calling
    it on every page load costs one query once the series has caught up.
    """
    if team.cycle_anchor is None:
        # Only reachable for a team that predates the migration and somehow
        # missed the backfill. Anchor it now rather than refusing to render.
        team.cycle_anchor = models.utcnow().date()
        db.add(team)
        db.commit()

    today = today or models.utcnow().date()
    wanted = min(number_for(team, today) + CYCLES_AHEAD, MAX_CYCLES)

    existing = {cycle.number: cycle for cycle in db.query(models.Cycle)
                .filter(models.Cycle.team_id == team.id).all()}

    created = False
    for number in range(1, wanted + 1):
        if number in existing:
            continue
        starts_on, ends_on = bounds(team, number)
        db.add(models.Cycle(team_id=team.id, number=number,
                            starts_on=starts_on, ends_on=ends_on))
        created = True
    if created:
        db.commit()

    return db.query(models.Cycle)\
        .filter(models.Cycle.team_id == team.id)\
        .order_by(models.Cycle.number).all()


def states(cycles, today=None):
    """Map cycle id -> completed / current / upcoming / planned.

    Exactly one Upcoming: the first one that has not started. Everything
    further out is Planned, which is what the reference shows.
    """
    today = today or models.utcnow().date()
    result = {}
    seen_upcoming = False
    for cycle in cycles:
        if cycle.ends_on < today:
            result[cycle.id] = "completed"
        elif cycle.starts_on <= today:
            result[cycle.id] = "current"
        elif not seen_upcoming:
            result[cycle.id] = "upcoming"
            seen_upcoming = True
        else:
            result[cycle.id] = "planned"
    return result


def pick(cycles, state, today=None):
    """The one cycle in a given state, or None."""
    by_id = states(cycles, today)
    for cycle in cycles:
        if by_id.get(cycle.id) == state:
            return cycle
    return None


def tallies(db, cycles):
    """scope and done counts per cycle id, in one query rather than per row."""
    ids = [cycle.id for cycle in cycles]
    scope, done = Counter(), Counter()
    if not ids:
        return scope, done
    for issue in db.query(models.Todos).filter(
            models.Todos.cycle_id.in_(ids)).all():
        scope[issue.cycle_id] += 1
        if (issue.status or "todo") == "done":
            done[issue.cycle_id] += 1
    return scope, done


def _on_or_before(stamp, day):
    return stamp is not None and stamp.date() <= day


def burn_up(cycle, issues, today=None):
    """Scope, Started and Completed for each day of a cycle.

    Scope uses each issue's creation date as the day it entered the cycle.
    Nothing records when an issue was *assigned* to a cycle, so this is an
    approximation -- an issue moved in late shows as having been there from
    the start. Stated here rather than left for a reader to infer from a line
    that climbs earlier than they remember.

    Actuals stop at today. Drawing the remaining days of a live cycle would
    put flat lines where there is no data yet, which reads as "no progress"
    rather than "not yet".
    """
    today = today or models.utcnow().date()
    last = min(cycle.ends_on, today)
    if last < cycle.starts_on:
        return None  # the cycle has not started

    days = []
    day = cycle.starts_on
    while day <= last:
        days.append(day)
        day += timedelta(days=1)

    rows = []
    for day in days:
        rows.append({
            "date": day,
            "scope": sum(1 for i in issues if _on_or_before(i.created_at, day)),
            "started": sum(1 for i in issues if _on_or_before(i.started_at, day)),
            "completed": sum(1 for i in issues
                             if _on_or_before(i.completed_at, day)),
        })
    return rows


NICE_MAXIMA = (2, 4, 6, 8, 10, 20, 30, 40, 50, 100, 200, 500, 1000)


def _nice_ceiling(value):
    for candidate in NICE_MAXIMA:
        if candidate >= value:
            return candidate
    return ((value + 999) // 1000) * 1000


def chart(cycle, rows, total_days=None):
    """Turn the daily rows into drawable geometry.

    The x axis spans the whole cycle even when the actuals stop at today, so
    the plot shows how much of the cycle is left rather than stretching a
    partial run across the full width.
    """
    if not rows:
        return None

    peak = max(max(row["scope"], row["started"], row["completed"])
               for row in rows)
    top = _nice_ceiling(max(peak, 1))

    span_days = total_days or ((cycle.ends_on - cycle.starts_on).days + 1)
    left, right = BOX["left"], BOX["right"]
    up, down = BOX["top"], BOX["bottom"]
    step = (right - left) / max(1, span_days - 1)

    def y_for(value):
        return round(down - (value / top) * (down - up), 1)

    series = []
    for name, field, role in (("Scope", "scope", "scope"),
                              ("Started", "started", "started"),
                              ("Completed", "completed", "completed")):
        points = [(round(left + index * step, 1), y_for(row[field]))
                  for index, row in enumerate(rows)]
        series.append({
            "name": name,
            "role": role,
            "points": " ".join(f"{x},{y}" for x, y in points),
            "end": points[-1],
            "end_value": rows[-1][field],
        })

    ticks = sorted({0, top // 2, top})
    gridlines = [{"value": value, "y": y_for(value)} for value in ticks]

    # Enough date labels to locate a point, few enough not to collide, and the
    # cycle's last day is always one of them.
    marks = [0]
    if len(rows) > 2:
        marks.append(len(rows) // 2)
    if len(rows) > 1:
        marks.append(len(rows) - 1)
    dates = [{"x": round(left + index * step, 1),
              "text": rows[index]["date"].strftime("%b %d")}
             for index in sorted(set(marks))]

    # Where today sits, when the cycle still has days to run.
    elapsed = None
    if len(rows) < span_days:
        elapsed = {"x": round(left + (len(rows) - 1) * step, 1),
                   "top": up, "bottom": down}

    return {"box": BOX, "series": series, "gridlines": gridlines,
            "dates": dates, "top": top, "elapsed": elapsed,
            "days_shown": len(rows), "days_total": span_days}
