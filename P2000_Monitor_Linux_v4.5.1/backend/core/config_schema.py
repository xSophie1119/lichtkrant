from __future__ import annotations
CONFIG_SCHEMA_VERSION=8
DISPLAY_SCHEMA_VERSION=5

def migrate_config(row: dict) -> tuple[dict,list[str]]:
    out=dict(row or {});changes=[]
    old=int(out.get("config_schema_version") or 0)
    if old<8:
        # v4.5 uses the signed/checksummed platform manifest before legacy branch ZIPs.
        out.setdefault("github_manifest_enabled",True)
        out.setdefault("startup_selftest",True)
        out.setdefault("safe_mode_on_repeated_failure",True)
        out["config_schema_version"]=CONFIG_SCHEMA_VERSION
        changes.append(f"configschema {old or 'legacy'} → {CONFIG_SCHEMA_VERSION}")
    return out,changes

def migrate_display(row: dict) -> tuple[dict,list[str]]:
    out=dict(row or {});changes=[]
    old=int(out.get("settingsSchemaVersion") or 0)
    if out.get("speechEngine") in {"browser","online",""}:
        out["speechEngine"]="native";changes.append("omroepengine → native")
    if out.get("mapMode") not in {"auto","route","incident","posts"}:
        out["mapMode"]="auto";changes.append("kaartmodus → auto")
    out.setdefault("speechTemplates",{})
    out.setdefault("mapMode","auto")
    out.setdefault("displayTarget","all")
    out["settingsSchemaVersion"]=DISPLAY_SCHEMA_VERSION
    return out,changes
