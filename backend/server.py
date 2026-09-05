#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
BRIDGE_DIR = ROOT / "b"
BASE_SERVER = BACKEND / "server.base.py"
DELTA_SHA256 = "2ada3f9179ae2911685f24f1c7ef7600f1e13bb53f340cd5f418c8673e911084"
BASE_TARGET_VERSION = "4.5.0"
TARGET_VERSION = "4.5.1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".p2u-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            try:
                os.fsync(fp.fileno())
            except OSError:
                pass
        try:
            os.chmod(tmp_name, 0o755 if executable else 0o644)
        except OSError:
            pass
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def apply_line_edits(old: bytes, payload: bytes) -> bytes:
    text = old.decode("utf-8")
    lines = text.splitlines(keepends=True)
    edits = json.loads(payload.decode("utf-8"))
    if not isinstance(edits, list):
        raise RuntimeError("ongeldig bridge line-edit formaat")
    for item in sorted(edits, key=lambda row: int(row[0]), reverse=True):
        if not isinstance(item, list) or len(item) != 3:
            raise RuntimeError("ongeldige bridge line-edit")
        start, end, replacement = int(item[0]), int(item[1]), str(item[2])
        if start < 0 or end < start or end > len(lines):
            raise RuntimeError("bridge line-edit valt buiten bestand")
        lines[start:end] = [replacement]
    return "".join(lines).encode("utf-8")


def read_delta() -> bytes:
    parts = []
    for index in range(10):
        part = BRIDGE_DIR / f"{index:02d}"
        if not part.is_file():
            raise RuntimeError(f"bridge payload ontbreekt: {part.name}")
        parts.append(part.read_bytes())
    data = b"".join(parts)
    if sha256_bytes(data) != DELTA_SHA256:
        raise RuntimeError("bridge payload SHA-256 klopt niet")
    return data


def patch_package() -> None:
    delta = read_delta()
    with zipfile.ZipFile(io.BytesIO(delta)) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if str(manifest.get("version") or "") != BASE_TARGET_VERSION:
            raise RuntimeError("bridge manifest heeft verkeerde doelversie")
        operations = manifest.get("operations")
        if not isinstance(operations, list):
            raise RuntimeError("bridge manifest bevat geen operations")

        for op in operations:
            rel = Path(str(op.get("path") or ""))
            if not rel.parts or rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError("onveilig bridge pad")
            target = ROOT / rel
            if rel.as_posix() == "VERSION":
                continue
            kind = str(op.get("kind") or "")
            payload = zf.read(str(op.get("payload") or ""))
            new_sha = str(op.get("new_sha256") or "").lower()

            if target.is_file() and sha256_bytes(target.read_bytes()) == new_sha:
                continue

            if kind == "add":
                new_data = payload
            elif kind == "line_edits":
                source = BASE_SERVER if rel.as_posix() == "backend/server.py" else target
                if not source.is_file():
                    raise RuntimeError(f"bridge basisbestand ontbreekt: {rel.as_posix()}")
                old = source.read_bytes()
                old_sha = str(op.get("old_sha256") or "").lower()
                if sha256_bytes(old) != old_sha:
                    raise RuntimeError(f"bridge basishash klopt niet: {rel.as_posix()}")
                new_data = apply_line_edits(old, payload)
            else:
                raise RuntimeError(f"onbekende bridge operatie: {kind}")

            if sha256_bytes(new_data) != new_sha:
                raise RuntimeError(f"bridge nieuwe hash klopt niet: {rel.as_posix()}")
            atomic_write(target, new_data, executable=target.suffix.lower() == ".sh")

        for op in operations:
            if str(op.get("path") or "") == "VERSION":
                continue
            target = ROOT / Path(str(op.get("path") or ""))
            if not target.is_file() or sha256_bytes(target.read_bytes()) != str(op.get("new_sha256") or "").lower():
                raise RuntimeError(f"bridge eindcontrole mislukt: {op.get('path')}")

    try:
        BASE_SERVER.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        shutil.rmtree(BRIDGE_DIR, ignore_errors=True)
    except Exception:
        pass


