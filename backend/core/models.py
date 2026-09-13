from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass(slots=True)
class UnitRef:
    callsign: str = ""
    lookup_key: str = ""
    discipline: str = ""
    function_code: str = ""
    function_name: str = ""
    station_name: str = ""
    source: str = ""
    verified: bool | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class ParsedMessage:
    id: str = ""
    raw: str = ""
    service: str = "overig"
    priority: str = ""
    incident_type: str = "P2000-melding"
    city: str = ""
    location: str = ""
    scale: str = ""
    incident_key: str = ""
    units: list[UnitRef] = field(default_factory=list)
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class TimelineEvent:
    time: str
    kind: str
    label: str
    message_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class Incident:
    id: str
    incident_key: str
    classification: str
    city: str
    location: str
    priority_tier: str = "normal"
    priority_score: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    units: list[UnitRef] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timeline"] = [x.to_dict() if hasattr(x, "to_dict") else x for x in self.timeline]
        data["units"] = [x.to_dict() if hasattr(x, "to_dict") else x for x in self.units]
        return data
