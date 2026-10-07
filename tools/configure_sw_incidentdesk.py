#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "secrets" / "sw-incidentdesk.json"
DEFAULT_ENDPOINT = "https://swmediaproducties.nl/api/p2000-ingest.php"


def private_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.parent.chmod(0o700)
        path.chmod(0o600)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Koppel P2000 Monitor aan de SW Mediaproducties Incidentdesk.")
    parser.add_argument("--url", default=DEFAULT_ENDPOINT, help="HTTPS ingest-endpoint")
    parser.add_argument("--disable", action="store_true", help="Schakel de bridge uit zonder de token te verwijderen")
    args = parser.parse_args()

    existing = {}
    if TARGET.exists():
        try:
            parsed = json.loads(TARGET.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                existing = parsed
        except Exception:
            pass

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if args.disable:
        existing["enabled"] = False
        existing.setdefault("url", args.url)
        TARGET.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        private_permissions(TARGET)
        print("SW Incidentdesk bridge uitgeschakeld.")
        return

    endpoint = (args.url or existing.get("url") or DEFAULT_ENDPOINT).strip()
    if not endpoint.startswith("https://"):
        raise SystemExit("Fout: gebruik een HTTPS-endpoint.")

    token = getpass.getpass("SW Incidentdesk Bearer token: ").strip()
    if not token:
        token = str(existing.get("token") or "").strip()
    if not token:
        raise SystemExit("Fout: geen token opgegeven.")

    TARGET.write_text(json.dumps({
        "enabled": True,
        "url": endpoint,
        "token": token,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    private_permissions(TARGET)
    print(f"Bridge actief: {endpoint}")
    print("Herstart de P2000 Monitor zodat de status direct zichtbaar is.")


if __name__ == "__main__":
    main()
