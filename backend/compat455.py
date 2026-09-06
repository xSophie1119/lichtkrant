#!/usr/bin/env python3
"""Byte-checked v4.5.5 layer, preserved as the proven compatibility baseline."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPAT454_PATH = HERE / "compat454.py"

spec = importlib.util.spec_from_file_location("p2000_compat454", COMPAT454_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("v4.5.4 compatibility bridge kon niet worden geladen")
compat454 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat454)
compat = compat454.compat

_apply_v454 = compat.apply_v451_hotfix

V454_SERVER_SHA = "2a5654899bcb6ebfa2309297d53d2cceab961936d57d72fa0eefc730f8318a45"
V455_SERVER_SHA = "aa98643455b9d2a26dfe49ad223b449f576137e3fb59e183f1913013a82ae95a"
V454_APP_SHA = "8c8d326b4c08f54b7da584b7cfc2aeb36a499dde866197b76c8b6f520d9bd7ad"
V455_APP_SHA = "915ee43a84f259e92bab133dbc05d496e8aa3b0bc9744e9fbbf94308df09a0fb"
V454_INDEX_SHA = "84b57f64a78e2d10b0bac85b3b73a5b9f495e7da3c42d3dfb518bafcb87185da"
PARSER_SHA = "c3e9f1e959e928463396316f59b801a0b6b15d2f5bca47c06aca8b1741e51405"

INSTALL_BLOCK = '''# v4.5.5: landelijke grammatica-/fallbackparser. Fail-open: een defect in deze\n# optionele laag mag nooit voorkomen dat de lichtkrant zelf start.\ntry:\n    from parser_nl_v455 import install_national_parser\n    install_national_parser(globals())\nexcept Exception as exc:\n    print(f"Waarschuwing: landelijke parserlaag v4.5.5 niet geladen: {exc}", file=sys.stderr, flush=True)\n\n\n'''


def _sha(path: Path) -> str:
    return compat.sha256_bytes(path.read_bytes())


def _apply_v455_hotfix() -> None:
    _apply_v454()

    parser = HERE / "parser_nl_v455.py"
    if not parser.is_file() or _sha(parser) != PARSER_SHA:
        raise RuntimeError("v4.5.5 landelijke parsermodule ontbreekt of heeft onverwachte SHA-256")

    server = HERE / "server.py"
    server_sha = _sha(server)
    if server_sha == V454_SERVER_SHA:
        text = server.read_text(encoding="utf-8")
        if text.count('APP_VERSION = "4.5.4"') != 1:
            raise RuntimeError("v4.5.5 kon backendversie niet eenduidig vervangen")
        text = text.replace('APP_VERSION = "4.5.4"', 'APP_VERSION = "4.5.5"', 1)
        marker = "def main():\n"
        if text.count(marker) != 1:
            raise RuntimeError("v4.5.5 kon parserinstallatiepunt niet eenduidig vinden")
        text = text.replace(marker, INSTALL_BLOCK + marker, 1)
        data = text.encode("utf-8")
        if compat.sha256_bytes(data) != V455_SERVER_SHA:
            raise RuntimeError("v4.5.5 backend eindhash klopt niet")
        compat.atomic_write(server, data)
    elif server_sha != V455_SERVER_SHA:
        raise RuntimeError("v4.5.5 basis-server heeft onverwachte SHA-256")

    app = ROOT / "frontend" / "app.js"
    app_sha = _sha(app)
    if app_sha == V454_APP_SHA:
        text = app.read_text(encoding="utf-8")
        old = "const CLIENT_VERSION='4.5.4';"
        new = "const CLIENT_VERSION='4.5.5';"
        if text.count(old) != 1:
            raise RuntimeError("v4.5.5 kon frontendversie niet eenduidig vervangen")
        data = text.replace(old, new, 1).encode("utf-8")
        if compat.sha256_bytes(data) != V455_APP_SHA:
            raise RuntimeError("v4.5.5 app.js eindhash klopt niet")
        compat.atomic_write(app, data)
    elif app_sha != V455_APP_SHA:
        raise RuntimeError("v4.5.5 basis-app.js heeft onverwachte SHA-256")

    index = ROOT / "frontend" / "index.html"
    if _sha(index) != V454_INDEX_SHA:
        raise RuntimeError("v4.5.5 index.html heeft onverwachte SHA-256")

    compat.atomic_write(ROOT / "VERSION", b"4.5.5\n")


def _apply_v454_then_v455() -> None:
    _apply_v455_hotfix()


compat.apply_v451_hotfix = _apply_v454_then_v455
compat.TARGET_VERSION = "4.5.5"
