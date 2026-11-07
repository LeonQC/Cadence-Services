import sys
sys.path.append("..")

import hashlib
import secrets

from starlette import status
from starlette.responses import RedirectResponse
from fastapi import Depends, HTTPException, status, APIRouter, Request, Response, Form
from pydantic import BaseModel
from typing import Optional
import models
import oauth_tokens
import provisioning
import redis_cache
from templating import templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from jose import jwt, JWTError
from fastapi.responses import HTMLResponse, JSONResponse

import os
from urllib.parse import urlencode
import httpx
from dotenv import load_dotenv
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


SECRET_KEY = "KlgH6AzYDeZeGwD288to79I3vTHT8wp7"
ALGORITHM = "HS256"

# Google login settings come from .env (see .env.example). Leaving them unset
# simply hides the Google button; the password login keeps working.
load_dotenv()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def google_login_enabled():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# The OAuth "state" parameter is what makes the callback verifiable: without
# it, anyone could hand your browser a /auth/google/callback?code=... URL and
# log you into an account you do not own (login CSRF).
#
# It is kept in a signed cookie rather than server-side, so Google login works
# whether or not Redis happens to be running. Signing reuses SECRET_KEY and
# jose, both already used for the access token.
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_TTL = 300  # seconds; long enough to click through Google's consent


def create_oauth_state_token(state, mode="login"):
    """Sign the state, plus what the round trip is for.

    mode is "login" (sign in, creating the account if needed) or "link"
    (attach Google to the account already signed in). It rides in the signed
    cookie rather than in the URL so the callback cannot be talked into
    treating one as the other.
    """
    return jwt.encode(
        {"state": state, "mode": mode,
         "exp": datetime.utcnow() + timedelta(seconds=OAUTH_STATE_TTL)},
        SECRET_KEY, algorithm=ALGORITHM)


def read_oauth_state_token(token):
    """Return (state, mode) from the cookie, or (None, None) if it is missing,
    expired or not signed by us."""
    if not token:
        return None, None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None, None
    return payload.get("state"), payload.get("mode", "login")

# Exposed as a global so login.html can hide the Google button when the
# credentials are not configured, without every render call passing it in.
# Registered on the shared instance from templating.py, so it is available to
# pages rendered from any router rather than only this one.
templates.env.globals["google_login_enabled"] = google_login_enabled

class CreateUser(BaseModel):
    username: str
    email: Optional[str]
    first_name: str
    last_name: str
    password: str


bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

models.Base.metadata.create_all(bind=engine)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="token")


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"user": "Not authorized"}}
)

class LoginForm:
    def __init__(self, request: Request):
        self.request: Request = request
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    async def create_oauth_form(self):
        form = await self.request.form()
        self.username = form.get("email")
        self.password = form.get("password")

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_password_hash(password):
    return bcrypt_context.hash(password)


def verify_password(plain_password, hashed_password):
    return bcrypt_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str, db):
    user = db.query(models.Users)\
        .filter(models.Users.username == username)\
        .first()

    if not user:
        return False
    # Google-only accounts have no password at all. Without this guard passlib
    # would be handed None and blow up instead of just refusing the login.
    if not user.hashed_password:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(username: str, user_id: int,
                        expires_delta: Optional[timedelta] = None,
                        token_version: int = 0, method: str = "password"):

    # jti uniquely identifies this token, so logout can deny-list it in Redis
    # without having to store the token itself. tv pins the token to the user's
    # current token_version, which is what makes "log out of all sessions"
    # possible -- see the note on Users.token_version. amr records how the user
    # proved who they are, which is what a workspace's security settings are
    # then able to accept or refuse.
    encode = {"sub": username, "id": user_id, "jti": str(uuid4()),
              "tv": token_version, "amr": method}
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    encode.update({"exp": expire})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


# API keys
#
# The plaintext key is shown once, at creation, and never stored. What goes in
# the database is its SHA-256, so a database leak does not hand out working
# keys. No salt and no bcrypt here on purpose: the key is 32 bytes of
# secrets.token_urlsafe entropy, not a human-chosen password, so there is
# nothing for a rainbow table or a slow hash to defend against.

API_KEY_PREFIX = "lin_api_"


