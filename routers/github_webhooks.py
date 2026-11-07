"""GitHub App webhook receiver for commit-to-issue linking."""
import hashlib
import hmac
import os
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

import models
from database import SessionLocal

router = APIRouter(tags=["github"])
ISSUE_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b", re.IGNORECASE)


def _valid_signature(body, signature):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _identifiers(*values):
    found = []
    for value in values:
        for match in ISSUE_ID_RE.findall(value or ""):
            identifier = match.upper()
            if identifier not in found:
                found.append(identifier)
    return found


def _committed_at(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _issue_for_identifier(db, identifier):
    key, number = identifier.rsplit("-", 1)
    if not number.isdigit():
        return None
    return db.query(models.Todos).join(models.Team).filter(
        models.Team.key == key,
        models.Todos.number == int(number)).first()


def _linked_integration(db, installation_id, repository):
    links = db.query(models.Integration).filter(
        models.Integration.provider == "github",
        models.Integration.github_installation_id == installation_id,
        models.Integration.enabled.is_(True)).all()
    repository = repository.lower()
    return next((link for link in links
                 if (link.target or "").lower() == repository), None)


def _save_commit(db, issue, repository, commit, branch):
    sha = commit.get("id") or commit.get("sha")
    if not sha:
        return False
    exists = db.query(models.GitHubCommit).filter(
        models.GitHubCommit.repository == repository,
        models.GitHubCommit.sha == sha,
        models.GitHubCommit.issue_id == issue.id).first()
    if exists:
        return False

    message = (commit.get("message") or "").strip()
    subject = message.splitlines()[0] if message else sha[:12]
    author = commit.get("author") or {}
    db.add(models.GitHubCommit(
        issue_id=issue.id,
        repository=repository,
        sha=sha,
        subject=subject,
        message=message,
        branch=branch,
        url=commit.get("html_url") or
            f"https://github.com/{repository}/commit/{sha}",
        author_name=author.get("name") or author.get("username"),
        committed_at=_committed_at(commit.get("timestamp")),
    ))
    return True


@router.post("/github/webhook")
async def github_webhook(request: Request):
    body = await request.body()
    if not _valid_signature(body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    event = request.headers.get("x-github-event")
    if event != "push":
        return {"accepted": True, "event": event, "linked": 0}

    payload = await request.json()
    installation = payload.get("installation") or {}
    repository_data = payload.get("repository") or {}
    installation_id = installation.get("id")
    repository = repository_data.get("full_name")
    if not installation_id or not repository:
        return {"accepted": True, "linked": 0}

    ref = payload.get("ref") or ""
    branch = ref.removeprefix("refs/heads/")
    db = SessionLocal()
    linked = 0
    try:
        if _linked_integration(db, installation_id, repository) is None:
            return {"accepted": True, "linked": 0}
        for commit in payload.get("commits") or []:
            identifiers = _identifiers(commit.get("message"), branch)
            for identifier in identifiers:
                issue = _issue_for_identifier(db, identifier)
                if issue and _save_commit(db, issue, repository, commit, branch):
                    linked += 1
        if linked:
            db.commit()
    finally:
        db.close()
    return {"accepted": True, "linked": linked}
