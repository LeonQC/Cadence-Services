"""Small GitHub App client used by the workspace integration."""
import os
import time
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from jose import jwt

load_dotenv()

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_SLUG = os.getenv("GITHUB_APP_SLUG")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY")
GITHUB_SETUP_URL = os.getenv(
    "GITHUB_SETUP_URL",
    "http://localhost:8000/settings/integrations/github/callback")


def configured():
    return bool(GITHUB_APP_ID and GITHUB_APP_SLUG and
                (GITHUB_PRIVATE_KEY_PATH or GITHUB_PRIVATE_KEY))


def _private_key():
    if GITHUB_PRIVATE_KEY:
        return GITHUB_PRIVATE_KEY.replace("\\n", "\n")
    if GITHUB_PRIVATE_KEY_PATH:
        with open(GITHUB_PRIVATE_KEY_PATH, "r", encoding="utf-8") as handle:
            return handle.read()
    raise RuntimeError("GitHub App private key is not configured")


def app_jwt():
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": str(GITHUB_APP_ID)},
        _private_key(), algorithm="RS256")


def install_url(state):
    query = urlencode({"state": state, "redirect_uri": GITHUB_SETUP_URL})
    return f"https://github.com/apps/{GITHUB_APP_SLUG}/installations/new?{query}"


async def installation_token(installation_id):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt()}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers=headers)
    response.raise_for_status()
    return response.json()["token"]


async def verify_installation(installation_id):
    """Confirm the installation belongs to this GitHub App."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt()}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{GITHUB_API}/app/installations/{installation_id}",
            headers=headers)
    return response.is_success


async def get_repository(installation_id, repository):
    token = await installation_token(installation_id)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{GITHUB_API}/repos/{repository}",
                                    headers=headers)
    response.raise_for_status()
    return response.json()
