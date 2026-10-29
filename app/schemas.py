"""Typed request/response models used for the OpenAPI documentation.
Responses allow extra keys and routes use exclude_unset where a key may be absent, so the JSON
on the wire stays exactly what the dashboard already receives."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class ErrorDetail(BaseModel):
    detail: str = Field(description="پیام خطا (فارسی)")
    code: str = Field(description="کد ماشینی خطا", examples=["USER_NOT_FOUND"])


class ErrorOut(BaseModel):
    detail: ErrorDetail


_ERR = {401: "احراز هویت لازم است یا توکن/کلید نامعتبر است", 403: "دسترسی یا سهمیه کافی نیست",
        404: "مورد پیدا نشد", 409: "تداخل یا وضعیت نامناسب", 429: "تلاش بیش از حد"}


def errs(*codes: int) -> dict:
    return {c: {"model": ErrorOut, "description": _ERR[c]} for c in codes}


class OkOut(_Out):
    ok: bool = True


class TokenOut(_Out):
    access_token: str | None = Field(default=None, description="توکن Bearer (JWT)")
    token_type: str | None = Field(default=None, examples=["bearer"])
    two_factor_required: bool | None = Field(default=None, description="اگر true بود، همین درخواست را با فیلد otp تکرار کنید")


class WhoAmIOut(_Out):
    id: int
    username: str
    role: str = Field(description="sudo یا admin")
    permissions: dict[str, Any] | None = None
    totp_enabled: bool


class TrafficOut(_Out):
    total: int | None = Field(description="سقف کل حجم؛ null = نامحدود")
    used: int
    remaining: int | None
    allocated: int = Field(description="مجموع حجم داده‌شده به کاربران")
    unallocated: int | None
    unlimited_users: int


class UsersStatOut(_Out):
    count: int
    max: int | None
    by_status: dict[str, int]


class LimitsOut(_Out):
    max_user_traffic: int | None
    max_user_days: int | None


class ServiceBrief(_Out):
    id: int
    name: str


class AccountOut(_Out):
    id: int
    username: str
    role: str
    disabled: bool
    created_at: datetime
    expire: datetime | None
    days_left: int | None
    totp_enabled: bool
    recovery_codes_left: int
    traffic: TrafficOut
    users: UsersStatOut
    limits: LimitsOut
    services: list[ServiceBrief]


class UserOut(_Out):
    id: int
    username: str
    admin_id: int
    service_id: int
    status: str = Field(description="active | disabled | limited | expired | on_hold")
    data_limit: int | float | None = Field(description="حجم به بایت؛ null = نامحدود")
    used_traffic: int = Field(description="مصرف به بایت")
    expire: datetime | None
    note: str
    created_at: datetime
    subscription_url: str | None = Field(description="مسیر لینک اشتراک (مثلاً /sub/...)؛ بدون دسترسی users.view_sub برابر null")


class UserListOut(_Out):
    total: int
    items: list[UserOut]


class UserUpdate(BaseModel):
    """فقط فیلدهای ارسال‌شده تغییر می‌کنند؛ فیلد ناشناخته با 422 رد می‌شود."""
    model_config = ConfigDict(extra="allow")
    status: str | None = None
    data_limit: int | float | None = Field(default=None, description="بایت؛ null = نامحدود (نیازمند دسترسی)")
    expire: datetime | None = Field(default=None, description="null = بدون انقضا (نیازمند دسترسی)")
    note: str | None = None
    data_limit_reset_strategy: str | None = None
    next_plan: dict[str, Any] | None = None
    on_hold_expire_duration: int | None = None
    on_hold_timeout: datetime | None = None


class BulkItem(_Out):
    username: str
    subscription_url: str | None


class BulkCreateOut(_Out):
    created: list[BulkItem]
    failed_at: str | None = None
    error: Any = None


class UsageLogOut(_Out):
    delta: int
    total_after: int
    recorded_at: datetime


class UserUsageOut(_Out):
    used_traffic: int
    data_limit: int | float | None
    logs: list[UsageLogOut]


class LastTaskOut(_Out):
    action: str
    state: str
    attempts: int
    error: str | None


class SyncAccountOut(_Out):
    panel: str | int
    panel_status: str | None
    remote_username: str
    sync_state: str
    last_task: LastTaskOut | None


class SyncStatusOut(_Out):
    username: str
    status: str
    accounts: list[SyncAccountOut]


class ServiceOut(_Out):
    id: int
    name: str
    display_name: str
    description: str
    enabled: bool
    sort_order: int
    sub_remark_template: str
    inbound_mode: str = "all"
    inbound_interval: int = 60
    inbound_count: int = 1
    items: list[dict[str, Any]] = Field(description="برای sudo جزئیات پنل‌ها؛ برای نماینده همیشه خالی")
    inbound_names: list[str] | None = Field(default=None, description="فقط برای نماینده")


class TemplateOut(_Out):
    id: int
    name: str
    service_id: int
    data_limit: int | None
    duration: int | None
    username_prefix: str
    username_suffix: str
    reset_strategy: str
    add_remaining_traffic: bool


class UsageRowOut(_Out):
    t: str = Field(description="برچسب بازه (YYYY-MM-DD یا YYYY-MM-DDTHH:00) به وقت tz_offset")
    admin: int | None
    panel: int | None
    service: int | None
    bytes: int


class UsageReportOut(_Out):
    bucket: str
    total: int
    rows: list[UsageRowOut]
    admins: dict[str, str]
    panels: dict[str, str]
    services: dict[str, str]
    deleted: dict[str, list[int]]


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["telegram-bot"])
    expire_days: int | None = Field(default=None, ge=1, le=3650, description="خالی = بدون انقضا")


class ApiKeyOut(_Out):
    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    expire: datetime | None
    revoked: bool


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="کلید کامل؛ فقط همین یک‌بار نمایش داده می‌شود")