V451_SERVER_OLD_SHA256 = "63e5a4b3b9525040af930aa7b8c04e4141f7cdb30587fee144044f724ecf7e18"
V451_SERVER_NEW_SHA256 = "34cfa04906379cf6c07d3b49185cf9bb4be541fc9414807ff7f36cdb715766fc"
V451_SERVER_EDITS = [[17, 17, "import ast\n"], [128, 129, "APP_VERSION = \"4.5.1\"\n"], [786, 787, "def _api_mapping(value) -> dict | None:\n    \"\"\"Return a mapping for real or legacy stringified API objects.\"\"\"\n    if isinstance(value, dict):\n        return value\n    if isinstance(value, str):\n        text = value.strip()\n        if text.startswith(\"{\") and text.endswith(\"}\"):\n            try:\n                parsed = ast.literal_eval(text)\n            except (ValueError, SyntaxError):\n                parsed = None\n            if isinstance(parsed, dict):\n                return parsed\n    return None\n\n\ndef _api_text(value, *, nested_keys: tuple[str, ...] = (\"name\", \"label\", \"detail\", \"code\", \"city\", \"value\"), limit: int = 240) -> str:\n    \"\"\"Turn SW/API scalar or nested objects into human text, never a Python-dict repr.\"\"\"\n    mapping = _api_mapping(value)\n    if mapping is not None:\n        for key in nested_keys:\n            if key not in mapping:\n                continue\n            text = _api_text(mapping.get(key), nested_keys=nested_keys, limit=limit)\n            if text:\n                return text\n        return \"\"\n    if value is None or isinstance(value, (list, tuple, set)):\n        return \"\"\n    text = normalize_space(str(value))\n    if (text.startswith(\"{\") and text.endswith(\"}\")) or (text.startswith(\"[\") and text.endswith(\"]\")):\n        return \"\"\n    return text[:limit]\n\n\ndef _pick_text(row: dict, *keys: str, limit: int = 240, nested_keys: tuple[str, ...] = (\"name\", \"label\", \"detail\", \"code\", \"city\", \"value\")) -> str:\n"], [788, 791, "        text = _api_text(row.get(key), nested_keys=nested_keys, limit=limit)\n        if text:\n            return text\n"], [803, 808, "    function_code = _pick_text(row, \"function_code\", \"functionCode\", \"type_code\", \"type\", \"function\", limit=64, nested_keys=(\"code\", \"function_code\", \"type_code\", \"name\"))\n    function_name = _pick_text(row, \"function_name\", \"functionName\", \"function\", \"description\", \"label\", limit=180, nested_keys=(\"name\", \"label\", \"detail\", \"description\", \"code\"))\n    station_name = _pick_text(row, \"station_name\", \"stationName\", \"station\", \"post\", \"kazerne\", limit=160, nested_keys=(\"name\", \"station_name\", \"label\", \"city\", \"code\"))\n    region_code = _pick_text(row, \"region_code\", \"regionCode\", \"region\", limit=32, nested_keys=(\"code\", \"region_code\", \"name\"))\n    discipline = _pick_text(row, \"discipline\", limit=40, nested_keys=(\"name\", \"code\", \"label\"))\n"], [828, 828, "    station_obj = _api_mapping(row.get(\"station\")) or {}\n    function_obj = _api_mapping(row.get(\"function\")) or {}\n    if not canonical.get(\"station_code\"):\n        value = _pick_text(station_obj, \"code\", \"station_code\", limit=80, nested_keys=(\"code\", \"name\"))\n        if value: canonical[\"station_code\"] = value\n    if not canonical.get(\"city\"):\n        value = _pick_text(station_obj, \"city\", limit=120, nested_keys=(\"name\", \"city\", \"value\"))\n        if value: canonical[\"city\"] = value\n    if not canonical.get(\"function_detail\"):\n        value = _pick_text(function_obj, \"detail\", \"description\", limit=240, nested_keys=(\"detail\", \"description\", \"name\"))\n        if value: canonical[\"function_detail\"] = value\n"], [909, 910, "                _normalized_key, normalized_row = canonical_sw_unit(dict(row))\n                clean[lookup] = normalized_row if isinstance(normalized_row, dict) else dict(row)\n"], [932, 935, "        function_code = _api_text(unit.get(\"function_code\"), nested_keys=(\"code\", \"function_code\", \"type_code\", \"name\"), limit=64)\n        function_name = _api_text(unit.get(\"function_name\"), nested_keys=(\"name\", \"label\", \"detail\", \"code\"), limit=180)\n        station_name = _api_text(unit.get(\"station_name\"), nested_keys=(\"name\", \"station_name\", \"label\", \"city\", \"code\"), limit=160)\n"], [2988, 2991, "            code = _api_text((meta or {}).get(\"type\") or (meta or {}).get(\"function_code\"), nested_keys=(\"code\", \"function_code\", \"type\", \"name\"), limit=64).upper()\n            label = _api_text((meta or {}).get(\"function_name\") or (meta or {}).get(\"label\"), nested_keys=(\"name\", \"label\", \"detail\", \"code\"), limit=180)\n            station = _api_text((meta or {}).get(\"station_name\") or (meta or {}).get(\"station\"), nested_keys=(\"name\", \"station_name\", \"label\", \"city\", \"code\"), limit=160)\n"]]


def apply_v451_hotfix() -> None:
    server = BACKEND / "server.py"
    old = server.read_bytes()
    if sha256_bytes(old) == V451_SERVER_NEW_SHA256:
        atomic_write(ROOT / "VERSION", b"4.5.1\n")
        return
    if sha256_bytes(old) != V451_SERVER_OLD_SHA256:
        raise RuntimeError("v4.5.1 hotfix basis-server heeft onverwachte SHA-256")
    payload = json.dumps(V451_SERVER_EDITS, ensure_ascii=False).encode("utf-8")
    new_data = apply_line_edits(old, payload)
    if sha256_bytes(new_data) != V451_SERVER_NEW_SHA256:
        raise RuntimeError("v4.5.1 hotfix server SHA-256 klopt niet")
    atomic_write(server, new_data)
    atomic_write(ROOT / "VERSION", b"4.5.1\n")


def main() -> None:
    try:
        patch_package()
        apply_v451_hotfix()
    except Exception as exc:
        print(f"P2000 v4.5.1 compatibility bridge mislukt: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(42)

    server = BACKEND / "server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server), *sys.argv[1:]],
        cwd=str(ROOT),
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=os.environ.copy(),
    )
    raise SystemExit(proc.wait())


if __name__ == "__main__":
    main()
