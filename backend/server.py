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
TARGET_VERSION = "4.5.0"


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
        if str(manifest.get("version") or "") != TARGET_VERSION:
            raise RuntimeError("bridge manifest heeft verkeerde doelversie")
        operations = manifest.get("operations")
        if not isinstance(operations, list):
            raise RuntimeError("bridge manifest bevat geen operations")

        for op in operations:
            rel = Path(str(op.get("path") or ""))
            if not rel.parts or rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError("onveilig bridge pad")
            target = ROOT / rel
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


def main() -> None:
    try:
        patch_package()
    except Exception as exc:
        print(f"P2000 v4.5.0 compatibility bridge mislukt: {exc}", file=sys.stderr, flush=True)
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
