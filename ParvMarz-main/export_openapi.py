"""Export the API docs offline (no server, DB or scheduler needed), like PasarGuard's export_openapi.py.

Usage:  python export_openapi.py            -> docs/openapi.json + docs/API-reference-fa.md
        python export_openapi.py --agent    -> same, but only the endpoints an agent/API key may call
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from app.core.apidocs import build_schema, to_markdown
    from app.main import app
    agent = "--agent" in sys.argv
    schema = build_schema(app, agent=agent)
    out = Path(__file__).resolve().parent / "docs"; out.mkdir(exist_ok=True)
    suffix = "-agent" if agent else ""
    (out / f"openapi{suffix}.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / f"API-reference-fa{suffix}.md").write_text(to_markdown(schema), encoding="utf-8")
    print(f"wrote docs/openapi{suffix}.json and docs/API-reference-fa{suffix}.md ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