def generate_api_key():
    """Return (plaintext, prefix, hash) for a fresh key."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:len(API_KEY_PREFIX) + 6], hash_api_key(raw)


def hash_api_key(raw_key: str):
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _user_from_cookie(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # Expired, or signed by someone else. Treated as "not signed in" rather
        # than raising: every caller renders HTML for a browser, and a bare 401
        # there is worse than a trip back to the login page.
        return None

    username: str = payload.get("sub")
    user_id: int = payload.get("id")
    if username is None or user_id is None:
        return None

    # Tokens issued before jti existed have none, so only check when present.
    jti: str = payload.get("jti")
    if jti and await redis_cache.is_denylisted(jti):
        return None

    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    if user is None or not user.is_active:
        return None
    # Tokens minted before token_version existed carry no "tv"; reading them as
    # 0 lets those cookies keep working until they expire on their own.
    if payload.get("tv", 0) != (user.token_version or 0):
        return None

    # Tokens minted before amr existed read as a password session, which is
    # what they were -- Google sign-in always went through create_access_token
    # with the method set.
    return {"username": user.username, "id": user.id,
            "method": payload.get("amr", "password")}


async def _user_from_api_key(raw_key: str, db: Session):
    api_key = db.query(models.ApiKey)\
        .filter(models.ApiKey.key_hash == hash_api_key(raw_key)).first()
    if api_key is None:
        return None
    user = db.query(models.Users).filter(models.Users.id == api_key.user_id).first()
    if user is None or not user.is_active:
        return None
    api_key.last_used_at = models.utcnow()
    db.add(api_key)
    db.commit()
    return {"username": user.username, "id": user.id, "method": "api_key"}


async def get_current_user(request: Request, db: Session = None):
    """Identify the caller, from an API key if one was sent and the session
    cookie otherwise. Returns {"username", "id"} or None.

    Still a plain dict because the existing routes index it that way;
    deps.current_user turns it into an ORM row for code that needs more.

    db is optional so the callers that predate it keep working -- when it is
    left out the function borrows a session of its own.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return await _user_from_api_key(header[len("Bearer "):], db)
        return await _user_from_cookie(request, db)
    finally:
        if owns_session:
            db.close()


@router.post("/create/user")
async def create_new_user(create_user: CreateUser, db: Session = Depends(get_db)):
    create_user_model = models.Users()
    create_user_model.email = create_user.email
    create_user_model.username = create_user.username
    create_user_model.first_name = create_user.first_name
    create_user_model.last_name = create_user.last_name

    hash_password = get_password_hash(create_user.password)

    create_user_model.hashed_password = hash_password
    create_user_model.is_active = True

    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)
    provisioning.provision_personal_workspace(db, create_user_model)


@router.post("/token")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(),
                                 db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        return False
    token_expires = timedelta(minutes=60)
    token = create_access_token(user.username,
                                user.id,
                                expires_delta=token_expires,
                                token_version=user.token_version or 0,
                                method="password")
    response.set_cookie(key="access_token", value=token, httponly=True)

    return True

@router.get("/", response_class=HTMLResponse)
async def authenticationpage(request: Request) :
    return templates.TemplateResponse(request, "auth/login.html")

