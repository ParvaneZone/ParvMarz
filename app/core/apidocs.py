"""Private API documentation: role-filtered OpenAPI + Persian Markdown. Nothing here is public."""
import copy

_AGENT_EXACT = {("post", "/api/admin/token"), ("get", "/api/admin"), ("get", "/api/admin/account"),
                ("get", "/api/services"), ("get", "/api/templates"), ("post", "/api/user"),
                ("get", "/api/users"), ("post", "/api/users/bulk-create")}


def agent_allows(method: str, path: str) -> bool:
    if (method, path) in _AGENT_EXACT:
        return True
    if path.startswith("/api/user/") and not path.endswith("/set-owner"):
        return True
    return path.startswith("/api/admin/api-keys")


def _refs(obj, acc: set):
    if isinstance(obj, dict):
        r = obj.get("$ref")
        if isinstance(r, str) and r.startswith("#/components/schemas/"):
            acc.add(r.rsplit("/", 1)[1])
        for v in obj.values():
            _refs(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _refs(v, acc)


def build_schema(app, agent: bool) -> dict:
    schema = copy.deepcopy(app.openapi())
    if not agent:
        return schema
    paths = {}
    for path, ops in schema.get("paths", {}).items():
        kept = {m: o for m, o in ops.items() if agent_allows(m.lower(), path)}
        if kept:
            paths[path] = kept
    schema["paths"] = paths
    comps = schema.get("components", {}).get("schemas", {})
    need: set = set(); _refs(paths, need)
    todo = list(need)
    while todo:
        name = todo.pop()
        sub: set = set(); _refs(comps.get(name, {}), sub)
        for n in sub - need:
            need.add(n); todo.append(n)
    if "components" in schema:
        schema["components"]["schemas"] = {k: v for k, v in comps.items() if k in need}
    return schema


def _ty(s: dict) -> str:
    if not isinstance(s, dict): return "any"
    if "$ref" in s: return s["$ref"].rsplit("/", 1)[1]
    for k in ("anyOf", "oneOf"):
        if k in s: return " | ".join(dict.fromkeys(_ty(x) for x in s[k]))
    t = s.get("type")
    if t == "array": return f"list[{_ty(s.get('items', {}))}]"
    if t == "object" and "additionalProperties" in s and isinstance(s["additionalProperties"], dict): return f"dict[str, {_ty(s['additionalProperties'])}]"
    return (t or "any") + (f"({s['format']})" if s.get("format") else "")


def _fields(name: str, comps: dict) -> list[str]:
    sch = comps.get(name, {}); req = set(sch.get("required", []))
    return [f"  - `{k}` ({_ty(v)}){' *الزامی*' if k in req else ''}{' — ' + v['description'] if v.get('description') else ''}"
            for k, v in sch.get("properties", {}).items()]


def to_markdown(schema: dict, title: str = "مستندات API") -> str:
    comps = schema.get("components", {}).get("schemas", {})
    out = [f"# {title}", "",
           "## احراز هویت",
           "- ورود: `POST /api/admin/token` با `{username, password}` (و `otp` در صورت فعال بودن 2FA) ← `access_token`؛ ارسال با هدر `Authorization: Bearer <token>`.",
           "- برای ربات‌ها: کلید API (`pmk_...`) با هدر `X-API-Key: <key>` یا `Authorization: Bearer <key>`. ساخت: `POST /api/admin/api-keys`.",
           "- کلید API فقط همان دسترسی‌های ادمین صاحبش را دارد و نمی‌تواند رمز/2FA/کلیدها را مدیریت کند.", "",
           "## قالب خطا", "همه خطاها: `{\"detail\": {\"detail\": \"پیام\", \"code\": \"CODE\"}}`. خطای اعتبارسنجی ورودی (422) قالب استاندارد FastAPI دارد.", ""]
    for path, ops in schema.get("paths", {}).items():
        for method, op in ops.items():
            out += [f"## `{method.upper()} {path}`", op.get("summary", "") or ""]
            if op.get("description"): out.append(op["description"])
            params = [p for p in op.get("parameters", []) if p.get("name", "").lower() != "x-api-key"]
            if params:
                out.append("**پارامترها:**")
                out += [f"- `{p['name']}` ({p['in']}, {_ty(p.get('schema', {}))}){' *الزامی*' if p.get('required') else ''}" for p in params]
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            if body:
                n = _ty(body); out.append(f"**بدنه:** `{n}`"); out += _fields(n, comps)
            for code, r in op.get("responses", {}).items():
                sch = r.get("content", {}).get("application/json", {}).get("schema")
                out.append(f"- **{code}**: {r.get('description', '')}" + (f" — `{_ty(sch)}`" if sch else ""))
                if sch and code.startswith("2"):
                    inner = sch.get("items", sch)
                    if "$ref" in inner: out += _fields(_ty(inner), comps)
            out.append("")
    return "\n".join(out)
