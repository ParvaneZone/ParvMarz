import os
import ssl
import sys
import urllib.request


def main() -> None:
    port = os.environ.get("PANEL_LISTEN_PORT", "8000")
    ctx = ssl._create_unverified_context()
    for scheme in ("https", "http"):
        try:
            urllib.request.urlopen(f"{scheme}://127.0.0.1:{port}/health", timeout=4, context=ctx if scheme == "https" else None)
            sys.exit(0)
        except Exception:
            continue
    sys.exit(1)


if __name__ == "__main__":
    main()
