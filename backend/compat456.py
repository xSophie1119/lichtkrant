#!/usr/bin/env python3
"""v4.5.6 layer applied strictly after the proven v4.5.5 build."""
from __future__ import annotations

import importlib.util
import io
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPAT455_PATH = HERE / "compat455.py"

spec = importlib.util.spec_from_file_location("p2000_compat455", COMPAT455_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("v4.5.5 compatibility bridge kon niet worden geladen")
compat455 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat455)
compat = compat455.compat
_apply_v455 = compat.apply_v451_hotfix

V455_SERVER_SHA = compat455.V455_SERVER_SHA
V455_APP_SHA = compat455.V455_APP_SHA
V454_INDEX_SHA = compat455.V454_INDEX_SHA

# Exact post-v4.5.5 artifacts that are allowed to coexist with the old bridge
# payload. This does NOT weaken the bridge globally: only these exact SHA-256
# values may bypass a legacy line-edit operation. backend/server.py and app.js
# are deliberately excluded so they must still traverse the proven chain.
POST_V455_ARTIFACTS = {
    "START_P2000.bat": "b82a5c44612ecf10636bb3ecb825a6b8ffd83407e71063bc98e98ffe41861b4f",
    "RUN_BACKEND.bat": "f25e62ead2581230a839b469cf5b2aebc4751c82f7c09f1dac70ad7cc3b45686",
    "STOP_P2000.bat": "37e0ae8eb85dae6fa8e8257342167e6ae792f1b107b48310805bf798a6154ee4",
    "START_P2000_DEBUG.bat": "7d541fef3a7be46dcc0e855174d1df124ec62479001c1af45607edfdabf41b83",
    "tools/runtime_probe.py": "8c1d770eac0414f4792dc9bba10f67cd236feb23ac9e96fe122341e60769523f",
    "tools/supervisor.py": "fe18cd308275668e6bace4acc36bd7454657721556f04a63502b64eaf1ac0f57",
    "tools/rollback_latest.py": "ea607cd622700bc6256937845b1c9178c67b1eb5d62005aa8b7ff0f54690a00e",
}


def _approved_post_v455(rel: str, target: Path) -> bool:
    expected = POST_V455_ARTIFACTS.get(rel)
    return bool(expected and target.is_file() and compat.sha256_bytes(target.read_bytes()) == expected)


def _patch_package_v456() -> None:
    """Run the legacy bridge while preserving only exact approved v4.5.6 artifacts."""
    delta = compat.read_delta()
    with zipfile.ZipFile(io.BytesIO(delta)) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if str(manifest.get("version") or "") != compat.BASE_TARGET_VERSION:
            raise RuntimeError("bridge manifest heeft verkeerde doelversie")
        operations = manifest.get("operations")
        if not isinstance(operations, list):
            raise RuntimeError("bridge manifest bevat geen operations")

        for op in operations:
            rel = Path(str(op.get("path") or ""))
            if not rel.parts or rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError("onveilig bridge pad")
            rel_text = rel.as_posix()
            target = ROOT / rel
            if rel_text == "VERSION":
                continue
            if _approved_post_v455(rel_text, target):
                continue
            kind = str(op.get("kind") or "")
            payload = zf.read(str(op.get("payload") or ""))
            new_sha = str(op.get("new_sha256") or "").lower()
            if target.is_file() and compat.sha256_bytes(target.read_bytes()) == new_sha:
                continue
            if kind == "add":
                new_data = payload
            elif kind == "line_edits":
                source = compat.BASE_SERVER if rel_text == "backend/server.py" else target
                if not source.is_file():
                    raise RuntimeError(f"bridge basisbestand ontbreekt: {rel_text}")
                old = source.read_bytes()
                old_sha = str(op.get("old_sha256") or "").lower()
                if compat.sha256_bytes(old) != old_sha:
                    raise RuntimeError(f"bridge basishash klopt niet: {rel_text}")
                new_data = compat.apply_line_edits(old, payload)
            else:
                raise RuntimeError(f"onbekende bridge operatie: {kind}")
            if compat.sha256_bytes(new_data) != new_sha:
                raise RuntimeError(f"bridge nieuwe hash klopt niet: {rel_text}")
            compat.atomic_write(target, new_data, executable=target.suffix.lower() == ".sh")

        for op in operations:
            rel_text = str(op.get("path") or "")
            if rel_text == "VERSION":
                continue
            target = ROOT / Path(rel_text)
            expected = str(op.get("new_sha256") or "").lower()
            if target.is_file() and compat.sha256_bytes(target.read_bytes()) == expected:
                continue
            if _approved_post_v455(rel_text, target):
                continue
            raise RuntimeError(f"bridge eindcontrole mislukt: {rel_text}")

    try:
        compat.BASE_SERVER.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        shutil.rmtree(compat.BRIDGE_DIR, ignore_errors=True)
    except Exception:
        pass


