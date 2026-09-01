import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p2000_persistence_under_test", ROOT / "backend" / "server.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_windows_settings_directory_is_outside_installation():
    with TemporaryDirectory() as tmp:
        base = Path(tmp) / "LocalAppData"
        resolved = mod.resolve_display_settings_dir(
            env={"LOCALAPPDATA": str(base)},
            platform_name="win32",
            home=Path(tmp) / "home",
        )
        assert resolved == base / "P2000-Monitor" / "Settings"


def test_settings_survive_a_fresh_application_database():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = (mod.DISPLAY_SETTINGS_PATH, mod.DATA_DIR, mod.DB_PATH)
        try:
            mod.DISPLAY_SETTINGS_PATH = tmp / "appdata" / "display-settings.json"
            mod.DATA_DIR = tmp / "install-one" / "data"
            mod.DB_PATH = mod.DATA_DIR / "p2000.sqlite3"

            first = mod.AppState({})
            first.init_db()
            saved = first.save_display_settings({
                "name": "Eemnes",
                "nightMode": False,
                "speechCities": ["Eemnes", "Laren"],
                "mapZoom": 17,
            })
            assert saved["name"] == "Eemnes"
            assert mod.DISPLAY_SETTINGS_PATH.is_file()
            assert json.loads(mod.DISPLAY_SETTINGS_PATH.read_text(encoding="utf-8"))["nightMode"] is False

            # Simulate unpacking/starting the program from a completely new
            # directory: this database has never seen the settings.
            mod.DATA_DIR = tmp / "install-two" / "data"
            mod.DB_PATH = mod.DATA_DIR / "p2000.sqlite3"
            second = mod.AppState({})
            second.init_db()
            loaded = second.get_display_settings()
            assert loaded["name"] == "Eemnes"
            assert loaded["speechCities"] == ["Eemnes", "Laren"]
            assert loaded["mapZoom"] == 17
        finally:
            mod.DISPLAY_SETTINGS_PATH, mod.DATA_DIR, mod.DB_PATH = original


def test_existing_sqlite_settings_are_migrated_once():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = (mod.DISPLAY_SETTINGS_PATH, mod.DATA_DIR, mod.DB_PATH)
        try:
            mod.DISPLAY_SETTINGS_PATH = tmp / "appdata" / "display-settings.json"
            mod.DATA_DIR = tmp / "legacy-install" / "data"
            mod.DB_PATH = mod.DATA_DIR / "p2000.sqlite3"
            mod.DATA_DIR.mkdir(parents=True)
            with sqlite3.connect(mod.DB_PATH) as con:
                con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                con.execute(
                    "INSERT INTO kv(key,value) VALUES('display:settings',?)",
                    (json.dumps({"name": "Bestaand", "services": ["brandweer"]}),),
                )

            state = mod.AppState({})
            assert state.get_display_settings()["name"] == "Bestaand"
            assert mod.DISPLAY_SETTINGS_PATH.is_file()
            assert json.loads(mod.DISPLAY_SETTINGS_PATH.read_text(encoding="utf-8"))["name"] == "Bestaand"
        finally:
            mod.DISPLAY_SETTINGS_PATH, mod.DATA_DIR, mod.DB_PATH = original


if __name__ == "__main__":
    tests = [
        test_windows_settings_directory_is_outside_installation,
        test_settings_survive_a_fresh_application_database,
        test_existing_sqlite_settings_are_migrated_once,
    ]
    for test in tests:
        test()
        print(test.__name__, "OK")
