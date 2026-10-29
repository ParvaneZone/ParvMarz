from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.db.session import Base, engine, SessionLocal
from app.db.models import Admin
from app.core.security import hash_password
from app.routers import auth, panels, system, subscription, admins, services, users, templates, bulk, inbounds, usage, ops, api_keys, docs_api
from app.jobs.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.initial_admin_username and settings.initial_admin_password:
        with SessionLocal() as db:
            existing = db.query(Admin).filter(Admin.username == settings.initial_admin_username).first()
            if not existing:
                db.add(Admin(username=settings.initial_admin_username,
                             password_hash=hash_password(settings.initial_admin_password),
                             role="sudo", permissions={"*": True}, allowed_services=[]))
                db.commit()
    if settings.environment != "test":
        start_scheduler()
    yield
    if settings.environment != "test":
        stop_scheduler()

app = FastAPI(title=settings.app_name, docs_url="/docs" if settings.openapi_enabled else None,
              openapi_url="/openapi.json" if settings.openapi_enabled else None,
              redoc_url="/redoc" if settings.openapi_enabled else None, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"],
                   allow_headers=["Authorization","Content-Type","Accept-Language"])
app.include_router(auth.router)
app.include_router(panels.router)
app.include_router(system.router)
app.include_router(subscription.router)
app.include_router(admins.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(templates.router)
app.include_router(bulk.router)
app.include_router(inbounds.router)
app.include_router(usage.router)
app.include_router(ops.router)
app.include_router(api_keys.router)
app.include_router(docs_api.router)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.get("/", include_in_schema=False)
def root():
    return {"service": settings.app_name, "dashboard": "/dashboard/"}

_dist = Path(__file__).parent / "dashboard" / "dist"
if (_dist / "assets").is_dir():
    app.mount("/dashboard/assets", StaticFiles(directory=_dist / "assets"), name="dashboard-assets")


@app.get("/health", include_in_schema=False)
def health_simple():
    return {"status": "ok"}


@app.api_route("/dashboard/", methods=["GET", "HEAD"], include_in_schema=False)
def dashboard():
    index = Path(__file__).parent / "dashboard" / "dist" / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Dashboard is not built yet", "build": "cd app/dashboard && npm ci && npm run build"}
