from __future__ import annotations
import re

def priority_tier(*, classification: str = "", text: str = "", scale: str = "", mmt: bool = False,
                  message_count: int = 1, special_vehicle: bool = False, base_score: int = 0) -> dict:
    """Return an explainable Critical/High/Normal/Low tier.

    Scores remain useful for sorting, but the tier is the stable contract used by
    the UI/audio queue. This avoids tiny heuristic score changes unexpectedly
    changing behaviour.
    """
    joined = f"{classification} {text} {scale}".upper()
    score = int(base_score or 0)
    reasons: list[str] = []
    critical = False
    high = False
    if re.search(r"\bGRIP\s*[1-5]\b", joined):
        score += 120; reasons.append("GRIP"); critical = True
    if re.search(r"\bZEER\s+(?:GROTE|GR\.?)[ ]*(?:BR|BRAND)\b", joined):
        score += 100; reasons.append("zeer grote brand"); critical = True
    if "SCHIET" in joined:
        score += 95; reasons.append("schietincident"); critical = True
    if "STEEK" in joined:
        score += 80; reasons.append("steekincident"); high = True
    if re.search(r"\bGROTE\s+(?:BR|BRAND)\b|\bGR\.?\s*BR\b", joined):
        score += 72; reasons.append("grote brand"); high = True
    if re.search(r"\bMIDDEL(?:BRAND|\s+BRAND|\s+BR)\b", joined):
        score += 45; reasons.append("middelbrand"); high = True
    if mmt:
        score += 42; reasons.append("MMT-inzet")
        if "REANIMAT" in joined:
            critical = True; score += 45; reasons.append("reanimatie + MMT")
    if message_count > 1:
        score += min(36, (message_count - 1) * 8); reasons.append(f"{message_count} gekoppelde meldingen")
    if special_vehicle:
        score += 24; reasons.append("bijzondere eenheid")
    if critical or score >= 150:
        tier = "critical"
    elif high or score >= 90:
        tier = "high"
    elif score >= 25:
        tier = "normal"
    else:
        tier = "low"
    return {"tier": tier, "score": min(999, score), "reasons": list(dict.fromkeys(reasons))}
