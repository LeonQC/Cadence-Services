"""Redis helpers for the TodoApp.

Two things live here:

1. A cache-aside cache for each team's issue list, so that the list view does
   not hit SQLite on every page load.
2. A denylist of logged-out JWTs. A JWT is stateless, so deleting the cookie on
   logout does not actually invalidate the token -- it stays valid until it
   expires. We store the token's "jti" with a TTL equal to the token's
   remaining lifetime, so logged-out tokens stop working immediately and the
   entries clean themselves up.

Every call degrades gracefully: if Redis is unreachable, reads look like a
cache miss and writes are skipped, so the app keeps working straight off the
database. That promise is enforced by @degrades below rather than left to each
function to remember.

NOTE: this module must not be named redis.py, or it would shadow the redis
package itself.
"""

import asyncio
import functools
import json
import os
import time
from datetime import datetime
from types import SimpleNamespace

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# The write paths invalidate the cache explicitly, so this TTL is only a
# safety net in case an invalidation is ever missed.
TODO_CACHE_TTL = 60

# How long to stop trying after a failure.
#
# Failing soft is not enough on its own: while Redis was down, every cache call
# on every request still paid redis-py's connect-and-retry before giving up,
# which took a 40ms page to 2s -- degraded into unusable. Short-circuiting for
# a few seconds keeps an outage boring. Short enough that recovery is noticed
# almost immediately.
OUTAGE_COOLDOWN = 10

# Bounds the one call per cooldown that does try. Without it a host that
# blackholes packets, rather than refusing them, would hang the request.
redis_client = redis.from_url(REDIS_URL, decode_responses=True,
                              socket_connect_timeout=1, socket_timeout=2)

# (function, error class) pairs already reported, so an outage says its piece
# once per failure mode instead of once per request.
_reported = set()

# Monotonic deadline before which calls are skipped outright. Monotonic, not
# wall clock, so a clock adjustment cannot strand it.
_down_until = 0.0


def degrades(default=None):
    """Make a cache call fail soft, returning `default` rather than raising.

    Catching redis.RedisError alone was not enough. A connection that dies
    underneath the client surfaces as an OSError from the socket layer or a
    RuntimeError from asyncio, and neither subclasses RedisError, so both used
    to escape and turn a page that merely wanted a cache lookup into a 500.
    Nothing in this module is worth failing a request over -- the database
    still has the answer.

    A failure also opens the circuit for OUTAGE_COOLDOWN seconds, so the rest
    of the request does not repeat a connection attempt that has just been
    shown not to work.

    CancelledError is deliberately re-raised: that is the request being torn
    down, not Redis being unavailable, and swallowing it would break shutdown.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            global _down_until

            if time.monotonic() < _down_until:
                return default

            try:
                result = await fn(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _down_until = time.monotonic() + OUTAGE_COOLDOWN
                signature = (fn.__name__, type(exc).__name__)
                if signature not in _reported:
                    _reported.add(signature)
                    print(f"Redis unavailable in {fn.__name__}: "
                          f"{type(exc).__name__}: {exc} - continuing without "
                          f"cache, and not retrying for {OUTAGE_COOLDOWN}s "
                          f"(further identical failures stay quiet)",
                          flush=True)
                return default

            if _down_until:
                print("Redis is answering again", flush=True)
                _down_until = 0.0
            return result
        return wrapper
    return decorator


@degrades(default=False)
async def ping():
    return await redis_client.ping()


@degrades()
async def close():
    await redis_client.aclose()


# Issue list cache
#
# Keyed by team rather than by user: an issue belongs to a team, and once a
# team has more than one member a per-user key would hand each of them a
# separate copy that the others' writes never invalidate.

def issues_key(team_id):
    return f"issues:team:{team_id}"


# Columns carried through the cache. Datetimes go over as ISO strings because
# json cannot take them, and come back as datetimes so a cached issue behaves
# like an ORM one in the templates.
_DATETIME_FIELDS = ("created_at", "updated_at", "completed_at", "started_at")

_FIELDS = ("id", "title", "description", "priority", "complete", "owner_id",
           "team_id", "number", "status", "assignee_id",
           "project_id", "cycle_id") + _DATETIME_FIELDS


def _serialize(todo):
    row = {field: getattr(todo, field, None) for field in _FIELDS}
    for field in _DATETIME_FIELDS:
        if row[field] is not None:
            row[field] = row[field].isoformat()
    return row


def _deserialize(row):
    for field in _DATETIME_FIELDS:
        if row.get(field):
            row[field] = datetime.fromisoformat(row[field])
    return SimpleNamespace(**row)


@degrades()
async def get_cached_issues(team_id):
    """Return the cached issues, or None on a miss (or if Redis is down).

    They come back as SimpleNamespace objects so that the templates can use
    issue.title / issue.status exactly like they do with the ORM objects.
    """
    cached = await redis_client.get(issues_key(team_id))
    if cached is None:
        return None
    return [_deserialize(row) for row in json.loads(cached)]


@degrades()
async def set_cached_issues(team_id, todos):
    payload = json.dumps([_serialize(todo) for todo in todos])
    await redis_client.setex(issues_key(team_id), TODO_CACHE_TTL, payload)


@degrades()
async def invalidate_issues(team_id):
    if team_id is None:
        return
    await redis_client.delete(issues_key(team_id))


# Logged-out token denylist

def denylist_key(jti):
    return f"denylist:{jti}"


@degrades()
async def denylist_token(jti, ttl_seconds):
    await redis_client.setex(denylist_key(jti), ttl_seconds, "1")


@degrades(default=False)
async def is_denylisted(jti):
    """False when Redis is unavailable, meaning a logged-out token stays usable
    until it expires on its own. Failing open is the existing trade-off:
    failing closed would sign every user out whenever Redis blinks.

    Users.token_version covers the case this cannot -- it lives in the database
    and so survives Redis being down entirely.
    """
    return bool(await redis_client.exists(denylist_key(jti)))
