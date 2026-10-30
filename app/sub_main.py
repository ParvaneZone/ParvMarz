"""Subscription-only app (own port). Knows nothing about the panel: no /api, no dashboard, no docs, no root page."""
from fastapi import FastAPI
from app.config import settings
from app.core.hardening import HostGuard, BlockSensitive, InputGuard, SecureHeaders
from app.routers import subscription

sub_app = FastAPI(title="sub", docs_url=None, redoc_url=None, openapi_url=None)
sub_app.include_router(subscription.router)
sub_app.add_middleware(SecureHeaders, hsts=bool(settings.sub_domain))
sub_app.add_middleware(InputGuard)
sub_app.add_middleware(BlockSensitive)
sub_app.add_middleware(HostGuard, domain=settings.sub_domain, allow_paths=())
