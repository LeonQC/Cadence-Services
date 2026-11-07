"""Server-side OAuth refresh-token storage and access-token renewal."""
import base64
import hashlib
import os

import httpx
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

import models

load_dotenv()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _cipher():
    configured = os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY")
    if configured:
        return Fernet(configured.encode())
    secret = os.getenv("SECRET_KEY", "KlgH6AzYDeZeGwD288to79I3vTHT8wp7")
    derived = base64.urlsafe_b64encode(hashlib.sha256(
        secret.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_refresh_token(value):
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_refresh_token(value):
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise RuntimeError("OAuth refresh token cannot be decrypted") from exc


def save_refresh_token(db, user_id, provider, refresh_token, scopes=""):
    row = db.query(models.OAuthToken).filter(
        models.OAuthToken.user_id == user_id,
        models.OAuthToken.provider == provider).first()
    if row is None:
        row = models.OAuthToken(user_id=user_id, provider=provider)
    row.encrypted_refresh_token = encrypt_refresh_token(refresh_token)
    row.scopes = scopes or None
    row.updated_at = models.utcnow()
    db.add(row)
    db.commit()
    return row


async def google_access_token(db, user_id, client_id, client_secret):
    """Use the stored Google refresh token to mint a new access token."""
    row = db.query(models.OAuthToken).filter(
        models.OAuthToken.user_id == user_id,
        models.OAuthToken.provider == "google").first()
    if row is None:
        raise RuntimeError("Google authorization is required")

    refresh_token = decrypt_refresh_token(row.encrypted_refresh_token)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    response.raise_for_status()
    payload = response.json()
    replacement = payload.get("refresh_token")
    if replacement:
        row.encrypted_refresh_token = encrypt_refresh_token(replacement)
        row.updated_at = models.utcnow()
        db.add(row)
        db.commit()
    return payload["access_token"]
