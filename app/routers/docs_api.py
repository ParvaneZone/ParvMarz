from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from app.core.apidocs import build_schema, to_markdown
from app.core.security import current_admin
from app.db.models import Admin
from app.schemas import errs

router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.get("/openapi.json", summary="اسکیمای OpenAPI (فقط با توکن/کلید معتبر)",
            description="مدیر اصلی اسکیمای کامل و نماینده فقط مسیرهای مخصوص نماینده را می‌بیند.", responses=errs(401))
def openapi_json(request: Request, admin: Admin = Depends(current_admin)):
    return build_schema(request.app, agent=admin.role != "sudo")


@router.get("/api.md", response_class=PlainTextResponse, summary="مستندات Markdown فارسی", responses=errs(401))
def openapi_markdown(request: Request, admin: Admin = Depends(current_admin)):
    return to_markdown(build_schema(request.app, agent=admin.role != "sudo"))
