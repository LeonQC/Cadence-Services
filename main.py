from contextlib import asynccontextmanager

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import deps
import models
import redis_cache
from database import engine, ensure_compatibility_columns
from routers import api, auth, github_webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    if await redis_cache.ping():
        print(f"Redis connected: {redis_cache.REDIS_URL}", flush=True)
    else:
        print("Redis unavailable - running without cache", flush=True)
    yield
    await redis_cache.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "TODOAPP_CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)
ensure_compatibility_columns()

app.include_router(auth.router)
app.include_router(github_webhooks.router)
app.include_router(api.router)


# The dependencies in deps.py raise instead of returning an error response, so
# a route can never carry on past a failed check. Turning those into responses
# happens once, here.

def _is_api_client(request: Request):
    """API-key callers want a status code; browsers want somewhere to go."""
    return (request.headers.get("Authorization", "").startswith("Bearer ")
            or request.url.path.startswith("/api/"))


@app.exception_handler(deps.NotAuthenticated)
async def handle_not_authenticated(request: Request, exc: deps.NotAuthenticated):
    return JSONResponse({"detail": "Not authenticated"}, status_code=401)


@app.exception_handler(deps.NoWorkspace)
async def handle_no_workspace(request: Request, exc: deps.NoWorkspace):
    return JSONResponse({"detail": "Account has no workspace"}, status_code=409)


@app.exception_handler(deps.Forbidden)
async def handle_forbidden(request: Request, exc: deps.Forbidden):
    return JSONResponse({"detail": exc.detail}, status_code=403)