compat.patch_package = _patch_package_v456


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f"v4.5.6 kon {label} niet eenduidig vinden")
    return text.replace(old, new, 1)


def _patch_optional_text(path: Path, replacements: list[tuple[str, str, str]]) -> None:
    if not path.is_file():
        raise RuntimeError(f"v4.5.6 bestand ontbreekt: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new, label in replacements:
        if new in text and old not in text:
            continue
        if old in text:
            if text.count(old) != 1:
                raise RuntimeError(f"v4.5.6 vond {label} meerdere keren")
            text = text.replace(old, new, 1)
            changed = True
    if changed:
        compat.atomic_write(path, text.encode("utf-8"))


def _apply_v456_hotfix() -> None:
    # Build and verify exactly the field-tested v4.5.5 runtime first.
    _apply_v455()

    server = HERE / "server.py"
    server_data = server.read_bytes()
    if compat.sha256_bytes(server_data) != V455_SERVER_SHA:
        raise RuntimeError("v4.5.6 basis-server is niet exact de bewezen v4.5.5-uitvoer")
    server_text = _replace_once(server_data.decode("utf-8"), 'APP_VERSION = "4.5.5"', 'APP_VERSION = "4.5.6"', "backendversie")
    compat.atomic_write(server, server_text.encode("utf-8"))

    app = ROOT / "frontend" / "app.js"
    app_data = app.read_bytes()
    if compat.sha256_bytes(app_data) != V455_APP_SHA:
        raise RuntimeError("v4.5.6 basis-app.js is niet exact de bewezen v4.5.5-uitvoer")
    app_text = _replace_once(app_data.decode("utf-8"), "const CLIENT_VERSION='4.5.5';", "const CLIENT_VERSION='4.5.6';", "frontendversie")
    compat.atomic_write(app, app_text.encode("utf-8"))

    index = ROOT / "frontend" / "index.html"
    if compat.sha256_bytes(index.read_bytes()) != V454_INDEX_SHA:
        raise RuntimeError("v4.5.6 index.html wijkt af van de bewezen v4.5.5-basis")

    # These files are intentionally patched only after the SHA-checked chain.
    _patch_optional_text(
        ROOT / "frontend" / "setup.html",
        [
            ('<div class="version-badge">v4.4.19</div>', '<div class="version-badge">v4.5.6</div>', "setup-versiebadge v4.4.19"),
            ('<div class="version-badge">v4.5.1</div>', '<div class="version-badge">v4.5.6</div>', "setup-versiebadge v4.5.1"),
            ('<div class="version-badge">v4.5.5</div>', '<div class="version-badge">v4.5.6</div>', "setup-versiebadge v4.5.5"),
        ],
    )
    _patch_optional_text(
        ROOT / "frontend" / "control.js",
        [
            ("setText('#vehicleVersion',st.version||'4.4.19');", "setText('#vehicleVersion',st.version||'4.5.6');", "control.js voertuigversie v4.4.19"),
            ("setText('#vehicleVersion',st.version||'4.5.1');", "setText('#vehicleVersion',st.version||'4.5.6');", "control.js voertuigversie v4.5.1"),
            ("setText('#vehicleVersion',st.version||'4.5.5');", "setText('#vehicleVersion',st.version||'4.5.6');", "control.js voertuigversie v4.5.5"),
        ],
    )
    _patch_optional_text(
        ROOT / "ENSURE_PYTHON.bat",
        [("rem P2000 Monitor v4.2.0 - Python bootstrap", "rem P2000 Monitor v4.5.6 - Python bootstrap", "Windows Python-bootstrap branding")],
    )
    _patch_optional_text(
        ROOT / "ENSURE_PYTHON.ps1",
        [("P2000-Monitor-Windows/4.2.0", "P2000-Monitor-Windows/4.5.6", "PowerShell bootstrap User-Agent")],
    )

    compat.atomic_write(ROOT / "VERSION", b"4.5.6\n")


def _apply_v455_then_v456() -> None:
    _apply_v456_hotfix()


compat.apply_v451_hotfix = _apply_v455_then_v456
compat.TARGET_VERSION = "4.5.6"
