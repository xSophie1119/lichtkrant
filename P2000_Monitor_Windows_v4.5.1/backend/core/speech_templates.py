from __future__ import annotations
import re

DEFAULT_TEMPLATES = {
    "incident": "{incident}{where}.",
    "scale": "Het incident is opgeschaald naar {scale}.",
    "units": "Gealarmeerde voertuigen: {units}.",
    "mmt": "Het Mobiel Medisch Team is gealarmeerd.",
}

def clean_station(value: str) -> str:
    return " ".join(re.sub(r"\s*[-–—]\s*", " ", value or "").split())

def join_spoken_units(rows: list[str]) -> str:
    rows=[" ".join(str(x).split()) for x in rows if str(x).strip()]
    rows=list(dict.fromkeys(rows))
    if not rows:return ""
    if len(rows)==1:return rows[0]
    if len(rows)==2:return f"{rows[0]} en {rows[1]}"
    return f"{', '.join(rows[:-1])} en {rows[-1]}"

def build_announcement(*, incident: str, where: str = "", scale: str = "", units: list[str] | None = None,
                       mmt: bool = False, templates: dict | None = None) -> str:
    t=dict(DEFAULT_TEMPLATES); t.update(templates or {})
    parts=[]
    first=t["incident"].format(incident=incident or "Incident", where=where or "").strip()
    if first: parts.append(first)
    if scale: parts.append(t["scale"].format(scale=scale.lower()).strip())
    spoken=join_spoken_units(units or [])
    if spoken: parts.append(t["units"].format(units=spoken).strip())
    if mmt and not any("Mobiel Medisch Team" in p for p in parts): parts.append(t["mmt"].strip())
    return " ".join(x for x in parts if x)