@router.post("/", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        form = LoginForm(request)
        await form.create_oauth_form()
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        validate_user_cookie = await login_for_access_token(response=response, form_data=form, db=db)

        if not validate_user_cookie:
            msg = "Incorrect Username or Password"
            return templates.TemplateResponse(request,"auth/login.html",{"msg":msg})
        return response
    except HTTPException:
        msg = "Unknown Error"
        return templates.TemplateResponse(request,"auth/login.html",{"msg":msg})

# Google login
#
# The flow is the standard OAuth 2.0 authorization code exchange:
#
#   GET /auth/google           -> redirect the browser to Google
#   (user approves on Google)
#   GET /auth/google/callback  -> swap the code for an id_token, then issue our
#                                 own access_token cookie exactly like the
#                                 password login does
#
# Everything downstream (get_current_user, the Redis denylist, todo ownership)
# is untouched -- Google only replaces the "who are you" step.


def unique_username(db, preferred):
    """Pick a free username, e.g. "peter" -> "peter2" if peter is taken."""
    base = preferred or "user"
    candidate = base
    suffix = 1
    while db.query(models.Users).filter(models.Users.username == candidate).first():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def find_or_create_google_user(db, id_info):
    """Map a verified Google identity onto a row in our users table.

    Returns the user, or None if the login has to be refused.

    Looked up by Google's "sub" first, because that never changes, while a
    Google account's email address can. Falling back to email is what lets an
    existing password account pick up Google sign-in -- but only when Google
    says the address is verified, otherwise anyone could claim someone else's
    account by signing up to Google with their address.
    """
    google_sub = id_info["sub"]

    user = db.query(models.Users).filter(models.Users.google_sub == google_sub).first()
    if user:
        return user

    email = id_info.get("email")
    existing = None
    if email:
        existing = db.query(models.Users).filter(models.Users.email == email).first()

    if existing is not None:
        if not id_info.get("email_verified"):
            # The address is already ours and Google will not vouch for it, so
            # linking would be a takeover. Refuse rather than create a second
            # row, which would collide with the unique index on email anyway.
            return None
        existing.google_sub = google_sub
        db.add(existing)
        db.commit()
        return existing

    user = models.Users()
    user.email = email
    user.username = unique_username(db, (email or "user").split("@")[0])
    user.first_name = id_info.get("given_name") or ""
    user.last_name = id_info.get("family_name") or ""
    user.hashed_password = None  # sign-in is via Google only
    user.is_active = True
    user.google_sub = google_sub
    db.add(user)
    db.commit()
    db.refresh(user)
    provisioning.provision_personal_workspace(db, user)
    return user


def reject_google_login(request, msg):
    """Back to the login page with a message, and drop the state cookie so a
    failed attempt cannot be retried with a stale one."""
    response = RedirectResponse(
        url=f"{FRONTEND_URL}/?{urlencode({'auth_error': msg})}",
        status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=OAUTH_STATE_COOKIE)
    return response


def start_google(mode):
    """Send the browser to Google, remembering why."""
    state = str(uuid4())
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        # Ask for consent so Google returns a refresh token on the first
        # authorization and when an existing grant is being upgraded.
        "prompt": "consent",
    })
    response = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}",
                                status_code=status.HTTP_302_FOUND)
    # The same state goes to Google in the URL and to the browser in a signed
    # cookie; the callback only proceeds if the two match. An attacker can
    # forge neither, because the cookie is signed with SECRET_KEY.
    #
    # samesite must be "lax", not "strict": the callback arrives as a
    # top-level navigation from accounts.google.com, and strict would withhold
    # the cookie on exactly that request.
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=create_oauth_state_token(state, mode),
        httponly=True,
        samesite="lax",
        max_age=OAUTH_STATE_TTL,
    )
    return response


@router.get("/google")
async def google_login(request: Request):
    if not google_login_enabled():
        return templates.TemplateResponse(
            request, "auth/login.html", {"msg": "Google login is not configured"})
    return start_google("login")


