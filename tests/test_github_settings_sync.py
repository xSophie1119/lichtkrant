import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p2000_server_sync", ROOT / "backend" / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = server
spec.loader.exec_module(server)


def test_remote_settings_are_sanitized_and_saved():
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        old_db = server.DB_PATH
        old_data = server.DATA_DIR
        old_status = server.GITHUB_SETTINGS_STATUS_PATH
        old_file = server._github_file
        server.DATA_DIR = base
        server.DB_PATH = base / "p2000.sqlite3"
        server.GITHUB_SETTINGS_STATUS_PATH = base / "github-settings-status.json"
        document = {
            "revision": 7,
            "display_settings": {
                "name": "Centraal",
                "speechEnabled": False,
                "messageMinutes": 999,
                "unknownDangerousKey": "ignored",
            },
        }
        server._github_file = lambda repo, path, branch: {
            "body": json.dumps(document).encode("utf-8"),
            "sha": "deadbeef",
        }
        try:
            state = server.AppState({
                "github_repo": "owner/repo",
                "github_settings_path": "p2000-settings.json",
                "github_settings_branch": "main",
            })
            state.init_db()
            result = server.github_pull_settings(state, force=True)
            saved = state.get_display_settings()
            assert result["state"] == "applied"
            assert result["revision"] == 7
            assert saved["name"] == "Centraal"
            assert saved["speechEnabled"] is False
            assert saved["messageMinutes"] == 15.0
            assert "unknownDangerousKey" not in saved
        finally:
            server._github_file = old_file
            server.DB_PATH = old_db
            server.DATA_DIR = old_data
            server.GITHUB_SETTINGS_STATUS_PATH = old_status


if __name__ == "__main__":
    test_remote_settings_are_sanitized_and_saved()
    print("test_remote_settings_are_sanitized_and_saved OK")
