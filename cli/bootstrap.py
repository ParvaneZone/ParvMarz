"""Standalone (must not import app.*, settings are invalid before this runs)."""
import base64, json, os, secrets
from pathlib import Path
def main():
    """Print `export` lines with auto-generated secrets (used by the Docker entrypoint)."""
    store = Path(os.environ.get("DATA_DIR", "data")) / "secrets.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(store.read_text()) if store.exists() else {}
    changed = False

    def bad(v: str) -> bool:
        return not v or v.startswith(("replace-with", "development-only", "change-me"))

    out: dict[str, str] = {}
    for key, gen in (("JWT_SECRET", lambda: secrets.token_hex(32)),
                     ("SUBSCRIPTION_HMAC_KEY", lambda: secrets.token_hex(32)),
                     ("CREDENTIALS_ENCRYPTION_KEY", lambda: base64.urlsafe_b64encode(os.urandom(32)).decode())):
        cur = os.environ.get(key, "")
        valid = not bad(cur) and (key == "CREDENTIALS_ENCRYPTION_KEY" or len(cur) >= 32)
        if key == "CREDENTIALS_ENCRYPTION_KEY" and valid:
            try:
                from cryptography.fernet import Fernet
                Fernet(cur.encode())
            except Exception:
                valid = False
        if valid:
            continue
        if key not in saved:
            saved[key] = gen(); changed = True
        out[key] = saved[key]
    if not os.environ.get("INITIAL_ADMIN_USERNAME"):
        out["INITIAL_ADMIN_USERNAME"] = "admin"
    if not os.environ.get("INITIAL_ADMIN_PASSWORD"):
        if "admin_password" not in saved:
            saved["admin_password"] = secrets.token_urlsafe(12); changed = True
            f = store.parent / "initial-admin.txt"
            f.write_text(f"username: {out.get('INITIAL_ADMIN_USERNAME') or os.environ['INITIAL_ADMIN_USERNAME']}\npassword: {saved['admin_password']}\n")
            f.chmod(0o600)
        out["INITIAL_ADMIN_PASSWORD"] = saved["admin_password"]
    port = os.environ.get("PORT", "8000")
    url = os.environ.get("PUBLIC_BASE_URL", "")
    if not url or "subhub.example.com" in url:
        out["PUBLIC_BASE_URL"] = url = f"http://localhost:{port}"
    cors = os.environ.get("CORS_ORIGINS", "")
    if not cors or "subhub.example.com" in cors:
        out["CORS_ORIGINS"] = url
    if changed:
        store.write_text(json.dumps(saved)); store.chmod(0o600)
    for k, v in out.items():
        print(f"export {k}='{v}'")


if __name__ == "__main__":
    main()