@router.get("/google/link")
async def google_link(request: Request, db: Session = Depends(get_db)):
    """Attach Google to the account already signed in.

    Same round trip as signing in; only the mode in the state cookie differs,
    which is what stops the callback from turning a link into a login of
    whichever account the Google identity happens to match.
    """
    if not google_login_enabled():
        return RedirectResponse(url=f"{FRONTEND_URL}/?settings=accounts&error=unconfigured",
                                status_code=status.HTTP_302_FOUND)
    if await get_current_user(request, db) is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_302_FOUND)
    return start_google("link")


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db),
                          code: Optional[str] = None, state: Optional[str] = None,
                          error: Optional[str] = None):
    if error or not code or not state:
        # Google sends ?error=access_denied when the user hits "cancel".
        msg = "Google login cancelled" if error == "access_denied" else "Google login failed"
        return reject_google_login(request, msg)

    expected, mode = read_oauth_state_token(request.cookies.get(OAUTH_STATE_COOKIE))
    if not expected or expected != state:
        # No cookie, expired cookie, or one that does not match the state
        # Google echoed back: this is not a login this browser started.
        return reject_google_login(request, "Invalid or expired login attempt")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            token_response.raise_for_status()
    except httpx.HTTPError:
        return reject_google_login(request, "Could not reach Google, please try again")

    token_payload = token_response.json()
    raw_id_token = token_payload.get("id_token")
    if not raw_id_token:
        return reject_google_login(request, "Google login failed")

    try:
        # Verifies the signature against Google's public keys, plus the issuer,
        # audience and expiry. Anything wrong in there raises ValueError.
        id_info = google_id_token.verify_oauth2_token(
            raw_id_token, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError:
        return reject_google_login(request, "Google login failed")

    if mode == "link":
        response = await link_google_to_current_user(request, db, id_info)
        linked_user = db.query(models.Users).filter(
            models.Users.google_sub == id_info["sub"]).first()
        if linked_user and token_payload.get("refresh_token"):
            oauth_tokens.save_refresh_token(
                db, linked_user.id, "google",
                token_payload["refresh_token"], token_payload.get("scope", ""))
        return response

    user = find_or_create_google_user(db, id_info)
    if user is None:
        return reject_google_login(
            request, "That email is already registered, please log in with your password")

    if token_payload.get("refresh_token"):
        oauth_tokens.save_refresh_token(
            db, user.id, "google", token_payload["refresh_token"],
            token_payload.get("scope", ""))

    token = create_access_token(user.username, user.id,
                                expires_delta=timedelta(minutes=60),
                                token_version=user.token_version or 0,
                                method="google")
    response = RedirectResponse(url=f"{FRONTEND_URL}/",
                                status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=token, httponly=True)
    response.delete_cookie(key=OAUTH_STATE_COOKIE)  # served its purpose
    return response


async def link_google_to_current_user(request, db, id_info):
    """Attach a verified Google identity to whoever is signed in.

    Deliberately not find_or_create_google_user: that resolves an identity to
    an account, which in link mode would sign the visitor into somebody else's
    account if the Google sub happened to match one.
    """
    def back(**params):
        response = RedirectResponse(
            url=f"{FRONTEND_URL}/?settings=accounts&" + urlencode(params),
            status_code=status.HTTP_302_FOUND)
        response.delete_cookie(key=OAUTH_STATE_COOKIE)
        return response

    who = await get_current_user(request, db)
    if who is None:
        return RedirectResponse(url=f"{FRONTEND_URL}/",
                                status_code=status.HTTP_302_FOUND)

    user = db.query(models.Users).filter(models.Users.id == who["id"]).first()
    if user is None:
        return RedirectResponse(url=f"{FRONTEND_URL}/",
                                status_code=status.HTTP_302_FOUND)

    google_sub = id_info["sub"]
    taken = db.query(models.Users)\
        .filter(models.Users.google_sub == google_sub)\
        .filter(models.Users.id != user.id).first()
    if taken is not None:
        return back(error="google_taken")

    user.google_sub = google_sub
    db.add(user)
    db.commit()
    return back(notice="google_linked")


@router.get("/logout")
async def logout(request: Request):
    # Deleting the cookie does not invalidate the JWT, so deny-list it for the
    # rest of its lifetime. The TTL means the entry disappears on its own once
    # the token would have expired anyway.
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                ttl = int(exp - datetime.now(timezone.utc).timestamp())
                if ttl > 0:
                    await redis_cache.denylist_token(jti, ttl)
        except JWTError:
            pass  # already expired or tampered with - nothing to deny-list

    response = JSONResponse({"message": "Logout successful"})
    response.delete_cookie(key="access_token")
    return response
@router.get("/register", response_class=HTMLResponse)
async def register(request: Request) :
    return templates.TemplateResponse(request, "auth/register.html")

@router.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, email: str = Form( ... ), username: str = Form( ... ),
    firstname: str = Form( ... ), lastname: str = Form( ... ),
    password: str = Form( ... ), password2: str = Form( ... ),
    db: Session = Depends(get_db)):

    validation1 = db.query(models.Users).filter(models.Users.username == username).first()

    validation2 = db.query(models.Users).filter(models.Users.email == email).first()

    if password != password2 or validation1 is not None or validation2 is not None:
        msg = "Invalid registration request"
        return templates. TemplateResponse(request,"auth/register.html", {"msg": msg})
    user_model = models.Users()
    user_model.username = username
    user_model.email = email
    user_model.first_name = firstname
    user_model.last_name = lastname

    hash_password = get_password_hash(password)
    user_model.hashed_password = hash_password
    user_model.is_active = True

    db.add(user_model)
    db.commit()
    db.refresh(user_model)
    # Without this the account would sign in to an app with no workspace, no
    # team, and nowhere to put an issue.
    provisioning.provision_personal_workspace(db, user_model)

    msg = "User successfully created"
    return templates.TemplateResponse(request,"auth/login.html", {"msg": msg})
#Exceptions
def get_user_exception():
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return credentials_exception


def token_exception():
    token_exception_response = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return token_exception_response












