from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "https://swmediaproducties.nl/api/p2000-ingest.php"


class SWIncidentBridge:
    """Best-effort, non-blocking push bridge to the SW Incidentdesk.

    Secrets stay local in data/secrets/sw-incidentdesk.json. Feed ingestion never
    waits for SW: messages are placed on a bounded queue and delivered by one
    background worker.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.secret_path = self.root / "data" / "secrets" / "sw-incidentdesk.json"
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._config_mtime = -1.0
        self._config: dict[str, Any] = {}
        self.sent = 0
        self.failed = 0
        self.dropped = 0
        self.last_error = ""
        self.last_success_at = ""
        self._thread = threading.Thread(target=self._worker, name="sw-incidentdesk-bridge", daemon=True)
        self._thread.start()

    def _load_config(self) -> dict[str, Any]:
        env_token = os.environ.get("SW_INCIDENTDESK_TOKEN", "").strip()
        env_url = os.environ.get("SW_INCIDENTDESK_URL", "").strip()
        env_enabled = os.environ.get("SW_INCIDENTDESK_ENABLED", "").strip().lower()

        try:
            mtime = self.secret_path.stat().st_mtime
        except OSError:
            mtime = -1.0

        if mtime != self._config_mtime:
            cfg: dict[str, Any] = {}
            if mtime >= 0:
                try:
                    raw = json.loads(self.secret_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        cfg = raw
                except Exception as exc:
                    self.last_error = f"Configuratie kon niet worden gelezen: {exc}"
            self._config = cfg
            self._config_mtime = mtime

        cfg = dict(self._config)
        if env_url:
            cfg["url"] = env_url
        if env_token:
            cfg["token"] = env_token
        if env_enabled in {"1", "true", "yes", "on"}:
            cfg["enabled"] = True
        elif env_enabled in {"0", "false", "no", "off"}:
            cfg["enabled"] = False

        cfg["url"] = str(cfg.get("url") or DEFAULT_ENDPOINT).strip()
        cfg["token"] = str(cfg.get("token") or "").strip()
        cfg["enabled"] = bool(cfg.get("enabled", bool(cfg["token"])))
        return cfg

    def configured(self) -> bool:
        cfg = self._load_config()
        return bool(cfg.get("enabled") and cfg.get("token") and str(cfg.get("url", "")).startswith("https://"))

    def submit(self, message: dict[str, Any]) -> bool:
        if not self.configured():
            return False
        payload = {
            "id": str(message.get("id") or "")[:160],
            "message": str(message.get("title") or message.get("summary") or "")[:3000],
            "timestamp": str(message.get("published") or message.get("updated") or ""),
            "discipline": str(message.get("service") or "overig")[:50],
            "priority": str(message.get("priority") or "")[:30],
            "city": str(message.get("city") or "")[:120],
            "location": str(message.get("location") or "")[:255],
            "units": list(message.get("units") or [])[:30],
            "source": str(message.get("source") or "P2000 Monitor")[:80],
        }
        if not payload["message"]:
            return False
        try:
            self.queue.put_nowait(payload)
            return True
        except queue.Full:
            self.dropped += 1
            self.last_error = "Pushwachtrij vol; melding overgeslagen."
            return False

    def _send(self, payload: dict[str, Any]) -> None:
        cfg = self._load_config()
        if not cfg.get("enabled") or not cfg.get("token"):
            return
        url = str(cfg.get("url") or DEFAULT_ENDPOINT)
        if not url.startswith("https://"):
            raise RuntimeError("SW Incidentdesk endpoint moet HTTPS gebruiken.")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + str(cfg["token"]),
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "P2000-Monitor/SW-Incidentdesk-Bridge",
            },
        )
        with urllib.request.urlopen(req, timeout=5.0) as response:
            raw = response.read(64 * 1024)
            if int(getattr(response, "status", 200) or 200) >= 300:
                raise RuntimeError("SW Incidentdesk gaf een foutstatus.")
            if raw:
                data = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(data, dict) and data.get("ok") is False:
                    raise RuntimeError(str(data.get("error") or "SW Incidentdesk weigerde de melding."))

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._send(payload)
                self.sent += 1
                self.last_success_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                self.last_error = ""
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                self.failed += 1
                self.last_error = str(exc)[:300]
            except Exception as exc:
                self.failed += 1
                self.last_error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                self.queue.task_done()

    def status(self) -> dict[str, Any]:
        cfg = self._load_config()
        return {
            "configured": self.configured(),
            "enabled": bool(cfg.get("enabled")),
            "endpoint": str(cfg.get("url") or DEFAULT_ENDPOINT),
            "queued": self.queue.qsize(),
            "sent": self.sent,
            "failed": self.failed,
            "dropped": self.dropped,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
        }

    def close(self) -> None:
        self._stop.set()
