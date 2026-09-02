#!/usr/bin/env python3
"""P2000 Monitor - Windows-only configurable P2000 backend.

Core server uses Python's standard library and bundles gTTS for optional speech:
- polls Alarmeringen.nl RSS feeds using ETag / If-Modified-Since
- normalizes and stores messages in SQLite
- exposes a small JSON REST API
- streams new messages to browsers using Server-Sent Events (SSE)
- serves the frontend

This project is intended as an informational monitor, not an emergency service.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import math
import os
import queue
import re
import signal
import sys
from io import BytesIO, StringIO
import socket
import ipaddress
import shutil
import sqlite3
import subprocess
import threading
import wave
import struct
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote, urljoin, unquote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
CONFIG_PATH = ROOT / "config" / "config.json"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "p2000.sqlite3"
VEHICLE_DB_PATH = FRONTEND_DIR / "vehicles.json"
VEHICLE_CACHE_DIR = DATA_DIR / "vehicles"
VEHICLE_OVERRIDES_PATH = VEHICLE_CACHE_DIR / "overrides.json"
VENDOR_DIR = ROOT / "vendor"
TTS_CACHE_DIR = DATA_DIR / "tts-cache"
BACKGROUND_DIR = DATA_DIR / "background"
MAX_BACKGROUND_BYTES = 15 * 1024 * 1024
TUNE_DIR = DATA_DIR / "tunes"
MAX_TUNE_BYTES = 12 * 1024 * 1024
UPDATE_DIR = DATA_DIR / "updates"
UPDATE_STATUS_PATH = UPDATE_DIR / "status.json"
UPDATE_BACKUP_DIR = UPDATE_DIR / "backups"
GITHUB_SETTINGS_STATUS_PATH = DATA_DIR / "github-settings-status.json"
GITHUB_API_BASE = "https://api.github.com"
DEFAULT_GITHUB_REPO = "xSophie1119/lichtkrant"
DEFAULT_GITHUB_BRANCH = "main"
DEFAULT_GITHUB_SETTINGS_PATH = "p2000-settings.json"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

APP_VERSION = "4.2.4"
USER_AGENT = f"LocalP2000Monitor/{APP_VERSION} (+local informational display)"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
ALARMERINGEN_BASE = "https://alarmeringen.nl/feeds"
ALARMERINGEN_TRAUMA_URL = f"{ALARMERINGEN_BASE}/discipline/trauma.rss"
ALARMERINGEN_KNRM_URL = f"{ALARMERINGEN_BASE}/discipline/knrm.rss"

# Landelijke brandweervoertuigendatabase.  De monitor houdt de statische seed klein
# en synchroniseert alleen de brandweerregio's die de gebruiker heeft gekozen.
# De bron is een publiek gepubliceerde Google Sheet van Tomzulu10.  Synchronisatie
# gebeurt op de achtergrond en blokkeert RSS, SSE of de lichtkrant nooit.
TOMZULU_FIRE_SHEET_ID = "2PACX-1vRN4hv6KvjYXT1Zc5HQG_WmAj17d1qspXlgCkTVK6s48ZtVGw6yCfQZS2NaZaTtTWIFuBpmcRVg2P6q"
FIRE_REGION_CODES = {
    "groningen":"01", "friesland":"02", "drenthe":"03", "ijsselland":"04", "twente":"05",
    "noord-en-oost-gelderland":"06", "gelderland-midden":"07", "gelderland-zuid":"08", "utrecht":"09",
    "noord-holland-noord":"10", "zaanstreek-waterland":"11", "kennemerland":"12", "amsterdam-amstelland":"13",
    "gooi-en-vechtstreek":"14", "haaglanden":"15", "hollands-midden":"16", "rotterdam-rijnmond":"17",
    "zuid-holland-zuid":"18", "zeeland":"19", "midden-en-west-brabant":"20", "brabant-noord":"21",
    "brabant-zuidoost":"22", "limburg-noord":"23", "limburg-zuid":"24", "flevoland":"25",
}
FIRE_REGION_SHEETS = {
    "01":"01 Groningen", "02":"02 Fryslân", "03":"03 Drenthe", "04":"04 IJsseland", "05":"05 Twente",
    "06":"06 Noord-Oost Gelderland", "07":"07 Gelderland Midden", "08":"08 Gelderland Zuid", "09":"09 Utrecht",
    "10":"10 Noord-Holland Noord", "11":"11 Zaanstreek Waterland", "12":"12 Kennemerland",
    "13":"13 Amsterdam-Amstelland", "14":"14 Gooi en Vechtstreek", "15":"15 Haaglanden",
    "16":"16 Hollands-Midden", "17":"17 Rotterdam-Rijnmond", "18":"18 Zuid-Holland Zuid", "19":"19 Zeeland",
    "20":"20 Midden-en West Brabant", "21":"21 Brabant-Noord", "22":"22 Brabant-Zuidoost",
    "23":"23 Limburg-Noord", "24":"24 Zuid-Limburg", "25":"25 Flevoland",
}
FIRE_REGION_LABELS = {code: slug.replace("-", " ").title() for slug, code in FIRE_REGION_CODES.items()}
# A daily background refresh keeps changing roepnummers substantially fresher
# without making live P2000 processing depend on a third-party website.
FIRE_DB_REFRESH_SECONDS = 24 * 3600

# Primary exact vehicle source. Hulpdienstvoertuigen publishes a paginated
# regional vehicle table and is much less brittle than a published Google
# workbook tab name.  The old Tomzulu workbook is retained only as fallback.
HULPDIENST_VEHICLES_BASE = "https://hulpdienstvoertuigen.nl/regio"
HULPDIENST_REGION_SLUGS = {
    code: slug for slug, code in FIRE_REGION_CODES.items()
}
HULPDIENST_REGION_SLUGS.update({
    "02": "friesland",       # site URL; display title is Fryslân
    "24": "zuid-limburg",   # monitor slug is limburg-zuid
})

# Selectable catalogue for the Windows setup wizard. The 25 veiligheidsregio's
# are primary; three familiar Alarmeringen subregions are included as optional
# narrower choices. Duplicate articles are de-duplicated by canonical URL.
REGION_CATALOG = {
    "amsterdam-amstelland": {"label": "Amsterdam-Amstelland", "kind": "veiligheidsregio"},
    "brabant-noord": {"label": "Brabant-Noord", "kind": "veiligheidsregio"},
    "brabant-zuidoost": {"label": "Brabant-Zuidoost", "kind": "veiligheidsregio"},
    "drenthe": {"label": "Drenthe", "kind": "veiligheidsregio"},
    "flevoland": {"label": "Flevoland", "kind": "veiligheidsregio"},
    "friesland": {"label": "Friesland", "kind": "veiligheidsregio"},
    "gelderland-midden": {"label": "Gelderland-Midden", "kind": "veiligheidsregio"},
    "gelderland-zuid": {"label": "Gelderland-Zuid", "kind": "veiligheidsregio"},
    "gooi-en-vechtstreek": {"label": "Gooi en Vechtstreek", "kind": "veiligheidsregio"},
    "groningen": {"label": "Groningen", "kind": "veiligheidsregio"},
    "haaglanden": {"label": "Haaglanden", "kind": "veiligheidsregio"},
    "hollands-midden": {"label": "Hollands Midden", "kind": "veiligheidsregio"},
    "ijsselland": {"label": "IJsselland", "kind": "veiligheidsregio"},
    "kennemerland": {"label": "Kennemerland", "kind": "veiligheidsregio"},
    "limburg-noord": {"label": "Limburg-Noord", "kind": "veiligheidsregio"},
    "limburg-zuid": {"label": "Limburg-Zuid", "kind": "veiligheidsregio"},
    "midden-en-west-brabant": {"label": "Midden- en West-Brabant", "kind": "veiligheidsregio"},
    "noord-en-oost-gelderland": {"label": "Noord- en Oost-Gelderland", "kind": "veiligheidsregio"},
    "noord-holland-noord": {"label": "Noord-Holland Noord", "kind": "veiligheidsregio"},
    "rotterdam-rijnmond": {"label": "Rotterdam-Rijnmond", "kind": "veiligheidsregio"},
    "twente": {"label": "Twente", "kind": "veiligheidsregio"},
    "utrecht": {"label": "Utrecht", "kind": "veiligheidsregio"},
    "zaanstreek-waterland": {"label": "Zaanstreek-Waterland", "kind": "veiligheidsregio"},
    "zeeland": {"label": "Zeeland", "kind": "veiligheidsregio"},
    "zuid-holland-zuid": {"label": "Zuid-Holland Zuid", "kind": "veiligheidsregio"},
    "achterhoek": {"label": "Achterhoek", "kind": "subregio"},
    "bollenstreek": {"label": "Bollenstreek", "kind": "subregio"},
    "hoeksche-waard": {"label": "Hoeksche Waard", "kind": "subregio"},
}
REGION_LABEL_TO_SLUG = {meta["label"].lower(): slug for slug, meta in REGION_CATALOG.items()}
SAFETY_REGION_SLUGS = tuple(slug for slug, meta in REGION_CATALOG.items() if meta.get("kind") == "veiligheidsregio")
SUBREGION_PARENT = {
    "achterhoek": "noord-en-oost-gelderland",
    "bollenstreek": "hollands-midden",
    "hoeksche-waard": "zuid-holland-zuid",
}
REGIONAL_DISCIPLINES = ("brandweer", "ambulance", "politie")
SPECIAL_DISCIPLINES = ("knrm", "lifeliner")
ALL_DISCIPLINES = REGIONAL_DISCIPLINES + SPECIAL_DISCIPLINES
NATIONAL_DISCIPLINE_URLS = {
    "brandweer": f"{ALARMERINGEN_BASE}/discipline/brandweer.rss",
    "ambulance": f"{ALARMERINGEN_BASE}/discipline/ambulance.rss",
    "politie": f"{ALARMERINGEN_BASE}/discipline/politie.rss",
    "knrm": ALARMERINGEN_KNRM_URL,
    "lifeliner": ALARMERINGEN_TRAUMA_URL,
}


def regional_feed_url(region_slug: str, discipline: str) -> str:
    return f"{ALARMERINGEN_BASE}/region/{region_slug}/{discipline}.rss"


def build_feed_urls(region_disciplines: dict) -> list[str]:
    """Build the smallest correct feed set for the selected matrix.

    Normally every selected region/discipline gets its direct regional RSS URL.
    If a regional discipline is selected for all 25 safety regions, the official
    national discipline feed is equivalent and avoids polling 25 overlapping
    feeds every cycle. Subregions are already covered by their parent safety
    regions in that all-Netherlands case. KNRM and traumaheli are always national
    feeds and are filtered back to the selected regions after parsing.
    """
    if not isinstance(region_disciplines, dict):
        return []
    cleaned: dict[str, set[str]] = {}
    for slug, disciplines in region_disciplines.items():
        if slug not in REGION_CATALOG or not isinstance(disciplines, list):
            continue
        selected = {str(x).lower() for x in disciplines if str(x).lower() in ALL_DISCIPLINES}
        if selected:
            cleaned[slug] = selected

    urls: list[str] = []
    safety_set = set(SAFETY_REGION_SLUGS)
    for discipline in REGIONAL_DISCIPLINES:
        selected_safety = {slug for slug in SAFETY_REGION_SLUGS if discipline in cleaned.get(slug, set())}
        nationwide = selected_safety == safety_set
        if nationwide:
            urls.append(NATIONAL_DISCIPLINE_URLS[discipline])
        else:
            for slug in REGION_CATALOG:
                if discipline not in cleaned.get(slug, set()):
                    continue
                # A selected safety region already contains its Alarmeringen
                # subregions. Do not poll both feeds for the same discipline.
                parent = SUBREGION_PARENT.get(slug)
                if parent and discipline in cleaned.get(parent, set()):
                    continue
                urls.append(regional_feed_url(slug, discipline))

    if any("knrm" in values for values in cleaned.values()):
        urls.append(NATIONAL_DISCIPLINE_URLS["knrm"])
    if any("lifeliner" in values for values in cleaned.values()):
        urls.append(NATIONAL_DISCIPLINE_URLS["lifeliner"])
    return list(dict.fromkeys(urls))


def region_slug_for_url(url: str) -> str | None:
    m = re.search(r"/feeds/region/([^/]+)(?:/|\.rss)", str(url or ""), re.I)
    if m and m.group(1).lower() in REGION_CATALOG:
        return m.group(1).lower()
    return None


def discipline_for_feed_url(url: str) -> str | None:
    low = str(url or "").lower()
    if "/discipline/trauma.rss" in low:
        return "lifeliner"
    if "/discipline/knrm.rss" in low:
        return "knrm"
    for discipline in REGIONAL_DISCIPLINES:
        if low.endswith(f"/{discipline}.rss"):
            return discipline
    return None


def region_slug_from_article_url(url: str) -> str | None:
    """Find an Alarmeringen region slug anywhere in an article URL path.

    Article URLs are not perfectly uniform: some start directly with the region,
    while others include a province or ``streek`` prefix. Scanning all path
    segments keeps national trauma/KNRM feeds filterable for every region.
    """
    try:
        parts = [unquote(x).lower() for x in urlparse(url).path.strip("/").split("/") if x]
    except Exception:
        return None
    for part in parts:
        if part in REGION_CATALOG:
            return part
    return None


def city_from_article_url(url: str) -> str:
    """Best-effort city fallback for feeds that omit a usable city category."""
    try:
        parts = [unquote(x).strip() for x in urlparse(url).path.strip("/").split("/") if x]
    except Exception:
        return ""
    lower = [x.lower() for x in parts]
    region_idx = next((i for i, part in enumerate(lower) if part in REGION_CATALOG), -1)
    if region_idx < 0:
        return ""
    ignored = {
        "brandweer", "ambulance", "politie", "trauma", "lifeliner", "knrm",
        "p2000", "112", "meldingen", "nieuws", "page",
    }
    for raw in parts[region_idx + 1:]:
        slug = raw.lower()
        if slug in ignored or re.fullmatch(r"\d+", slug) or slug.endswith(".html"):
            continue
        # Article title slugs usually occur after a numeric id; the first clean
        # segment after the region is therefore the safest locality candidate.
        text = re.sub(r"[-_]+", " ", raw).strip()
        if text:
            return re.sub(r"^'S(?=[ -])", "'s", text.title())
    return ""

SOURCE_NAME = "Alarmeringen.nl"

def source_name_for_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower() if url else ""
    if host.endswith("alarmeringen.nl"):
        return "Alarmeringen.nl"
    if host.endswith("112-nu.nl"):
        return "112-nu.nl"
    if host.endswith("zwaailicht.nl"):
        return "Zwaailicht.nl"
    return host or SOURCE_NAME
LOCAL_TZ_NAME = os.environ.get("P2000_TIMEZONE", "Europe/Amsterdam")
try:
    LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
except Exception:
    LOCAL_TZ = datetime.now().astimezone().tzinfo

SERVICE_ALIASES = {
    "brandweer": "brandweer",
    "fire": "brandweer",
    "ambulance": "ambulance",
    "ambu": "ambulance",
    "medisch": "ambulance",
    "politie": "politie",
    "police": "politie",
    "lifeliner": "lifeliner",
    "mmt": "lifeliner",
    "traumaheli": "lifeliner",
    "knrm": "knrm",
    "kustwacht": "knrm",
}

PRIORITY_RE = re.compile(r"\b(?:P\s*([1-5])|PRIO\s*([1-5])|(A[012]|B[12]))\b", re.I)
# Police dispatches in regional feeds commonly use e.g.
# "P 1 366315 Letsel Rillaerse-Baan Riel". The numeric value is a
# dispatch/bundle identifier, not a vehicle callsign.
POLICE_BUNDLE_RE = re.compile(r"^\s*P\s*[1-5]\s+\d{4,7}\b", re.I)
# Rotterdam-Rijnmond / industrial-port police rows also occur without a P-prefix,
# e.g. "1 Ongeval wegvervoer letsel ... ICnum 465101".
POLICE_ICNUM_RE = re.compile(r"^\s*[1-5]\s+.+?\bICnum\b", re.I)
# Noord-Nederland pers/police rows often use slash-separated incident taxonomy,
# e.g. "ongeval/wegvervoer/letsel prio 1 groningen osloweg".
POLICE_SLASH_RE = re.compile(r"^\s*(?:ongeval|verkeer|politie)/[^\n]+?\bprio\s*[1-5]\b", re.I)
POLICE_PLAIN_RE = re.compile(
    r"^\s*(?:P\s*[1-5]|PRIO\s*[1-5])\s+(?:(?:\d{4,7})\s+)?(?:"
    r"SCHIET(?:PARTIJ|INCIDENT)|STEEK(?:PARTIJ|INCIDENT)|ACHTERVOLGING|OVERVAL|BEROVING|"
    r"INBRAAK(?:\s+BEDRIJF)?|DEMONSTRATIE|LETSEL|AANRIJDING(?:\s+LETSEL)?|ONGEVAL(?:\s+WEGVERVOER)?\s+LETSEL|"
    r"VERDACHTE\s+SITUATIE|VERMISSING)\b", re.I)
POLICE_PRIO_ROAD_RE = re.compile(
    r"^\s*PRIO\s*[1-5]\b.+?\b(?:ONGEVAL\s+WEGVERVOER\s+(?:LETSEL|MATERIEEL)|WEGVERKEER\s+VERKEERSSTREMMING)\b", re.I
)
AMBULANCE_RAW_RE = re.compile(r"^\s*(?:A[012]|B[12])\b", re.I)
POSTCODE_RE = re.compile(r"\b\d{4}\s?[A-Z]{2}\b", re.I)
UNIT_RE = re.compile(
    # Require an actual separator after the unit type. This prevents words such
    # as "woning" from being misread as a WO-unit.
    r"\b(?:TS|HV|HW|AL|RV|OVD|HOVD|AGS|VEBS|WT|WTS|WTH|DA|DB|PM|WO|FRB|MMT|LFL|AMB(?:U)?|RWS)[-\s]+(?=[A-Z0-9-]*\d)[A-Z0-9-]{2,}\b",
    re.I,
)

# Six-digit fire-brigade callsigns used by the local regional feeds
# safety regions. Keep this deliberately separate from five-digit MMT resources.
FIRE_CALLSIGN_PREFIXES = tuple(f"{i:02d}" for i in range(1, 100))
FIRE_CALLSIGN_RE = re.compile(r"(?<!\d)(\d{2})[-\s]?(\d{4})(?!\d)", re.I)
FIRE_DISPATCH_CODE_RE = re.compile(r"\b(?:B[A-Z]{2}|S[A-Z]{2}|KAZ)-\d{1,3}\b", re.I)

# Seven-digit hyphenated roepnummers are seen in the northern regions
# (for example 01-18-849). Keep them separate from six-digit callsigns.
FIRE_EXTENDED_CALLSIGN_RE = re.compile(r"(?<!\d)(\d{2})[- ](\d{2})[- ](\d{3})(?!\d)", re.I)

FIRE_INCIDENT_HINT_RE = re.compile(
    r"\b(?:BR(?:AND)?(?:\s|$)|OMS|PAC|ROOKMELDER|CO-MELDER|BRANDGERUCHT|NACONTROLE|"
    r"LIFTOPSLUITING|STORMSCHADE|WATEROVERLAST|ASS\.?\s*(?:AMBU|POL(?:ITIE)?)|"
    r"REANIMATIE|DIER\s+(?:IN\s+PROBLEMEN|TE\s+WATER|OP\s+HOOGTE|IN\s+PUT/KELDER)|"
    r"PERSOON\s+(?:TE\s+WATER|IN\s+DRIJFZAND)|VOERTUIG\s+TE\s+WATER|ONGEVAL|"
    r"ONGEVAL\s+(?:GEV\.?\s*STOF|OP\s+WATER)|BIJSTAND|HERBEZET|KAZERNEREN|"
    r"DIENSTVERLENING|STANK/HIND\.?\s+LUCHT|LUID/OPTISCH\s+ALARM)\b", re.I
)


def normalize_vehicle_digits(value: str) -> str:
    """Normalize a supported fire callsign to its digit key."""
    text = str(value or "").strip()
    ext = re.search(r"(?<!\d)(\d{2})[- ](\d{2})[- ](\d{3})(?!\d)", text)
    if ext:
        return "".join(ext.groups())
    normal = re.search(r"(?<!\d)(\d{2})[- ]?(\d{4})(?!\d)", text)
    if normal:
        return "".join(normal.groups())
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) in {6, 7} else ""


def fire_vehicle_type(description: str, digits: str = "") -> tuple[str, str]:
    """Map free-form Dutch vehicle descriptions to a compact display type."""
    text = normalize_space(str(description or ""))
    up = text.upper()
    rules = [
        (r"TANKAUTOSPUIT.*NATUUR|NATUURBRAND.*(?:VOERTUIG|TANKAUTOSPUIT)|\bCCFM\b", "TST-NB", "Tankautospuit natuurbrand"),
        (r"TANKAUTOSPUIT|\bTS\b", "TS", "Tankautospuit"),
        (r"AUTOLADDER|\bAL\b", "AL", "Autoladder"),
        (r"HOOGWERKER|\bHW\b", "HW", "Hoogwerker"),
        (r"HULPVERLENINGSVOERTUIG|\bHV\b", "HV", "Hulpverleningsvoertuig"),
        (r"WATERONGEVALLEN|OPPERVLAKTEREDDING|DUIK", "WO", "Waterongevallenvoertuig"),
        (r"BRANDWEERVAARTUIG|BLUSBOOT|REDDINGSBOOT|FAST RESCUE", "BRV", "Brandweervaartuig"),
        (r"SCHUIMBLUS|\bSB\b", "SB", "Schuimblusvoertuig"),
        (r"WATERTANKWAGEN|WATERTANKHAK|\bWTW\b|\bWTH\b", "WT", "Watertankwagen"),
        (r"DOMPELPOMP|SLANGENHAK|GROOTSCHALIGE WATER|WATERTRANSPORT|\bWTS\b", "WTS", "Watertransport"),
        (r"ADVISEUR GEVAARLIJKE|\bAGS\b", "AGS", "Adviseur Gevaarlijke Stoffen"),
        (r"HOOFD.?OFFICIER|\bHOVD\b", "HOVD-B", "Hoofdofficier van Dienst Brandweer"),
        (r"OFFICIER VAN DIENST|\bOVD\b", "OVD-B", "Officier van Dienst Brandweer"),
        (r"COMMANDOVOERTUIG|CO.?PI|COMMANDO", "CO", "Commandovoertuig"),
        (r"VERKENNINGSEENHEID|DIGITALE VERKENNING|DRONE", "VEBS", "Verkenningseenheid"),
        (r"HAAKARMVOERTUIG|\bHA\b", "HA", "Haakarmvoertuig"),
        (r"PERSONEEL.?MATERIAAL|MATERIAALVOERTUIG|MATERIAALWAGEN|\bPM\b", "PM", "Personeel/materiaalvoertuig"),
        (r"DIENSTBUS|\bDB\b", "DB", "Dienstbus"),
        (r"DIENSTAUTO|DIENSTVOERTUIG|\bDA\b", "DA", "Dienstauto"),
        (r"LOGISTIEK|HERBEVOORRADING|ADEMLUCHT", "LOG", "Logistiek voertuig"),
    ]
    for pattern, short, label in rules:
        if re.search(pattern, up, re.I):
            return short, label
    # Nationaal nummerplan: vijfde cijfer geeft de materieelgroep.  Dit is een
    # betrouwbare fallback als een nieuw voertuig nog niet in de online lijst staat.
    d = normalize_vehicle_digits(digits)
    if len(d) >= 6:
        group = d[4]
        fallback = {
            "0": ("DA/DB", "Personenvervoer"), "1": ("WO", "Waterongevallenmaterieel"),
            "2": ("OGS", "Gevaarlijke-stoffenmaterieel"), "3": ("TS", "Tankautospuit"),
            "4": ("TST-NB", "Natuurbrandvoertuig"), "5": ("RV", "Redmaterieel"),
            "6": ("BB", "Bijzonder brandbestrijdingsmaterieel"), "7": ("HV", "Hulpverleningsmaterieel"),
            "8": ("OV", "Overig materieel"), "9": ("CO", "Staf/commandomaterieel"),
        }
        if group in fallback:
            return fallback[group]
    return "BRW", text or "Brandweervoertuig"


def vehicle_cache_path(region_code: str) -> Path:
    return VEHICLE_CACHE_DIR / f"{region_code}.json"


def format_vehicle_callsign(digits: str) -> str:
    digits = normalize_vehicle_digits(digits)
    if len(digits) == 7:
        return f"{digits[:2]}-{digits[2:4]}-{digits[4:]}"
    if len(digits) == 6:
        return f"{digits[:2]}-{digits[2:]}"
    return ""


def sanitize_vehicle_override(payload: dict) -> tuple[str, dict]:
    if not isinstance(payload, dict):
        raise ValueError("Ongeldige voertuiggegevens")
    digits = normalize_vehicle_digits(str(payload.get("digits") or payload.get("callsign") or ""))
    if len(digits) not in {6, 7}:
        raise ValueError("Gebruik een brandweerroepnummer zoals 20-3161 of 01-18-849")
    type_text = normalize_space(str(payload.get("type") or ""))[:32].upper()
    type_text = re.sub(r"[^A-Z0-9/+-]", "", type_text)
    station = normalize_space(str(payload.get("station") or ""))[:120]
    label = normalize_space(str(payload.get("label") or ""))[:180]
    display = normalize_space(str(payload.get("display") or ""))[:180]
    if not type_text:
        type_text = fire_vehicle_type(label or display, digits)[0]
    if not label:
        label = display or fire_vehicle_type(type_text, digits)[1]
    if not display:
        display = " ".join(x for x in (type_text, station) if x).strip() or label
    if not display:
        raise ValueError("Vul een type, standplaats of weergavenaam in")
    return digits, {
        "callsign": format_vehicle_callsign(digits),
        "type": type_text or "BRW",
        "label": label or display,
        "station": station,
        "display": display,
        "region": digits[:2],
        "source": "handmatige override",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manual": True,
    }


def load_vehicle_overrides() -> dict[str, dict]:
    try:
        data = json.loads(VEHICLE_OVERRIDES_PATH.read_text(encoding="utf-8"))
        rows = data.get("vehicles", {}) if isinstance(data, dict) else {}
        clean: dict[str, dict] = {}
        for key, value in rows.items():
            if not isinstance(value, dict):
                continue
            try:
                digits, item = sanitize_vehicle_override({**value, "digits": key})
                # Preserve the original edit timestamp when it is valid text.
                item["updated_at"] = normalize_space(str(value.get("updated_at") or item["updated_at"]))[:40]
                clean[digits] = item
            except ValueError:
                continue
        return clean
    except Exception:
        return {}


def write_vehicle_overrides(vehicles: dict[str, dict]) -> None:
    VEHICLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "vehicles": vehicles}
    tmp = VEHICLE_OVERRIDES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(VEHICLE_OVERRIDES_PATH)


def load_vehicle_seed() -> dict[str, dict]:
    try:
        data = json.loads(VEHICLE_DB_PATH.read_text(encoding="utf-8"))
        vehicles = data.get("vehicles", {}) if isinstance(data, dict) else {}
        return {str(k): dict(v) for k, v in vehicles.items() if isinstance(v, dict)}
    except Exception:
        return {}


def load_cached_vehicle_region(region_code: str) -> tuple[dict[str, dict], dict]:
    path = vehicle_cache_path(region_code)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        vehicles = data.get("vehicles", {}) if isinstance(data, dict) else {}
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        return ({str(k): dict(v) for k, v in vehicles.items() if isinstance(v, dict)}, dict(meta))
    except Exception:
        return {}, {}


def selected_fire_region_codes(config: dict) -> list[str]:
    matrix = config.get("region_disciplines", {}) if isinstance(config, dict) else {}
    if not isinstance(matrix, dict):
        return []
    slugs: set[str] = set()
    for slug, disciplines in matrix.items():
        if not isinstance(disciplines, list) or "brandweer" not in [str(x).lower() for x in disciplines]:
            continue
        parent = SUBREGION_PARENT.get(slug, slug)
        if parent in FIRE_REGION_CODES:
            slugs.add(parent)
    return sorted({FIRE_REGION_CODES[slug] for slug in slugs})


def load_vehicle_catalog(config: dict | None = None) -> tuple[dict[str, dict], dict[str, dict]]:
    """Load only useful regional shards into one O(1) dictionary.

    A full-NL profile is still small enough for memory, but a one-region monitor
    will not parse/load the other 24 regional files at all.
    """
    seed = load_vehicle_seed()
    wanted = set(selected_fire_region_codes(config or {}))
    if not wanted:
        wanted = {k[:2] for k in seed if len(k) >= 6}
    catalog: dict[str, dict] = {}
    # Keep only fire-style 6/7 digit entries from the legacy seed. Ambulances are
    # deliberately not copied into this database.
    for key, value in seed.items():
        digits = normalize_vehicle_digits(key)
        if digits and len(digits) >= 6 and (not wanted or digits[:2] in wanted):
            catalog[digits] = value
    metas: dict[str, dict] = {}
    for code in sorted(wanted):
        vehicles, meta = load_cached_vehicle_region(code)
        if vehicles:
            catalog.update(vehicles)
        if meta:
            metas[code] = meta
    # User corrections are deliberately applied last and therefore always win
    # over both online sources and the bundled seed.
    catalog.update(load_vehicle_overrides())
    return catalog, metas


def load_known_vehicle_keys(config: dict | None = None) -> set[str]:
    catalog, _ = load_vehicle_catalog(config)
    return set(catalog)


# Static bundled vehicle database; classification itself never depends on it.
KNOWN_FIRE_VEHICLE_KEYS = load_known_vehicle_keys()


def _header_indices(rows: list[list[str]]) -> dict[str, int]:
    aliases = {
        "callsign": ("roepnummer", "voertuignummer", "roepnaam", "nummer"),
        "station": ("standplaats", "kazerne", "post", "locatie"),
        "description": ("voertuig", "omschrijving", "type", "materieel", "functie"),
    }
    for row in rows[:20]:
        low = [normalize_space(c).lower() for c in row]
        found: dict[str, int] = {}
        for name, words in aliases.items():
            for i, cell in enumerate(low):
                if any(w in cell for w in words):
                    found[name] = i
                    break
        if "callsign" in found and ("station" in found or "description" in found):
            return found
    return {}


class _VehicleHtmlTableParser(HTMLParser):
    """Tiny stdlib HTML table parser for the public regional vehicle pages."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.text_parts: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if data:
            self.text_parts.append(data)
            if self._cell is not None:
                self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(normalize_space(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def parse_hulpdienst_vehicle_html(text: str, region_code: str) -> tuple[dict[str, dict], int]:
    """Parse one Hulpdienstvoertuigen region page and return (vehicles, pages).

    Only Brandweer/Veiligheidsregio six/seven digit roepnummers are imported;
    ambulance/police rows on the same page are intentionally ignored.
    """
    parser = _VehicleHtmlTableParser()
    parser.feed(text or "")
    vehicles: dict[str, dict] = {}
    for row in parser.rows:
        if len(row) < 5:
            continue
        callsign, discipline, type_text, description, station = row[:5]
        if normalize_space(callsign).lower() in {"id", "roepnummer", "nummer"}:
            continue
        disc = normalize_space(discipline).lower()
        if disc not in {"brandweer", "veiligheidsregio"}:
            continue
        digits = normalize_vehicle_digits(callsign)
        if len(digits) not in {6, 7} or not digits.startswith(region_code):
            continue
        station = normalize_space(station)
        if station in {"-", "–", "—"}:
            station = ""
        type_text = normalize_space(type_text)
        description = normalize_space(description)
        type_code, mapped_label = fire_vehicle_type(f"{type_text} {description}", digits)
        # Compact display: exact short type + exact station.  Keep the fuller
        # description separately for speech/diagnostics.
        label = description or mapped_label or type_text or "Brandweervoertuig"
        display_type = type_code if type_code and type_code != "BRW" else (type_text or mapped_label or "Brandweer")
        display = " ".join(x for x in (display_type, station) if x).strip()
        vehicles[digits] = {
            "callsign": callsign,
            "type": type_code,
            "label": label,
            "station": station,
            "display": display or label,
            "region": region_code,
            "source": "hulpdienstvoertuigen.nl",
        }
    page_text = normalize_space(" ".join(parser.text_parts))
    m = re.search(r"\bPagina\s+\d+\s+van\s+(\d+)\b", page_text, re.I)
    pages = max(1, min(20, int(m.group(1)))) if m else 1
    return vehicles, pages


def parse_vehicle_csv(text: str, region_code: str) -> dict[str, dict]:
    """Parse the public vehicle spreadsheet defensively.

    The published workbook occasionally changes column order/merged headings.
    This parser therefore uses headers when present and falls back to row context.
    Unknown formatting never crashes the monitor; it merely yields fewer exact
    labels while the number-plan fallback remains available.
    """
    rows = [[normalize_space(c) for c in row] for row in csv.reader(StringIO(text or ""))]
    rows = [row for row in rows if any(row)]
    headers = _header_indices(rows)
    vehicles: dict[str, dict] = {}
    current_station = ""
    station_hint_re = re.compile(rf"^(?:{re.escape(region_code)}[- ]?\d{{2}}\s+)?([A-Za-zÀ-ÿ'’()./ -]{{2,60}})$")
    normal_re = re.compile(rf"(?<!\d)({re.escape(region_code)})[- ]?(\d{{4}})(?!\d)")
    extended_re = re.compile(rf"(?<!\d)({re.escape(region_code)})[- ](\d{{2}})[- ](\d{{3}})(?!\d)")

    for row in rows:
        joined = " | ".join(row)
        normal = normal_re.search(joined)
        extended = extended_re.search(joined)
        if not normal and not extended:
            # Merged station headings in published sheets often appear as a
            # single non-empty cell. Carry that heading into following rows.
            nonempty = [c for c in row if c]
            if len(nonempty) == 1:
                candidate = re.sub(rf"^{re.escape(region_code)}[- ]?\d{{2}}\s*", "", nonempty[0]).strip(" -:")
                if station_hint_re.match(candidate) and not re.search(r"voertuig|nummer|standplaats|brandweer|database", candidate, re.I):
                    current_station = candidate
            continue
        m = extended or normal
        callsign = m.group(0).replace(" ", "-")
        digits = normalize_vehicle_digits(callsign)
        if not digits:
            continue

        call_idx = next((i for i, c in enumerate(row) if m.group(0) in c or normalize_vehicle_digits(c) == digits), -1)
        station = ""
        description = ""
        if headers:
            si = headers.get("station", -1)
            di = headers.get("description", -1)
            if 0 <= si < len(row): station = row[si]
            if 0 <= di < len(row): description = row[di]
        # Row-based fallbacks: type words tend to be adjacent to the callsign.
        context_cells = [c for i, c in enumerate(row) if c and i != call_idx and normalize_vehicle_digits(c) != digits]
        context = " ".join(context_cells)
        if not description:
            type_cells = [c for c in context_cells if re.search(r"tankautospuit|autoladder|hoogwerker|hulpverlen|water|dienst|haakarm|schuim|commando|officier|gevaarlijke|materiaal|verkenning|logist", c, re.I)]
            description = max(type_cells, key=len, default="")
        if not station:
            # Prefer short proper-name cells that are not the vehicle description.
            candidates = [c for c in context_cells if c != description and 2 <= len(c) <= 60 and not re.search(r"tankautospuit|autoladder|hoogwerker|hulpverlen|voertuig|wagen|haakarm|aanhanger|dienstauto|dienstbus|materieel|officier|adviseur|brandweer", c, re.I)]
            station = candidates[0] if candidates else current_station
        station = re.sub(rf"^{re.escape(region_code)}[- ]?\d{{2}}\s*", "", station or current_station).strip(" -:")
        type_code, type_label = fire_vehicle_type(description or context, digits)
        if not description:
            description = type_label
        if station and station.lower() in {"actief", "in dienst", "roepnummer"}:
            station = current_station
        display = " ".join(x for x in (type_label, station) if x).strip()
        vehicles[digits] = {
            "callsign": callsign,
            "type": type_code,
            "label": type_label,
            "station": station,
            "display": display or type_label,
            "region": region_code,
        }
    return vehicles


def extract_fire_callsigns(*values: str) -> list[tuple[str, str]]:
    """Return stable unique (digits, formatted) nationwide fire callsigns."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for value in values:
        raw = value or ""
        for m in FIRE_EXTENDED_CALLSIGN_RE.finditer(raw):
            prefix, post, tail = m.group(1), m.group(2), m.group(3)
            digits = f"{prefix}{post}{tail}"
            if digits not in seen:
                seen.add(digits); out.append((digits, f"{prefix}-{post}-{tail}"))
        for m in FIRE_CALLSIGN_RE.finditer(raw):
            prefix, tail = m.group(1), m.group(2)
            digits = f"{prefix}{tail}"
            if digits in seen:
                continue
            seen.add(digits)
            out.append((digits, f"{prefix}-{tail}"))
    return out


def raw_line_for_callsign(message: "Message", digits: str) -> str:
    """Pick the most P2000-like raw field containing a callsign for diagnostics."""
    prefix, tail = digits[:2], digits[2:]
    variants = {digits, f"{prefix}-{tail}", f"{prefix} {tail}"}
    if len(digits) == 7:
        variants.update({f"{prefix}-{digits[2:4]}-{digits[4:]}", f"{prefix} {digits[2:4]} {digits[4:]}"})
    candidates = []
    for raw in (message.title, message.summary):
        compact = re.sub(r"\s+", " ", raw or "").strip()
        hay_digits = re.sub(r"\D", "", compact)
        if digits in hay_digits or any(v in compact for v in variants):
            score = 0
            if re.match(r"^\s*(?:P\s*[123]|A[012]|B[12])\b", compact, re.I):
                score += 10
            if re.search(r"\b(?:BR|OMS|BZB|GRIP|TS|HV|HW|OVD|HOVD)\b", compact, re.I):
                score += 4
            score += min(4, len(re.findall(r"\b\d{5,8}\b", compact)))
            candidates.append((score, len(compact), compact))
    if candidates:
        return max(candidates)[2][:1200]
    return (message.title or message.summary or "")[:1200]


def local_lan_addresses() -> list[dict]:
    """Best-effort LAN IPv4 discovery, preferring physical Wi-Fi/Ethernet interfaces."""
    found: dict[str, str] = {}
    ip_cmd = shutil.which("ip")
    if ip_cmd:
        try:
            proc = subprocess.run([ip_cmd, "-j", "-4", "addr", "show", "up"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=3, check=False)
            if proc.returncode == 0:
                rows = json.loads(proc.stdout.decode("utf-8", "replace") or "[]")
                skip_prefixes = ("lo", "docker", "br-", "veth", "virbr", "tailscale", "tun", "tap", "wg", "zt", "proton", "nord", "vpn")
                for row in rows:
                    ifname = str(row.get("ifname", ""))
                    if ifname.lower().startswith(skip_prefixes):
                        continue
                    for info in row.get("addr_info", []):
                        if info.get("family") != "inet":
                            continue
                        addr = str(info.get("local", ""))
                        try:
                            ip = ipaddress.ip_address(addr)
                        except ValueError:
                            continue
                        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                            continue
                        found[addr] = ifname
        except Exception:
            pass
    # Optional fallback when interface discovery is limited.
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            addr = item[4][0]
            ip = ipaddress.ip_address(addr)
            if not ip.is_loopback and not ip.is_link_local:
                found.setdefault(addr, "host")
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(.5)
        sock.connect(("1.1.1.1", 80))
        addr = sock.getsockname()[0]
        sock.close()
        ip = ipaddress.ip_address(addr)
        if not ip.is_loopback and not ip.is_link_local:
            found.setdefault(addr, "default")
    except Exception:
        pass
    def score(item):
        addr, iface = item
        if addr.startswith("192.168."):
            n = 0
        elif addr.startswith("172."):
            n = 1
        elif addr.startswith("10."):
            n = 2
        else:
            n = 3
        return (n, iface, addr)
    return [{"address": addr, "interface": iface} for addr, iface in sorted(found.items(), key=score)]

GRIP_RULES = [
    (re.compile(r"\bGRIP\s*5\b", re.I), "GRIP 5", 100),
    (re.compile(r"\bGRIP\s*4\b", re.I), "GRIP 4", 95),
    (re.compile(r"\bGRIP\s*3\b", re.I), "GRIP 3", 90),
    (re.compile(r"\bGRIP\s*2\b", re.I), "GRIP 2", 85),
    (re.compile(r"\bGRIP\s*1\b", re.I), "GRIP 1", 80),
]
FIRE_SCALE_RULES = [
    # Native P2000 uses both full and abbreviated forms, e.g.
    # (Zeer grote BR) and (Zeer gr. BR).
    (re.compile(r"\bZEER\s+(?:GROTE|GR\.?)\s+(?:BRAND|BR)\b", re.I), "Zeer grote brand", 70),
    (re.compile(r"\b(?:GROTE|GR\.?)\s+(?:BRAND|BR)\b", re.I), "Grote brand", 60),
    (re.compile(r"\bMIDDEL\s*(?:BRAND|BR)\b", re.I), "Middelbrand", 50),
    (re.compile(r"\bKLEINE?\s+(?:BRAND|BR)\b", re.I), "Kleine brand", 40),
]
OTHER_SCALE_RULES = [
    (re.compile(r"\bZEER\s+(?:GROTE|GR\.?)\s+HV\b", re.I), "Zeer grote hulpverlening", 70),
    (re.compile(r"\b(?:GROTE|GR\.?)\s+HV\b", re.I), "Grote hulpverlening", 60),
    (re.compile(r"\bMIDDEL\s+HV\b", re.I), "Middel hulpverlening", 50),
    (re.compile(r"\bKLEINE?\s+HV\b", re.I), "Kleine hulpverlening", 40),
    (re.compile(r"\bZEER\s+(?:GROTE|GR\.?)\s+IBGS\b", re.I), "Zeer groot IBGS", 70),
    (re.compile(r"\b(?:GROTE|GR\.?)\s+IBGS\b", re.I), "Groot IBGS", 60),
    (re.compile(r"\bMIDDEL\s+IBGS\b", re.I), "Middel IBGS", 50),
    (re.compile(r"\bKLEINE?\s+IBGS\b", re.I), "Klein IBGS", 40),
]

# Runtime scope is selected by the user in the Windows setup wizard.
# Legacy place aliases below are retained only as parser hints for older fixtures;
# they no longer restrict which regions the monitor can receive.
LIFELINER_123_RE = re.compile(
    r"\b(?:life\s*liner|lifeliner|mmt|lfl|ll)\s*[- ]?0?([123])\b", re.I
)
SCOPE_LABEL = "Configureerbare regioselectie"

# Parser hints retained for a handful of ambiguous older P2000 formats.
# They are NOT a reception scope; live scope is fully profile-driven nationwide.
PARSER_HINT_PLACES = {
    "eemnes",
    "baarn",
    "bunschoten", "bunschoten-spakenburg", "spakenburg", "eemdijk", "eembrugge",
    "hoogland", "hooglanderveen", "amersfoort",
    "soest", "soesterberg", "lage vuursche",
    "laren", "laren nh", "laren-nh",
    "blaricum", "huizen", "hilversum",
    "bussum", "naarden", "muiderberg",
    "s-graveland", "'s-graveland", "graveland",
    "loosdrecht", "kortenhoef",
    "almere", "almere haven", "almere stad", "almere buiten",
}
PARSER_HINT_SPACE_KEYS = {p.replace("-", " ") for p in PARSER_HINT_PLACES}
KNOWN_MONITOR_PLACES = set(PARSER_HINT_PLACES)
BORDER_DISPATCH_PLACES: set[str] = set()

# Geocoding search areas. These are deliberately a little wider than each town
# so boundary roads and mutual-aid locations are not lost. They are used only
# to rank/filter official PDOK results; they are never shown as incident points.
GEOCODE_AREAS = {
    "eemnes": ("Eemnes", (5.18, 52.20, 5.34, 52.31), (5.263, 52.254)),
    "baarn": ("Baarn", (5.18, 52.13, 5.36, 52.25), (5.287, 52.211)),
    "eembrugge": ("Baarn", (5.18, 52.13, 5.36, 52.25), (5.315, 52.218)),
    "lage vuursche": ("Baarn", (5.15, 52.12, 5.30, 52.23), (5.224, 52.179)),
    "bunschoten": ("Bunschoten", (5.29, 52.20, 5.47, 52.34), (5.378, 52.244)),
    "bunschoten spakenburg": ("Bunschoten", (5.29, 52.20, 5.47, 52.34), (5.378, 52.251)),
    "spakenburg": ("Bunschoten", (5.29, 52.20, 5.47, 52.34), (5.378, 52.251)),
    "eemdijk": ("Bunschoten", (5.29, 52.20, 5.47, 52.34), (5.330, 52.254)),
    "amersfoort": ("Amersfoort", (5.27, 52.10, 5.50, 52.24), (5.387, 52.156)),
    "hoogland": ("Amersfoort", (5.27, 52.10, 5.50, 52.24), (5.373, 52.182)),
    "hooglanderveen": ("Amersfoort", (5.27, 52.10, 5.50, 52.24), (5.430, 52.187)),
    "soest": ("Soest", (5.20, 52.06, 5.38, 52.20), (5.291, 52.173)),
    "soesterberg": ("Soest", (5.20, 52.06, 5.38, 52.20), (5.285, 52.119)),
    "laren": ("Laren", (5.16, 52.20, 5.29, 52.29), (5.227, 52.256)),
    "laren nh": ("Laren", (5.16, 52.20, 5.29, 52.29), (5.227, 52.256)),
    "blaricum": ("Blaricum", (5.17, 52.23, 5.32, 52.32), (5.248, 52.272)),
    "huizen": ("Huizen", (5.16, 52.25, 5.34, 52.36), (5.243, 52.299)),
    "hilversum": ("Hilversum", (5.05, 52.15, 5.25, 52.29), (5.176, 52.224)),
    "s graveland": ("Wijdemeren", (5.05, 52.19, 5.16, 52.28), (5.121, 52.244)),
    "graveland": ("Wijdemeren", (5.05, 52.19, 5.16, 52.28), (5.121, 52.244)),
    "loosdrecht": ("Wijdemeren", (5.00, 52.13, 5.16, 52.25), (5.067, 52.206)),
    "kortenhoef": ("Wijdemeren", (5.05, 52.18, 5.16, 52.26), (5.107, 52.239)),
    "bussum": ("Gooise Meren", (5.08, 52.24, 5.22, 52.34), (5.161, 52.274)),
    "naarden": ("Gooise Meren", (5.08, 52.25, 5.24, 52.36), (5.163, 52.296)),
    "muiderberg": ("Gooise Meren", (5.07, 52.30, 5.18, 52.35), (5.121, 52.326)),
    "almere": ("Almere", (5.03, 52.27, 5.43, 52.46), (5.264, 52.367)),
    "almere haven": ("Almere", (5.03, 52.27, 5.43, 52.46), (5.220, 52.338)),
    "almere stad": ("Almere", (5.03, 52.27, 5.43, 52.46), (5.218, 52.371)),
    "almere buiten": ("Almere", (5.03, 52.27, 5.43, 52.46), (5.290, 52.394)),
}
GEOCODE_REGION_BBOX = (3.20, 50.70, 7.30, 53.65)
GEOCODE_REGION_CENTER = (5.30, 52.15)

# Region name fragments that can appear in enriched feed descriptions.
REGION_PATTERNS = {
    "Utrecht": re.compile(r"\bregio\s+utrecht\b|\bveiligheidsregio\s+utrecht\b", re.I),
    "Gooi en Vechtstreek": re.compile(r"\bgooi\s+en\s+vechtstreek\b", re.I),
    "Flevoland": re.compile(r"\bregio\s+flevoland\b|\bveiligheidsregio\s+flevoland\b", re.I),
}

def _place_key(value: str) -> str:
    value = (value or "").lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9à-ÿ' -]+", " ", value)
    return normalize_space(value)


def place_is_nearby(city: str, categories: list[str] | None = None, region_key: str | None = None) -> bool:
    return place_is_monitor_area(city, categories)

def place_is_monitor_area(city: str, categories: list[str] | None = None) -> bool:
    candidates = [city or "", *(categories or [])]
    for raw in candidates:
        key = _place_key(raw.replace("_", " "))
        if key in PARSER_HINT_PLACES or key.replace("-", " ") in PARSER_HINT_SPACE_KEYS:
            return True
        # Categories may contain forms such as "Plaats Eemnes".
        for place in PARSER_HINT_SPACE_KEYS:
            if len(place) >= 5 and re.search(rf"(?:^|\b){re.escape(place)}(?:\b|$)", key.replace("-", " ")):
                return True
    return False

def region_for_city(city: str) -> str:
    key = _place_key(city).replace("-", " ")
    if key in {"eemnes", "baarn", "bunschoten", "bunschoten spakenburg", "spakenburg", "eemdijk", "eembrugge", "hoogland", "hooglanderveen", "amersfoort", "soest", "soesterberg", "lage vuursche"}:
        return "Utrecht"
    if key in {"laren", "laren nh", "blaricum", "huizen", "hilversum", "bussum", "naarden", "muiderberg", "s graveland", "'s graveland", "graveland", "loosdrecht", "kortenhoef"}:
        return "Gooi en Vechtstreek"
    if key.startswith("almere"):
        return "Flevoland"
    return ""

def detect_region(summary: str) -> str:
    text = summary or ""
    for label, pattern in REGION_PATTERNS.items():
        if pattern.search(text):
            return label
    m = re.search(r"\bRegio\s+([^.]+?)(?:\.\s*(?:Gemeld|$)|$)", text, re.I)
    return normalize_space(m.group(1)) if m else ""


MMT_RESOURCES = {
    "13991": {"team": 1, "kind": "helicopter", "label": "Lifeliner 1"},
    "13901": {"team": 1, "kind": "car", "label": "MMT-auto 1"},
    "17992": {"team": 2, "kind": "helicopter", "label": "Lifeliner 2"},
    "17902": {"team": 2, "kind": "car", "label": "MMT-auto 2"},
    "17901": {"team": 2, "kind": "car", "label": "MMT-auto 2"},
    "08993": {"team": 3, "kind": "helicopter", "label": "Lifeliner 3"},
    "08903": {"team": 3, "kind": "car", "label": "MMT-auto 3"},
}
MMT_RESOURCE_RE = re.compile(r"(?<!\d)(?:13[- ]?991|13[- ]?901|17[- ]?992|17[- ]?902|17[- ]?901|08[- ]?993|08[- ]?903)(?!\d)", re.I)
LL2_CAPCODE_RE = re.compile(r"(?<!\d)(?:17992|17[- ]?992)(?!\d)", re.I)
LL3_CAPCODE_RE = re.compile(r"(?<!\d)(?:08993|08[- ]?993)(?!\d)", re.I)

# OvD-G capcodes remain known to the parser for fire-service assistance context.
OVDG_CAPCODES = {"1220803", "1220804", "1220805"}
OVDG_CAPCODE_RE = re.compile(r"(?<!\d)(?:1220803|1220804|1220805|12[- ]?2080[345])(?!\d)", re.I)

def detect_ovdg_capcode(title: str, summary: str, units: list[str] | None = None) -> str | None:
    hay = " ".join([title or "", summary or "", " ".join(units or [])])
    m = OVDG_CAPCODE_RE.search(hay)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    return digits if digits in OVDG_CAPCODES else None

def allowed_by_service_policy(title: str, summary: str, service: str, units: list[str] | None = None) -> bool:
    """Basic parser sanity check; the setup profile decides what is visible."""
    svc = (service or "").lower()
    resource = detect_mmt_resource(title, summary, units)
    if resource:
        return resource.get("kind") in {"helicopter", "car"}
    return svc in {"brandweer", "ambulance", "politie", "lifeliner", "knrm", "overig"}

def detect_mmt_resource(title: str, summary: str, units: list[str] | None = None) -> dict | None:
    hay = " ".join([title or "", summary or "", " ".join(units or [])])
    hit = MMT_RESOURCE_RE.search(hay)
    if hit:
        digits = re.sub(r"\D", "", hit.group(0))
        meta = MMT_RESOURCES.get(digits)
        if meta:
            return {"code": digits, **meta}
    m = LIFELINER_123_RE.search(hay)
    if m:
        team = int(m.group(1))
        return {"code": "", "team": team, "kind": "helicopter", "label": f"Lifeliner {team}"}
    return None

def detect_lifeliner_number(title: str, summary: str, units: list[str] | None = None) -> int | None:
    meta = detect_mmt_resource(title, summary, units)
    return int(meta["team"]) if meta else None


def message_region_slug(categories: list[str] | None = None, url: str = "") -> str | None:
    for cat in categories or []:
        raw = normalize_space(str(cat or ""))
        if raw.lower().startswith("regio "):
            label = raw[6:].strip().lower()
            if label in REGION_LABEL_TO_SLUG:
                return REGION_LABEL_TO_SLUG[label]
            slug = re.sub(r"[^a-z0-9]+", "-", label).strip("-")
            if slug in REGION_CATALOG:
                return slug
    return region_slug_from_article_url(url)


def setup_region_disciplines(config: dict | None) -> dict[str, list[str]]:
    raw = (config or {}).get("region_disciplines") or {}
    out: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for slug, values in raw.items():
            if slug not in REGION_CATALOG or not isinstance(values, list):
                continue
            requested = {str(v).lower() for v in values}
            clean = [x for x in ALL_DISCIPLINES if x in requested]
            if clean:
                out[slug] = clean
    return out


def config_allows_message(config: dict, message: "Message") -> bool:
    matrix = setup_region_disciplines(config)
    if not matrix:
        return False
    service = (message.service or "overig").lower()
    resource = detect_mmt_resource(message.title, message.summary, message.units)
    if resource:
        service = "lifeliner" if resource.get("kind") == "helicopter" else "ambulance"
    wanted = "lifeliner" if service == "lifeliner" else service
    if wanted not in {"brandweer", "ambulance", "politie", "knrm", "lifeliner"}:
        return False
    region_slug = message_region_slug(message.categories, message.url)
    if not region_slug:
        # A national RSS item can occasionally lack a usable region marker.
        # Only accept that ambiguity when the user explicitly selected this
        # discipline for all 25 safety regions; narrower profiles stay strict.
        return all(wanted in matrix.get(slug, []) for slug in SAFETY_REGION_SLUGS)
    if wanted in matrix.get(region_slug, []):
        return True
    # National feeds can identify an article by one of Alarmeringen's three
    # subregions even when the user selected the encompassing safety region.
    parent = SUBREGION_PARENT.get(region_slug)
    return bool(parent and wanted in matrix.get(parent, []))


def in_monitor_scope(title: str, summary: str, units: list[str] | None = None,
                     city: str = "", categories: list[str] | None = None) -> bool:
    # Retained for backwards parser tests. Runtime filtering is profile-driven.
    return True

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_dt(value: str | None) -> str:
    if not value:
        return utcnow_iso()
    value = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            dt = None
    if dt is None:
        return utcnow_iso()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    # Atom summaries can contain escaped/simple HTML. Keep this deliberately small.
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def enumerate_windows_monitors() -> list[dict]:
    """Enumerate attached desktop monitors through the native Windows API."""
    fallback = {"id":"primary","device":"primary","label":"Primair scherm","x":0,"y":0,"width":1920,"height":1080,"primary":True}
    if os.name != "nt":
        return [fallback]
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        class RECT(ctypes.Structure):
            _fields_=[("left",wintypes.LONG),("top",wintypes.LONG),("right",wintypes.LONG),("bottom",wintypes.LONG)]
        class MONITORINFOEXW(ctypes.Structure):
            _fields_=[("cbSize",wintypes.DWORD),("rcMonitor",RECT),("rcWork",RECT),("dwFlags",wintypes.DWORD),("szDevice",wintypes.WCHAR*32)]
        rows=[]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(RECT),wintypes.LPARAM)
        def collect(hmon, hdc, rect, lparam):
            info=MONITORINFOEXW(); info.cbSize=ctypes.sizeof(info)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r=info.rcMonitor
                rows.append({"device":str(info.szDevice or ""),"x":int(r.left),"y":int(r.top),"width":int(r.right-r.left),"height":int(r.bottom-r.top),"primary":bool(info.dwFlags & 1)})
            return True
        cb=callback_type(collect)
        user32.EnumDisplayMonitors(0,0,cb,0)
        rows.sort(key=lambda m:(not m["primary"],m["x"],m["y"],m["device"]))
        for i,row in enumerate(rows,1):
            row["id"]=row["device"] or f"display-{i}"
            row["label"]=f"Scherm {i} • {row['width']}×{row['height']}" + (" • primair" if row["primary"] else "")
        return rows or [fallback]
    except Exception:
        return [fallback]


def choose_windows_monitor(selector: str | None, monitors: list[dict] | None = None) -> dict:
    rows=list(monitors or enumerate_windows_monitors())
    wanted=normalize_space(str(selector or "primary"))
    if wanted.lower() not in {"primary","primair","auto"}:
        for row in rows:
            if wanted.lower() in {str(row.get("id") or "").lower(),str(row.get("device") or "").lower()}:
                return row
        if wanted.isdigit():
            idx=int(wanted)-1
            if 0 <= idx < len(rows): return rows[idx]
    return next((row for row in rows if row.get("primary")), rows[0])


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _simple_ascii_lower(value: str) -> str:
    value = normalize_space(str(value or "")).lower()
    return value


def normalize_location_token(value: str, alias_map: dict[str, str] | None = None) -> str:
    """Normalize Dutch street/place spellings so trivial variants cluster together.

    Examples: Prof. Asserweg / Prof Asserweg / Professor Asserweg.
    User-defined aliases from the control page are applied first, after light
    punctuation folding, and then several common Dutch abbreviations are
    expanded so incident grouping remains stable across source variants.
    """
    raw = normalize_space(str(value or ""))
    if not raw:
        return ""
    probe = _simple_ascii_lower(raw)
    probe = re.sub(r"[.,;:()]+", " ", probe)
    probe = re.sub(r"\s+", " ", probe).strip()
    normalized_aliases: dict[str, str] = {}
    if isinstance(alias_map, dict):
        for k, v in alias_map.items():
            kk = re.sub(r"\s+", " ", str(k or "").lower().replace(".", " ")).strip()
            vv = normalize_space(str(v or ""))
            if kk and vv:
                normalized_aliases[kk] = vv
    if probe in normalized_aliases:
        raw = normalized_aliases[probe]
    s = normalize_space(str(raw or ""))
    replacements = [
        (r"\bprof\.?\b", "professor"),
        (r"\bburg\.?\b", "burgemeester"),
        (r"\bdr\.?\b", "dokter"),
        (r"\bst\.?\b", "sint"),
        (r"\bsint\b", "sint"),
        (r"\bgen\.?\b", "generaal"),
        (r"\bkon\.?\b", "koningin"),
        (r"\bprins\.?\b", "prins"),
        (r"\bpr\.?\b", "prins"),
    ]
    lowered = s.lower()
    for pattern, repl in replacements:
        lowered = re.sub(pattern, repl, lowered, flags=re.I)
    lowered = POSTCODE_RE.sub(" ", lowered)
    lowered = re.sub(r"[^a-z0-9à-ÿ]+", " ", lowered)
    return normalize_space(lowered)


def normalize_city_token(value: str) -> str:
    return normalize_location_token(value, None)


def geocode_area_for_city(city: str) -> tuple[str, tuple[float, float, float, float], tuple[float, float]]:
    key = normalize_city_token(city)
    return GEOCODE_AREAS.get(key, (normalize_space(city) or "Nederland", GEOCODE_REGION_BBOX, GEOCODE_REGION_CENTER))


def geocode_street_key(value: str) -> str:
    """Normalize a P2000 location to a BAG/BGT public-space name when possible."""
    raw = normalize_space(value)
    if not raw:
        return ""
    # Motorway hectometer locations are not ordinary BAG street names.
    if re.search(r"\b[AN]\d{1,3}\b", raw, re.I) and re.search(r"\b(?:LI|RE)\b|\d{1,3}[,.]\d\b", raw, re.I):
        return ""
    raw = POSTCODE_RE.sub(" ", raw)
    raw = re.sub(r"\s+[0-9]{1,5}(?:[A-Za-z])?(?:[-/]?[0-9A-Za-z]{1,6})?(?:\s+[A-Za-z])?\s*$", "", raw)
    raw = re.sub(r"\s+(?:thv|t\.?h\.?v\.?|nabij|tegenover)\b.*$", "", raw, flags=re.I)
    return normalize_location_token(raw)


def geometry_center(geometry: dict | None) -> tuple[float, float] | None:
    """Return a stable WGS84 centre from Point/Line/Polygon GeoJSON geometry."""
    if not isinstance(geometry, dict):
        return None
    coords = geometry.get("coordinates")
    points: list[tuple[float, float]] = []
    def walk(node):
        if isinstance(node, (list, tuple)) and len(node) >= 2 and all(isinstance(x, (int, float)) for x in node[:2]):
            lon, lat = float(node[0]), float(node[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                points.append((lon, lat))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
    walk(coords)
    if not points:
        return None
    # For very detailed polygons/lines, sample evenly so this stays cheap.
    if len(points) > 500:
        step = max(1, len(points) // 500)
        points = points[::step][:500]
    lon = sum(x for x, _ in points) / len(points)
    lat = sum(y for _, y in points) / len(points)
    return lat, lon


def rough_distance_sq(lat: float, lon: float, center: tuple[float, float]) -> float:
    """Cheap local ranking distance; longitude is scaled for Dutch latitude."""
    clon, clat = center[0], center[1]
    return (lat - clat) ** 2 + ((lon - clon) * 0.615) ** 2


def build_location_alias_map(settings: dict | None) -> dict[str, str]:
    aliases = (settings or {}).get("locationAliases") or {}
    out: dict[str, str] = {}
    if isinstance(aliases, dict):
        for k, v in aliases.items():
            kk = normalize_location_token(str(k or ""), None)
            vv = normalize_space(str(v or ""))
            if kk and vv:
                out[kk] = vv
    return out



def is_fire_dispatch_context(title: str, summary: str, units: list[str] | None = None) -> bool:
    """Recognize a genuine fire-brigade dispatch without stealing ambulance rows.

    A regional Bxx dispatch identifier (BOB/BRT/BZB/...) is authoritative. A raw
    A0/A1/A2/B1/B2 ambulance line is authoritative in the other direction: its
    numeric ambulance/resource identifiers must never become a fire signal merely
    because they can resemble six-digit regional fire callsigns.
    """
    hay = " ".join([title or "", summary or "", " ".join(units or [])])
    if FIRE_DISPATCH_CODE_RE.search(hay):
        return True

    # Ambulance feeds commonly contain numbers that look exactly like regional
    # fire callsigns. Priority-at-start wins unless an actual Bxx fire dispatch
    # marker above proves this is a fire-brigade row. MMT is promoted separately.
    if AMBULANCE_RAW_RE.search(title or "") or AMBULANCE_RAW_RE.search(summary or ""):
        return False

    # Strong police/pers syntaxes use numeric incident IDs that can look exactly
    # like a six-digit fire callsign. Reject them before the generic fire hint.
    if (POLICE_BUNDLE_RE.search(title or "") or POLICE_BUNDLE_RE.search(summary or "") or
            POLICE_ICNUM_RE.search(title or "") or POLICE_ICNUM_RE.search(summary or "") or
            POLICE_SLASH_RE.search(title or "") or POLICE_SLASH_RE.search(summary or "") or
            POLICE_PRIO_ROAD_RE.search(title or "") or POLICE_PRIO_ROAD_RE.search(summary or "")):
        return False

    # Explicit fire vehicle labels are strong even without a Bxx bundle code.
    if re.search(r"\b(?:TS|HV|HW|AL|RV|OVD-B|HOVD-B|AGS|VEBS|WT|WTS|WTH|WO|FRB)\s*[- ]+\d{2}[- ]?\d{4}\b", hay, re.I):
        return True

    # A fire-specific incident phrase plus one or more *trailing* roepnummers is
    # also authoritative. This catches rows such as "P 2 Ass. Politie ... 203132"
    # where a regional Bxx dispatch code is omitted. Do not use arbitrary six-
    # digit numbers in the middle: police bundle IDs look identical.
    if FIRE_INCIDENT_HINT_RE.search(hay):
        if re.search(r"(?:\b\d{6}\b|\b\d{2}[- ]\d{2}[- ]\d{3}\b)(?:\s+(?:\d{6}|\d{2}[- ]\d{2}[- ]\d{3}))*\s*$", title or ""):
            return True

    # For other bare six-digit numbers, only trust callsigns present in our
    # bundled vehicle database.
    return any(digits in KNOWN_FIRE_VEHICLE_KEYS for digits, _formatted in extract_fire_callsigns(hay))


def is_fire_assist_ambulance(title: str, summary: str, units: list[str] | None = None) -> bool:
    """Backward-compatible helper for Ass. Ambu fire-brigade dispatches."""
    hay = " ".join([title or "", summary or "", " ".join(units or [])])
    return bool(re.search(r"\bASS\.?\s*AMBU\b", hay, re.I) and is_fire_dispatch_context(title, summary, units))


def detect_service(title: str, summary: str, categories: list[str]) -> str:
    # A real fire dispatch may contain words such as AMBU or POL and can even be
    # mislabeled by an upstream category. Strong dispatch markers win first.
    if is_fire_dispatch_context(title, summary):
        return "brandweer"
    # Strong police/pers formats seen across several regions. These checks run
    # before feed categories because aggregation pages can occasionally carry
    # mixed or stale category metadata.
    if (POLICE_BUNDLE_RE.search(title or "") or POLICE_BUNDLE_RE.search(summary or "") or
            POLICE_ICNUM_RE.search(title or "") or POLICE_ICNUM_RE.search(summary or "") or
            POLICE_SLASH_RE.search(title or "") or POLICE_SLASH_RE.search(summary or "") or
            POLICE_PLAIN_RE.search(title or "") or POLICE_PLAIN_RE.search(summary or "") or
            POLICE_PRIO_ROAD_RE.search(title or "") or POLICE_PRIO_ROAD_RE.search(summary or "")):
        return "politie"
    # Categories are the cleanest signal according to the feed documentation.
    for cat in categories:
        key = cat.strip().lower()
        if key in SERVICE_ALIASES:
            return SERVICE_ALIASES[key]
    # Prefer distinctive service names before generic words such as "medisch".
    joined = " ".join([title, summary]).lower()
    ordered = [
        ("lifeliner", "lifeliner"), ("mmt", "lifeliner"), ("traumaheli", "lifeliner"),
        ("brandweer", "brandweer"), ("ambulance", "ambulance"), ("ambu", "ambulance"),
        ("politie", "politie"), ("knrm", "knrm"), ("kustwacht", "knrm"), ("medisch", "ambulance"),
    ]
    for needle, service in ordered:
        if re.search(rf"\b{re.escape(needle)}\b", joined):
            return service
    if "🚒" in title or "🔥" in title:
        return "brandweer"
    if "🚑" in title:
        return "ambulance"
    if "🚓" in title or "👮" in title:
        return "politie"
    if "🚁" in title:
        return "lifeliner"
    return "overig"


def detect_priority(title: str, summary: str) -> str:
    match = PRIORITY_RE.search(f"{title} {summary}")
    if not match:
        # Some Rotterdam police/pers rows use a bare leading 1..5 as priority.
        m = re.match(r"^\s*([1-5])\s+(?=.+?\bICnum\b)", title or "", re.I)
        return f"P{m.group(1)}" if m else ""
    if match.group(1) or match.group(2):
        return f"P{match.group(1) or match.group(2)}"
    return (match.group(3) or "").replace(" ", "").upper()


def detect_scale(title: str, summary: str) -> tuple[str, int]:
    """Return every meaningful escalation carried by one P2000 row.

    A single dispatch can legitimately contain both a fire-size escalation and
    a GRIP level, e.g. ``(GRIP 1) (Zeer gr. BR)``. Older versions returned the
    first match only, which made the rest of the row look like unparsed noise.
    The API keeps one string for compatibility but joins both labels.
    """
    joined = f"{title} {summary}"
    labels: list[str] = []
    scores: list[int] = []

    # Fire size first so UI/speech reads naturally: "zeer grote brand en GRIP 1".
    fire_match = None
    for regex, label, score in FIRE_SCALE_RULES:
        m = regex.search(joined)
        if not m:
            continue
        # The generic "gr. BR" rule can also occur inside "zeer gr. BR";
        # once the specific zeer-groot form matched, do not add "Grote brand".
        if label == "Grote brand" and re.search(r"\bZEER\s+(?:GROTE|GR\.?)\s+(?:BRAND|BR)\b", joined, re.I):
            continue
        fire_match = (label, score)
        break
    if fire_match:
        labels.append(fire_match[0]); scores.append(fire_match[1])

    for regex, label, score in OTHER_SCALE_RULES:
        if regex.search(joined):
            labels.append(label); scores.append(score)
            break

    for regex, label, score in GRIP_RULES:
        if regex.search(joined):
            labels.append(label); scores.append(score)
            break

    return (" + ".join(labels), max(scores)) if labels else ("", 0)


def infer_city(categories: list[str], title: str) -> str:
    # Feed docs specify categories for service and city. Remove known service terms.
    candidates = []
    for cat in categories:
        clean = normalize_space(cat)
        if clean.lower().startswith("regio "):
            continue
        if clean.lower() not in SERVICE_ALIASES and clean.lower() not in {
            "melding", "p2000", "spoed", "brand", "medisch", "trauma"
        }:
            candidates.append(clean)
    if candidates:
        # Usually city is the most human-looking category; the last one is a good fallback.
        return re.sub(r"^'S(?=[ -])", "'s", candidates[-1].title())

    # Alarmeringen ambulance format: "A1 Breda rit: 123456".
    m = re.search(r"\b(?:A[012]|B[12])\s+([A-Za-zÀ-ÿ' -]{2,}?)\s+rit\s*:", title, re.I)
    if m:
        return re.sub(r"^'S(?=[ -])", "'s", normalize_space(m.group(1)).title())

    # For monitor-area messages, prefer the longest known place occurring in the raw title.
    # This covers fire messages where the place is near the end, before vehicle numbers.
    title_key = f" {_place_key(title)} "
    hits = [place for place in KNOWN_MONITOR_PLACES if f" {place} " in title_key]
    if hits:
        return re.sub(r"^'S(?=[ -])", "'s", max(hits, key=len).title().replace(" En ", " en ").replace(" Van ", " van "))

    # Mutual-aid rows can end in a Belgian border place that is intentionally
    # not in the broad local substring set (e.g. "Meer"). Only trust such a name
    # when the row has a strong native fire marker and the place is directly
    # before a trailing 20-xxxx callsign.
    if is_fire_dispatch_context(title, ""):
        tail = re.sub(r"(?:\s+\d{2}[- ]?\d{4})+\s*$", "", normalize_space(title), flags=re.I)
        tail = re.sub(r"\([^)]*\)", " ", tail)
        tail = normalize_space(tail.strip(" ,-–—#"))
        tail_key = _place_key(tail)
        for place in sorted(BORDER_DISPATCH_PLACES, key=len, reverse=True):
            if tail_key == place or tail_key.endswith(" " + place):
                return place.title()

    # Common title format: "... — Street, City" or "... in City".
    if "—" in title:
        tail = title.rsplit("—", 1)[-1].strip()
        if "," in tail:
            return tail.rsplit(",", 1)[-1].strip()
    m = re.search(r"\bin\s+([A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’ .-]{2,})$", title, re.I)
    return normalize_space(m.group(1)) if m else ""


def _title_before_city(value: str, city: str) -> str:
    """Return the title portion before an exact city token (case-insensitive)."""
    text = normalize_space(value)
    if not text or not city:
        return text
    m = re.search(rf"\b{re.escape(city)}\b", text, re.I)
    return normalize_space(text[:m.start()]) if m else text


def _strip_trailing_dispatch_noise(value: str) -> str:
    """Remove bundle/callsign bookkeeping that is never part of an address."""
    s = normalize_space(value)
    if not s:
        return ""
    s = re.sub(r"\s+ICnum\s*[A-Za-z0-9-]*\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*\(\s*Heterdaad\s*:[^)]*\)\s*$", "", s, flags=re.I)
    s = re.sub(r"\b(?:BON|RIT)\s*:?[ ]*[0-9A-Za-z-]+\b.*$", "", s, flags=re.I)
    # Regional fire callsigns at the tail: 203132 / 20-3132 / 01-18-849.
    tail_unit = r"(?:\d{6}|\d{2}[- ]\d{4}|\d{2}[- ]\d{2}[- ]\d{3})"
    s = re.sub(rf"(?:\s+{tail_unit})+\s*$", "", s)
    return normalize_space(s.strip(" ,-–—"))


def _city_forms(city: str) -> list[str]:
    city = normalize_space(city)
    if not city:
        return []
    forms = [city]
    low = city.lower()
    aliases = {
        "den haag": ["'s-Gravenhage", "s-Gravenhage", "SGRAVH"],
        "'s-gravenhage": ["Den Haag", "s-Gravenhage", "SGRAVH"],
        "s-gravenhage": ["Den Haag", "'s-Gravenhage", "SGRAVH"],
        "leidschendam": ["LEIDDM"],
        "voorburg": ["VOORBG"],
        "poeldijk": ["POELDK"],
        "wateringen": ["WATERI"],
        "maassluis": ["MAASSL"],
        "spijkenisse": ["SPIJKN"],
        "rotterdam": ["ROTTDM"],
    }
    forms.extend(aliases.get(low, []))
    return list(dict.fromkeys(x for x in forms if x))


def _remove_city_token(value: str, city: str, *, prefer_tail: bool = True) -> str:
    """Remove one explicit city token without eating similarly named streets."""
    s = normalize_space(value)
    if not s or not city:
        return s
    matches: list[tuple[int, int]] = []
    for form in _city_forms(city):
        for m in re.finditer(rf"(?<![\wÀ-ÿ]){re.escape(form)}(?![\wÀ-ÿ])", s, re.I):
            matches.append((m.start(), m.end()))
    if not matches:
        return s
    mstart, mend = (max(matches, key=lambda x: (x[1], -x[0])) if prefer_tail else min(matches, key=lambda x: (x[0], -x[1])))
    return normalize_space((s[:mstart] + " " + s[mend:]).strip(" ,-–—"))


# Incident labels that may precede the public-space/object section. Longest and
# most specific phrases are intentionally first.
_DISPATCH_PREFIX_RE = re.compile(
    r"^(?:(?:TESTMELDING|OEFENING)\s+)?(?:"
    r"ONGEVAL\s+WEGVERVOER\s+(?:LETSEL|MATERIEEL)|"
    r"ONGEVAL\s+WEGVERVOER|ONGEVAL\s+GEV\.?\s*STOF|ONGEVAL\s+OP\s+WATER|ONGEVAL|"
    r"BR(?:AND)?\s+(?:GEZONDHEIDSZORG|WEGVERVOER|NATUUR|BOS|HEIDE|RIET|BOSSAGE|INDUSTRIE|"
    r"SCHEEPVAART|VAARTUIG|BOOT|SPOORVERVOER|TREIN|LUCHTVAART|AFVAL|VUILNIS|CONTAINER|BERM/BOSSCHAGE|BERM/BOSSAGE|BERM|"
    r"WONING|GEBOUW|BIJGEBOUW|SCHUUR|LOODS|AGRARISCH|BUITEN|VOERTUIG|WINKEL)|"
    r"ASS\.?\s*(?:AMBU|POL(?:ITIE)?)|OMS(?:\s+(?:BRANDMELDING|BEHEERSSYSTEEM|HANDMELDER|GEV\.?\s*STOF))?|"
    r"PAC(?:\s+BRANDMELDING)?|NACONTROLE|BRANDGERUCHT|ROOKONTWIKKELING|ROOKMELDER|CO-MELDER|"
    r"LUID/OPTISCH\s+ALARM|GAS(?:LUCHT|LEKKAGE|LEK)|STANK/HIND\.?\s+LUCHT|STANKOVERLAST|"
    r"PERSOON\s+(?:TE\s+WATER|IN\s+DRIJFZAND)|VOERTUIG\s+TE\s+WATER|DIER\s+(?:TE\s+WATER|IN\s+PROBLEMEN|"
    r"OP\s+HOOGTE|IN\s+PUT/KELDER)|WATERONGEVAL|LIFTOPSLUITING|STORMSCHADE|WATEROVERLAST|"
    r"BUITENSLUITING|AFHIJSEN|TILASSISTENTIE|TILHULP|REANIMATIE|DIENSTVERLENING|BIJSTAND|"
    r"HERBEZET\.?/KAZERNEREN|HERBEZETTING|HERBEVOORRADING|CONTACT\s+MKB|TELEFONISCH\s+CONTACT\s+MKB|"
    r"SCHIET(?:PARTIJ|INCIDENT)|STEEK(?:PARTIJ|INCIDENT)|ACHTERVOLGING|OVERVAL|BEROVING|"
    r"INBRAAK(?:\s+BEDRIJF)?|DEMONSTRATIE|LETSEL|AANRIJDING(?:\s+LETSEL)?|VERMISSING|"
    r"VERDACHTE\s+SITUATIE|LOSLOPENDE\s+DIEREN|SCHIP/WATERSP\.?\s+IN\s+PROBLEMEN|"
    r"WEGVERKEER\s+VERKEERSSTREMMING"
    r")\b\s*", re.I,
)


def _strip_dispatch_prefix(value: str) -> str:
    s = normalize_space(value)
    # Operational parentheticals may be stacked directly after the incident label.
    for _ in range(4):
        before = s
        s = _DISPATCH_PREFIX_RE.sub("", s, count=1)
        s = re.sub(r"^\s*\([^)]*\)\s*", "", s, count=1)
        s = normalize_space(s)
        if s == before:
            break
    return normalize_space(s.strip(" ,-–—"))


def _strip_inline_fire_units(value: str) -> str:
    """Remove callsign bookkeeping that may appear before an object/street.

    Six-digit regional callsigns and 2-4 / 2-2-3 display variants are never
    house numbers in a P2000 location. Some regions put these in the middle of
    control/herbevoorrading rows rather than only at the tail.
    """
    s = normalize_space(value)
    if not s:
        return ""
    s = re.sub(r"(?<!\d)(?:\d{6}|\d{2}[- ]\d{4}|\d{2}[- ]\d{2}[- ]\d{3})(?!\d)", " ", s)
    return normalize_space(s)


def _collapse_location_repeats(value: str) -> str:
    """Collapse obvious source-side duplicate object/street fragments.

    P2000/pers feeds sometimes repeat an intersection token or object name,
    e.g. ``Kapittelweg Nieuwe Kadijk Kapittelweg`` or
    ``Juwelier - ATA Gold Juwelier - ATA Gold Ginnekenstraat``. Preserve real
    multi-street locations while removing only exact adjacent or edge repeats.
    """
    s = normalize_space(value)
    if not s:
        return ""
    words = s.split()
    # Adjacent repeated chunks, longest first.
    changed = True
    while changed and len(words) >= 2:
        changed = False
        max_n = min(7, len(words) // 2)
        for n in range(max_n, 0, -1):
            for i in range(0, len(words) - 2 * n + 1):
                a = normalize_location_token(" ".join(words[i:i+n]), None)
                b = normalize_location_token(" ".join(words[i+n:i+2*n]), None)
                if a and a == b:
                    del words[i+n:i+2*n]
                    changed = True
                    break
            if changed:
                break
    # Same exact fragment at both edges: retain the first occurrence.
    max_n = min(7, len(words) // 2)
    for n in range(max_n, 0, -1):
        left = normalize_location_token(" ".join(words[:n]), None)
        right = normalize_location_token(" ".join(words[-n:]), None)
        if left and left == right:
            words = words[:-n]
            break
    return normalize_space(" ".join(words).strip(" ,-–—/"))


def _clean_dispatch_location(value: str, *, fire_context: bool = False) -> str:
    s = normalize_space(value)
    if fire_context:
        s = _strip_inline_fire_units(s)
    s = _collapse_location_repeats(s)
    # A slash can remain when a source taxonomy contains ``berm/bosschage``.
    s = re.sub(r"^[/\\]+", "", s)
    return normalize_space(s.strip(" ,-–—/"))


def _infer_structured_dispatch_location(title: str, city: str) -> str:
    """Parse compact P2000 formats used throughout the Netherlands.

    This intentionally works from syntax rather than hard-coded place lists. The
    RSS category/article URL supplies the locality; the parser removes dispatch
    bookkeeping, incident labels and callsigns to leave an object/street section.
    """
    raw = normalize_space(title)
    if not raw:
        return ""

    # A/B ambulance/MMT format (kept for Lifeliner parsing even when normal
    # ambulance reception is disabled).
    if AMBULANCE_RAW_RE.search(raw) and re.search(r"\b(?:AMBU|AMBULANCE)\b|(?<!\d)(?:13991|13901|17992|17902|17901|08993|08903)(?!\d)", raw, re.I):
        s = re.sub(r"^\s*(?:A[012]|B[12])\b\s*", "", raw, flags=re.I)
        s = re.sub(r"^\s*\(\s*DIA(?:\s*:\s*(?:JA|NEE))?\s*\)\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*DIA(?:\s*:\s*(?:JA|NEE))?\b\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*(?:AMBU|AMBULANCE)\b\s*", "", s, flags=re.I)
        s = re.sub(r"^(?:\s*\d{5}\s+)+", "", s)
        s = _strip_trailing_dispatch_noise(s)
        s = re.sub(r"\bREGIO\s+\d+\b", " ", s, flags=re.I)
        s = POSTCODE_RE.sub(" ", s)
        s = normalize_space(s)
        comma_parts = [normalize_space(x) for x in s.split(",") if normalize_space(x)]
        if len(comma_parts) >= 2:
            city_key = _place_key(city)
            for part in comma_parts:
                part_key = _place_key(part)
                if not part_key or (city_key and part_key == city_key):
                    continue
                if re.fullmatch(r"regio\s+\d+", part, re.I):
                    continue
                return normalize_space(part.strip(" ,-–—"))
        s = _remove_city_token(s, city, prefer_tail=True)
        return _clean_dispatch_location(s)

    # Bundle format used by several police regions: P 1 375865 Letsel ...
    if POLICE_BUNDLE_RE.search(raw):
        s = re.sub(r"^\s*P\s*[1-5]\s+\d{4,7}\b\s*", "", raw, flags=re.I)
        s = _strip_trailing_dispatch_noise(s)
        s = _strip_dispatch_prefix(s)
        s = _remove_city_token(s, city, prefer_tail=True)
        return _clean_dispatch_location(s)

    # Rotterdam port/police ICnum format: "1 Ongeval ... Botlek Rotterdam ICnum 465101".
    if POLICE_ICNUM_RE.search(raw):
        s = re.sub(r"^\s*[1-5]\s+", "", raw)
        s = _strip_trailing_dispatch_noise(s)
        s = _strip_dispatch_prefix(s)
        s = _remove_city_token(s, city, prefer_tail=True)
        return _clean_dispatch_location(s)

    # Northern pers/police slash format: incident taxonomy, priority, city, location.
    if POLICE_SLASH_RE.search(raw):
        s = re.sub(r"^\s*[^\s]+(?:/[^\s]+){1,3}\s+prio\s*[1-5]\s*", "", raw, flags=re.I)
        s = _strip_trailing_dispatch_noise(s)
        s = _remove_city_token(s, city, prefer_tail=False)
        return _clean_dispatch_location(s)

    # Native fire dispatch. This covers Bxx, SNH and KAZ dispatch codes plus
    # fire-specific lines whose regional code is omitted.
    if is_fire_dispatch_context(raw, ""):
        s = re.sub(r"^\s*(?:P\s*[1-5]|PRIO\s*[1-5])\b\s*", "", raw, flags=re.I)
        s = FIRE_DISPATCH_CODE_RE.sub(" ", s, count=1)
        s = re.sub(r"^\s*\(\s*INTREKKEN\s+ALARM\s+BRW\s*\)\s*", "", s, flags=re.I)
        s = _strip_trailing_dispatch_noise(s)
        s = _remove_city_token(s, city, prefer_tail=True)
        s = _strip_dispatch_prefix(s)
        return _clean_dispatch_location(s, fire_context=True)

    # Strong police lines without bundle id, e.g. "P 1 Steekpartij ..." or
    # "aanrijding letsel Franciscusdreef Utrecht".
    if POLICE_PLAIN_RE.search(raw) or re.match(
        r"^\s*(?:AANRIJDING\s+LETSEL|ONGEVAL(?:\s+WEGVERVOER)?\s+LETSEL|SCHIETPARTIJ|STEEKPARTIJ|ACHTERVOLGING)\b",
        raw, re.I,
    ):
        s = re.sub(r"^\s*(?:P\s*[1-5]|PRIO\s*[1-5])\b\s*", "", raw, flags=re.I)
        s = _strip_trailing_dispatch_noise(s)
        s = _strip_dispatch_prefix(s)
        s = _remove_city_token(s, city, prefer_tail=True)
        return _clean_dispatch_location(s)

    # Haaglanden/RWS-style row where the incident taxonomy is at the end:
    # "Prio 1 A4 Li - Kp Prins Clausplein 46,0 h SGRAVH Ongeval wegvervoer letsel".
    if re.match(r"^\s*Prio\s*[1-5]\b", raw, re.I):
        s = re.sub(r"^\s*Prio\s*[1-5]\b\s*", "", raw, flags=re.I)
        s = re.sub(r"\s+(?:Ongeval\s+wegvervoer\s+(?:letsel|materieel)|Wegverkeer\s+verkeersstremming)(?:\s*\([^)]*\))?\s*$", "", s, flags=re.I)
        s = _remove_city_token(s, city, prefer_tail=True)
        s = re.sub(r"\s+[hH]\s*$", "", s)
        return _clean_dispatch_location(s)

    # Last syntactic fallback for feed rows whose service is known from RSS
    # categories but which omit a regional dispatch code/callsign. This is used
    # for lines such as "P 2 Herbezet./kazerneren ... Zwolle" and
    # "P 1 Ass. Ambu Kepplerstraat Zaandam".
    if city and (re.match(r"^\s*(?:P\s*[1-5])\b", raw, re.I) or _DISPATCH_PREFIX_RE.search(re.sub(r"^\s*P\s*[1-5]\b\s*", "", raw, flags=re.I))):
        s = re.sub(r"^\s*P\s*[1-5]\b\s*", "", raw, flags=re.I)
        s = FIRE_DISPATCH_CODE_RE.sub(" ", s, count=1)
        s = _strip_trailing_dispatch_noise(s)
        s = _remove_city_token(s, city, prefer_tail=True)
        s = _strip_dispatch_prefix(s)
        if s:
            return _clean_dispatch_location(s, fire_context=True)

    return ""

def normalize_location_display_case(value: str) -> str:
    """Make all-lowercase source locations readable without rewriting real names."""
    s = normalize_space(value)
    letters = [c for c in s if c.isalpha()]
    if not s or not letters or any(c.isupper() for c in letters):
        return s
    titled = s.title()
    # Dutch connectors are normally lowercase inside a street/object name.
    words = titled.split()
    lower_inside = {"De", "Den", "Der", "Van", "Het", "En", "Op", "Aan", "In", "Te", "Ten", "Ter", "Bij"}
    for i, word in enumerate(words):
        if i > 0 and word in lower_inside:
            words[i] = word.lower()
    out = " ".join(words)
    out = re.sub(r"^'T\b", "'t", out)
    out = re.sub(r"^'S\b", "'s", out)
    return out


def infer_location(title: str, summary: str, city: str) -> str:
    # Preserve feed privacy behavior: no attempt is made to reconstruct omitted house numbers.
    structured = _infer_structured_dispatch_location(title, city)
    if structured:
        return normalize_location_display_case(structured)
    t = re.sub(r"^[^\w]+", "", title)
    if "—" in t:
        tail = normalize_space(t.rsplit("—", 1)[-1])
        if tail:
            return normalize_location_display_case(tail)
    # "... naar Jachthoorn in Capelle ..."
    m = re.search(r"\bnaar\s+(.+?)\s+in\s+.+$", t, re.I)
    if m:
        return normalize_location_display_case(m.group(1))
    # Fallback: postcode-bearing portion in summary.
    p = POSTCODE_RE.search(summary)
    if p:
        left = summary[:p.start()].strip(" ,-–—")
        words = left.split()
        return normalize_location_display_case(" ".join(words[-5:]))
    return normalize_location_display_case(city)


def infer_units(summary: str, title: str = "") -> list[str]:
    units: list[str] = []
    # Most enriched feed summaries put units after "Ingezet:".
    m = re.search(r"Ingezet:\s*(.+?)(?:\.|$)", summary, re.I)
    if m:
        raw = re.split(r",|\ben\b", m.group(1), flags=re.I)
        for item in raw:
            item = normalize_space(item)
            if item and item.lower() not in {"onbekend", "geen"}:
                units.append(item)
    hay = f"{title} {summary}"
    if not units:
        units = [normalize_space(x) for x in UNIT_RE.findall(hay)]
        # Bare six-/seven-digit values are only vehicle-like inside a confirmed
        # fire dispatch. Police incident/bundle IDs are intentionally excluded.
        if is_fire_dispatch_context(title, summary):
            units.extend(formatted for _, formatted in extract_fire_callsigns(title))
            for m_ext in FIRE_EXTENDED_CALLSIGN_RE.finditer(title or ""):
                units.append(f"{m_ext.group(1)}-{m_ext.group(2)}-{m_ext.group(3)}")
    # Normalize known Dutch MMT helicopter/car resource numbers to readable units.
    for hit in MMT_RESOURCE_RE.finditer(hay):
        digits = re.sub(r"\D", "", hit.group(0))
        meta = MMT_RESOURCES.get(digits)
        if not meta:
            continue
        units = [u for u in units if digits not in re.sub(r"\D", "", u)]
        units.append(f"{digits} - {meta['label']}")
    # Stable de-duplication.
    return list(dict.fromkeys(units))[:30]



def incident_type_label(title: str, summary: str = "") -> str:
    """Normalize the most common Dutch P2000 incident taxonomies nationwide."""
    hay = normalize_space(f"{title} {summary}")
    if re.search(r"\bTESTMELDING\b", hay, re.I):
        return "Testmelding"
    if re.search(r"\bOEFENING\b", hay, re.I):
        return "Oefening"
    if re.search(r"\bINTREKKEN\s+ALARM\s+BRW\b", hay, re.I):
        return "Alarm ingetrokken"
    storm = re.search(r"\bSTORMSCHADE\b", hay, re.I)
    if storm:
        subtype = re.search(r"\(\s*SOORT\s+GEVAAR\s*:\s*([^)]{2,60})\)", hay, re.I)
        return f"Stormschade door {normalize_space(subtype.group(1)).lower()}" if subtype else "Stormschade"
    if re.search(r"\bBR\s+WONING\b[^\n]{0,50}\(\s*DAK\s*\)", hay, re.I):
        return "Dakbrand"
    if re.search(r"\bASS\.?\s*AMBU\b[^\n]{0,70}\(\s*REDDINGSKUSSEN\s*\)", hay, re.I):
        return "Assistentie ambulance met reddingskussen"
    rules = [
        (r"\bSCHIET(?:PARTIJ|INCIDENT)\b", "Schietincident"),
        (r"\bSTEEK(?:PARTIJ|INCIDENT)\b", "Steekincident"),
        (r"\bACHTERVOLGING\b", "Achtervolging"),
        (r"\bOVERVAL\b", "Overval"),
        (r"\bBEROVING\b", "Beroving"),
        (r"\bINBRAAK\s+BEDRIJF\b", "Inbraak bedrijf"),
        (r"\bINBRAAK\b", "Inbraak"),
        (r"\bDEMONSTRATIE\b", "Demonstratie"),
        (r"\bVERMISSING\b", "Vermissing"),
        (r"\bREANIMATIE\b", "Reanimatie"),
        (r"\bONGEVAL\s+WEGVERVOER\s+MATERIEEL\b|\bONGEVAL/WEGVERVOER/MATERIEEL\b", "Ongeval met materiële schade"),
        (r"\bAANRIJDING\s+LETSEL\b|\bONGEVAL\s+WEGVERVOER\s+LETSEL\b|\bONGEVAL/WEGVERVOER/LETSEL\b|\bLETSEL\b", "Ongeval met letsel"),
        (r"\bWEGVERKEER\s+VERKEERSSTREMMING\b|\bVERKEER/WEGVERKEER/VERKEERSSTREMMING\b", "Verkeersstremming"),
        (r"\bONGEVAL\s+GEV\.?\s*STOF\b|\bOMS\s+GEV\.?\s*STOF\b", "Incident gevaarlijke stoffen"),
        (r"\bSTANK\s*/?\s*HIND\.?\s+LUCHT\b|\bSTANKOVERLAST\b|\bGAS(?:LUCHT|LEKKAGE|LEK)\b", "Stank- of gaslucht"),
        (r"\bCO-MELDER\b|\bKOOLMONOXIDE\b", "CO-melding"),
        (r"\bROOKMELDER\b", "Rookmelder"),
        (r"\bLUID/OPTISCH\s+ALARM\b", "Luid/optisch alarm"),
        (r"\bOMS\s+HANDMELDER\b", "OMS handmelder"),
        (r"\bOMS\s+BEHEERSSYSTEEM\b", "OMS beheerssysteem"),
        (r"\bOMS(?:\s+BRANDMELDING)?\b|\bPAC\s+BRANDMELDING\b", "Automatische brandmelding"),
        (r"\bBRANDGERUCHT\b", "Brandgerucht"),
        (r"\bNACONTROLE\b", "Nacontrole"),
        (r"\bWATEROVERLAST\b", "Wateroverlast"),
        (r"\bLIFTOPSLUITING\b", "Liftopsluiting"),
        (r"\bHERBEZET\.?/KAZERNEREN\b|\bHERBEZETTING\b", "Herbezetting"),
        (r"\bHERBEVOORRADING\b", "Herbevoorrading"),
        (r"\bBIJSTAND\b", "Bijstand"),
        (r"\bDIENSTVERLENING\b", "Dienstverlening"),
        (r"\bDIER\s+IN\s+PUT/KELDER\b", "Dier in put of kelder"),
        (r"\bDIER\s+OP\s+HOOGTE\b", "Dier op hoogte"),
        (r"\bDIER\s+TE\s+WATER\b", "Dier te water"),
        (r"\bDIER\s+IN\s+PROBLEMEN\b|\bLOSLOPENDE\s+DIEREN\b", "Dier in problemen"),
        (r"\bPERSOON\s+IN\s+DRIJFZAND\b", "Persoon in drijfzand"),
        (r"\bPERSOON\s+TE\s+WATER\b|\bWATERONGEVAL\b|\bONGEVAL\s+OP\s+WATER\b", "Waterongeval"),
        (r"\bVOERTUIG\s+TE\s+WATER\b", "Voertuig te water"),
        (r"\bSCHIP/WATERSP\.?\s+IN\s+PROBLEMEN\b", "Vaartuig of watersporter in problemen"),
        (r"\bBR\s+INDUSTRIE\b|\bINDUSTRIEBRAND\b", "Industriebrand"),
        (r"\bBR\s+GEZONDHEIDSZORG\b", "Brand gezondheidszorg"),
        (r"\bBR\s+WINKEL\b", "Winkelbrand"),
        (r"\bBR\s+WONING\b|\bWONINGBRAND\b", "Woningbrand"),
        (r"\bBR\s+(?:GEBOUW|BIJGEBOUW|SCHUUR|LOODS)\b|\bGEBOUWBRAND\b", "Gebouwbrand"),
        (r"\bBR\s+(?:NATUUR|BOS|HEIDE|RIET|BOSSAGE|BERM/BOSSCHAGE|BERM)\b|\bNATUURBRAND\b", "Natuurbrand"),
        (r"\bONGEVAL\s+WEGVERVOER[^\n]{0,60}\(\s*MET\s+BRAND\s*\)", "Ongeval wegvervoer met brand"),
        (r"\bBR\s+(?:WEGVERVOER|VOERTUIG)\b|\bVOERTUIGBRAND\b", "Voertuigbrand"),
        (r"\bBR\s+(?:AFVAL|VUILNIS|CONTAINER)\b", "Afval- of containerbrand"),
        (r"\bBR\s+BUITEN\b|\bBRAND\s+BUITEN\b|\bBUITENBRAND\b", "Buitenbrand"),
        (r"\bASS\.?\s*POL(?:ITIE)?\b", "Assistentie politie"),
        (r"\bASS\.?\s*AMBU\b", "Assistentie ambulance"),
        (r"\bONGEVAL\s+WEGVERVOER\b", "Ongeval wegvervoer"),
        (r"\bONGEVAL\b", "Ongeval"),
        (r"\bBRAND\b|\bBR\b", "Brand"),
        (r"\bCONTACT\s+MKB\b|\bTELEFONISCH\s+CONTACT\b|\bGRAAG\s+(?:TEL(?:EFONISCH)?\.?\s+)?CONTACT\b", "Contact meldkamer"),
    ]
    for pattern, label in rules:
        if re.search(pattern, hay, re.I):
            return label
    if detect_mmt_resource(title, summary, infer_units(summary, title)):
        return "MMT-inzet"
    return "P2000-melding"

def parser_confidence_details(title: str, summary: str, categories: list[str], service: str,
                              priority: str, city: str, location: str, units: list[str],
                              scale: str = "") -> tuple[int, list[str]]:
    """Explainable, intentionally conservative parse confidence (0..100)."""
    score = 0
    notes: list[str] = []
    if service and service != "overig":
        score += 20; notes.append(f"dienst herkend: {service}")
    else:
        score += 4; notes.append("dienst onzeker")
    if priority:
        score += 10; notes.append(f"prioriteit herkend: {priority}")
    else:
        notes.append("geen prioriteit gevonden")
    if city:
        score += 20; notes.append(f"plaats herkend: {city}")
    else:
        notes.append("plaats ontbreekt")
    clean_loc = normalize_space(location)
    if clean_loc and normalize_city_token(clean_loc) != normalize_city_token(city):
        score += 25; notes.append(f"locatie herkend: {clean_loc}")
    elif clean_loc:
        score += 8; notes.append("alleen plaats als locatie")
    else:
        notes.append("locatie ontbreekt")
    if units:
        score += 15; notes.append(f"{len(units)} eenheid/eenheden herkend")
    elif service in {"politie", "overig"}:
        score += 6; notes.append("geen voertuig verwacht/gevonden")
    else:
        notes.append("geen eenheid herkend")
    incident_type = incident_type_label(title, summary)
    if incident_type != "P2000-melding":
        score += 8; notes.append(f"incidenttype: {incident_type}")
    if scale:
        score += 2; notes.append(f"opschaling: {scale}")
    # Strong native formats get a small reliability bonus.
    raw = normalize_space(f"{title} {summary}")
    if is_fire_dispatch_context(title, summary, units) or POLICE_BUNDLE_RE.search(raw) or AMBULANCE_RAW_RE.search(raw):
        score += 4; notes.append("bekend P2000-formaat")
    return max(0, min(100, score)), notes


def parse_raw_p2000_line(state: "AppState", raw: str, categories: list[str] | None = None) -> dict:
    """Parse one pasted raw P2000 line through the same primitives as the feed parser."""
    title = normalize_space(strip_html(raw or ""))[:1200]
    cats = [normalize_space(x) for x in (categories or []) if normalize_space(x)]
    service = detect_service(title, "", cats)
    priority = detect_priority(title, "")
    city = infer_city(cats, title)
    location = infer_location(title, "", city)
    units = infer_units("", title)
    if detect_mmt_resource(title, "", units):
        service = "lifeliner"
    scale, scale_score = detect_scale(title, "")
    alias_map = build_location_alias_map(state.get_display_settings())
    ikey = incident_key(service, city, location, title, alias_map)
    confidence, notes = parser_confidence_details(title, "", cats, service, priority, city, location, units, scale)
    return {
        "raw": title,
        "service": service,
        "priority": priority,
        "incident_type": incident_type_label(title, ""),
        "region": next((normalize_space(c[6:]) for c in cats if c.lower().startswith("regio ")), "") or region_for_city(city),
        "city": city,
        "location": location,
        "normalized_location": normalize_location_token(location, alias_map),
        "units": units,
        "scale": scale,
        "scale_score": scale_score,
        "incident_key": ikey,
        "confidence": confidence,
        "confidence_level": "hoog" if confidence >= 80 else "middel" if confidence >= 55 else "laag",
        "notes": notes,
        "map_query": ", ".join(x for x in [location, city, "Nederland"] if x),
    }

def incident_key(service: str, city: str, location: str, title: str, alias_map: dict[str, str] | None = None) -> str:
    norm_city = normalize_city_token(city)
    norm_location = normalize_location_token(location, alias_map)
    base = f"{norm_city}|{norm_location}".lower()
    base = POSTCODE_RE.sub("", base)
    base = re.sub(r"\b(p\s?[123]|a[012]|b[12]|spoed|met|zonder|naar|ter plaatse|brandweer|ambulance|politie|lifeliner)\b", " ", base, flags=re.I)
    base = re.sub(r"[^a-z0-9à-ÿ]+", " ", base)
    base = normalize_space(base)
    if len(base) < 4:
        fallback = normalize_location_token(title, alias_map)
        base = fallback[:80]
    # Cross-service clustering is useful for larger incidents, so service is intentionally omitted.
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def build_osm_embed_url(lat: float, lon: float, bbox: list[float] | tuple[float, ...] | None = None, zoom: int = 16) -> str:
    """Return the local kiosk map renderer instead of framing openstreetmap.org.

    The previous remote OSM iframe could stay blank on Windows/Edge because it
    depended on an external framed document. The local renderer loads only the
    actual map tiles, keeps attribution visible and can show a useful fallback
    even while tiles are temporarily unavailable.
    """
    z = max(12, min(18, int(zoom or 16)))
    return f"/map-view.html?lat={float(lat):.7f}&lon={float(lon):.7f}&zoom={z}"


@dataclass
class Message:
    id: str
    published: str
    updated: str
    title: str
    summary: str
    url: str
    service: str
    priority: str
    city: str
    location: str
    units: list[str]
    categories: list[str]
    scale: str
    scale_score: int
    incident_key: str
    source: str = SOURCE_NAME
    parser_confidence: int = 0
    parser_notes: list[str] | None = None


class AppState:
    def __init__(self, config: dict):
        self.config = config
        self.db_lock = threading.RLock()
        self.config_lock = threading.RLock()
        self.subscribers: list[queue.Queue] = []
        self.sub_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_poll: str | None = None
        self.last_success: str | None = None
        self.last_error: str | None = None
        self.feed_cache: dict[str, dict[str, str]] = {}
        self.feed_diag: dict[str, dict] = {}
        self.feed_status = "starting"
        self.started_at = utcnow_iso()
        # Changes on every backend process start. Browser displays use this to
        # detect a completed self-update/restart and reload their static assets.
        self.server_instance = hashlib.sha256(f"{time.time_ns()}:{os.getpid()}".encode()).hexdigest()[:16]
        self.watchdog_recoveries = 0
        self.last_watchdog_action: str | None = None
        self.consecutive_failures = 0
        self.manual_refresh_event = threading.Event()
        self.display_power_status = "unknown"
        self.display_power_error: str | None = None
        self.display_power_changed_at: str | None = None
        self.display_power_method: str | None = None
        self.display_connector: str | None = None
        self.display_name: str | None = None
        self.display_info_cache: dict | None = None
        self.display_info_monotonic: float = 0.0
        self.display_manual_wake_until_monotonic: float = 0.0
        self.vehicle_catalog, self.vehicle_region_meta = load_vehicle_catalog(self.config)
        self.known_vehicle_keys: set[str] = set(self.vehicle_catalog)
        self.vehicle_catalog_lock = threading.RLock()
        self.vehicle_overrides_lock = threading.RLock()
        self.vehicle_sync_lock = threading.Lock()
        self.vehicle_sync_force_pending = False
        self.vehicle_sync_status: dict = {
            "running": False, "last_started": None, "last_finished": None, "last_error": None,
            "regions": {}, "count": len(self.vehicle_catalog),
        }
        self.started_monotonic = time.monotonic()
        self.api_requests = 0
        self.api_errors = 0
        self.sse_peak = 0
        self.feed_latency_history: dict[str, list[float]] = {}
        self.feed_fetch_history: dict[str, list[float]] = {}
        self.fallback_activations = 0
        self.last_fallback_action: str | None = None
        self.client_health: dict = {}
        self.client_health_lock = threading.Lock()
        self.test_results: dict[str, dict] = {}
        self.test_results_lock = threading.Lock()
        # One background BGT street-index warmup per town at a time.  This lets
        # normal incidents resolve immediately via PDOK while the monitor quietly
        # learns the official local street/public-space names for later offline use.
        self.street_index_warming: set[str] = set()
        self.street_index_warm_lock = threading.Lock()

    @contextmanager
    def connect(self):
        """Open one short-lived SQLite connection and always close it."""
        con = sqlite3.connect(DB_PATH, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("PRAGMA synchronous=NORMAL")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def init_db(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            # WAL persists; do not execute this locking pragma on every API query.
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    published TEXT NOT NULL,
                    updated TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    url TEXT NOT NULL,
                    service TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    city TEXT NOT NULL,
                    location TEXT NOT NULL,
                    units_json TEXT NOT NULL,
                    categories_json TEXT NOT NULL,
                    scale TEXT NOT NULL,
                    scale_score INTEGER NOT NULL DEFAULT 0,
                    incident_key TEXT NOT NULL,
                    source TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    parser_confidence INTEGER NOT NULL DEFAULT 0,
                    parser_notes_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_messages_published ON messages(published DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_service ON messages(service, published DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_city ON messages(city, published DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_incident ON messages(incident_key, published DESC);
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS unknown_vehicles (
                    callsign TEXT PRIMARY KEY,
                    digits TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    last_message_id TEXT NOT NULL,
                    last_message TEXT NOT NULL,
                    last_city TEXT NOT NULL DEFAULT '',
                    last_url TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_unknown_vehicles_last_seen ON unknown_vehicles(last_seen DESC);
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    lookup_key TEXT PRIMARY KEY,
                    city TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    bbox_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT 'nominatim',
                    cached_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_geocode_cached_at ON geocode_cache(cached_at DESC);
                CREATE TABLE IF NOT EXISTS street_index (
                    city_key TEXT NOT NULL,
                    street_key TEXT NOT NULL,
                    city TEXT NOT NULL DEFAULT '',
                    street TEXT NOT NULL DEFAULT '',
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    source TEXT NOT NULL DEFAULT 'bgt',
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY(city_key, street_key)
                );
                CREATE INDEX IF NOT EXISTS idx_street_index_street ON street_index(street_key);
                CREATE TABLE IF NOT EXISTS street_area_cache (
                    city_key TEXT PRIMARY KEY,
                    city TEXT NOT NULL DEFAULT '',
                    bbox_json TEXT NOT NULL DEFAULT '[]',
                    fetched_at TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    complete INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            # In-place migration for installations upgraded from <= 2.10.x.
            message_cols = {row[1] for row in con.execute("PRAGMA table_info(messages)").fetchall()}
            if "parser_confidence" not in message_cols:
                con.execute("ALTER TABLE messages ADD COLUMN parser_confidence INTEGER NOT NULL DEFAULT 0")
            if "parser_notes_json" not in message_cols:
                con.execute("ALTER TABLE messages ADD COLUMN parser_notes_json TEXT NOT NULL DEFAULT '[]'")


    @staticmethod
    def _clean_feed_urls(values, *, maximum: int = 128, exclude: set[str] | None = None) -> list[str]:
        if not isinstance(values, list):
            return []
        out=[]; excluded=exclude or set()
        for value in values[:maximum]:
            url=normalize_space(str(value or ""))
            try: parsed=urlparse(url)
            except Exception: continue
            if parsed.scheme not in {"http","https"} or not parsed.netloc or len(url)>1000 or url in excluded:
                continue
            if url not in out: out.append(url)
        return out

    def feed_config_view(self) -> dict:
        return {
            "primary_feed_urls": list(self.config.get("feed_urls") or []),
            "fallback_feed_urls": list(self.config.get("fallback_feed_urls") or []),
            "poll_interval_seconds": int(self.config.get("poll_interval_seconds",20)),
            "watchdog_stale_seconds": int(self.config.get("watchdog_stale_seconds",600)),
        }

    def save_feed_config(self, payload: dict) -> dict:
        # Advanced diagnostics may still configure a small fallback list, but
        # primary feeds are always owned by the setup wizard.
        primary=set(self.config.get("feed_urls") or [])
        fallback=self._clean_feed_urls(payload.get("fallback_feed_urls"), maximum=6, exclude=primary)
        watchdog=bounded_int(payload.get("watchdog_stale_seconds", self.config.get("watchdog_stale_seconds",600)),600,180,86400)
        with self.config_lock:
            self.config["fallback_feed_urls"]=fallback
            self.config["watchdog_stale_seconds"]=watchdog
            disk={}
            try:
                loaded=json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
                if isinstance(loaded,dict): disk.update(loaded)
            except Exception:
                disk.update({k:v for k,v in self.config.items() if k not in {"port","bind"}})
            disk["fallback_feed_urls"]=fallback
            disk["watchdog_stale_seconds"]=watchdog
            CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
            tmp=CONFIG_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(disk,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            tmp.replace(CONFIG_PATH)
        self.broadcast({"type":"status","status":self.feed_status,"error":self.last_error})
        return self.feed_config_view()

    def github_update_view(self) -> dict:
        return github_update_config(self.config)

    def save_github_update_config(self, payload: dict) -> dict:
        cfg = sanitize_github_update_payload(payload, current=self.config)
        with self.config_lock:
            self.config.update(cfg)
            self._persist_config()
        _write_update_status(
            github_repo=cfg.get("github_repo", ""),
            auto_check=cfg.get("github_auto_check", False),
            auto_install=cfg.get("github_auto_install", False),
            check_minutes=cfg.get("github_check_minutes", 5),
            message="GitHub-updateinstellingen opgeslagen",
        )
        if cfg.get("github_repo") and cfg.get("github_auto_check"):
            def immediate_check():
                time.sleep(.6)
                try:
                    github_check_and_maybe_install(self, install=bool(cfg.get("github_auto_install")))
                except Exception as exc:
                    _write_update_status(state="error", source="github", github_repo=cfg.get("github_repo", ""), error=str(exc), message="GitHub updatecontrole mislukt")
            threading.Thread(target=immediate_check, daemon=True, name="github-update-config-check").start()
        return self.github_update_view()

    def github_settings_sync_view(self) -> dict:
        return github_settings_sync_config(self.config)

    def save_github_settings_sync_config(self, payload: dict) -> dict:
        cfg = sanitize_github_settings_sync_payload(payload, current=self.config)
        with self.config_lock:
            self.config.update(cfg)
            self._persist_config()
        if cfg.get("github_settings_auto_sync"):
            threading.Thread(
                target=_delayed_github_settings_pull,
                args=(self,), daemon=True, name="github-settings-config-pull",
            ).start()
        return self.github_settings_sync_view()

    def setup_view(self) -> dict:
        return {
            "setup_complete": self.config.get("setup_complete") is True,
            "profile_type": self.config.get("profile_type", "particulier"),
            "person_name": self.config.get("person_name", ""),
            "company_name": self.config.get("company_name", ""),
            "department_name": self.config.get("department_name", ""),
            "contact_name": self.config.get("contact_name", ""),
            "standplaats": self.config.get("standplaats", ""),
            "standplaats_city": self.setup_city(),
            "monitor_name": self.config.get("display_name", "P2000 Monitor"),
            "region_disciplines": setup_region_disciplines(self.config),
            "regions": [{"slug": slug, **meta} for slug, meta in REGION_CATALOG.items()],
            "disciplines": [
                {"key":"brandweer","label":"Brandweer","regional_feed":True},
                {"key":"ambulance","label":"Ambulance","regional_feed":True},
                {"key":"politie","label":"Politie","regional_feed":True},
                {"key":"knrm","label":"KNRM / waterhulp","regional_feed":False},
                {"key":"lifeliner","label":"Lifeliner / traumaheli","regional_feed":False},
            ],
            "feed_urls": list(self.config.get("feed_urls") or []),
            "poll_interval_seconds": int(self.config.get("poll_interval_seconds", 20)),
        }

    @staticmethod
    def _standplaats_city_hint(value: str) -> str:
        """Best-effort woonplaats extraction for an address-like standplaats.

        The setup wizard historically called this field ``standplaats`` and users
        understandably entered either a town *or* a full street address. Parsing
        code must never treat that whole address as the incident city.
        """
        raw = normalize_space(value)
        if not raw:
            return ""
        # Explicit comma form: ``Straat 12, 5043BS, Tilburg``.
        parts = [normalize_space(x) for x in raw.split(",") if normalize_space(x)]
        if len(parts) >= 2:
            tail = POSTCODE_RE.sub(" ", parts[-1])
            tail = re.sub(r"^\d+[A-Za-z-]*\s+", "", normalize_space(tail))
            if re.search(r"[A-Za-zÀ-ÿ]", tail):
                return normalize_space(tail)[:120]
        # Compact address form: ``Straat 12 5043BS Tilburg``.
        m = re.search(r"\b\d{4}\s*[A-Z]{2}\b\s*[,;-]?\s*(.+)$", raw, re.I)
        if m:
            tail = normalize_space(m.group(1).strip(" ,-;"))
            if tail and re.search(r"[A-Za-zÀ-ÿ]", tail):
                return tail[:120]
        return raw[:120]

    def setup_city(self) -> str:
        explicit = normalize_space(str(self.config.get("standplaats_city") or ""))[:120]
        return explicit or self._standplaats_city_hint(str(self.config.get("standplaats") or ""))

    def _resolve_setup_city(self, standplaats: str) -> str:
        """Resolve the canonical BAG woonplaats once during setup.

        This is intentionally *not* part of the live message path. A one-time PDOK
        lookup keeps an address-like monitor standplaats from poisoning every test
        message while adding zero recurring cost to RSS/parsing/rendering.
        """
        fallback = self._standplaats_city_hint(standplaats)
        q = normalize_space(standplaats)
        if not q:
            return fallback
        url = f"https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?q={quote(q)}&rows=8"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                body = json.loads(resp.read(1_000_000).decode("utf-8", "replace") or "{}")
            docs = ((body or {}).get("response") or {}).get("docs") or []
            if isinstance(docs, list):
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    city = normalize_space(str(doc.get("woonplaatsnaam") or ""))
                    if city:
                        return city[:120]
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    city = normalize_space(str(doc.get("gemeentenaam") or ""))
                    if city:
                        return city[:120]
        except Exception:
            pass
        return fallback

    def _persist_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        disk = dict(self.config)
        tmp = CONFIG_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(disk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(CONFIG_PATH)

    def save_setup(self, payload: dict) -> dict:
        profile = str(payload.get("profile_type") or "particulier").lower()
        if profile not in {"particulier", "bedrijf"}:
            raise ValueError("Kies particulier of bedrijf")
        standplaats = normalize_space(str(payload.get("standplaats") or ""))[:120]
        if not standplaats:
            raise ValueError("Vul een standplaats in")
        person_name = normalize_space(str(payload.get("person_name") or ""))[:120]
        company_name = normalize_space(str(payload.get("company_name") or ""))[:160]
        department_name = normalize_space(str(payload.get("department_name") or ""))[:160]
        contact_name = normalize_space(str(payload.get("contact_name") or ""))[:120]
        if profile == "particulier" and not person_name:
            raise ValueError("Vul je naam in")
        if profile == "bedrijf" and not company_name:
            raise ValueError("Vul de bedrijfsnaam in")
        raw_matrix = payload.get("region_disciplines") or {}
        matrix: dict[str, list[str]] = {}
        if isinstance(raw_matrix, dict):
            for slug, values in raw_matrix.items():
                if slug not in REGION_CATALOG or not isinstance(values, list):
                    continue
                requested = {str(v).lower() for v in values}
                selected = [d for d in ALL_DISCIPLINES if d in requested]
                if selected:
                    matrix[slug] = selected
        if not matrix:
            raise ValueError("Selecteer minimaal één regio en discipline")
        feeds = build_feed_urls(matrix)
        if not feeds:
            raise ValueError("Er konden geen RSS-feeds worden opgebouwd")
        standplaats_city = self._resolve_setup_city(standplaats) or self._standplaats_city_hint(standplaats)
        requested_name = normalize_space(str(payload.get("monitor_name") or ""))[:120]
        monitor_name = requested_name or f"P2000 {standplaats_city or standplaats}"
        poll = bounded_int(payload.get("poll_interval_seconds", 20), 20, 15, 300)
        with self.config_lock:
            self.config.update({
                "setup_complete": True,
                "profile_type": profile,
                "person_name": person_name if profile == "particulier" else "",
                "company_name": company_name if profile == "bedrijf" else "",
                "department_name": department_name if profile == "bedrijf" else "",
                "contact_name": contact_name if profile == "bedrijf" else "",
                "standplaats": standplaats,
                "standplaats_city": standplaats_city,
                "display_name": monitor_name,
                "region_disciplines": matrix,
                "feed_urls": feeds,
                "poll_interval_seconds": poll,
            })
            self._persist_config()
        enabled: list[str] = []
        for values in matrix.values():
            for d in values:
                if d not in enabled:
                    enabled.append(d)
        existing = self.get_display_settings()
        existing.update({"name": monitor_name, "services": enabled})
        self.save_display_settings(existing)
        self.clear_feed_cache()
        self.purge_out_of_scope()
        self._refresh_vehicle_catalog()
        self.start_vehicle_sync(force=False)
        self.request_feed_refresh(clear_cache=False)
        self.broadcast({"type":"settings","settings":self.get_display_settings()})
        return self.setup_view()

    def vehicle_catalog_payload(self) -> dict:
        # self.vehicle_catalog is replaced atomically and never mutated in place.
        # Returning that immutable snapshot avoids an unnecessary full dictionary
        # copy for a nationwide catalogue.
        with self.vehicle_catalog_lock:
            vehicles = self.vehicle_catalog
            metas = self.vehicle_region_meta
        return {
            "meta": {
                "version": APP_VERSION,
                "count": len(vehicles),
                "selected_regions": selected_fire_region_codes(self.config),
                "region_meta": metas,
                "override_count": len(load_vehicle_overrides()),
                "source": "handmatige overrides + lokale regionale cache + landelijke nummerplan-fallback",
            },
            "vehicles": vehicles,
        }

    def vehicle_sync_view(self) -> dict:
        with self.vehicle_catalog_lock:
            status = dict(self.vehicle_sync_status)
            status["version"] = APP_VERSION
            status["count"] = len(self.vehicle_catalog)
            status["selected_regions"] = selected_fire_region_codes(self.config)
            status["cached_regions"] = sorted(self.vehicle_region_meta)
            status["region_meta"] = dict(self.vehicle_region_meta)
            status["force_pending"] = bool(self.vehicle_sync_force_pending)
            status["override_count"] = len(load_vehicle_overrides())
        return status

    def vehicle_overrides_view(self) -> dict:
        with self.vehicle_overrides_lock:
            rows = load_vehicle_overrides()
        return {
            "count": len(rows),
            "path": "data/vehicles/overrides.json",
            "vehicles": rows,
        }

    def upsert_vehicle_override(self, payload: dict) -> dict:
        digits, item = sanitize_vehicle_override(payload)
        with self.vehicle_overrides_lock:
            rows = load_vehicle_overrides()
            rows[digits] = item
            write_vehicle_overrides(rows)
            self._refresh_vehicle_catalog()
        self.broadcast({"type": "vehicle-db", "status": self.vehicle_sync_view()})
        return {"ok": True, "digits": digits, "vehicle": item, "overrides": self.vehicle_overrides_view()}

    def delete_vehicle_override(self, payload: dict) -> dict:
        digits = normalize_vehicle_digits(str(payload.get("digits") or payload.get("callsign") or ""))
        if len(digits) not in {6, 7}:
            raise ValueError("Ongeldig roepnummer")
        with self.vehicle_overrides_lock:
            rows = load_vehicle_overrides()
            existed = rows.pop(digits, None) is not None
            write_vehicle_overrides(rows)
            self._refresh_vehicle_catalog()
        self.broadcast({"type": "vehicle-db", "status": self.vehicle_sync_view()})
        return {"ok": True, "deleted": existed, "digits": digits, "overrides": self.vehicle_overrides_view()}

    def begin_test_command(self, token: str, mode: str, subscribers: int) -> dict:
        now = utcnow_iso()
        row = {"token": token, "mode": mode, "status": "pending", "ok": None, "detail": "Wachten op lichtkrant", "created_at": now, "updated_at": now, "subscribers": subscribers}
        with self.test_results_lock:
            self.test_results[token] = row
            if len(self.test_results) > 100:
                for old_token in list(self.test_results)[:-80]:
                    self.test_results.pop(old_token, None)
        return dict(row)

    def finish_test_command(self, payload: dict) -> dict:
        token = normalize_space(str(payload.get("token") or ""))[:120]
        if not token:
            raise ValueError("Testtoken ontbreekt")
        with self.test_results_lock:
            row = self.test_results.get(token)
            if not row:
                raise ValueError("Onbekende of verlopen test")
            row.update({
                "status": "completed" if bool(payload.get("ok")) else "error",
                "ok": bool(payload.get("ok")),
                "detail": normalize_space(str(payload.get("detail") or ("afgespeeld" if payload.get("ok") else "afspelen mislukt")))[:240],
                "updated_at": utcnow_iso(),
            })
            return dict(row)

    def test_command_view(self, token: str) -> dict | None:
        with self.test_results_lock:
            row = self.test_results.get(token)
            return dict(row) if row else None

    def _refresh_vehicle_catalog(self):
        catalog, metas = load_vehicle_catalog(self.config)
        with self.vehicle_catalog_lock:
            self.vehicle_catalog = catalog
            self.vehicle_region_meta = metas
            self.known_vehicle_keys = set(catalog)
            self.vehicle_sync_status["count"] = len(catalog)

    def _fetch_vehicle_url(self, url: str, timeout: float = 6.0) -> str:
        req = urllib.request.Request(url, headers={
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36 P2000Monitor/{APP_VERSION}",
            "Accept": "text/html,text/csv,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.5",
            "Cache-Control": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(3_000_000)
            charset = "utf-8"
            ctype = resp.headers.get_content_charset() if hasattr(resp.headers, "get_content_charset") else None
            if ctype:
                charset = ctype
        return raw.decode(charset, errors="replace")

    def _sync_vehicle_region_hulpdienst(self, region_code: str) -> dict:
        slug = HULPDIENST_REGION_SLUGS.get(region_code)
        if not slug:
            raise ValueError("geen Hulpdienstvoertuigen-regioslug")
        first_url = f"{HULPDIENST_VEHICLES_BASE}/{quote(slug)}?pagina=1"
        first = self._fetch_vehicle_url(first_url, timeout=6.0)
        vehicles, pages = parse_hulpdienst_vehicle_html(first, region_code)
        if pages > 1:
            # Region pages are small (normally 50 rows). Fetch sequentially inside
            # the per-region worker so total network concurrency stays bounded by
            # the outer four-worker pool.
            for page_no in range(2, pages + 1):
                page = self._fetch_vehicle_url(
                    f"{HULPDIENST_VEHICLES_BASE}/{quote(slug)}?pagina={page_no}", timeout=6.0
                )
                more, _ = parse_hulpdienst_vehicle_html(page, region_code)
                vehicles.update(more)
        if not vehicles:
            raise ValueError("bron bevatte geen herkenbare brandweervoertuigen")
        return {
            "vehicles": vehicles,
            "source": "Hulpdienstvoertuigen.nl",
            "endpoint": "regional-html",
            "pages": pages,
        }

    def _sync_vehicle_region_tomzulu(self, region_code: str) -> dict:
        sheet = FIRE_REGION_SHEETS.get(region_code)
        if not sheet:
            raise ValueError("onbekende regio")
        sheet_q = quote(sheet, safe="")
        urls = [
            ("gviz", f"https://docs.google.com/spreadsheets/d/e/{TOMZULU_FIRE_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_q}"),
            ("published-csv", f"https://docs.google.com/spreadsheets/d/e/{TOMZULU_FIRE_SHEET_ID}/pub?output=csv&single=true&sheet={sheet_q}"),
        ]
        errors = []
        for endpoint, url in urls:
            try:
                text = self._fetch_vehicle_url(url, timeout=5.0)
                vehicles = parse_vehicle_csv(text, region_code)
                if not vehicles:
                    raise ValueError("geen herkenbare voertuignummers")
                return {"vehicles": vehicles, "source": "Tomzulu10", "endpoint": endpoint, "pages": 1}
            except Exception as exc:
                errors.append(f"{endpoint}: {exc}")
        raise RuntimeError(" | ".join(errors))

    def _sync_vehicle_region(self, region_code: str, force: bool = False) -> dict:
        VEHICLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = vehicle_cache_path(region_code)
        if path.exists() and not force:
            age = max(0.0, time.time() - path.stat().st_mtime)
            if age < FIRE_DB_REFRESH_SECONDS:
                vehicles, meta = load_cached_vehicle_region(region_code)
                if vehicles:
                    return {
                        "ok": True, "cached": True, "count": len(vehicles),
                        "updated_at": meta.get("updated_at"), "source": meta.get("source"),
                        "pages": meta.get("pages", 1),
                    }

        attempts: list[str] = []
        result = None
        for source_name, loader in (
            ("Hulpdienstvoertuigen.nl", self._sync_vehicle_region_hulpdienst),
            ("Tomzulu10 fallback", self._sync_vehicle_region_tomzulu),
        ):
            try:
                result = loader(region_code)
                break
            except Exception as exc:
                attempts.append(f"{source_name}: {exc}")

        if result:
            vehicles = result["vehicles"]
            meta = {
                "region": region_code,
                "updated_at": utcnow_iso(),
                "count": len(vehicles),
                "source": result.get("source"),
                "endpoint": result.get("endpoint"),
                "pages": result.get("pages", 1),
            }
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"meta": meta, "vehicles": vehicles}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tmp.replace(path)
            return {
                "ok": True, "cached": False, "count": len(vehicles),
                "updated_at": meta["updated_at"], "source": meta["source"],
                "endpoint": meta["endpoint"], "pages": meta["pages"],
            }

        old, meta = load_cached_vehicle_region(region_code)
        return {
            "ok": bool(old), "cached": bool(old), "stale": bool(old), "count": len(old),
            "updated_at": meta.get("updated_at"), "source": meta.get("source"),
            "error": " | ".join(attempts)[:1200],
        }

    def sync_vehicle_catalog(self, force: bool = False) -> dict:
        if not self.vehicle_sync_lock.acquire(blocking=False):
            if force:
                with self.vehicle_catalog_lock:
                    self.vehicle_sync_force_pending = True
                    self.vehicle_sync_status["force_pending"] = True
            return self.vehicle_sync_view()
        rerun_force = False
        try:
            codes = selected_fire_region_codes(self.config)
            started = utcnow_iso()
            with self.vehicle_catalog_lock:
                self.vehicle_sync_status.update({
                    "running": True, "last_started": started, "last_error": None,
                    "force_pending": bool(self.vehicle_sync_force_pending),
                })
            results: dict[str, dict] = {}
            errors: list[str] = []
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(codes))), thread_name_prefix="vehicle-region") as pool:
                futures = {pool.submit(self._sync_vehicle_region, code, force): code for code in codes}
                for future in as_completed(futures):
                    code = futures[future]
                    if self.stop_event.is_set():
                        break
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}
                    results[code] = result
                    if result.get("error") and not result.get("ok"):
                        errors.append(f"{code}: {result['error']}")
            self._refresh_vehicle_catalog()
            with self.vehicle_catalog_lock:
                self.vehicle_sync_status.update({
                    "running": False, "last_finished": utcnow_iso(), "regions": results,
                    "last_error": "; ".join(errors[:5]) if errors else None,
                    "count": len(self.vehicle_catalog),
                })
            self.broadcast({"type": "vehicle-db", "status": self.vehicle_sync_view()})
            return self.vehicle_sync_view()
        finally:
            with self.vehicle_catalog_lock:
                rerun_force = bool(self.vehicle_sync_force_pending)
                self.vehicle_sync_force_pending = False
                self.vehicle_sync_status["running"] = False
                self.vehicle_sync_status["force_pending"] = False
            self.vehicle_sync_lock.release()
            # A manual force-click during startup sync must never be lost. Start
            # one fresh forced pass after the current pass releases the lock.
            if rerun_force and not self.stop_event.is_set():
                threading.Thread(target=self.sync_vehicle_catalog, kwargs={"force": True}, daemon=True, name="vehicle-db-force-sync").start()

    def start_vehicle_sync(self, force: bool = False):
        if not selected_fire_region_codes(self.config):
            self._refresh_vehicle_catalog()
            return
        threading.Thread(target=self.sync_vehicle_catalog, kwargs={"force": force}, daemon=True, name="vehicle-db-sync").start()

    def save_kv(self, key: str, value: str | None):
        if value is None:
            return
        with self.connect() as con:
            con.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def migrate_source_v16(self) -> int:
        """Drop cached rows from the retired Zwaailicht collector once."""
        key = "migration:v16:alarmeringen-source"
        with self.connect() as con:
            done = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            if done:
                return 0
            cur = con.execute("DELETE FROM messages WHERE source <> ?", (SOURCE_NAME,))
            removed = cur.rowcount if cur.rowcount is not None else 0
            con.execute("INSERT INTO kv(key,value) VALUES(?,?)", (key, utcnow_iso()))
        return max(0, removed)

    def purge_out_of_scope(self) -> int:
        """Remove rows from older versions that stored the full nationwide feed."""
        removed = 0
        with self.db_lock, self.connect() as con:
            rows = con.execute("SELECT id,title,summary,units_json,city,categories_json,service FROM messages").fetchall()
            delete_ids = []
            for row in rows:
                try:
                    units = json.loads(row["units_json"])
                except Exception:
                    units = []
                try:
                    categories = json.loads(row["categories_json"])
                except Exception:
                    categories = []
                service = row["service"] if "service" in row.keys() else ""
                msg = Message(id=row["id"], published="", updated="", title=row["title"], summary=row["summary"], url="", service=service,
                              priority="", city=row["city"], location="", units=units, categories=categories, scale="", scale_score=0,
                              incident_key="", source="")
                if not config_allows_message(self.config, msg):
                    delete_ids.append((row["id"],))
            if delete_ids:
                con.executemany("DELETE FROM messages WHERE id=?", delete_ids)
                removed = len(delete_ids)
        return removed

    def clear_feed_cache(self):
        """Forget conditional-request cache so the next poll fetches complete bodies."""
        self.feed_cache.clear()
        with self.connect() as con:
            con.execute("DELETE FROM kv WHERE key LIKE 'feed:%'")

    def request_feed_refresh(self, clear_cache: bool = False):
        if clear_cache:
            self.clear_feed_cache()
        self.manual_refresh_event.set()

    def get_display_settings(self) -> dict:
        try:
            with self.connect() as con:
                row = con.execute("SELECT value FROM kv WHERE key='display:settings'").fetchone()
        except sqlite3.OperationalError:
            # Parser/unit tests and first-start recovery paths can ask for display
            # settings before schema initialization. Treat that exactly like an
            # empty settings store instead of breaking feed parsing.
            return {}
        if not row:
            return {}
        try:
            value = json.loads(row["value"])
            if not isinstance(value, dict):
                return {}
            if isinstance(value.get("services"), list):
                allowed = {"brandweer", "ambulance", "politie", "lifeliner", "knrm", "overig"}
                value["services"] = [x for x in value["services"] if x in allowed]
                if not value["services"]:
                    value["services"] = ["brandweer", "politie", "lifeliner", "knrm", "overig"]
            return value
        except Exception:
            return {}

    def save_display_settings(self, payload: dict) -> dict:
        allowed = {
            "name", "services", "cities", "keywords", "nightMode", "nightStart", "nightEnd",
            "messageMinutes", "maxAgeMinutes", "dateFormat", "idleCentered", "burnInProtection",
            "burnInPixels", "autoTextSize", "darkLedPercent", "vehicleHeader", "displaySleep",
            "speechEnabled", "speechCities", "speechRate", "speechEngine", "speechPitch",
            "speechDeviceVolumeDay", "speechDeviceVolumeNight", "speechDeviceVolumeUrgent",
            "mapEnabled", "mapZoom", "locationAliases", "ttsDictionary", "capcodeMap",
            "idleStyle", "idleDimEnabled", "idleDimStart", "idleDimEnd", "idleDimMin",
            "idleDimEarliest", "smartSilenceEnabled", "smartSilenceMinutes",
            "postIncidentQuietEnabled", "postIncidentQuietSeconds",
            "backgroundStyle", "backgroundColor", "backgroundPhotoVersion", "backgroundPhotoDarkness", "backgroundPhotoFit", "kioskMonitor",
            "dispatchTuneEnabled", "dispatchTuneDefault", "dispatchTuneBrandweer", "dispatchTuneAmbulance",
            "dispatchTunePolitie", "dispatchTuneLifeliner", "dispatchTuneKnrm", "dispatchTuneUrgent",
            "dispatchTuneYoutubeUrl", "dispatchTuneYoutubeSeconds", "dispatchTuneVolume", "dispatchTuneCustomVersion"
        }
        clean = {k: v for k, v in (payload or {}).items() if k in allowed}
        # Server-side type/range hygiene as well as frontend validation. A bad
        # control request must never leave persistent settings in a state that
        # makes the kiosk render or speak unpredictably.
        bool_keys = (
            "nightMode", "idleCentered", "burnInProtection", "autoTextSize",
            "vehicleHeader", "displaySleep", "speechEnabled",
            "mapEnabled", "idleDimEnabled",
            "smartSilenceEnabled", "postIncidentQuietEnabled", "dispatchTuneEnabled",
        )
        for key in bool_keys:
            if key in clean and not isinstance(clean[key], bool):
                clean.pop(key, None)

        numeric_ranges = {
            "messageMinutes": (0.25, 15.0, float),
            "maxAgeMinutes": (0.25, 30.0, float),
            "burnInPixels": (0, 30, int),
            "darkLedPercent": (0, 30, float),
            "speechRate": (0.65, 1.25, float),
            "speechPitch": (0.75, 1.30, float),
            "speechDeviceVolumeDay": (5, 100, int),
            "speechDeviceVolumeNight": (5, 100, int),
            "speechDeviceVolumeUrgent": (5, 100, int),
            "backgroundPhotoVersion": (0, 9_999_999_999_999, int),
            "backgroundPhotoDarkness": (0.0, 0.90, float),
            "dispatchTuneYoutubeSeconds": (1.0, 15.0, float),
            "dispatchTuneVolume": (0, 100, int),
            "dispatchTuneCustomVersion": (0, 9_999_999_999_999, int),
        }
        for key, (lo, hi, caster) in numeric_ranges.items():
            if key not in clean:
                continue
            try:
                value = caster(clean[key])
                clean[key] = max(lo, min(hi, value))
            except (TypeError, ValueError):
                clean.pop(key, None)

        for key in ("services", "cities", "keywords", "speechCities"):
            if key in clean:
                if not isinstance(clean[key], list):
                    clean.pop(key, None)
                else:
                    clean[key] = [str(x)[:80] for x in clean[key][:50]]
        if "services" in clean:
            allowed_services = {"brandweer", "ambulance", "politie", "lifeliner", "knrm", "overig"}
            clean["services"] = [x for x in clean["services"] if x in allowed_services]
        if "dateFormat" in clean and clean["dateFormat"] not in ("dd-mm-yyyy", "yyyy-mm-dd", "weekday"):
            clean["dateFormat"] = "dd-mm-yyyy"
        # The supported primary path is locally rendered WAV played by
        # the lightkrant tab. Old "browser" preferences are migrated away.
        if "speechEngine" in clean:
            clean["speechEngine"] = "online"
        for time_key in ("nightStart", "nightEnd", "idleDimStart", "idleDimEnd", "idleDimEarliest"):
            if time_key in clean and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(clean[time_key])):
                clean.pop(time_key, None)

        for dict_key in ("locationAliases", "ttsDictionary", "capcodeMap"):
            if dict_key in clean:
                if not isinstance(clean[dict_key], dict):
                    clean.pop(dict_key, None)
                else:
                    clipped = {}
                    for i, (k, v) in enumerate(clean[dict_key].items()):
                        if i >= 300:
                            break
                        kk = str(k)[:120].strip()
                        if not kk:
                            continue
                        if dict_key == "capcodeMap":
                            if isinstance(v, dict):
                                clipped[kk] = {
                                    "label": str(v.get("label") or "")[:160],
                                    "speech": str(v.get("speech") or v.get("label") or "")[:160],
                                }
                            else:
                                vv = str(v)[:160].strip()
                                if vv:
                                    clipped[kk] = {"label": vv, "speech": vv}
                        else:
                            vv = str(v)[:160].strip()
                            if vv:
                                clipped[kk] = vv
                    clean[dict_key] = clipped
        if "name" in clean:
            clean["name"] = str(clean["name"])[:20]
        if "mapZoom" in clean:
            try:
                clean["mapZoom"] = max(12, min(18, int(clean["mapZoom"])))
            except Exception:
                clean.pop("mapZoom", None)
        if "idleStyle" in clean and clean["idleStyle"] not in ("minimal", "normal", "informative"):
            clean["idleStyle"] = "normal"
        if "idleDimMin" in clean:
            try:
                clean["idleDimMin"] = max(0.2, min(1.0, float(clean["idleDimMin"])))
            except Exception:
                clean.pop("idleDimMin", None)
        for num_key, lo, hi in (("smartSilenceMinutes", 5, 180), ("postIncidentQuietSeconds", 5, 120)):
            if num_key in clean:
                try:
                    clean[num_key] = max(lo, min(hi, int(clean[num_key])))
                except Exception:
                    clean.pop(num_key, None)
        for key in ("nightStart", "nightEnd", "dateFormat", "speechEngine", "idleStyle", "idleDimStart", "idleDimEnd", "idleDimEarliest"):
            if key in clean:
                clean[key] = str(clean[key])[:20]
        if "backgroundStyle" in clean:
            clean["backgroundStyle"] = str(clean["backgroundStyle"] or "black").lower()
            if clean["backgroundStyle"] not in {"black","nightblue","graphite","deepgreen","deepred","custom","photo"}:
                clean["backgroundStyle"] = "black"
        if "backgroundColor" in clean:
            color = str(clean["backgroundColor"] or "").strip()[:16]
            clean["backgroundColor"] = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#020506"
        if "backgroundPhotoFit" in clean:
            clean["backgroundPhotoFit"] = "contain" if str(clean["backgroundPhotoFit"]).lower() == "contain" else "cover"
        if "kioskMonitor" in clean:
            clean["kioskMonitor"] = str(clean["kioskMonitor"] or "primary")[:80]
        tune_choices = {"inherit", "none", "builtin:classic", "builtin:double", "builtin:rising", "builtin:urgent", "youtube", "custom"}
        for key in ("dispatchTuneDefault", "dispatchTuneBrandweer", "dispatchTuneAmbulance", "dispatchTunePolitie", "dispatchTuneLifeliner", "dispatchTuneKnrm", "dispatchTuneUrgent"):
            if key in clean:
                val = str(clean[key] or "inherit").lower()[:40]
                clean[key] = val if val in tune_choices else "inherit"
        if "dispatchTuneDefault" in clean and clean["dispatchTuneDefault"] == "inherit":
            clean["dispatchTuneDefault"] = "none"
        if "dispatchTuneYoutubeUrl" in clean:
            url = str(clean["dispatchTuneYoutubeUrl"] or "").strip()[:500]
            if url and not re.match(r"^https?://(?:www\.)?(?:youtube\.com|youtu\.be)/", url, re.I):
                url = ""
            clean["dispatchTuneYoutubeUrl"] = url
        with self.connect() as con:
            con.execute(
                "INSERT INTO kv(key,value) VALUES('display:settings',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(clean, ensure_ascii=False, separators=(",", ":")),),
            )
        self.broadcast({"type": "settings", "settings": clean})
        return clean

    def lookup_cached_geocode(self, city: str, location: str) -> dict | None:
        key = f"{normalize_city_token(city)}|{normalize_location_token(location)}"
        with self.connect() as con:
            row = con.execute("SELECT * FROM geocode_cache WHERE lookup_key=?", (key,)).fetchone()
        if not row:
            return None
        try:
            bbox = json.loads(row["bbox_json"] or "[]")
        except Exception:
            bbox = []
        return {
            "lookup_key": key,
            "city": row["city"],
            "location": row["location"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "display_name": row["display_name"],
            "bbox": bbox if isinstance(bbox, list) else [],
            "source": row["source"],
            "cached_at": row["cached_at"],
            "cached": True,
        }

    def store_geocode(self, city: str, location: str, payload: dict) -> dict:
        key = f"{normalize_city_token(city)}|{normalize_location_token(location)}"
        bbox = payload.get("bbox") or []
        now = utcnow_iso()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO geocode_cache(lookup_key, city, location, lat, lon, display_name, bbox_json, source, cached_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(lookup_key) DO UPDATE SET
                    city=excluded.city, location=excluded.location, lat=excluded.lat, lon=excluded.lon,
                    display_name=excluded.display_name, bbox_json=excluded.bbox_json,
                    source=excluded.source, cached_at=excluded.cached_at
                """,
                (key, str(city or ""), str(location or ""), float(payload["lat"]), float(payload["lon"]), str(payload.get("display_name") or "")[:240], json.dumps(bbox, ensure_ascii=False), str(payload.get("source") or "nominatim"), now),
            )
            # Keep the persistent map cache useful but bounded on a monitor that
            # may run for years and see thousands of unique incident locations.
            con.execute(
                "DELETE FROM geocode_cache WHERE lookup_key IN "
                "(SELECT lookup_key FROM geocode_cache ORDER BY cached_at DESC LIMIT -1 OFFSET 5000)"
            )
        out = {**payload, "lookup_key": key, "city": city, "location": location, "cached_at": now, "cached": False}
        return out

    def _fetch_json_url(self, url: str, timeout: float = 4.0, attempts: int = 2):
        """Small resilient JSON fetcher for public geodata services."""
        last_exc = None
        for attempt in range(max(1, attempts)):
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/geo+json, application/json;q=0.9, */*;q=0.2",
                "Cache-Control": "no-cache",
            })
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read(4_000_000)
                return json.loads(raw.decode("utf-8", "replace") or "{}")
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                    raise
            except Exception as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise
            time.sleep(0.16 * (attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError("Lege geodatarespons")

    def _pdok_location_search(self, city: str, query: str) -> dict | None:
        """Use the PDOK Location API, constrained to the best known Dutch search area."""
        query = normalize_space(query)
        if not query:
            return None
        _, bbox, center = geocode_area_for_city(city)
        bbox_text = ",".join(f"{x:.6f}" for x in bbox)
        # Address + road + named-place collections cover normal P2000 locations,
        # while functioneel_gebied catches sites such as stations/industrial areas.
        url = (
            "https://api.pdok.nl/kadaster/location-api/v1/search"
            f"?q={quote(query)}&f=geojson&limit=12&bbox={quote(bbox_text)}"
            "&adres%5Bversion%5D=1&adres%5Brelevance%5D=1"
            "&wegdeel%5Bversion%5D=1&wegdeel%5Brelevance%5D=0.95"
            "&plaats%5Bversion%5D=1&plaats%5Brelevance%5D=0.70"
            "&woonplaats%5Bversion%5D=1&woonplaats%5Brelevance%5D=0.70"
            "&functioneel_gebied%5Bversion%5D=1&functioneel_gebied%5Brelevance%5D=0.65"
            "&gebouw%5Bversion%5D=1&gebouw%5Brelevance%5D=0.55"
        )
        body = self._fetch_json_url(url, timeout=4.0, attempts=2)
        features = body.get("features") if isinstance(body, dict) else None
        if not isinstance(features, list):
            return None
        loc_key = normalize_location_token(query)
        city_key = normalize_city_token(city)
        # If P2000 only gives a street, an arbitrary BAG address (often house
        # number 1/2/12) must not look like an exact incident address. Prefer
        # road/public-space geometry unless the source text really contains a
        # house number. Road numbers such as A27/N65 are not house numbers.
        house_query = bool(re.search(r"\b\d{1,5}[A-Za-z]?(?:[-/]\d+[A-Za-z]?)?\b", query)) and not bool(re.fullmatch(r"\s*[AN]\s*\d{1,4}.*", query, re.I))
        ranked = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            point = geometry_center(feature.get("geometry"))
            if not point:
                continue
            lat, lon = point
            minx, miny, maxx, maxy = bbox
            if not (miny - .03 <= lat <= maxy + .03 and minx - .03 <= lon <= maxx + .03):
                continue
            props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
            # Location API deliberately keeps search results compact and property
            # names can differ per source collection. Rank against all scalar
            # properties instead of assuming one legacy Locatieserver field.
            prop_text = normalize_space(" ".join(
                str(v) for v in props.values()
                if isinstance(v, (str, int, float)) and str(v).strip()
            ))
            display = normalize_space(str(
                props.get("display_name") or props.get("weergavenaam") or
                props.get("weergave") or props.get("title") or props.get("name") or
                prop_text or query
            ))
            display_key = normalize_location_token(prop_text or display)
            collection = str(feature.get("collection") or props.get("collection") or props.get("collection_id") or "").lower()
            score = 0.0
            if loc_key and display_key == loc_key:
                score += 180
            elif loc_key and loc_key in display_key:
                score += 125
            elif loc_key:
                loc_words = {x for x in loc_key.split() if len(x) >= 3}
                score += 12 * len(loc_words & set(display_key.split()))
            if city_key and city_key in display_key:
                score += 90
            if "adres" in collection:
                score += 28 if house_query else -18
            if "weg" in collection or "openbare" in collection:
                score += 18 if house_query else 42
            if "woonplaats" in collection or "plaats" in collection:
                score += 4
            score -= min(45.0, rough_distance_sq(lat, lon, center) * 2500)
            fb = feature.get("bbox")
            if isinstance(fb, list) and len(fb) >= 4:
                try:
                    pbbox = [float(fb[1]), float(fb[3]), float(fb[0]), float(fb[2])]
                except Exception:
                    pbbox = [lat - .0035, lat + .0035, lon - .0055, lon + .0055]
            else:
                pbbox = [lat - .0035, lat + .0035, lon - .0055, lon + .0055]
            ranked.append((score, {
                "lat": lat, "lon": lon, "display_name": display, "bbox": pbbox,
                "source": "pdok-location",
            }))
        if not ranked:
            return None
        ranked.sort(key=lambda x: x[0], reverse=True)
        # A weak result is more dangerous than no result; older geocoders/BGT can
        # still resolve it without silently pinning the wrong same-named street.
        return ranked[0][1] if ranked[0][0] >= 35 else None

    def _lookup_street_index(self, city: str, location: str) -> dict | None:
        city_key = normalize_city_token(city)
        street_key = geocode_street_key(location)
        if not city_key or not street_key:
            return None
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM street_index WHERE city_key=? AND street_key=?",
                (city_key, street_key),
            ).fetchone()
        if not row:
            return None
        lat, lon = float(row["lat"]), float(row["lon"])
        return {
            "lat": lat, "lon": lon, "display_name": f"{row['street']}, {city}",
            "bbox": [lat - .0035, lat + .0035, lon - .0055, lon + .0055],
            "source": str(row["source"] or "bgt-straatindex"),
        }

    def _refresh_bgt_street_index(self, city: str, target_location: str = "", *, full: bool = False) -> dict | None:
        """Lazy-load official BGT public-space labels for one monitor town.

        This is a third geocoding layer, not the first network dependency. Once a
        town has been fetched, street-name lookups are local SQLite operations.
        """
        city_key = normalize_city_token(city)
        area_name, bbox, center = geocode_area_for_city(city)
        if city_key not in GEOCODE_AREAS and city:
            try:
                place_hit = self._pdok_location_search(city, city)
            except Exception:
                place_hit = None
            if place_hit:
                center = (float(place_hit["lon"]), float(place_hit["lat"]))
                cx, cy = center
                bbox = (max(3.1, cx - .22), max(50.65, cy - .16), min(7.35, cx + .22), min(53.70, cy + .16))
                area_name = city
        target_key = geocode_street_key(target_location)
        now = datetime.now(timezone.utc)
        with self.connect() as con:
            area = con.execute("SELECT * FROM street_area_cache WHERE city_key=?", (city_key,)).fetchone()
        if area:
            try:
                age = now - datetime.fromisoformat(str(area["fetched_at"]).replace("Z", "+00:00"))
            except Exception:
                age = timedelta(days=999)
            if age < timedelta(days=30) and int(area["complete"] or 0):
                return self._lookup_street_index(city, target_location)

        minx, miny, maxx, maxy = bbox
        url = (
            "https://api.pdok.nl/lv/bgt/ogc/v1/collections/openbareruimtelabel/items"
            f"?bbox={minx:.6f},{miny:.6f},{maxx:.6f},{maxy:.6f}&limit=1000&f=json"
        )
        best_by_key: dict[str, tuple[float, str, float, float]] = {}
        total = 0
        complete = False
        seen_urls = set()
        # A live unresolved incident may stop as soon as its exact street appears.
        # Background warmup is allowed to finish the complete town index.
        max_pages = 50 if full else 8
        for _page in range(max_pages):
            if not url or url in seen_urls:
                break
            seen_urls.add(url)
            body = self._fetch_json_url(url, timeout=4.5, attempts=1)
            features = body.get("features") if isinstance(body, dict) else None
            if not isinstance(features, list):
                break
            total += len(features)
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
                if normalize_space(str(props.get("termination_date") or props.get("eind_registratie") or "")):
                    continue
                if str(props.get("status") or "").lower() not in {"", "bestaand"}:
                    continue
                street = normalize_space(str(props.get("openbareruimtenaam") or ""))
                street_key = normalize_location_token(street)
                point = geometry_center(feature.get("geometry"))
                if not street_key or not point:
                    continue
                lat, lon = point
                dist = rough_distance_sq(lat, lon, center)
                old = best_by_key.get(street_key)
                if old is None or dist < old[0]:
                    best_by_key[street_key] = (dist, street, lat, lon)
            next_url = ""
            for link in body.get("links", []) if isinstance(body, dict) and isinstance(body.get("links"), list) else []:
                if isinstance(link, dict) and str(link.get("rel") or "").lower() == "next" and link.get("href"):
                    next_url = urljoin(url, str(link["href"]))
                    break
            if not next_url:
                complete = True
                break
            # If the exact requested street has already been seen, there is no
            # reason to delay the live incident while downloading the whole city.
            if (not full) and target_key and target_key in best_by_key:
                break
            url = next_url

        cached_at = utcnow_iso()
        if best_by_key:
            with self.connect() as con:
                # A completed background rebuild is authoritative for this town;
                # remove obsolete names before inserting the current BGT snapshot.
                if full and complete:
                    con.execute("DELETE FROM street_index WHERE city_key=?", (city_key,))
                for street_key, (_dist, street, lat, lon) in best_by_key.items():
                    con.execute(
                        """INSERT INTO street_index(city_key,street_key,city,street,lat,lon,source,cached_at)
                           VALUES(?,?,?,?,?,?,?,?)
                           ON CONFLICT(city_key,street_key) DO UPDATE SET
                           city=excluded.city, street=excluded.street, lat=excluded.lat, lon=excluded.lon,
                           source=excluded.source, cached_at=excluded.cached_at""",
                        (city_key, street_key, city, street, lat, lon, "bgt-straatindex", cached_at),
                    )
                con.execute(
                    """INSERT INTO street_area_cache(city_key,city,bbox_json,fetched_at,item_count,complete)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(city_key) DO UPDATE SET city=excluded.city,bbox_json=excluded.bbox_json,
                       fetched_at=excluded.fetched_at,item_count=MAX(street_area_cache.item_count,excluded.item_count),
                       complete=MAX(street_area_cache.complete,excluded.complete)""",
                    (city_key, area_name, json.dumps(list(bbox)), cached_at, total, 1 if complete else 0),
                )
        return self._lookup_street_index(city, target_location)

    def _ensure_street_index_async(self, city: str):
        """Build a complete official street-name cache for a used monitor town.

        This never blocks the lightkrant.  The first incident still uses the fast
        Location API/Locatieserver path; future streets in that town can then be
        resolved from SQLite even when an external geocoder is temporarily down.
        """
        city_key = normalize_city_token(city)
        if not city_key or self.stop_event.is_set():
            return
        with self.connect() as con:
            row = con.execute("SELECT fetched_at, complete FROM street_area_cache WHERE city_key=?", (city_key,)).fetchone()
        if row and int(row["complete"] or 0):
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
            except Exception:
                age = timedelta(days=999)
            if age < timedelta(days=30):
                return
        with self.street_index_warm_lock:
            if city_key in self.street_index_warming:
                return
            self.street_index_warming.add(city_key)

        def worker():
            try:
                self._refresh_bgt_street_index(city, "", full=True)
            except Exception:
                # Geocoding already has live fallbacks; a failed warmup must never
                # disturb an incident. It will be retried on a later request.
                pass
            finally:
                with self.street_index_warm_lock:
                    self.street_index_warming.discard(city_key)

        threading.Thread(target=worker, daemon=True, name=f"street-index-{city_key[:24]}").start()

    def geocode_incident(self, city: str, location: str, zoom: int = 16) -> dict:
        city = normalize_space(city)
        location = normalize_space(location)
        if not location and not city:
            raise ValueError("Geen locatie opgegeven")

        # Apply the same user-defined location aliases that incident clustering uses.
        # This means e.g. Prof. Asserweg / Prof Asserweg can resolve as the canonical
        # Professor Asserweg before a geocoder is queried.
        settings = self.get_display_settings()
        alias_map = build_location_alias_map(settings)
        canonical_location = alias_map.get(normalize_location_token(location), location) if location else location

        # Start learning this town's official BGT street labels in the background.
        # It is guarded per town and refreshes at most once every 30 days.
        self._ensure_street_index_async(city)

        cached = self.lookup_cached_geocode(city, canonical_location or location)
        if cached:
            lat = float(cached["lat"]); lon = float(cached["lon"])
            bbox = cached.get("bbox") or [lat - .004, lat + .004, lon - .006, lon + .006]
            cached["embed_url"] = build_osm_embed_url(lat, lon, bbox, zoom)
            return cached

        queries: list[str] = []

        # Keep road-specific metadata useful for Dutch geocoding. PDOK can
        # resolve hectometer points, but sources write decimals/rijbanen in many
        # forms (A27 Li 21,3 / A27 21.3). Feed multiple precise variants first.
        road_match = re.search(r"\b([AN]\d{1,3})\s+(LI|RE)\s+(\d{1,3})[,.](\d)\b", canonical_location or location, re.I)
        if road_match:
            road, side, whole, dec = road_match.groups()
            hm_dot = f"{whole}.{dec}"
            if city:
                queries.extend([
                    f"{road.upper()} hectometer {hm_dot} {city}",
                    f"{road.upper()} {hm_dot} {city}",
                    f"{road.upper()} {side.upper()} {hm_dot} {city}",
                ])
            queries.extend([f"{road.upper()} hectometer {hm_dot}", f"{road.upper()} {hm_dot}"])

        # A '#' in native P2000 means a crossing. Try the full crossing first,
        # then both streets separately in the same city as resilient fallbacks.
        crossing = [normalize_space(x) for x in re.split(r"\s*#\s*", canonical_location or location) if normalize_space(x)]
        if len(crossing) == 2:
            if city:
                queries.extend([
                    f"{crossing[0]} {crossing[1]} {city}",
                    f"{crossing[0]} {city}",
                    f"{crossing[1]} {city}",
                ])
            else:
                queries.extend(crossing)

        if canonical_location and city:
            queries.append(f"{canonical_location} {city}")
        if location and city and normalize_space(location).lower() != normalize_space(canonical_location).lower():
            queries.append(f"{location} {city}")
        if canonical_location:
            queries.append(canonical_location)
        if location:
            queries.append(location)
        if city and not location:
            queries.append(city)
        queries = list(dict.fromkeys([normalize_space(x) for x in queries if normalize_space(x)]))

        errors: list[str] = []

        # If this town was indexed previously, an ordinary street name is now an
        # offline SQLite lookup and does not depend on an external service.
        local_street = self._lookup_street_index(city, canonical_location or location)
        if local_street:
            stored = self.store_geocode(city, canonical_location or location, local_street)
            stored["embed_url"] = build_osm_embed_url(float(stored["lat"]), float(stored["lon"]), stored.get("bbox"), zoom)
            return stored

        # Primary source: the new PDOK Location API. It searches multiple current
        # government collections and supports a geographic bounding box, which is
        # useful for resolving duplicate Dutch street names in any configured standplaats.
        for q in queries:
            try:
                payload = self._pdok_location_search(city, q)
                if not payload:
                    continue
                lat, lon = float(payload["lat"]), float(payload["lon"])
                stored = self.store_geocode(city, canonical_location or location or q, payload)
                stored["embed_url"] = build_osm_embed_url(lat, lon, payload.get("bbox"), zoom)
                return stored
            except Exception as exc:
                errors.append(f"PDOK Location: {type(exc).__name__}: {exc}")

        # Secondary source: classic PDOK Locatieserver. Keep it because it is
        # especially good at BAG addresses and hectometer posts.
        for q in queries:
            url = (
                "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
                f"?q={quote(q)}&rows=5"
            )
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = json.loads(resp.read().decode("utf-8", "replace") or "{}")
                docs = ((body or {}).get("response") or {}).get("docs") or []
                if not isinstance(docs, list) or not docs:
                    continue

                query_has_house = bool(re.search(r"\b\d{1,5}[A-Za-z]?(?:[-/]\d+[A-Za-z]?)?\b", q)) and not bool(re.fullmatch(r"\s*[AN]\s*\d{1,4}.*", q, re.I))
                def pdok_score(doc: dict) -> tuple:
                    typ = str(doc.get("type") or "").lower()
                    bron = str(doc.get("bron") or "").upper()
                    place = str(doc.get("woonplaatsnaam") or doc.get("gemeentenaam") or "").lower()
                    city_match = 1 if city and normalize_city_token(place) == normalize_city_token(city) else 0
                    if query_has_house:
                        type_rank = {"hectometerpaal": 8, "adres": 7, "weg": 5, "straat": 5, "woonplaats": 2}.get(typ, 1)
                    else:
                        type_rank = {"hectometerpaal": 8, "weg": 8, "straat": 8, "openbareruimte": 8, "adres": 3, "woonplaats": 2}.get(typ, 1)
                    bag_rank = 1 if bron == "BAG" else 0
                    try: source_score = float(doc.get("score") or 0)
                    except Exception: source_score = 0.0
                    return (city_match, type_rank, bag_rank, source_score)

                for doc in sorted((d for d in docs if isinstance(d, dict)), key=pdok_score, reverse=True):
                    point = str(doc.get("centroide_ll") or "")
                    m = re.search(r"POINT\(\s*([-+0-9.]+)\s+([-+0-9.]+)\s*\)", point, re.I)
                    if not m:
                        continue
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    # A compact side-panel works best with a predictable street-level viewport.
                    bbox = [lat - .0035, lat + .0035, lon - .0055, lon + .0055]
                    display = str(doc.get("weergavenaam") or doc.get("straatnaam") or q)
                    payload = {
                        "lat": lat,
                        "lon": lon,
                        "display_name": display,
                        "bbox": bbox,
                        "source": "pdok",
                    }
                    stored = self.store_geocode(city, canonical_location or location or q, payload)
                    stored["embed_url"] = build_osm_embed_url(lat, lon, bbox, zoom)
                    return stored
            except Exception as exc:
                errors.append(f"PDOK: {type(exc).__name__}: {exc}")

        # Third official layer: lazily build a local BGT public-space/street index
        # for this town. The BGT collection contains the official named public
        # spaces. Once fetched, subsequent incidents on those streets are offline.
        try:
            local_street = self._refresh_bgt_street_index(city, canonical_location or location)
            if local_street:
                lat, lon = float(local_street["lat"]), float(local_street["lon"])
                stored = self.store_geocode(city, canonical_location or location, local_street)
                stored["embed_url"] = build_osm_embed_url(lat, lon, local_street.get("bbox"), zoom)
                return stored
        except Exception as exc:
            errors.append(f"BGT straatindex: {type(exc).__name__}: {exc}")

        # Last network fallback: Nominatim/OpenStreetMap. This is useful for a
        # landmark that is not an official BAG/BGT public-space name.
        for q in queries:
            osm_q = f"{q}, Nederland"
            url = (
                "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=nl"
                f"&addressdetails=0&q={quote(osm_q)}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    rows = json.loads(resp.read().decode("utf-8", "replace") or "[]")
                if not rows:
                    continue
                row = rows[0]
                lat = float(row.get("lat")); lon = float(row.get("lon"))
                bb = row.get("boundingbox") or []
                if len(bb) == 4:
                    bbox = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
                else:
                    bbox = [lat - .004, lat + .004, lon - .006, lon + .006]
                payload = {
                    "lat": lat,
                    "lon": lon,
                    "display_name": str(row.get("display_name") or osm_q),
                    "bbox": bbox,
                    "source": "nominatim",
                }
                stored = self.store_geocode(city, canonical_location or location or q, payload)
                stored["embed_url"] = build_osm_embed_url(lat, lon, bbox, zoom)
                return stored
            except Exception as exc:
                errors.append(f"OSM: {type(exc).__name__}: {exc}")

        detail = errors[-1] if errors else "geen resultaat"
        raise RuntimeError(f"Geocoding mislukt: {detail}")

    def _windows_monitor_power(self, mode: str) -> tuple[bool, str | None]:
        """Control monitor power with the native Windows API."""
        if os.name != "nt":
            return False, "Windows monitorbesturing is alleen beschikbaar op Windows"
        try:
            import ctypes
            if mode == "off":
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
            else:
                # Keep the display awake and generate a tiny mouse movement so a
                # monitor that is already in power-save wakes immediately.
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
                ctypes.windll.user32.mouse_event(0x0001, 0, 1, 0, 0)
                ctypes.windll.user32.mouse_event(0x0001, 0, -1, 0, 0)
            return True, None
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def display_info(self, force: bool = False, allow_stale: bool = False) -> dict:
        supported = os.name == "nt"
        monitors = enumerate_windows_monitors()
        settings = self.get_display_settings()
        selected = choose_windows_monitor(settings.get("kioskMonitor", "primary"), monitors)
        result = {
            "connected": supported,
            "connector": "Windows display" if supported else "",
            "name": selected.get("label") if supported else "Niet op Windows gestart",
            "method": "windows-monitor-power" if supported else None,
            "session": "windows" if supported else os.name,
            "monitors": monitors,
            "selected_monitor": selected,
            "selected_monitor_id": settings.get("kioskMonitor", "primary"),
        }
        self.display_connector = result["connector"] or None
        self.display_name = result["name"]
        self.display_power_method = result["method"]
        self.display_info_cache = dict(result)
        self.display_info_monotonic = time.monotonic()
        return result

    def set_display_power(self, mode: str, manual: bool = False) -> dict:
        mode = (mode or "").lower()
        if mode not in {"on", "off"}:
            return {"ok": False, "status": self.display_power_status, "error": "state must be on/off"}
        if mode == "off" and not manual and time.monotonic() < self.display_manual_wake_until_monotonic:
            remaining = max(1, int(self.display_manual_wake_until_monotonic - time.monotonic()))
            return {"ok": True, "status": "on", "method": "windows-monitor-power", "held": True, "retry_after": remaining, "error": None}
        ok, err = self._windows_monitor_power(mode)
        self.display_power_status = mode if ok else "unsupported"
        self.display_power_method = "windows-monitor-power" if ok else None
        self.display_power_error = err
        self.display_power_changed_at = utcnow_iso()
        if manual and mode == "on" and ok:
            self.display_manual_wake_until_monotonic = time.monotonic() + 120.0
        elif manual and mode == "off":
            self.display_manual_wake_until_monotonic = 0.0
        return {"ok": ok, "status": self.display_power_status, "method": self.display_power_method, "error": err, "display": self.display_info(force=True)}

    def record_unknown_callsigns(self, con: sqlite3.Connection, message: Message):
        """Persist plausible fire callsigns not present in the exact regional cache.

        Police/ambulance incident numbers can also contain six digits.  Never feed
        those into the unknown-fire list; only inspect actual fire dispatches and
        region prefixes relevant to the configured fire scope (plus 26/28 national
        fire/NIPV/Defence prefixes).
        """
        if str(message.service or "").lower() != "brandweer":
            return
        selected = set(selected_fire_region_codes(self.config))
        allowed_prefixes = selected | {"26", "28"}
        raw_values = [message.title, message.summary, " ".join(message.units or [])]
        for digits, callsign in extract_fire_callsigns(*raw_values):
            if not digits or digits[:2] not in allowed_prefixes:
                continue
            if digits in self.known_vehicle_keys:
                continue
            now = message.published or utcnow_iso()
            line = raw_line_for_callsign(message, digits)
            con.execute(
                """
                INSERT INTO unknown_vehicles
                (callsign,digits,first_seen,last_seen,seen_count,last_message_id,last_message,last_city,last_url)
                VALUES (?,?,?,?,1,?,?,?,?)
                ON CONFLICT(callsign) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    seen_count=unknown_vehicles.seen_count+1,
                    last_message_id=excluded.last_message_id,
                    last_message=excluded.last_message,
                    last_city=excluded.last_city,
                    last_url=excluded.last_url
                """,
                (callsign, digits, now, now, message.id, line, message.city or "", message.url or ""),
            )

    def list_unknown_callsigns(self, limit: int = 100) -> list[dict]:
        # Catalog is kept in memory and refreshed atomically after regional sync.
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM unknown_vehicles ORDER BY last_seen DESC LIMIT ?",
                (min(max(int(limit), 1), 500),),
            ).fetchall()
        return [dict(r) for r in rows if r["digits"] not in self.known_vehicle_keys]

    def add_messages(self, messages: list[Message]) -> list[Message]:
        # Enforce the first-run region/discipline matrix before SQLite or SSE.
        messages = [m for m in messages if config_allows_message(self.config, m)]
        inserted: list[Message] = []
        ingested_times: dict[str, str] = {}
        with self.db_lock, self.connect() as con:
            for m in sorted(messages, key=lambda x: x.published):
                ingested_at = utcnow_iso()
                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO messages
                    (id,published,updated,title,summary,url,service,priority,city,location,
                     units_json,categories_json,scale,scale_score,incident_key,source,ingested_at,parser_confidence,parser_notes_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        m.id, m.published, m.updated, m.title, m.summary, m.url, m.service,
                        m.priority, m.city, m.location, json.dumps(m.units, ensure_ascii=False),
                        json.dumps(m.categories, ensure_ascii=False), m.scale, m.scale_score,
                        m.incident_key, m.source, ingested_at, int(m.parser_confidence or 0),
                        json.dumps(m.parser_notes or [], ensure_ascii=False),
                    ),
                )
                if cur.rowcount:
                    inserted.append(m)
                    ingested_times[m.id] = ingested_at
                    self.record_unknown_callsigns(con, m)
            retention_days = int(self.config.get("retention_days", 30))
            cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat(timespec="seconds")
            con.execute("DELETE FROM messages WHERE published < ?", (cutoff,))
        for m in inserted:
            payload = asdict(m)
            payload["ingested_at"] = ingested_times.get(m.id) or utcnow_iso()
            self.broadcast({"type": "message", "message": payload})
        return inserted

    def broadcast(self, payload: dict) -> int:
        dead = []
        with self.sub_lock:
            for q in self.subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                if q in self.subscribers:
                    self.subscribers.remove(q)
            return max(0, len(self.subscribers))

    def subscriber_count(self) -> int:
        with self.sub_lock:
            return len(self.subscribers)

    def record_feed_metrics(self, url: str, source_latency_seconds: float | None, fetch_ms: float | None):
        if source_latency_seconds is not None:
            rows = self.feed_latency_history.setdefault(url, [])
            rows.append(float(source_latency_seconds)); del rows[:-120]
        if fetch_ms is not None:
            rows = self.feed_fetch_history.setdefault(url, [])
            rows.append(float(fetch_ms)); del rows[:-120]

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float | None:
        if not values:
            return None
        rows = sorted(values)
        idx = max(0, min(len(rows) - 1, round((len(rows) - 1) * percentile)))
        return round(rows[idx], 1)

    def health_snapshot(self) -> dict:
        try:
            db_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        except OSError:
            db_bytes = 0
        try:
            tts_files = ([*TTS_CACHE_DIR.glob("*.mp3"), *TTS_CACHE_DIR.glob("*.wav")]) if TTS_CACHE_DIR.exists() else []
            tts_bytes = sum(f.stat().st_size for f in tts_files)
        except OSError:
            tts_files, tts_bytes = [], 0
        try:
            fd_count = len(os.listdir(f"/proc/{os.getpid()}/fd"))
        except OSError:
            fd_count = None
        rss_bytes = None
        try:
            with open(f"/proc/{os.getpid()}/status", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        rss_bytes = int(line.split()[1]) * 1024
                        break
        except (OSError, ValueError, IndexError):
            pass
        with self.sub_lock:
            sse_clients = len(self.subscribers)
        try:
            load1, load5, load15 = os.getloadavg()
        except (OSError, AttributeError):
            load1 = load5 = load15 = None
        try:
            with self.connect() as con:
                geocode_rows = con.execute("SELECT COUNT(*) FROM geocode_cache").fetchone()[0]
                message_rows = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        except Exception:
            geocode_rows = message_rows = None
        feed_metrics = []
        for url, diag in self.feed_diag.items():
            latency = self.feed_latency_history.get(url, [])
            fetches = self.feed_fetch_history.get(url, [])
            feed_metrics.append({
                "url": url,
                "status": diag.get("status"),
                "ingest_latency_seconds": diag.get("ingest_latency_seconds"),
                "latest_entry_age_seconds": diag.get("latest_entry_age_seconds"),
                "latency_p50_seconds": self._percentile(latency, .50),
                "latency_p95_seconds": self._percentile(latency, .95),
                "fetch_p50_ms": self._percentile(fetches, .50),
                "fetch_p95_ms": self._percentile(fetches, .95),
                "samples": max(len(latency), len(fetches)),
            })
        with self.client_health_lock:
            client_health = dict(self.client_health)
        return {
            "uptime_seconds": int(max(0, time.monotonic() - self.started_monotonic)),
            "rss_bytes": rss_bytes,
            "open_fds": fd_count,
            "database_bytes": db_bytes,
            "tts_cache_bytes": tts_bytes,
            "tts_cache_files": len(tts_files),
            "sse_clients": sse_clients,
            "sse_peak": self.sse_peak,
            "api_requests": self.api_requests,
            "api_errors": self.api_errors,
            "threads": threading.active_count(),
            "load_average": [round(load1, 2), round(load5, 2), round(load15, 2)] if load1 is not None else None,
            "messages": message_rows,
            "geocode_cache_rows": geocode_rows,
            "feed_metrics": feed_metrics,
            "fallback_configured": len(self.config.get("fallback_feed_urls") or []),
            "fallback_activations": self.fallback_activations,
            "last_fallback_action": self.last_fallback_action,
            "display_client": client_health,
        }

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self.sub_lock:
            self.subscribers.append(q)
            self.sse_peak = max(self.sse_peak, len(self.subscribers))
        return q

    def unsubscribe(self, q: queue.Queue):
        with self.sub_lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


class FeedPoller(threading.Thread):
    daemon = True

    def __init__(self, state: AppState):
        super().__init__(name="p2000-feed-poller")
        self.state = state
        self.nearby_poll_cycle = 0

    def parse_feed(self, xml_bytes: bytes, source_url: str = "") -> list[Message]:
        """Parse either RSS 2.0 (Alarmeringen) or Atom for backwards-safe tests."""
        root = ET.fromstring(xml_bytes)
        messages: list[Message] = []
        source_region_key = region_slug_for_url(source_url)
        source_region_label = REGION_CATALOG.get(source_region_key, {}).get("label", "") if source_region_key else ""
        alias_map = build_location_alias_map(self.state.get_display_settings())
        source_label = source_name_for_url(source_url)

        # RSS 2.0
        if root.tag.lower().endswith("rss") or root.find("channel") is not None:
            channel = root.find("channel")
            if channel is None:
                channel = root
            items = channel.findall("item")
            for item in items:
                title = strip_html(item.findtext("title", default=""))
                summary = strip_html(item.findtext("description", default=""))
                url = normalize_space(item.findtext("link", default=""))
                guid = normalize_space(item.findtext("guid", default=""))
                published = parse_dt(item.findtext("pubDate", default=""))
                updated = published
                categories = [normalize_space(c.text or "") for c in item.findall("category") if normalize_space(c.text or "")]
                if source_region_label:
                    categories.append(f"Regio {source_region_label}")
                elif url:
                    article_region = region_slug_from_article_url(url)
                    if article_region:
                        categories.append(f"Regio {REGION_CATALOG[article_region]['label']}")
                service = detect_service(title, summary, categories)
                priority = detect_priority(title, summary)
                city = infer_city(categories, title) or city_from_article_url(url)
                location = infer_location(title, summary, city)
                units = infer_units(summary, title)
                ll = detect_lifeliner_number(title, summary, units)
                mmt_resource = detect_mmt_resource(title, summary, units)
                if mmt_resource:
                    service = "lifeliner" if mmt_resource.get("kind") == "helicopter" else "ambulance"
                scale, scale_score = detect_scale(title, summary)
                # Prefer the canonical article URL so the same item appearing in both
                # RSS feeds gets one database id. GUID is only a fallback.
                raw_id = url or guid or f"{published}|{title}|{summary}"
                msg_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24]
                ikey = incident_key(service, city, location, title, alias_map)
                confidence, parser_notes = parser_confidence_details(title, summary, categories, service, priority, city, location, units, scale)
                messages.append(Message(
                    id=msg_id, published=published, updated=updated, title=title,
                    summary=summary, url=url, service=service, priority=priority,
                    city=city, location=location, units=units, categories=list(dict.fromkeys(categories)),
                    scale=scale, scale_score=scale_score, incident_key=ikey, source=source_label,
                    parser_confidence=confidence, parser_notes=parser_notes,
                ))
            return messages

        # Atom fallback (kept so existing test fixtures and imports remain harmless).
        for entry in root.findall("a:entry", ATOM_NS):
            title = strip_html(entry.findtext("a:title", default="", namespaces=ATOM_NS))
            summary = strip_html(entry.findtext("a:summary", default="", namespaces=ATOM_NS))
            if not summary:
                summary = strip_html(entry.findtext("a:content", default="", namespaces=ATOM_NS))
            atom_id = normalize_space(entry.findtext("a:id", default="", namespaces=ATOM_NS))
            published = parse_dt(entry.findtext("a:published", default="", namespaces=ATOM_NS))
            updated = parse_dt(entry.findtext("a:updated", default=published, namespaces=ATOM_NS))
            links = entry.findall("a:link", ATOM_NS)
            url = next((link.attrib.get("href", "") for link in links if link.attrib.get("href") and link.attrib.get("rel", "alternate") in ("alternate", "")), "")
            if not url and links:
                url = links[0].attrib.get("href", "")
            categories = [normalize_space(c.attrib.get("term", "")) for c in entry.findall("a:category", ATOM_NS)]
            categories = [c for c in categories if c]
            if source_region_label:
                categories.append(f"Regio {source_region_label}")
            elif url:
                article_region = region_slug_from_article_url(url)
                if article_region:
                    categories.append(f"Regio {REGION_CATALOG[article_region]['label']}")
            service = detect_service(title, summary, categories)
            priority = detect_priority(title, summary)
            city = infer_city(categories, title) or city_from_article_url(url)
            location = infer_location(title, summary, city)
            units = infer_units(summary, title)
            ll = detect_lifeliner_number(title, summary, units)
            mmt_resource = detect_mmt_resource(title, summary, units)
            if mmt_resource:
                service = "lifeliner" if mmt_resource.get("kind") == "helicopter" else "ambulance"
            scale, scale_score = detect_scale(title, summary)
            raw_id = url or atom_id or f"{published}|{title}|{summary}"
            msg_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24]
            ikey = incident_key(service, city, location, title, alias_map)
            confidence, parser_notes = parser_confidence_details(title, summary, categories, service, priority, city, location, units, scale)
            messages.append(Message(id=msg_id,published=published,updated=updated,title=title,summary=summary,url=url,service=service,priority=priority,city=city,location=location,units=units,categories=list(dict.fromkeys(categories)),scale=scale,scale_score=scale_score,incident_key=ikey,source=source_label,parser_confidence=confidence,parser_notes=parser_notes))
        return messages

    def _accept_for_feed(self, url: str, m: Message) -> bool:
        return config_allows_message(self.state.config, m)

    def _cache_key(self, url: str, kind: str) -> str:
        return f"feed:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]}:{kind}"

    def _load_cache(self, url: str) -> dict[str, str]:
        if url in self.state.feed_cache:
            return self.state.feed_cache[url]
        cache = {}
        with self.state.connect() as con:
            for kind in ("etag", "last_modified"):
                row = con.execute("SELECT value FROM kv WHERE key=?", (self._cache_key(url, kind),)).fetchone()
                if row:
                    cache[kind] = row["value"]
        self.state.feed_cache[url] = cache
        return cache

    def _save_cache(self, url: str, kind: str, value: str | None):
        if not value:
            return
        self.state.feed_cache.setdefault(url, {})[kind] = value
        self.state.save_kv(self._cache_key(url, kind), value)

    def _process_payload(self, url: str, payload: bytes, diag: dict) -> tuple[int, int, int]:
        messages = self.parse_feed(payload, source_url=url)
        scoped = [m for m in messages if self._accept_for_feed(url, m)]
        inserted = self.state.add_messages(scoped)
        latest_entry = max((m.published for m in messages), default=None)
        latest_scope = max((m.published for m in scoped), default=None)
        latest_age = None
        if latest_entry:
            try:
                latest_dt = datetime.fromisoformat(latest_entry.replace("Z", "+00:00"))
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                latest_age = max(0.0, (datetime.now(timezone.utc) - latest_dt.astimezone(timezone.utc)).total_seconds())
            except Exception:
                latest_age = None
        ingest_latency = None
        if inserted:
            samples=[]
            now_utc=datetime.now(timezone.utc)
            for item in inserted:
                try:
                    dt=datetime.fromisoformat(item.published.replace("Z", "+00:00"))
                    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                    samples.append(max(0.0,(now_utc-dt.astimezone(timezone.utc)).total_seconds()))
                except Exception:
                    pass
            if samples:
                ingest_latency=min(samples)
        fetch_ms = diag.get("fetch_ms")
        diag.update(status="online",entries=len(messages),in_scope=len(scoped),inserted=len(inserted),
                    latest_entry=latest_entry,latest_scope=latest_scope,last_success=utcnow_iso(),
                    latest_entry_age_seconds=round(latest_age, 1) if latest_age is not None else None,
                    ingest_latency_seconds=round(ingest_latency, 1) if ingest_latency is not None else None)
        self.state.record_feed_metrics(url, ingest_latency, fetch_ms)
        return len(messages),len(scoped),len(inserted)

    def _curl_fallback(self, url: str, diag: dict) -> tuple[int, int, int] | None:
        curl = shutil.which("curl")
        if not curl:
            return None
        timeout = str(max(5, int(self.state.config.get("request_timeout_seconds", 15))))
        cmd=[curl,"-fsSL","--max-time",timeout,"--connect-timeout",timeout,
             "-A",USER_AGENT,"-H","Accept: application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",url]
        try:
            started = time.monotonic()
            proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=int(timeout)+5)
            diag["fetch_ms"] = round((time.monotonic() - started) * 1000, 1)
            if proc.returncode != 0:
                err=proc.stderr.decode("utf-8","replace").strip() or f"curl exit {proc.returncode}"
                diag["curl_error"]=err
                return None
            diag["transport"]="curl-fallback"
            return self._process_payload(url, proc.stdout, diag)
        except Exception as e:
            diag["curl_error"]=f"{type(e).__name__}: {e}"
            return None

    def fetch_url(self, url: str, force_full: bool = False, role: str = "primary") -> tuple[int, int, int]:
        cfg = self.state.config
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1"}
        cache = self._load_cache(url)
        if not force_full:
            if cache.get("etag"):
                headers["If-None-Match"] = cache["etag"]
            if cache.get("last_modified"):
                headers["If-Modified-Since"] = cache["last_modified"]
        req = urllib.request.Request(url, headers=headers)
        fetch_started = time.monotonic()
        previous = self.state.feed_diag.get(url, {})
        diag={"url":url,"role":role,"status":"fetching","transport":"python-urllib","last_poll":utcnow_iso(),
              "entries":0,"in_scope":0,"inserted":0,"error":None,
              "latest_entry":previous.get("latest_entry"),"latest_scope":previous.get("latest_scope"),
              "last_success":previous.get("last_success")}
        self.state.feed_diag[url]=diag
        try:
            with urllib.request.urlopen(req, timeout=int(cfg.get("request_timeout_seconds", 15))) as resp:
                payload = resp.read(int(cfg.get("max_feed_bytes", 2_000_000)))
                self._save_cache(url, "etag", resp.headers.get("ETag"))
                self._save_cache(url, "last_modified", resp.headers.get("Last-Modified"))
            diag["fetch_ms"] = round((time.monotonic() - fetch_started) * 1000, 1)
            return self._process_payload(url, payload, diag)
        except urllib.error.HTTPError as e:
            if e.code == HTTPStatus.NOT_MODIFIED:
                diag["fetch_ms"] = round((time.monotonic() - fetch_started) * 1000, 1)
                diag.update(status="online",not_modified=True,last_success=utcnow_iso())
                self.state.record_feed_metrics(url, None, diag["fetch_ms"])
                return 0,0,0
            diag["python_error"]=f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            diag["python_error"]=f"{type(e).__name__}: {e}"

        fallback=self._curl_fallback(url,diag)
        if fallback is not None:
            return fallback
        diag.update(status="error",error=diag.get("curl_error") or diag.get("python_error") or "Onbekende downloadfout")
        return 0,0,0


    def fetch_once(self) -> int:
        cfg=self.state.config
        core_urls=cfg.get("feed_urls") or build_feed_urls(setup_region_disciplines(cfg))
        effective_primary=list(dict.fromkeys(core_urls))
        nearby_urls=[]
        fallback_urls=[u for u in (cfg.get("fallback_feed_urls") or []) if u and u not in effective_primary]
        self.state.last_poll=utcnow_iso()
        # Empty DB + cached ETags can otherwise produce an empty screen after an
        # upgrade. Force a body fetch until at least one scoped message exists.
        with self.state.connect() as con:
            db_empty=con.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        total_inserted=0
        primary_any_ok=False
        primary_errors=[]
        for url in core_urls:
            _,_,inserted=self.fetch_url(url, force_full=db_empty, role="primary")
            total_inserted+=inserted
            d=self.state.feed_diag.get(url,{})
            if d.get("status")=="online": primary_any_ok=True
            elif d.get("error"): primary_errors.append(f"{url}: {d['error']}")

        # Nearby feeds are auxiliary. Their availability must never make the
        # core monitor healthy/unhealthy and must never suppress true failover.
        for url in nearby_urls:
            _,_,inserted=self.fetch_url(url, force_full=db_empty, role="nearby")
            total_inserted+=inserted

        fallback_used = False
        fallback_errors=[]
        if not primary_any_ok and fallback_urls:
            for url in fallback_urls:
                _,_,inserted=self.fetch_url(url, force_full=True, role="fallback")
                total_inserted+=inserted
                d=self.state.feed_diag.get(url,{})
                if d.get("status")=="online":
                    primary_any_ok=True; fallback_used=True
                elif d.get("error"):
                    fallback_errors.append(f"fallback {url}: {d['error']}")
            if fallback_used:
                self.state.fallback_activations += 1
                self.state.last_fallback_action = utcnow_iso()

        if primary_any_ok:
            self.state.last_success=utcnow_iso()
            if fallback_used:
                self.state.last_error="Primaire feed onbereikbaar; fallback actief"
                self.state.feed_status="fallback"
            else:
                self.state.last_error="; ".join(primary_errors) if primary_errors else None
                self.state.feed_status="online" if not primary_errors else "degraded"
            self.state.consecutive_failures = 0
        else:
            self.state.consecutive_failures += 1
            self.state.last_error="; ".join(primary_errors+fallback_errors) or "Geen primaire feed kon worden opgehaald"
            self.state.feed_status="error"
        self.state.broadcast({"type":"status","status":self.state.feed_status,"error":self.state.last_error})
        if total_inserted:
            self.state.broadcast({"type":"batch","count":total_inserted,"at":utcnow_iso()})
        return total_inserted

    def run(self):
        interval=max(15,int(self.state.config.get("poll_interval_seconds",20)))
        while not self.state.stop_event.is_set():
            try:
                self.fetch_once()
            except Exception as e:
                self.state.consecutive_failures += 1
                self.state.feed_status = "error"
                self.state.last_error = f"Poller: {type(e).__name__}: {e}"
                self.state.broadcast({"type":"status","status":"error","error":self.state.last_error})
            # A manual/watchdog refresh can wake this wait immediately.
            self.state.manual_refresh_event.wait(interval)
            self.state.manual_refresh_event.clear()


class FeedWatchdog(threading.Thread):
    daemon = True

    def __init__(self, state: AppState):
        super().__init__(name="p2000-feed-watchdog")
        self.state = state

    @staticmethod
    def _age_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        except Exception:
            return None

    def run(self):
        last_recovery_monotonic = 0.0
        while not self.state.stop_event.wait(30):
            stale_after = max(180, int(self.state.config.get("watchdog_stale_seconds", 600)))
            age = self._age_seconds(self.state.last_success)
            startup_age = self._age_seconds(self.state.started_at) or 0
            stale = (age is not None and age > stale_after) or (age is None and startup_age > stale_after)
            if not stale:
                continue
            self.state.feed_status = "stale"
            self.state.last_error = f"Watchdog: al >{stale_after}s geen succesvolle feed-update; herstel wordt geprobeerd"
            now_mono = time.monotonic()
            # Do at most one forced full reconnect per half stale window.
            if now_mono - last_recovery_monotonic >= max(90, stale_after / 2):
                self.state.clear_feed_cache()
                self.state.watchdog_recoveries += 1
                self.state.last_watchdog_action = utcnow_iso()
                self.state.manual_refresh_event.set()
                last_recovery_monotonic = now_mono
            self.state.broadcast({"type":"status","status":"stale","error":self.state.last_error})


def bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        number = int(default)
    return max(int(minimum), min(int(maximum), number))


def bounded_float(value, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        number = float(default)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(default)
    return max(float(minimum), min(float(maximum), number))


def row_to_message(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["units"] = json.loads(d.pop("units_json"))
    d["categories"] = json.loads(d.pop("categories_json"))
    notes_raw = d.pop("parser_notes_json", "[]")
    try:
        d["parser_notes"] = json.loads(notes_raw or "[]")
    except Exception:
        d["parser_notes"] = []
    d["parser_confidence"] = int(d.get("parser_confidence") or 0)
    return d


def query_messages(state: AppState, qs: dict[str, list[str]]) -> list[dict]:
    limit = bounded_int(qs.get("limit", ["100"])[0], 100, 1, 500)
    where, args = [], []
    for key in ("service", "city", "priority"):
        value = normalize_space(qs.get(key, [""])[0])
        if value:
            where.append(f"LOWER({key}) = LOWER(?)")
            args.append(value)
    q = normalize_space(qs.get("q", [""])[0])
    if q:
        where.append("(title LIKE ? OR summary LIKE ? OR location LIKE ? OR city LIKE ?)")
        token = f"%{q}%"
        args.extend([token] * 4)
    since = normalize_space(qs.get("since", [""])[0])
    if since:
        where.append("published >= ?")
        args.append(parse_dt(since))
    sql = "SELECT * FROM messages"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY published DESC, ingested_at DESC, rowid DESC LIMIT ?"
    args.append(limit)
    with state.connect() as con:
        return [row_to_message(r) for r in con.execute(sql, args).fetchall()]


def _incident_type_rank(label: str) -> int:
    if label.startswith("Stormschade"):
        return 72
    if label.startswith("Assistentie ambulance"):
        return 45
    return {
        "Schietincident": 100, "Steekincident": 100, "Reanimatie": 95,
        "Industriebrand": 90, "Dakbrand": 89, "Gebouwbrand": 88, "Natuurbrand": 86,
        "Voertuigbrand": 82, "Waterongeval": 80, "Stormschade": 72,
        "Ongeval met letsel": 70, "Ongeval": 60, "Brand": 58,
        "Assistentie politie": 45, "Assistentie ambulance": 45, "MMT-inzet": 42,
        "P2000-melding": 0,
    }.get(label, 50)


def incident_classification(chunk: list[dict]) -> str:
    candidates = []
    for idx, m in enumerate(chunk):
        label = incident_type_label(m.get("title", ""), m.get("summary", ""))
        candidates.append((_incident_type_rank(label), -idx, label))
    return max(candidates)[2] if candidates else "P2000-melding"


def _priority_score(value: str) -> int:
    token = normalize_space(value).upper().replace(" ", "")
    return {"P1": 5, "A0": 5, "A1": 4, "P2": 3, "B1": 3, "A2": 2, "P3": 1, "B2": 1}.get(token, 0)


def _incident_unit_token(value) -> str:
    """Return a stable human-readable unit token for incident aggregation.

    Current DB rows store unit strings, but accepting small mapping objects here
    keeps the incident model compatible with richer parser output later.
    """
    if isinstance(value, dict):
        code = normalize_space(value.get("code", ""))
        label = normalize_space(value.get("label", ""))
        if code and label and code.casefold() not in label.casefold():
            return f"{code} - {label}"
        return label or code
    return normalize_space(value)


def _incident_timeline(chunk: list[dict]) -> tuple[list[dict], dict]:
    timeline: list[dict] = []
    known_services: set[str] = set()
    known_units: set[str] = set()
    highest_scale = -1
    highest_priority = -1
    latest_delta: dict = {"kind": "start", "label": "Incident gestart", "parts": []}
    for idx, m in enumerate(chunk):
        parts: list[str] = []
        service = normalize_space(m.get("service", ""))
        units = [token for x in (m.get("units") or []) if (token := _incident_unit_token(x))]
        new_services = [service] if service and service not in known_services else []
        new_units = [u for u in units if u not in known_units]
        scale_score = int(m.get("scale_score") or 0)
        pscore = _priority_score(m.get("priority", ""))
        kind = "update"
        if idx == 0:
            kind = "start"
            parts.append("eerste melding")
        else:
            if scale_score > highest_scale and normalize_space(m.get("scale", "")):
                kind = "scale"
                parts.append(f"opgeschaald naar {m['scale']}")
            if new_services:
                if kind == "update": kind = "discipline"
                parts.append("discipline erbij: " + ", ".join(new_services))
            if new_units:
                if kind == "update": kind = "units"
                parts.append(("extra voertuig: " if len(new_units) == 1 else "extra voertuigen: ") + ", ".join(new_units))
            if pscore > highest_priority and m.get("priority"):
                if kind == "update": kind = "priority"
                parts.append(f"prioriteit {m['priority']}")
            if not parts:
                parts.append("vervolgmelding")
        known_services.update(new_services)
        known_units.update(new_units)
        highest_scale = max(highest_scale, scale_score)
        highest_priority = max(highest_priority, pscore)
        label = "; ".join(parts)
        event = {
            "time": m.get("published"),
            "kind": kind,
            "label": label,
            "message_id": m.get("id"),
            "service": service,
            "priority": m.get("priority", ""),
            "scale": m.get("scale", ""),
            "new_services": new_services,
            "new_units": new_units,
            "parser_confidence": int(m.get("parser_confidence") or 0),
        }
        timeline.append(event)
        latest_delta = {"kind": kind, "label": label, "parts": parts, "new_services": new_services, "new_units": new_units, "scale": m.get("scale", "")}
    return timeline, latest_delta


def build_incidents(messages: list[dict], limit: int = 20) -> list[dict]:
    """Build incident-centric views from individual P2000 rows.

    Rows sharing a normalized incident key are grouped, but a >30 minute gap always
    starts a new incident so frequently used locations never become one eternal job.
    """
    groups: dict[str, list[dict]] = {}
    for m in messages:
        groups.setdefault(m["incident_key"], []).append(m)
    incidents = []
    now = datetime.now(timezone.utc)
    for key, rows in groups.items():
        rows.sort(key=lambda m: m["published"])
        chunks: list[list[dict]] = [[]]
        prev = None
        for m in rows:
            dt = datetime.fromisoformat(m["published"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if prev and (dt - prev).total_seconds() > 1800:
                chunks.append([])
            chunks[-1].append(m)
            prev = dt
        for chunk in chunks:
            if not chunk:
                continue
            services = list(dict.fromkeys(m["service"] for m in chunk if m.get("service")))
            units = list(dict.fromkeys(token for m in chunk for u in (m.get("units") or []) if (token := _incident_unit_token(u))))
            highest = max(chunk, key=lambda m: (int(m.get("scale_score") or 0), _priority_score(m.get("priority", ""))))
            latest = chunk[-1]
            first = chunk[0]
            timeline, latest_delta = _incident_timeline(chunk)
            last_dt = datetime.fromisoformat(latest["published"].replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age_seconds = max(0, int((now - last_dt.astimezone(timezone.utc)).total_seconds()))
            confidences = [int(m.get("parser_confidence") or 0) for m in chunk]
            incidents.append({
                "id": f"{key}-{first['published'][:16]}",
                "incident_key": key,
                "first_seen": first["published"],
                "last_seen": latest["published"],
                "age_seconds": age_seconds,
                "active": age_seconds <= 1800,
                "classification": incident_classification(chunk),
                "title": latest["title"],
                "city": latest["city"],
                "location": latest["location"],
                "priority": latest["priority"],
                "services": services,
                "units": units,
                "message_count": len(chunk),
                "scale": highest.get("scale", ""),
                "scale_score": highest.get("scale_score", 0),
                "parser_confidence": int(latest.get("parser_confidence") or 0),
                "parser_confidence_avg": round(sum(confidences) / len(confidences)) if confidences else 0,
                "timeline": timeline,
                "latest_delta": latest_delta,
                "messages": list(reversed(chunk))[:20],
                "source_url": latest["url"],
            })
    incidents.sort(key=lambda i: (bool(i["active"]), i["last_seen"], i["scale_score"]), reverse=True)
    return incidents[:limit]


_TTS_RENDER_LOCK = threading.Lock()
_TTS_RENDER_LAST_ENGINE = ""
_TTS_RENDER_LAST_ERROR = ""
_TTS_RENDER_LAST_AT = ""
_TTS_RENDER_LAST_VOICE = ""


def _powershell_executable() -> str | None:
    if os.name != "nt":
        return None
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _dispatch_tones(service: str = "brandweer", urgent: bool = False) -> list[tuple[int, int]]:
    service = (service or "brandweer").lower()
    if urgent:
        return [(950, 120), (1150, 120), (1350, 170)]
    if service == "ambulance":
        return [(880, 120), (1050, 150)]
    if service in {"politie", "lifeliner"}:
        return [(1000, 110), (1250, 150)]
    return [(820, 120), (1030, 150)]


def _prepend_attention_to_wav(speech_wav: bytes, service: str = "brandweer", urgent: bool = False) -> bytes:
    """Prepend a short PCM attention cue to a SAPI WAV.

    System.Speech normally emits uncompressed PCM. If Windows ever returns an
    unexpected WAV format, keep the speech intact rather than failing TTS.
    """
    try:
        src_io = BytesIO(speech_wav)
        with wave.open(src_io, "rb") as src:
            channels = src.getnchannels()
            sampwidth = src.getsampwidth()
            framerate = src.getframerate()
            comptype = src.getcomptype()
            frames = src.readframes(src.getnframes())
        if channels not in (1, 2) or sampwidth != 2 or comptype != "NONE" or framerate < 8000:
            return speech_wav

        pcm = bytearray()
        amp = 8200

        def append_silence(ms: int) -> None:
            n = max(0, int(framerate * ms / 1000))
            pcm.extend(b"\x00\x00" * channels * n)

        def append_tone(freq: int, ms: int) -> None:
            n = max(1, int(framerate * ms / 1000))
            fade = max(1, int(framerate * 0.008))
            for i in range(n):
                env = min(1.0, i / fade, (n - 1 - i) / fade)
                sample = int(amp * max(0.0, env) * math.sin(2.0 * math.pi * freq * i / framerate))
                packed = struct.pack("<h", sample)
                pcm.extend(packed * channels)

        append_silence(65)
        for freq, duration in _dispatch_tones(service, urgent):
            append_tone(freq, duration)
            append_silence(45)
        append_silence(110)
        pcm.extend(frames)

        out = BytesIO()
        with wave.open(out, "wb") as dst:
            dst.setnchannels(channels)
            dst.setsampwidth(sampwidth)
            dst.setframerate(framerate)
            dst.setcomptype("NONE", "not compressed")
            dst.writeframes(bytes(pcm))
        return out.getvalue()
    except Exception:
        return speech_wav


def generate_local_sapi_wav(text: str, rate: float = 0.96, service: str = "brandweer", urgent: bool = False, attention: bool = True) -> bytes:
    """Render Dutch speech to a real WAV file with Windows SAPI/System.Speech.

    The browser only receives ordinary same-origin audio. This deliberately
    avoids browser SpeechSynthesis, cloud voice timing and Edge-specific APIs;
    Chrome and Edge play the exact same WAV through the same <audio> element.
    """
    global _TTS_RENDER_LAST_ENGINE, _TTS_RENDER_LAST_ERROR, _TTS_RENDER_LAST_AT, _TTS_RENDER_LAST_VOICE
    text = normalize_space(str(text or ""))[:1200]
    if not text:
        raise ValueError("empty tts text")
    ps = _powershell_executable()
    if not ps:
        raise RuntimeError("Windows PowerShell/System.Speech niet beschikbaar")

    rate = max(0.65, min(1.25, float(rate or 0.96)))
    sapi_rate = max(-5, min(4, int(round((rate - 1.0) * 11))))
    cue_key = f"{(service or 'brandweer').lower()}:{1 if urgent else 0}:{1 if attention else 0}"
    key = hashlib.sha256((f"sapi-wav-v3-nl-only|{sapi_rate}|{cue_key}|" + text).encode("utf-8")).hexdigest()
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = TTS_CACHE_DIR / f"{key}.wav"
    if cache_file.exists() and cache_file.stat().st_size > 1000:
        _TTS_RENDER_LAST_ENGINE = "windows-sapi-wav-cache"
        _TTS_RENDER_LAST_VOICE = _TTS_RENDER_LAST_VOICE or "nl-NL (gecachete lokale stem)"
        _TTS_RENDER_LAST_ERROR = ""
        _TTS_RENDER_LAST_AT = utcnow_iso()
        return cache_file.read_bytes()

    with _TTS_RENDER_LOCK:
        if cache_file.exists() and cache_file.stat().st_size > 1000:
            _TTS_RENDER_LAST_ENGINE = "windows-sapi-wav-cache"
            _TTS_RENDER_LAST_VOICE = _TTS_RENDER_LAST_VOICE or "nl-NL (gecachete lokale stem)"
            _TTS_RENDER_LAST_ERROR = ""
            _TTS_RENDER_LAST_AT = utcnow_iso()
            return cache_file.read_bytes()
        speech_tmp = TTS_CACHE_DIR / f".{key}-{time.time_ns()}-speech.wav"
        script = r"""
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$text=$env:P2000_TTS_TEXT
$out=$env:P2000_TTS_OUT
$rate=[int]$env:P2000_TTS_RATE
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  # NOOIT de standaard (vaak Engelse) Windows-stem gebruiken voor Nederlandse P2000-tekst.
  # Eerst exact nl-NL, daarna een andere nl-* stem. Als Windows geen Nederlandse
  # stem heeft, stoppen we bewust zodat Python kan terugvallen op Nederlandse gTTS.
  $voices=@($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'nl-*' })
  if($voices.Count -eq 0){ throw 'Geen Nederlandse Windows TTS-stem (nl-NL) geinstalleerd.' }
  $preferredNames='Fenna|Colette|Frank|Maarten|Xander|Claire|Ellen'
  $voice=@($voices | Sort-Object `
    @{Expression={ if($_.VoiceInfo.Culture.Name -eq 'nl-NL'){0}else{1} }}, `
    @{Expression={ if($_.VoiceInfo.Name -match $preferredNames){0}else{1} }}, `
    @{Expression={$_.VoiceInfo.Name}})[0].VoiceInfo
  $s.SelectVoice($voice.Name)
  if($s.Voice.Culture.Name -notlike 'nl-*'){
    throw ('Geselecteerde Windows-stem is niet Nederlands: ' + $s.Voice.Name + ' (' + $s.Voice.Culture.Name + ')')
  }
  [Console]::Out.WriteLine(('P2000_DUTCH_VOICE=' + $s.Voice.Name + '|' + $s.Voice.Culture.Name))
  $s.Rate=$rate
  $s.Volume=100
  $s.SetOutputToWaveFile($out)
  $s.Speak($text)
} finally {
  try { $s.SetOutputToNull() } catch {}
  $s.Dispose()
}
""".strip()
        env = os.environ.copy()
        env["P2000_TTS_TEXT"] = text
        env["P2000_TTS_OUT"] = str(speech_tmp)
        env["P2000_TTS_RATE"] = str(sapi_rate)
        try:
            result = subprocess.run(
                [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=12,
                creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0),
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", "replace").strip()[-500:]
                raise RuntimeError(err or f"PowerShell TTS exit {result.returncode}")
            if not speech_tmp.exists() or speech_tmp.stat().st_size < 1000:
                raise RuntimeError("Windows TTS maakte geen bruikbaar WAV-bestand")
            stdout = result.stdout.decode("utf-8", "replace")
            for line in stdout.splitlines():
                if line.startswith("P2000_DUTCH_VOICE="):
                    _TTS_RENDER_LAST_VOICE = line.split("=", 1)[1].replace("|", " • ")[:180]
                    break
            if not _TTS_RENDER_LAST_VOICE:
                _TTS_RENDER_LAST_VOICE = "Nederlandse Windows-stem (nl-*)"
            speech = speech_tmp.read_bytes()
            data = _prepend_attention_to_wav(speech, service=service, urgent=urgent) if attention else speech
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(cache_file)
            files = sorted(TTS_CACHE_DIR.glob("*.wav"), key=lambda f: f.stat().st_mtime, reverse=True)
            for old in files[160:]:
                try:
                    old.unlink()
                except OSError:
                    pass
            _TTS_RENDER_LAST_ENGINE = "windows-sapi-wav"
            _TTS_RENDER_LAST_ERROR = ""
            _TTS_RENDER_LAST_AT = utcnow_iso()
            return data
        except Exception as exc:
            _TTS_RENDER_LAST_ERROR = str(exc)[:500]
            raise RuntimeError(f"lokale Windows TTS mislukt: {exc}") from exc
        finally:
            try:
                speech_tmp.unlink(missing_ok=True)
            except Exception:
                pass


def generate_dispatch_audio(text: str, rate: float = 0.96, service: str = "brandweer", urgent: bool = False, attention: bool = True) -> tuple[bytes, str, str]:
    """Render one complete dispatch audio asset.

    Windows SAPI WAV is primary and fully local. gTTS MP3 remains a network
    fallback so the display can still speak if the Dutch Windows voice stack is
    unavailable. Playback always happens in the lightkrant browser tab.
    """
    global _TTS_RENDER_LAST_ENGINE, _TTS_RENDER_LAST_ERROR, _TTS_RENDER_LAST_AT, _TTS_RENDER_LAST_VOICE
    local_error = None
    try:
        data = generate_local_sapi_wav(text, rate=rate, service=service, urgent=urgent, attention=attention)
        return data, "audio/wav", _TTS_RENDER_LAST_ENGINE or "windows-sapi-wav"
    except Exception as exc:
        local_error = exc
    try:
        data = generate_online_tts(text)
        _TTS_RENDER_LAST_ENGINE = "gtts-mp3-fallback"
        _TTS_RENDER_LAST_VOICE = "Google TTS • Nederlands (nl)"
        _TTS_RENDER_LAST_ERROR = str(local_error or "")[:500]
        _TTS_RENDER_LAST_AT = utcnow_iso()
        return data, "audio/mpeg", "gtts-mp3-fallback"
    except Exception as exc:
        _TTS_RENDER_LAST_ERROR = f"local={local_error}; online={exc}"[:500]
        _TTS_RENDER_LAST_AT = utcnow_iso()
        raise RuntimeError(f"geen TTS-audio beschikbaar: lokaal: {local_error}; online: {exc}") from exc


def generate_online_tts(text: str) -> bytes:
    """Generate/cached Dutch MP3 speech using one fixed Dutch gTTS voice route.

    v2.6.2 pins the natural Dutch voice to the stable translate.google.com route.
    It never falls back to a different system voice automatically, so consecutive
    announcements keep the same speaker. Retries only repeat this exact route.
    """
    text = normalize_space(str(text or ""))[:1200]
    if not text:
        raise ValueError("empty tts text")
    # New namespace prevents older .com-fallback audio from being reused.
    cache_key = hashlib.sha256(("gtts-nl-fixed-com-v3|" + text).encode("utf-8")).hexdigest()
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = TTS_CACHE_DIR / f"{cache_key}.mp3"
    if cache_file.exists() and cache_file.stat().st_size > 100:
        return cache_file.read_bytes()
    try:
        from gtts import gTTS
    except Exception as e:
        raise RuntimeError(f"gTTS niet beschikbaar: {e}") from e

    last_error = None
    # Try the fixed Dutch Google route briefly. The lightkrant browser has its own Dutch fallback, so a slow cloud voice must never block the dispatch queue.
    for attempt in range(1):
        try:
            fp = BytesIO()
            gTTS(text=text, lang="nl", tld="com", slow=False, timeout=(3, 5)).write_to_fp(fp)
            data = fp.getvalue()
            if len(data) < 100:
                raise RuntimeError("lege TTS-respons")
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(cache_file)
            files = sorted(TTS_CACHE_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime, reverse=True)
            for old in files[100:]:
                try: old.unlink()
                except OSError: pass
            return data
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"vaste Nederlandse TTS tijdelijk niet beschikbaar: {last_error}")


_TTS_PLAYER_LOCK = threading.Lock()
_TTS_PLAYER_PROCESS = None
_TTS_LAST_ERROR = ""
_TTS_LAST_PLAYER = ""
_TTS_LAST_PLAYED = ""


def detect_local_audio_player(volume: int = 100) -> tuple[str, list[str]] | tuple[None, None]:
    """Return the built-in Windows MediaPlayer command used for MP3 TTS."""
    if os.name != "nt":
        return None, None
    volume = max(0, min(100, int(volume or 100)))
    gain = volume / 100.0
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps:
        return None, None
    script = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p=New-Object System.Windows.Media.MediaPlayer; "
        "$p.Open([Uri]$args[0]); $p.Volume=" + f"{gain:.3f}" + "; $p.Play(); "
        "for($i=0;$i -lt 80 -and -not $p.NaturalDuration.HasTimeSpan;$i++){Start-Sleep -Milliseconds 50}; "
        "if($p.NaturalDuration.HasTimeSpan){Start-Sleep -Milliseconds ([int]$p.NaturalDuration.TimeSpan.TotalMilliseconds+250)}else{Start-Sleep -Seconds 8}; "
        "$p.Close()"
    )
    return "windows-media", [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]


_TTS_DEVICE_VOLUME_LOCK = threading.Lock()
_TTS_DEVICE_VOLUME_SNAPSHOT = None
_TTS_DEVICE_VOLUME_TOKEN = 0
_TTS_LAST_DEVICE_CONTROLLER = ""
_TTS_LAST_DEVICE_VOLUME = None

def detect_device_volume_controller() -> str:
    return ""

def read_device_volume(controller: str = "") -> dict | None:
    return None

def set_device_volume_percent(percent: int, controller: str = "") -> bool:
    return False

def begin_temporary_device_volume(max_percent: int | None) -> tuple[int, dict | None]:
    # Windows build changes only the MediaPlayer volume; it never rewrites the
    # user's global Windows mixer level.
    return 0, None

def restore_temporary_device_volume(token: int | None = None, force: bool = False) -> bool:
    return True

def _restore_device_volume_when_player_finishes(process, token: int) -> None:
    return

def tts_cache_path(text: str) -> Path:
    text = normalize_space(str(text or ""))[:1200]
    key = hashlib.sha256(("gtts-nl-fixed-com-v3|" + text).encode("utf-8")).hexdigest()
    return TTS_CACHE_DIR / f"{key}.mp3"


ATTENTION_TONES = {
    "brandweer": [880, 740],
    "politie": [660, 880],
    "ambulance": [784, 988],
    "lifeliner": [988, 1319],
    "knrm": [620, 784],
    "urgent": [1319, 1175, 1319],
    "default": [784, 880],
}


def play_attention_cue(service: str = "brandweer", urgent: bool = False, volume: int = 100) -> bool:
    """Play a short Windows attention tone before the spoken dispatch."""
    if os.name != "nt":
        return False
    try:
        import winsound
        service = (service or "brandweer").lower()
        if urgent:
            tones = [(950, 120), (1150, 120), (1350, 170)]
        elif service == "ambulance":
            tones = [(880, 120), (1050, 150)]
        elif service in {"politie", "lifeliner"}:
            tones = [(1000, 110), (1250, 150)]
        else:
            tones = [(820, 120), (1030, 150)]
        for freq, dur in tones:
            winsound.Beep(freq, dur)
            time.sleep(.045)
        return True
    except Exception:
        return False

def play_online_tts_on_host(text: str, volume: int = 100, cue_service: str = "", cue_urgent: bool = False, device_volume: int | None = None) -> dict:
    """Generate the fixed Dutch voice and play it on the kiosk machine itself."""
    global _TTS_PLAYER_PROCESS, _TTS_LAST_ERROR, _TTS_LAST_PLAYER, _TTS_LAST_PLAYED
    data = generate_online_tts(text)
    # Stop any pre-empted announcement and restore its pristine device level
    # before taking a new snapshot. This prevents chained calls from ratcheting
    # the physical sink quieter and quieter.
    with _TTS_PLAYER_LOCK:
        if _TTS_PLAYER_PROCESS is not None and _TTS_PLAYER_PROCESS.poll() is None:
            try:
                _TTS_PLAYER_PROCESS.terminate()
                _TTS_PLAYER_PROCESS.wait(timeout=.6)
            except Exception:
                try: _TTS_PLAYER_PROCESS.kill()
                except Exception: pass
        restore_temporary_device_volume(force=True)
    device_token, _ = begin_temporary_device_volume(device_volume)
    cue_played = False
    if cue_service or cue_urgent:
        try:
            cue_played = play_attention_cue(cue_service or "default", bool(cue_urgent), volume)
        except Exception:
            cue_played = False
    cache_file = tts_cache_path(text)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not cache_file.exists() or cache_file.stat().st_size < 100:
        cache_file.write_bytes(data)
    player, argv = detect_local_audio_player(volume)
    if not player or not argv:
        restore_temporary_device_volume(device_token)
        _TTS_LAST_ERROR = "Geen lokale MP3-speler gevonden (Windows Media/PowerShell of een compatibele speler)."
        raise RuntimeError(_TTS_LAST_ERROR)
    with _TTS_PLAYER_LOCK:
        try:
            _TTS_PLAYER_PROCESS = subprocess.Popen(
                [*argv, str(cache_file)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            restore_temporary_device_volume(device_token)
            _TTS_LAST_ERROR = f"Lokale audioplayer start niet: {exc}"
            raise RuntimeError(_TTS_LAST_ERROR) from exc
        process = _TTS_PLAYER_PROCESS
        threading.Thread(target=_restore_device_volume_when_player_finishes, args=(process, device_token), daemon=True, name="tts-volume-restore").start()
        _TTS_LAST_PLAYER = player
        _TTS_LAST_ERROR = ""
        _TTS_LAST_PLAYED = utcnow_iso()
    return {"ok": True, "player": player, "played_at": _TTS_LAST_PLAYED, "bytes": len(data), "volume": max(0, min(100, int(volume or 100))), "device_volume": device_volume, "device_volume_controller": _TTS_LAST_DEVICE_CONTROLLER, "cue_played": cue_played, "cue_service": cue_service or "", "cue_urgent": bool(cue_urgent)}


def stop_host_tts() -> bool:
    global _TTS_PLAYER_PROCESS
    with _TTS_PLAYER_LOCK:
        if _TTS_PLAYER_PROCESS is not None and _TTS_PLAYER_PROCESS.poll() is None:
            try:
                _TTS_PLAYER_PROCESS.terminate()
                _TTS_PLAYER_PROCESS.wait(timeout=.6)
            except Exception:
                try: _TTS_PLAYER_PROCESS.kill()
                except Exception: pass
            restore_temporary_device_volume(force=True)
            return True
    restore_temporary_device_volume(force=True)
    return False


def tts_runtime_status() -> dict:
    try:
        from gtts import gTTS as _unused_gtts
        online_generator = True
    except Exception:
        online_generator = False
    local_wav = bool(_powershell_executable())
    return {
        "engine": "local-wav-lightkrant-tab",
        "generator_available": bool(local_wav or online_generator),
        "local_wav_available": local_wav,
        "online_fallback_available": online_generator,
        "local_player": "",
        "server_playback_ready": False,
        "playback_target": "lightkrant-tab",
        "render_last_engine": _TTS_RENDER_LAST_ENGINE,
        "render_last_error": _TTS_RENDER_LAST_ERROR,
        "render_last_at": _TTS_RENDER_LAST_AT,
        "render_last_voice": _TTS_RENDER_LAST_VOICE,
        "language": "nl-NL",
        "english_voice_fallback": False,
        "last_player": _TTS_LAST_PLAYER,
        "last_played": _TTS_LAST_PLAYED,
        "last_error": _TTS_LAST_ERROR,
        "playing": bool(_TTS_PLAYER_PROCESS is not None and _TTS_PLAYER_PROCESS.poll() is None),
        "device_volume_controller": detect_device_volume_controller(),
        "device_volume_active": bool(_TTS_DEVICE_VOLUME_SNAPSHOT is not None),
        "device_volume_last": _TTS_LAST_DEVICE_VOLUME,
    }


MAX_UPDATE_BYTES = 64 * 1024 * 1024
MAX_UPDATE_UNPACKED_BYTES = 220 * 1024 * 1024
MAX_UPDATE_FILES = 3500
_UPDATE_STATE_LOCK = threading.Lock()
_UPDATE_STATUS_LOCK = threading.Lock()
_GITHUB_SETTINGS_STATUS_LOCK = threading.Lock()
_UPDATE_ACTIVE = False


def _claim_update_slot() -> bool:
    global _UPDATE_ACTIVE
    with _UPDATE_STATE_LOCK:
        if _UPDATE_ACTIVE:
            return False
        _UPDATE_ACTIVE = True
        return True


def _release_update_slot():
    global _UPDATE_ACTIVE
    with _UPDATE_STATE_LOCK:
        _UPDATE_ACTIVE = False


def _write_update_status(**fields) -> dict:
    with _UPDATE_STATUS_LOCK:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        current = {}
        if UPDATE_STATUS_PATH.exists():
            try:
                current = json.loads(UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
            except Exception:
                current = {}
        current.update(fields)
        current["current_version"] = APP_VERSION
        current["updated_at"] = utcnow_iso()
        tmp = UPDATE_STATUS_PATH.with_name(f"{UPDATE_STATUS_PATH.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(UPDATE_STATUS_PATH)
        return current


def update_runtime_status() -> dict:
    status = {"state": "idle", "current_version": APP_VERSION, "remote_upload": True, "github_supported": True}
    if UPDATE_STATUS_PATH.exists():
        try:
            status.update(json.loads(UPDATE_STATUS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    status["current_version"] = APP_VERSION
    status["remote_upload"] = True
    return status


def normalize_github_repo(value: str) -> str:
    raw = normalize_space(str(value or "")).strip().rstrip("/")
    if not raw:
        return ""
    raw = re.sub(r"\.git$", "", raw, flags=re.I)
    if raw.lower().startswith(("https://", "http://")):
        try:
            parsed = urlparse(raw)
        except Exception:
            return ""
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            return ""
        raw = parsed.path.strip("/")
    parts = [x for x in raw.split("/") if x]
    if len(parts) != 2:
        return ""
    owner, repo = parts
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo):
        return ""
    return f"{owner}/{repo}"


def github_update_config(config: dict) -> dict:
    repo = normalize_github_repo(config.get("github_repo", "") or DEFAULT_GITHUB_REPO)
    return {
        "github_repo": repo,
        "github_auto_check": bool(config.get("github_auto_check", False)) and bool(repo),
        "github_auto_install": bool(config.get("github_auto_install", False)) and bool(repo),
        # v4.2.4 deliberately migrates the old hourly setting to a five-minute
        # default. Keeping the legacy six-hour value would make existing
        # installations miss the faster update checks after upgrading.
        "github_check_minutes": bounded_int(config.get("github_check_minutes", 5), 5, 5, 1440),
        "github_branch_updates": bool(config.get("github_branch_updates", True)) and bool(repo),
        "github_branch": normalize_github_branch(config.get("github_branch", DEFAULT_GITHUB_BRANCH)),
    }


def sanitize_github_update_payload(payload: dict, current: dict | None = None) -> dict:
    current = current or {}
    repo_raw = payload.get("github_repo", current.get("github_repo", DEFAULT_GITHUB_REPO))
    repo = normalize_github_repo(repo_raw)
    if normalize_space(str(repo_raw or "")) and not repo:
        raise ValueError("Gebruik owner/repository of https://github.com/owner/repository")
    auto_check = bool(payload.get("github_auto_check", current.get("github_auto_check", False))) and bool(repo)
    auto_install = bool(payload.get("github_auto_install", current.get("github_auto_install", False))) and bool(repo)
    if auto_install:
        auto_check = True
    return {
        "github_repo": repo,
        "github_auto_check": auto_check,
        "github_auto_install": auto_install,
        "github_check_minutes": bounded_int(payload.get("github_check_minutes", current.get("github_check_minutes", 5)), 5, 5, 1440),
        "github_branch_updates": bool(payload.get("github_branch_updates", current.get("github_branch_updates", True))) and bool(repo),
        "github_branch": normalize_github_branch(payload.get("github_branch", current.get("github_branch", DEFAULT_GITHUB_BRANCH))),
    }


def normalize_github_branch(value: str) -> str:
    branch = normalize_space(str(value or DEFAULT_GITHUB_BRANCH)).strip().strip("/")
    if not branch or len(branch) > 120 or branch.startswith("-") or ".." in branch:
        return DEFAULT_GITHUB_BRANCH
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        return DEFAULT_GITHUB_BRANCH
    return branch


def normalize_github_settings_path(value: str) -> str:
    raw = normalize_space(str(value or DEFAULT_GITHUB_SETTINGS_PATH)).replace("\\", "/").strip("/")
    parts = [part for part in raw.split("/") if part]
    if not parts or ".." in parts or len(raw) > 240:
        return DEFAULT_GITHUB_SETTINGS_PATH
    if not all(re.fullmatch(r"[A-Za-z0-9._ -]+", part) for part in parts):
        return DEFAULT_GITHUB_SETTINGS_PATH
    if not raw.lower().endswith(".json"):
        return DEFAULT_GITHUB_SETTINGS_PATH
    return "/".join(parts)


def github_settings_sync_config(config: dict) -> dict:
    repo = normalize_github_repo(config.get("github_repo", "") or DEFAULT_GITHUB_REPO)
    return {
        "github_repo": repo,
        "github_settings_auto_sync": bool(config.get("github_settings_auto_sync", False)) and bool(repo),
        "github_settings_path": normalize_github_settings_path(config.get("github_settings_path", DEFAULT_GITHUB_SETTINGS_PATH)),
        "github_settings_branch": normalize_github_branch(config.get("github_settings_branch", config.get("github_branch", DEFAULT_GITHUB_BRANCH))),
        "github_settings_minutes": bounded_int(config.get("github_settings_minutes", 5), 5, 1, 1440),
    }


def sanitize_github_settings_sync_payload(payload: dict, current: dict | None = None) -> dict:
    current = current or {}
    repo_raw = payload.get("github_repo", current.get("github_repo", DEFAULT_GITHUB_REPO))
    repo = normalize_github_repo(repo_raw)
    if normalize_space(str(repo_raw or "")) and not repo:
        raise ValueError("Gebruik owner/repository of https://github.com/owner/repository")
    return {
        "github_settings_auto_sync": bool(payload.get("github_settings_auto_sync", current.get("github_settings_auto_sync", False))) and bool(repo),
        "github_settings_path": normalize_github_settings_path(payload.get("github_settings_path", current.get("github_settings_path", DEFAULT_GITHUB_SETTINGS_PATH))),
        "github_settings_branch": normalize_github_branch(payload.get("github_settings_branch", current.get("github_settings_branch", current.get("github_branch", DEFAULT_GITHUB_BRANCH)))),
        "github_settings_minutes": bounded_int(payload.get("github_settings_minutes", current.get("github_settings_minutes", 5)), 5, 1, 1440),
    }


def _version_key(value: str) -> tuple[int, ...]:
    raw = normalize_space(str(value or "")).lower().lstrip("v")
    nums = [int(x) for x in re.findall(r"\d+", raw)[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


def _is_newer_version(remote: str, current: str = APP_VERSION) -> bool:
    return _version_key(remote) > _version_key(current)


def _github_request_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if int(getattr(resp, "status", 200)) != 200:
            raise RuntimeError(f"GitHub API HTTP {getattr(resp, 'status', '?')}")
        return json.loads(resp.read(2_000_000).decode("utf-8", "replace") or "{}")


def _select_github_release_asset(release: dict) -> dict:
    assets = [x for x in (release.get("assets") or []) if isinstance(x, dict)]
    zips = [x for x in assets if str(x.get("name") or "").lower().endswith(".zip")]
    if not zips:
        raise ValueError("De nieuwste GitHub Release bevat geen update-ZIP asset")
    def score(asset):
        name = str(asset.get("name") or "").lower()
        points = 0
        if "p2000" in name: points += 8
        if "monitor" in name: points += 5
        if "windows" in name or "multiplatform" in name: points += 8
        if APP_VERSION.lower() in name: points -= 1
        if "source" in name: points -= 10
        return points
    zips.sort(key=score, reverse=True)
    asset = zips[0]
    url = normalize_space(str(asset.get("browser_download_url") or ""))
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if host not in {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}:
        raise ValueError("GitHub Release asset heeft een onverwacht downloadadres")
    return asset


def _github_latest_release(repo: str) -> dict:
    data = _github_request_json(f"{GITHUB_API_BASE}/repos/{repo}/releases/latest")
    tag = normalize_space(str(data.get("tag_name") or data.get("name") or ""))[:80]
    if not tag:
        raise ValueError("GitHub Release heeft geen versienummer/tag")
    asset = _select_github_release_asset(data)
    return {
        "repo": repo,
        "version": tag.lstrip("vV"),
        "tag": tag,
        "name": normalize_space(str(data.get("name") or tag))[:160],
        "published_at": data.get("published_at"),
        "html_url": data.get("html_url"),
        "body": str(data.get("body") or "")[:4000],
        "asset": {
            "name": str(asset.get("name") or "")[:240],
            "url": str(asset.get("browser_download_url") or ""),
            "size": int(asset.get("size") or 0),
            "digest": normalize_space(str(asset.get("digest") or ""))[:200],
        },
    }


def _github_file(repo: str, path: str, branch: str) -> dict:
    safe_path = quote(path, safe="/")
    safe_branch = quote(branch, safe="")
    data = _github_request_json(f"{GITHUB_API_BASE}/repos/{repo}/contents/{safe_path}?ref={safe_branch}")
    if data.get("type") != "file" or not isinstance(data.get("content"), str):
        raise ValueError(f"GitHub-bestand {path} is niet leesbaar")
    try:
        body = base64.b64decode(data["content"], validate=False)
    except Exception as exc:
        raise ValueError(f"GitHub-bestand {path} bevat ongeldige inhoud") from exc
    if len(body) > 2_000_000:
        raise ValueError(f"GitHub-bestand {path} is te groot")
    return {"body": body, "sha": str(data.get("sha") or ""), "html_url": data.get("html_url")}


def _github_latest_branch(repo: str, branch: str) -> dict:
    version_file = _github_file(repo, "VERSION", branch)
    version = normalize_space(version_file["body"].decode("utf-8", "replace"))[:80].lstrip("vV")
    if not version or not re.search(r"\d", version):
        raise ValueError("VERSION op de GitHub-branch bevat geen geldig versienummer")
    safe_branch = quote(branch, safe="")
    return {
        "repo": repo, "version": version, "tag": branch,
        "name": f"GitHub branch {branch}", "published_at": None,
        "html_url": f"https://github.com/{repo}/tree/{quote(branch, safe='/')}",
        "body": "Automatische branch-update na een GitHub push.", "source_kind": "branch",
        "asset": {"name": f"{repo.split('/', 1)[1]}-{branch}.zip", "url": f"https://codeload.github.com/{repo}/zip/refs/heads/{safe_branch}", "size": 0, "digest": ""},
    }


def _github_latest_software(repo: str, branch: str, include_branch: bool) -> dict:
    candidates: list[dict] = []
    errors: list[str] = []
    try:
        release = _github_latest_release(repo)
        release["source_kind"] = "release"
        candidates.append(release)
    except urllib.error.HTTPError as exc:
        if int(getattr(exc, "code", 0) or 0) != 404:
            errors.append(f"Release: HTTP {getattr(exc, 'code', '?')}")
    except Exception as exc:
        errors.append(f"Release: {exc}")
    if include_branch:
        try:
            candidates.append(_github_latest_branch(repo, branch))
        except urllib.error.HTTPError as exc:
            errors.append(f"Branch {branch}: HTTP {getattr(exc, 'code', '?')}")
        except Exception as exc:
            errors.append(f"Branch {branch}: {exc}")
    if not candidates:
        raise ValueError("Geen bruikbare GitHub Release of branch-update gevonden" + (f" ({'; '.join(errors)})" if errors else ""))
    candidates.sort(key=lambda row: _version_key(row.get("version", "")), reverse=True)
    return candidates[0]


def _download_github_asset(release: dict) -> Path:
    asset = release.get("asset") or {}
    size = int(asset.get("size") or 0)
    if size and size > MAX_UPDATE_BYTES:
        raise ValueError("GitHub update is groter dan 64 MB")
    url = str(asset.get("url") or "")
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if host not in {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "codeload.github.com"}:
        raise ValueError("GitHub-update heeft een onverwacht downloadadres")
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    target = UPDATE_DIR / f"github-{int(time.time())}-{Path(str(asset.get('name') or 'update.zip')).name}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    h = hashlib.sha256(); total = 0
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, target.open("wb") as fp:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPDATE_BYTES:
                    raise ValueError("Gedownloade update is groter dan 64 MB")
                h.update(chunk); fp.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    digest = str(asset.get("digest") or "").lower().strip()
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].strip()
        if expected and h.hexdigest().lower() != expected.lower():
            target.unlink(missing_ok=True)
            raise ValueError("SHA-256 van GitHub Release asset klopt niet")
    return target


def _create_update_backup() -> Path:
    UPDATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = UPDATE_BACKUP_DIR / f"v{APP_VERSION}-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    skip_top = {"data", ".git", "__pycache__"}
    for src in ROOT.iterdir():
        if src.name in skip_top or src == CONFIG_PATH.parent:
            continue
        dst = backup / src.name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.is_file():
            shutil.copy2(src, dst)
    meta = {"version": APP_VERSION, "created_at": utcnow_iso(), "root": str(ROOT)}
    (backup / "backup.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    backups = sorted([x for x in UPDATE_BACKUP_DIR.iterdir() if x.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
    for old in backups[3:]:
        shutil.rmtree(old, ignore_errors=True)
    return backup


def _latest_update_backup() -> Path | None:
    if not UPDATE_BACKUP_DIR.exists():
        return None
    rows = sorted([x for x in UPDATE_BACKUP_DIR.iterdir() if x.is_dir() and (x / "backend" / "server.py").exists()], key=lambda x: x.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _restore_update_backup(backup: Path):
    if not backup or not (backup / "backend" / "server.py").is_file():
        raise ValueError("Geen bruikbare updatebackup gevonden")
    for src in backup.iterdir():
        if src.name == "backup.json":
            continue
        dst = ROOT / src.name
        if src.is_dir():
            if dst.exists() and dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def github_check_and_maybe_install(state: "AppState", install: bool = False) -> dict:
    cfg = github_update_config(state.config)
    repo = cfg.get("github_repo") or ""
    if not repo:
        raise ValueError("Stel eerst een openbaar GitHub repository in")
    _write_update_status(state="checking", source="github", github_repo=repo, message="GitHub Releases en branch controleren", error="")
    release = _github_latest_software(repo, cfg.get("github_branch") or DEFAULT_GITHUB_BRANCH, bool(cfg.get("github_branch_updates")))
    newer = _is_newer_version(release["version"], APP_VERSION)
    base = {
        "source": "github", "source_kind": release.get("source_kind", "release"), "github_repo": repo, "latest_version": release["version"],
        "latest_tag": release["tag"], "release_url": release.get("html_url"),
        "release_name": release.get("name"), "release_published_at": release.get("published_at"),
        "asset_name": release["asset"].get("name"), "asset_size": release["asset"].get("size"),
        "available": newer, "target_version": "", "backup": "", "installed_version": "",
    }
    if not newer:
        return _write_update_status(state="up-to-date", message="Je gebruikt de nieuwste versie", error="", **base)
    if not install:
        return _write_update_status(state="available", message=f"Versie {release['version']} is beschikbaar", error="", **base)
    if not _claim_update_slot():
        raise RuntimeError("Er wordt al een update geïnstalleerd")
    incoming = None
    try:
        _write_update_status(state="downloading", message=f"Versie {release['version']} downloaden", **base)
        incoming = _download_github_asset(release)
        _write_update_status(state="validating", message="GitHub update controleren", **base)
        package_root, package_version = _validate_and_extract_update(incoming)
        incoming.unlink(missing_ok=True); incoming = None
        if _version_key(package_version) != _version_key(release["version"]):
            raise ValueError(f"ZIP-versie {package_version} komt niet overeen met GitHub-versie {release['version']}")
        _write_update_status(state="staged", target_version=package_version, message="GitHub update klaar voor installatie", **base)
        threading.Thread(target=_apply_update_and_exec, args=(package_root, package_version), daemon=True, name="github-self-update").start()
        return update_runtime_status()
    except Exception:
        if incoming is not None:
            incoming.unlink(missing_ok=True)
        _release_update_slot()
        raise


def github_update_worker(state: "AppState"):
    # Wait until the HTTP server and kiosk have had time to come online. Checks
    # are deliberately infrequent so public GitHub API rate limits are a non-issue.
    time.sleep(10)
    while not state.stop_event.is_set():
        cfg = github_update_config(state.config)
        if cfg.get("github_repo") and cfg.get("github_auto_check"):
            try:
                status = github_check_and_maybe_install(state, install=bool(cfg.get("github_auto_install")))
                if status.get("state") in {"installing", "restarting", "staged", "downloading"}:
                    return
            except Exception as exc:
                _write_update_status(state="error", source="github", github_repo=cfg.get("github_repo", ""), error=str(exc), message="GitHub updatecontrole mislukt")
        minutes = max(5, int(cfg.get("github_check_minutes") or 5))
        if state.stop_event.wait(minutes * 60):
            return


def _write_github_settings_status(**fields) -> dict:
    with _GITHUB_SETTINGS_STATUS_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        current = {}
        if GITHUB_SETTINGS_STATUS_PATH.exists():
            try: current = json.loads(GITHUB_SETTINGS_STATUS_PATH.read_text(encoding="utf-8"))
            except Exception: current = {}
        current.update(fields); current["updated_at"] = utcnow_iso()
        tmp = GITHUB_SETTINGS_STATUS_PATH.with_name(f"{GITHUB_SETTINGS_STATUS_PATH.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"); tmp.replace(GITHUB_SETTINGS_STATUS_PATH)
        return current


def github_settings_sync_status() -> dict:
    status = {"state": "idle", "last_sha": "", "changed": False, "error": ""}
    if GITHUB_SETTINGS_STATUS_PATH.exists():
        try:
            loaded = json.loads(GITHUB_SETTINGS_STATUS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict): status.update(loaded)
        except Exception: pass
    return status


def github_pull_settings(state: "AppState", force: bool = False) -> dict:
    cfg = github_settings_sync_config(state.config); repo = cfg.get("github_repo") or ""
    if not repo: raise ValueError("Stel eerst een openbaar GitHub repository in")
    branch, path = cfg["github_settings_branch"], cfg["github_settings_path"]
    _write_github_settings_status(state="checking", repo=repo, branch=branch, path=path, changed=False, error="", message="Instellingen op GitHub controleren")
    try:
        remote = _github_file(repo, path, branch); doc = json.loads(remote["body"].decode("utf-8", "replace"))
        if not isinstance(doc, dict): raise ValueError("Het instellingenbestand moet een JSON-object bevatten")
        incoming = doc.get("display_settings", doc.get("settings"))
        if incoming is None: incoming = {k:v for k,v in doc.items() if k not in {"revision","description","updated_at"}}
        if not isinstance(incoming, dict) or not incoming: raise ValueError("Geen display_settings of settings in het GitHub-bestand gevonden")
        previous = github_settings_sync_status(); sha = remote.get("sha") or hashlib.sha256(remote["body"]).hexdigest()
        if not force and sha and sha == previous.get("last_sha"):
            return _write_github_settings_status(state="up-to-date", repo=repo, branch=branch, path=path, changed=False, error="", message="GitHub-instellingen zijn al actueel")
        merged = state.get_display_settings()
        merged.update(incoming)
        applied = state.save_display_settings(merged)
        return _write_github_settings_status(state="applied", repo=repo, branch=branch, path=path, last_sha=sha, revision=doc.get("revision", ""), applied_keys=sorted(applied), changed=True, error="", message=f"{len(applied)} instellingen vanaf GitHub toegepast")
    except urllib.error.HTTPError as exc:
        message = f"{path} bestaat niet op branch {branch}" if int(getattr(exc,"code",0) or 0)==404 else f"GitHub HTTP {getattr(exc,'code','?')}"
        _write_github_settings_status(state="error", repo=repo, branch=branch, path=path, changed=False, error=message, message=message)
        raise ValueError(message) from exc
    except Exception as exc:
        _write_github_settings_status(state="error", repo=repo, branch=branch, path=path, changed=False, error=str(exc), message="Instellingen synchroniseren mislukt")
        raise


def _delayed_github_settings_pull(state: "AppState"):
    time.sleep(.6)
    try: github_pull_settings(state, force=True)
    except Exception: pass


def github_settings_worker(state: "AppState"):
    time.sleep(6)
    while not state.stop_event.is_set():
        cfg = github_settings_sync_config(state.config)
        if cfg.get("github_settings_auto_sync"):
            try: github_pull_settings(state, force=False)
            except Exception: pass
        if state.stop_event.wait(max(1, int(cfg.get("github_settings_minutes") or 5))*60): return


def _safe_update_client(ip: str) -> bool:
    """Only allow self-update from loopback/LAN/Tailscale-style addresses."""
    try:
        addr = ipaddress.ip_address((ip or "").split("%", 1)[0])
    except ValueError:
        return False
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return True
    if addr.version == 4 and addr in ipaddress.ip_network("100.64.0.0/10"):
        return True
    return False


def _same_origin_or_nonbrowser(headers) -> bool:
    """Block cross-site browser requests to consequential local admin actions."""
    origin = normalize_space(headers.get("Origin") or "")
    if not origin:
        return True  # curl/local scripts do not normally send Origin
    host = normalize_space(headers.get("Host") or "").lower()
    try:
        parsed = urlparse(origin)
    except Exception:
        return False
    return bool(host and parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host)


def _validate_and_extract_update(zip_path: Path) -> tuple[Path, str]:
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{time.time_ns()}-{threading.get_ident()}"
    stage = UPDATE_DIR / f"stage-{stamp}"
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        if not infos:
            raise ValueError("Update-ZIP is leeg")
        for info in infos:
            count += 1
            if count > MAX_UPDATE_FILES:
                raise ValueError("Update bevat te veel bestanden")
            total += max(0, int(info.file_size))
            if total > MAX_UPDATE_UNPACKED_BYTES:
                raise ValueError("Update is uitgepakt te groot")
            name = info.filename.replace("\\", "/")
            parts = Path(name).parts
            if not name or name.startswith("/") or ".." in parts:
                raise ValueError("Onveilige bestandsnaam in update")
            # Reject symlinks from uploaded archives.
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError("Symlinks zijn niet toegestaan in updates")
            target = (stage / name).resolve()
            if stage.resolve() not in target.parents and target != stage.resolve():
                raise ValueError("Update probeert buiten de stagingmap te schrijven")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            # Preserve executable intent when present in ZIP metadata. Some producers do
            # not retain Unix mode bits, so the known launcher scripts also get
            # a safe executable fallback. Without this, a successful self-update
            # could leave start/kiosk/restart scripts at 0644 after the next reboot.
            archived_mode = (info.external_attr >> 16) & 0o777
            launcher_names = {"start.sh", "restart.sh", "kiosk.sh", "install-user-service.sh", "diagnose.sh"}
            should_exec = bool(archived_mode & 0o111) or target.name in launcher_names
            try:
                target.chmod(0o755 if should_exec else 0o644)
            except OSError:
                pass

    candidates = []
    if (stage / "backend" / "server.py").is_file():
        candidates.append(stage)
    for server_file in stage.glob("*/backend/server.py"):
        candidates.append(server_file.parent.parent)
    # dedupe while preserving order
    roots = []
    seen = set()
    for root in candidates:
        rp = root.resolve()
        if rp not in seen:
            seen.add(rp); roots.append(root)
    if len(roots) != 1:
        raise ValueError("ZIP moet precies één P2000 Monitor-map bevatten")
    package_root = roots[0]
    required = [package_root / "backend" / "server.py", package_root / "frontend" / "index.html", package_root / "frontend" / "control.html"]
    if not all(x.is_file() for x in required):
        raise ValueError("Dit lijkt geen complete P2000 Monitor-update")
    version = "onbekend"
    version_file = package_root / "VERSION"
    if version_file.exists():
        version = normalize_space(version_file.read_text(encoding="utf-8", errors="ignore"))[:40] or version
    if version == "onbekend":
        text = (package_root / "backend" / "server.py").read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', text)
        if match:
            version = match.group(1)[:40]
    return package_root, version


def _copy_update_into_place(package_root: Path):
    """Replace app code while preserving this installation's database/config."""
    package_root = package_root.resolve()
    keep_exact = {Path("config/config.json")}
    skip_top = {"data", ".git", "__pycache__"}
    for src in package_root.rglob("*"):
        rel = src.relative_to(package_root)
        if not rel.parts or rel.parts[0] in skip_top or rel in keep_exact:
            continue
        if any(part == "__pycache__" for part in rel.parts):
            continue
        dst = ROOT / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _apply_update_and_exec(package_root: Path, target_version: str):
    try:
        time.sleep(1.1)  # give the browser time to receive the upload response
        _write_update_status(state="backup", target_version=target_version, message="Vorige versie veiligstellen")
        backup = _create_update_backup()
        _write_update_status(state="installing", target_version=target_version, backup=str(backup), message="Bestanden installeren")
        _copy_update_into_place(package_root)
        try:
            stage_dir = package_root if package_root.name.startswith("stage-") else (package_root.parent if package_root.parent.name.startswith("stage-") else None)
            if stage_dir is not None and (stage_dir.parent == UPDATE_DIR or UPDATE_DIR in stage_dir.parents):
                shutil.rmtree(stage_dir, ignore_errors=True)
        except Exception:
            pass
        _write_update_status(state="restarting", target_version=target_version, message="Backend herstarten")
        time.sleep(.35)
        os.execv(sys.executable, [sys.executable, str(ROOT / "backend" / "server.py"), *sys.argv[1:]])
    except Exception as exc:
        _release_update_slot()
        _write_update_status(state="error", target_version=target_version, error=str(exc), message="Update mislukt")


def schedule_self_restart(delay: float = .8):
    def worker():
        time.sleep(delay)
        os.execv(sys.executable, [sys.executable, str(ROOT / "backend" / "server.py"), *sys.argv[1:]])
    threading.Thread(target=worker, daemon=True, name="self-restart").start()


MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
    ".mp3": "audio/mpeg",
}


_DISCONNECT_ERRNOS = {32, 54, 104, 10053, 10054}


def is_client_disconnect(exc: BaseException | None) -> bool:
    """True for normal browser/client disconnects that should not print tracebacks."""
    if exc is None:
        return False
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    return isinstance(exc, OSError) and getattr(exc, "errno", None) in _DISCONNECT_ERRNOS


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Threading server that treats vanished browsers as a normal network event."""
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if is_client_disconnect(exc):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    server_version = "P2000Monitor"
    protocol_version = "HTTP/1.1"
    state: AppState

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except OSError as exc:
            if is_client_disconnect(exc):
                self.close_connection = True
                return
            raise

    def _short_response_connection(self):
        # Mobile browsers aggressively tear down idle HTTP/1.1 keep-alive sockets.
        # Short API/static responses do not benefit from keeping them around. SSE is
        # handled separately and remains a long-lived connection.
        self.send_header("Connection", "close")
        self.close_connection = True

    def _safe_write(self, body: bytes) -> bool:
        try:
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
            return False
        except OSError as exc:
            if is_client_disconnect(exc):
                self.close_connection = True
                return False
            raise

    def log_message(self, fmt, *args):
        if self.state.config.get("http_log", False):
            super().log_message(fmt, *args)

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, data, status=200):
        if int(status) >= 400:
            self.state.api_errors += 1
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self._short_response_connection()
        self.end_headers()
        self._safe_write(body)

    def send_bytes(self, body: bytes, content_type: str, status=200, extra_headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=86400")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(str(key), str(value))
        self.cors()
        self._short_response_connection()
        self.end_headers()
        self._safe_write(body)

    @staticmethod
    def _background_file():
        for name, mime in (("background.jpg","image/jpeg"),("background.png","image/png"),("background.webp","image/webp")):
            path = BACKGROUND_DIR / name
            if path.exists() and path.is_file():
                return path, mime
        return None, None

    def _background_info(self):
        path, mime = self._background_file()
        if not path:
            return {"exists": False, "version": 0, "bytes": 0, "type": ""}
        st = path.stat()
        return {"exists": True, "version": int(st.st_mtime_ns // 1_000_000), "bytes": int(st.st_size), "type": mime, "name": path.name}

    def _handle_background_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return self.send_json({"ok": False, "error": "Geen foto ontvangen."}, 400)
        if length > MAX_BACKGROUND_BYTES:
            return self.send_json({"ok": False, "error": "Achtergrondfoto is groter dan 15 MB."}, 413)
        body = self.rfile.read(length)
        if len(body) != length:
            return self.send_json({"ok": False, "error": "Foto-upload werd voortijdig afgebroken."}, 400)
        ext = mime = None
        if body.startswith(b"\xff\xd8\xff"):
            ext, mime = ".jpg", "image/jpeg"
        elif body.startswith(b"\x89PNG\r\n\x1a\n"):
            ext, mime = ".png", "image/png"
        elif len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
            ext, mime = ".webp", "image/webp"
        if not ext:
            return self.send_json({"ok": False, "error": "Alleen JPG, PNG en WebP worden ondersteund."}, 415)
        BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKGROUND_DIR / f"background{ext}"
        temp = BACKGROUND_DIR / f".upload-{time.time_ns()}{ext}"
        temp.write_bytes(body)
        for old in BACKGROUND_DIR.glob("background.*"):
            if old != target:
                old.unlink(missing_ok=True)
        os.replace(temp, target)
        info = self._background_info()
        info.update({"ok": True, "mime": mime})
        return self.send_json(info)

    @staticmethod
    def _tune_file():
        for name, mime in (("custom.mp3","audio/mpeg"),("custom.wav","audio/wav"),("custom.ogg","audio/ogg")):
            path = TUNE_DIR / name
            if path.exists() and path.is_file():
                return path, mime
        return None, None

    def _tune_info(self):
        path, mime = self._tune_file()
        if not path:
            return {"exists": False, "version": 0, "bytes": 0, "type": ""}
        st = path.stat()
        return {"exists": True, "version": int(st.st_mtime_ns // 1_000_000), "bytes": int(st.st_size), "type": mime, "name": path.name}

    def _handle_tune_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return self.send_json({"ok": False, "error": "Geen audiobestand ontvangen."}, 400)
        if length > MAX_TUNE_BYTES:
            return self.send_json({"ok": False, "error": "Deuntje is groter dan 12 MB."}, 413)
        body = self.rfile.read(length)
        if len(body) != length:
            return self.send_json({"ok": False, "error": "Audio-upload werd voortijdig afgebroken."}, 400)
        ext = mime = None
        if body.startswith(b"ID3") or (len(body) >= 2 and body[0] == 0xFF and (body[1] & 0xE0) == 0xE0):
            ext, mime = ".mp3", "audio/mpeg"
        elif len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WAVE":
            ext, mime = ".wav", "audio/wav"
        elif body.startswith(b"OggS"):
            ext, mime = ".ogg", "audio/ogg"
        if not ext:
            return self.send_json({"ok": False, "error": "Alleen MP3, WAV en OGG worden ondersteund."}, 415)
        TUNE_DIR.mkdir(parents=True, exist_ok=True)
        target = TUNE_DIR / f"custom{ext}"
        temp = TUNE_DIR / f".upload-{time.time_ns()}{ext}"
        temp.write_bytes(body)
        for old in TUNE_DIR.glob("custom.*"):
            if old != target:
                old.unlink(missing_ok=True)
        os.replace(temp, target)
        info = self._tune_info()
        info.update({"ok": True, "mime": mime})
        return self.send_json(info)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self._short_response_connection()
        self.end_headers()

    def do_POST(self):
        self.state.api_requests += 1
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self.send_json({"error":"not found"}, 404)

        client_ip = self.client_address[0] if self.client_address else ""
        if not _safe_update_client(client_ip) or not _same_origin_or_nonbrowser(self.headers):
            return self.send_json({"ok": False, "error": "Schrijfacties zijn alleen toegestaan vanaf localhost, LAN of Tailscale via dezelfde control-origin."}, 403)

        if parsed.path == "/api/background/upload":
            return self._handle_background_upload()
        if parsed.path == "/api/tune/upload":
            return self._handle_tune_upload()
        if parsed.path == "/api/tune/remove":
            TUNE_DIR.mkdir(parents=True, exist_ok=True)
            removed = False
            for old in TUNE_DIR.glob("custom.*"):
                if old.is_file():
                    old.unlink(missing_ok=True); removed = True
            return self.send_json({"ok": True, "removed": removed})
        if parsed.path == "/api/background/remove":
            BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
            removed = False
            for old in BACKGROUND_DIR.glob("background.*"):
                if old.is_file():
                    old.unlink(missing_ok=True); removed = True
            return self.send_json({"ok": True, "removed": removed})

        if parsed.path == "/api/update/upload":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_UPDATE_BYTES:
                return self.send_json({"ok": False, "error": "Update-ZIP ontbreekt of is groter dan 64 MB."}, 413)
            if not _claim_update_slot():
                return self.send_json({"ok": False, "error": "Er wordt al een update gevalideerd of geïnstalleerd."}, 409)
            incoming = None
            remaining = length
            try:
                UPDATE_DIR.mkdir(parents=True, exist_ok=True)
                incoming = UPDATE_DIR / f"incoming-{time.time_ns()}-{threading.get_ident()}.zip"
                with incoming.open("wb") as fp:
                    while remaining > 0:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Upload werd voortijdig afgebroken")
                        fp.write(chunk); remaining -= len(chunk)
                _write_update_status(state="validating", message="Update controleren", uploaded_bytes=length)
                package_root, target_version = _validate_and_extract_update(incoming)
                incoming.unlink(missing_ok=True)
                _write_update_status(state="staged", target_version=target_version, message="Update klaar voor installatie")
                self.send_json({"ok": True, "target_version": target_version, "restarting": True, "message": "Update ontvangen. De monitor installeert en herstart nu automatisch."})
                threading.Thread(target=_apply_update_and_exec, args=(package_root, target_version), daemon=True, name="self-update").start()
                return
            except (ValueError, zipfile.BadZipFile) as exc:
                if incoming is not None:
                    incoming.unlink(missing_ok=True)
                _release_update_slot()
                _write_update_status(state="error", error=str(exc), message="Update geweigerd")
                return self.send_json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                if incoming is not None:
                    incoming.unlink(missing_ok=True)
                _release_update_slot()
                _write_update_status(state="error", error=str(exc), message="Update mislukt")
                return self.send_json({"ok": False, "error": str(exc)}, 500)

        try:
            raw_length = int(self.headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError, OverflowError):
            return self.send_json({"ok": False, "error": "Ongeldige Content-Length"}, 400)
        if raw_length < 0 or raw_length > 65536:
            return self.send_json({"ok": False, "error": "API-request is groter dan 64 KB"}, 413)
        try:
            payload = json.loads(self.rfile.read(raw_length) or b"{}")
        except Exception:
            return self.send_json({"ok": False, "error":"invalid json"}, 400)
        if not isinstance(payload, dict):
            return self.send_json({"ok": False, "error": "JSON-object verwacht"}, 400)
        if parsed.path == "/api/update/github/settings":
            try:
                return self.send_json({"ok": True, "settings": self.state.save_github_update_config(payload)})
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        if parsed.path == "/api/github/settings-sync/config":
            try: return self.send_json({"ok": True, "config": self.state.save_github_settings_sync_config(payload)})
            except ValueError as exc: return self.send_json({"ok": False, "error": str(exc)}, 400)
        if parsed.path == "/api/github/settings-sync/pull":
            try:
                status = github_pull_settings(self.state, force=True)
                return self.send_json({"ok": True, "status": status, "settings": self.state.get_display_settings()})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc), "status": github_settings_sync_status()}, 500)
        if parsed.path == "/api/update/github/check":
            install = bool(payload.get("install", False))
            try:
                result = github_check_and_maybe_install(self.state, install=install)
                return self.send_json({"ok": True, "status": result, "restarting": bool(install and result.get("available"))})
            except Exception as exc:
                _write_update_status(state="error", source="github", error=str(exc), message="GitHub update mislukt")
                return self.send_json({"ok": False, "error": str(exc), "status": update_runtime_status()}, 500)
        if parsed.path == "/api/update/rollback":
            if not _claim_update_slot():
                return self.send_json({"ok": False, "error": "Er loopt al een updateactie"}, 409)
            try:
                backup = _latest_update_backup()
                if backup is None:
                    raise ValueError("Er is nog geen vorige versie opgeslagen")
                meta = {}
                try:
                    meta = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
                except Exception:
                    pass
                target = str(meta.get("version") or "vorige versie")
                _write_update_status(state="rollback", target_version=target, message=f"Terug naar {target}")
                self.send_json({"ok": True, "target_version": target, "restarting": True})
                def rollback_worker():
                    try:
                        time.sleep(.8)
                        _restore_update_backup(backup)
                        _write_update_status(state="restarting", target_version=target, message="Vorige versie herstarten")
                        os.execv(sys.executable, [sys.executable, str(ROOT / "backend" / "server.py"), *sys.argv[1:]])
                    except Exception as exc:
                        _release_update_slot()
                        _write_update_status(state="error", error=str(exc), message="Rollback mislukt")
                threading.Thread(target=rollback_worker, daemon=True, name="update-rollback").start()
                return
            except Exception as exc:
                _release_update_slot()
                return self.send_json({"ok": False, "error": str(exc)}, 400)

        if parsed.path == "/api/client-health":
            clean = {
                "reported_at": utcnow_iso(),
                "viewport": normalize_space(str(payload.get("viewport") or ""))[:80],
                "canvas": normalize_space(str(payload.get("canvas") or ""))[:80],
                "dpr": bounded_float(payload.get("dpr",1),1,0.1,8.0),
                "render_avg_ms": bounded_float(payload.get("render_avg_ms",0),0,0,5000),
                "render_p95_ms": bounded_float(payload.get("render_p95_ms",0),0,0,5000),
                "render_max_ms": bounded_float(payload.get("render_max_ms",0),0,0,5000),
                "render_samples": bounded_int(payload.get("render_samples",0),0,0,10000),
                "js_heap_used": bounded_int(payload.get("js_heap_used",0),0,0,2_000_000_000),
                "active": bool(payload.get("active",False)),
                "active_count": bounded_int(payload.get("active_count",0),0,0,200),
                "map_visible": bool(payload.get("map_visible",False)),
                "busy": bool(payload.get("busy",False)),
                "visibility": normalize_space(str(payload.get("visibility") or ""))[:40],
                "audio_attempts": bounded_int(payload.get("audio_attempts",0),0,0,1_000_000),
                "audio_successes": bounded_int(payload.get("audio_successes",0),0,0,1_000_000),
                "audio_failures": bounded_int(payload.get("audio_failures",0),0,0,1_000_000),
                "audio_fallbacks": bounded_int(payload.get("audio_fallbacks",0),0,0,1_000_000),
                "audio_last_error": normalize_space(str(payload.get("audio_last_error") or ""))[:240],
                "audio_last_mode": normalize_space(str(payload.get("audio_last_mode") or ""))[:60],
                "audio_unlocked": bool(payload.get("audio_unlocked",False)),
                "audio_last_success_at": bounded_int(payload.get("audio_last_success_at",0),0,0,9_999_999_999_999),
            }
            with self.state.client_health_lock:
                self.state.client_health = clean
            return self.send_json({"ok": True})
        if parsed.path == "/api/parser/debug":
            raw = str(payload.get("raw") or payload.get("title") or "")[:1200]
            if not normalize_space(raw):
                return self.send_json({"ok": False, "error": "Plak eerst een P2000-regel"}, 400)
            categories = payload.get("categories") if isinstance(payload.get("categories"), list) else []
            return self.send_json({"ok": True, "parse": parse_raw_p2000_line(self.state, raw, categories)})
        if parsed.path == "/api/tts":
            text = str(payload.get("text") or "")[:500]
            service = normalize_space(str(payload.get("service") or "brandweer"))[:40].lower()
            urgent = bool(payload.get("urgent", False))
            attention = bool(payload.get("attention", True))
            try:
                rate = max(0.65, min(1.25, float(payload.get("rate", 0.96) or 0.96)))
            except Exception:
                rate = 0.96
            try:
                audio, mime, engine = generate_dispatch_audio(text, rate=rate, service=service, urgent=urgent, attention=attention)
                return self.send_bytes(audio, mime, extra_headers={"X-P2000-TTS-Engine": engine})
            except Exception as e:
                return self.send_json({"error": str(e), "fallback": "none"}, 503)
        if parsed.path == "/api/tts/play":
            # Host audio is deliberately disabled: speech must originate from the
            # lightkrant browser tab, never from PowerShell/Windows host audio.
            return self.send_json({"ok": False, "error": "Host-TTS is uitgeschakeld; audio hoort bij het lichtkrant-tabblad."}, 409)
        if parsed.path == "/api/tts/stop":
            return self.send_json({"ok": True, "stopped": stop_host_tts()})
        if parsed.path == "/api/settings":
            return self.send_json({"settings": self.state.save_display_settings(payload)})
        if parsed.path == "/api/setup":
            try:
                return self.send_json({"ok": True, "setup": self.state.save_setup(payload)})
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 500)
        if parsed.path == "/api/vehicles/sync":
            force = bool(payload.get("force", True))
            self.state.start_vehicle_sync(force=force)
            return self.send_json({"ok": True, "status": self.state.vehicle_sync_view()})
        if parsed.path == "/api/vehicle-overrides/upsert":
            try:
                return self.send_json(self.state.upsert_vehicle_override(payload))
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 500)
        if parsed.path == "/api/vehicle-overrides/delete":
            try:
                return self.send_json(self.state.delete_vehicle_override(payload))
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 500)
        if parsed.path == "/api/feed-config":
            try:
                return self.send_json({"ok": True, "config": self.state.save_feed_config(payload)})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 500)
        if parsed.path == "/api/test-message":
            default_city = normalize_space(str(self.state.setup_city() or "Nederland"))[:120] or "Nederland"
            default_title = f"P 1 BR woning Hoofdstraat {default_city}"
            requested_speak = bool(payload.get("speak", True))
            speech_text = normalize_space(str(payload.get("speech_text") or ""))[:500]
            host_speak = False  # speech is always owned by the lightkrant browser tab
            test_title = str(payload.get("title") or default_title)[:1000]
            test_summary = str(payload.get("summary") or payload.get("title") or default_title)[:1000]
            test_city = str(payload.get("city") or default_city)[:120]
            test_location = str(payload.get("location") or "")[:240]
            # Test messages follow the same location parser as the live feed. This
            # is especially important for "Eigen P2000-regel": the control page
            # only needs to know the city; the backend extracts the street itself.
            if not normalize_space(test_location):
                test_location = infer_location(test_title, test_summary, test_city)[:240]
            test_payload = {
                "type": "test",
                "token": str(payload.get("token") or f"test-{int(time.time()*1000)}"),
                "mode": str(payload.get("mode") or "message")[:40],
                "title": test_title,
                "summary": test_summary,
                "city": test_city,
                "location": test_location,
                "service": str(payload.get("service") or "brandweer")[:40],
                "priority": str(payload.get("priority") or "P1")[:20],
                "scale": str(payload.get("scale") or "")[:80],
                "scale_score": bounded_int(payload.get("scale_score", 0), 0, 0, 100),
                "speech_text": speech_text,
                "duration_ms": bounded_int(payload.get("duration_ms", 60000), 60000, 0, 15 * 60 * 1000),
                # Every test/speech request is broadcast to the lightkrant client.
                "speak": bool(requested_speak),
                "force_audio": bool(payload.get("force_audio", False)),
                "tune_choice": str(payload.get("tune_choice") or "")[:40] if str(payload.get("tune_choice") or "") in {"none", "builtin:classic", "builtin:double", "builtin:rising", "builtin:urgent", "youtube", "custom"} else "",
            }
            connected = self.state.subscriber_count()
            self.state.begin_test_command(test_payload["token"], test_payload["mode"], connected)
            delivered = self.state.broadcast({"type": "test", "payload": test_payload})
            if test_payload["mode"] == "stop-speech":
                stop_host_tts()
            if delivered < 1:
                with self.state.test_results_lock:
                    row = self.state.test_results.get(test_payload["token"])
                    if row:
                        row.update({"status": "error", "ok": False, "detail": "Geen lichtkrant-tabblad verbonden", "updated_at": utcnow_iso()})
                return self.send_json({"ok": False, "error": "Geen lichtkrant-tabblad verbonden. Start of open eerst de monitor.", "test": test_payload}, 409)
            return self.send_json({"ok": True, "test": test_payload, "speech_target": "lightkrant-tab", "connected_clients": delivered})
        if parsed.path == "/api/test-result":
            try:
                return self.send_json({"ok": True, "result": self.state.finish_test_command(payload)})
            except ValueError as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 404)
        if parsed.path == "/api/system/restart":
            self.send_json({"ok": True, "message": "Backend herstart"})
            schedule_self_restart()
            return
        if parsed.path == "/api/display/power":
            return self.send_json(self.state.set_display_power(str(payload.get("state", "")), bool(payload.get("manual", False))))
        if parsed.path == "/api/feeds/reconnect":
            self.state.request_feed_refresh(clear_cache=True)
            self.state.last_watchdog_action = utcnow_iso()
            return self.send_json({"ok":True,"message":"Volledige feed-herverbinding aangevraagd"})
        return self.send_json({"error":"not found"}, 404)

    def do_GET(self):
        self.state.api_requests += 1
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self.handle_api(parsed)
        return self.serve_static(parsed.path)

    def handle_api(self, parsed):
        qs = parse_qs(parsed.query)
        if parsed.path == "/api/background/info":
            return self.send_json(self._background_info())
        if parsed.path == "/api/tune/info":
            return self.send_json(self._tune_info())
        if parsed.path == "/api/tune/audio":
            path, mime = self._tune_file()
            if not path:
                return self.send_json({"error": "Geen eigen deuntje ingesteld"}, 404)
            try:
                return self.send_bytes(path.read_bytes(), mime, extra_headers={"Accept-Ranges": "bytes"})
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)
        if parsed.path == "/api/background/image":
            path, mime = self._background_file()
            if not path:
                return self.send_json({"error": "Geen achtergrondfoto ingesteld"}, 404)
            try:
                return self.send_bytes(path.read_bytes(), mime)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)

        if parsed.path == "/api/tts/status":
            return self.send_json(tts_runtime_status())
        if parsed.path == "/api/update/github/settings":
            return self.send_json({"ok": True, "settings": self.state.github_update_view()})
        if parsed.path == "/api/github/settings-sync/config":
            return self.send_json({"ok": True, "config": self.state.github_settings_sync_view()})
        if parsed.path == "/api/github/settings-sync/status":
            return self.send_json({"ok": True, "status": github_settings_sync_status()})
        if parsed.path == "/api/update/status":
            allowed = _safe_update_client(self.client_address[0] if self.client_address else "")
            data = update_runtime_status()
            data["allowed_from_here"] = allowed
            return self.send_json(data)
        if parsed.path == "/api/runtime":
            # Lightweight kiosk heartbeat. Unlike /api/status this deliberately
            # avoids SQLite queries so the monitor can cheaply detect a backend
            # restart/update on low-power hardware.
            return self.send_json({
                "app": "P2000 Monitor",
                "version": APP_VERSION,
                "server_instance": self.state.server_instance,
                "started_at": self.state.started_at,
            })
        if parsed.path == "/api/setup":
            return self.send_json({"ok": True, "setup": self.state.setup_view()})
        if parsed.path == "/api/vehicles":
            return self.send_json(self.state.vehicle_catalog_payload())
        if parsed.path == "/api/vehicles/status":
            return self.send_json({"ok": True, "status": self.state.vehicle_sync_view()})
        if parsed.path == "/api/vehicle-overrides":
            return self.send_json({"ok": True, "overrides": self.state.vehicle_overrides_view()})
        if parsed.path == "/api/test-status":
            token = normalize_space(str(qs.get("token", [""])[0]))[:120]
            row = self.state.test_command_view(token) if token else None
            if not row:
                return self.send_json({"ok": False, "error": "Onbekende of verlopen test"}, 404)
            return self.send_json({"ok": True, "result": row})
        if parsed.path == "/api/feed-catalog":
            rows=[]
            for slug, meta in REGION_CATALOG.items():
                rows.append({"slug": slug, **meta, "feeds": {d: regional_feed_url(slug,d) for d in REGIONAL_DISCIPLINES}})
            return self.send_json({
                "regions": rows,
                "disciplines": list(ALL_DISCIPLINES),
                "national_feeds": dict(NATIONAL_DISCIPLINE_URLS),
                "subregion_parent": dict(SUBREGION_PARENT),
            })
        if parsed.path == "/api/feed-config":
            return self.send_json({"ok": True, "config": self.state.feed_config_view()})
        if parsed.path == "/api/display/info":
            try:
                return self.send_json({"ok": True, "display": self.state.display_info(force=True)})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 500)
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "health": self.state.health_snapshot()})
        if parsed.path == "/api/status":
            with self.state.connect() as con:
                count = con.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
                now_local = datetime.now(LOCAL_TZ)
                midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                cutoff_utc = midnight_local.astimezone(timezone.utc).isoformat(timespec="seconds")
                count_today = con.execute("SELECT COUNT(*) c FROM messages WHERE published >= ?", (cutoff_utc,)).fetchone()["c"]
                last = con.execute("SELECT published FROM messages ORDER BY published DESC LIMIT 1").fetchone()
            return self.send_json({
                "app": "P2000 Monitor",
                "version": APP_VERSION,
                "server_instance": self.state.server_instance,
                "started_at": self.state.started_at,
                "feed_status": self.state.feed_status,
                "last_poll": self.state.last_poll,
                "last_success": self.state.last_success,
                "last_error": self.state.last_error,
                "last_message": last["published"] if last else None,
                "messages_total": count,
                "messages_today": count_today,
                "poll_interval_seconds": max(15, int(self.state.config.get("poll_interval_seconds", 20))),
                "source": SOURCE_NAME,
                "source_url": "https://alarmeringen.nl/",
                "scope": self.state.config.get("standplaats") or SCOPE_LABEL,
                "scope_code": "+".join(setup_region_disciplines(self.state.config).keys()),
                "profile": self.state.setup_view(),
                "feeds": list(self.state.feed_diag.values()),
                "consecutive_failures": self.state.consecutive_failures,
                "watchdog_recoveries": self.state.watchdog_recoveries,
                "last_watchdog_action": self.state.last_watchdog_action,
                "watchdog_stale_seconds": max(180, int(self.state.config.get("watchdog_stale_seconds", 600))),
                "display_power": {
                    "status": self.state.display_power_status,
                    "error": self.state.display_power_error,
                    "changed_at": self.state.display_power_changed_at,
                    "method": self.state.display_power_method,
                    "connector": self.state.display_connector,
                    "name": self.state.display_name,
                    "supported_hint": "Windows SC_MONITORPOWER + input-wake",
                },
            })
        if parsed.path == "/api/settings":
            return self.send_json({"settings": self.state.get_display_settings()})
        if parsed.path == "/api/network":
            port = int(self.state.config.get("port", 8765))
            addresses = local_lan_addresses()
            urls = [f"http://{item['address']}:{port}/control" for item in addresses]
            host = (self.headers.get("Host") or "").strip()
            request_url = None
            if host and not re.match(r"^(?:localhost|127\.0\.0\.1|\[::1\])(?::|$)", host, re.I):
                request_url = f"http://{host}/control"
                if request_url not in urls:
                    urls.insert(0, request_url)
            return self.send_json({"control_urls": urls, "addresses": addresses, "preferred": urls[0] if urls else None})
        if parsed.path == "/api/geocode":
            city = normalize_space((qs.get("city", [""])[0] or ""))[:120]
            location = normalize_space((qs.get("location", [""])[0] or ""))[:240]
            settings = self.state.get_display_settings()
            zoom = bounded_int(qs.get("zoom", [str(settings.get("mapZoom", 16))])[0], int(settings.get("mapZoom", 16) or 16), 12, 18)
            if not location and not city:
                return self.send_json({"ok": False, "error": "Geen locatie opgegeven"}, 400)
            try:
                return self.send_json({"ok": True, "map": self.state.geocode_incident(city, location, zoom)})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 503)
        if parsed.path == "/api/unknown-vehicles":
            limit = bounded_int(qs.get("limit", ["100"])[0], 100, 1, 500)
            rows = self.state.list_unknown_callsigns(limit)
            return self.send_json({"unknown": rows, "count": len(rows)})
        if parsed.path == "/api/messages":
            return self.send_json({"messages": query_messages(self.state, qs)})
        if parsed.path == "/api/incidents":
            # Fetch enough rows to group recent related messages without a heavy query.
            raw_qs = dict(qs)
            raw_qs["limit"] = [str(bounded_int(qs.get("scan", ["500"])[0], 500, 1, 1000))]
            messages = query_messages(self.state, raw_qs)
            limit = bounded_int(qs.get("limit", ["30"])[0], 30, 1, 100)
            return self.send_json({"incidents": build_incidents(messages, limit=limit)})
        if parsed.path == "/api/services":
            with self.state.connect() as con:
                rows = con.execute("SELECT service, COUNT(*) count FROM messages GROUP BY service ORDER BY count DESC").fetchall()
            return self.send_json({"services": [dict(r) for r in rows]})
        if parsed.path == "/api/cities":
            with self.state.connect() as con:
                rows = con.execute("SELECT city, COUNT(*) count FROM messages WHERE city <> '' GROUP BY city ORDER BY count DESC LIMIT 250").fetchall()
            return self.send_json({"cities": [dict(r) for r in rows]})
        if parsed.path == "/api/stream":
            return self.handle_sse()
        if parsed.path == "/api/config":
            public = {
                "display_name": self.state.config.get("display_name", "P2000 Monitor"),
                "feed_urls": list(self.state.config.get("feed_urls") or []),
                "poll_interval_seconds": max(15, int(self.state.config.get("poll_interval_seconds", 20))),
                "scope": self.state.config.get("standplaats") or SCOPE_LABEL,
                "setup_complete": self.state.config.get("setup_complete") is True,
            }
            return self.send_json(public)
        return self.send_json({"error": "not found"}, 404)

    def handle_sse(self):
        q = self.state.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.cors()
        self.end_headers()
        try:
            # Send runtime identity as real SSE data. EventSource reconnects by
            # itself after an update, so the kiosk can reload immediately without
            # hammering /api/status in the background.
            runtime = json.dumps({
                "type": "runtime",
                "version": APP_VERSION,
                "server_instance": self.state.server_instance,
                "started_at": self.state.started_at,
            }, ensure_ascii=False, separators=(",", ":"))
            self.wfile.write(f"data: {runtime}\n\n".encode("utf-8"))
            self.wfile.flush()
            while not self.state.stop_event.is_set():
                try:
                    payload = q.get(timeout=20)
                    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.state.unsubscribe(q)

    def serve_static(self, path: str):
        if path in ("", "/"):
            path = "/index.html" if self.state.config.get("setup_complete") is True else "/setup.html"
        elif path == "/index.html" and self.state.config.get("setup_complete") is not True:
            path = "/setup.html"
        if path == "/control":
            path = "/control.html"
        clean = Path(path.lstrip("/"))
        if ".." in clean.parts:
            return self.send_error(403)
        target = (FRONTEND_DIR / clean).resolve()
        if FRONTEND_DIR.resolve() not in target.parents and target != FRONTEND_DIR.resolve():
            return self.send_error(403)
        if not target.exists() or not target.is_file():
            # SPA-ish fallback for harmless display URLs.
            target = FRONTEND_DIR / "index.html"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        if target.suffix in {".html", ".js", ".css"}:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self._short_response_connection()
        self.end_headers()
        self._safe_write(body)


def load_config() -> dict:
    default = {
        "display_name": "P2000 Monitor",
        "setup_complete": False,
        "profile_type": "particulier",
        "person_name": "",
        "company_name": "",
        "department_name": "",
        "contact_name": "",
        "standplaats": "",
        "standplaats_city": "",
        "region_disciplines": {},
        "bind": "0.0.0.0",
        "port": 8765,
        "feed_urls": [],
        "fallback_feed_urls": [],
        "poll_interval_seconds": 20,
        "request_timeout_seconds": 15,
        "max_feed_bytes": 2_000_000,
        "retention_days": 30,
        "watchdog_stale_seconds": 600,
        "http_log": False,
        "github_repo": DEFAULT_GITHUB_REPO,
        "github_auto_check": True,
        "github_auto_install": True,
        "github_check_minutes": 5,
        "github_branch_updates": True,
        "github_branch": DEFAULT_GITHUB_BRANCH,
        "github_settings_auto_sync": False,
        "github_settings_path": DEFAULT_GITHUB_SETTINGS_PATH,
        "github_settings_branch": DEFAULT_GITHUB_BRANCH,
        "github_settings_minutes": 5,
    }
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                default.update(loaded)
        except Exception as exc:
            print(f"Waarschuwing: config/config.json kon niet worden gelezen; veilige defaults worden gebruikt: {exc}", file=sys.stderr)

    # Keep a hand-edited/broken config from taking the complete kiosk offline.
    default["display_name"] = normalize_space(str(default.get("display_name") or "P2000 Monitor"))[:120] or "P2000 Monitor"
    bind = normalize_space(str(default.get("bind") or "0.0.0.0"))
    default["bind"] = bind if len(bind) <= 120 else "0.0.0.0"
    default["port"] = bounded_int(default.get("port"), 8765, 1, 65535)
    default["poll_interval_seconds"] = bounded_int(default.get("poll_interval_seconds"), 20, 15, 3600)
    default["request_timeout_seconds"] = bounded_int(default.get("request_timeout_seconds"), 15, 5, 60)
    default["max_feed_bytes"] = bounded_int(default.get("max_feed_bytes"), 2_000_000, 100_000, 10_000_000)
    default["retention_days"] = bounded_int(default.get("retention_days"), 30, 1, 365)
    default["watchdog_stale_seconds"] = bounded_int(default.get("watchdog_stale_seconds"), 600, 180, 86_400)
    default["http_log"] = default.get("http_log") is True
    default.update(github_update_config(default))
    # Drop the pre-v4.2.4 key so it cannot be written back to config.json and
    # accidentally suggest that the updater still runs on an hourly interval.
    default.pop("github_check_hours", None)
    default.update(github_settings_sync_config(default))

    raw_urls = default.get("feed_urls")
    if not isinstance(raw_urls, list):
        raw_urls = []
    urls = []
    for value in raw_urls[:128]:
        url = normalize_space(str(value or ""))
        try:
            parsed = urlparse(url)
        except Exception:
            continue
        if parsed.scheme in {"http", "https"} and parsed.netloc and len(url) <= 1000:
            urls.append(url)
    default["feed_urls"] = urls
    raw_fallback = default.get("fallback_feed_urls")
    if not isinstance(raw_fallback, list):
        raw_fallback = []
    fallback_urls = []
    for value in raw_fallback[:6]:
        url = normalize_space(str(value or ""))
        try:
            parsed = urlparse(url)
        except Exception:
            continue
        if parsed.scheme in {"http", "https"} and parsed.netloc and len(url) <= 1000 and url not in default["feed_urls"]:
            fallback_urls.append(url)
    default["fallback_feed_urls"] = fallback_urls
    default["setup_complete"] = default.get("setup_complete") is True
    default["profile_type"] = default.get("profile_type") if default.get("profile_type") in {"particulier", "bedrijf"} else "particulier"
    default["standplaats"] = normalize_space(str(default.get("standplaats") or ""))[:120]
    default["standplaats_city"] = normalize_space(str(default.get("standplaats_city") or ""))[:120]
    default["person_name"] = normalize_space(str(default.get("person_name") or ""))[:120]
    default["company_name"] = normalize_space(str(default.get("company_name") or ""))[:160]
    default["department_name"] = normalize_space(str(default.get("department_name") or ""))[:160]
    default["contact_name"] = normalize_space(str(default.get("contact_name") or ""))[:120]
    default["region_disciplines"] = setup_region_disciplines(default)
    if default["setup_complete"] and not default["region_disciplines"]:
        default["setup_complete"] = False
    if default["region_disciplines"]:
        default["feed_urls"] = build_feed_urls(default["region_disciplines"])
    return default


def main():
    parser = argparse.ArgumentParser(description="Local P2000 monitor API and dashboard")
    parser.add_argument("--bind", help="Override bind address")
    parser.add_argument("--port", type=int, help="Override port")
    parser.add_argument("--no-poll", action="store_true", help="Do not start remote feed poller (testing/demo)")
    args = parser.parse_args()

    config = load_config()
    if args.bind:
        config["bind"] = args.bind
    if args.port:
        config["port"] = args.port

    state = AppState(config)
    state.init_db()
    try:
        previous_update = update_runtime_status()
        if previous_update.get("state") in {"staged", "installing", "restarting"}:
            _write_update_status(state="ready", message="Monitor online na update", installed_version=APP_VERSION, latest_version=APP_VERSION, available=False, error="")
    except Exception:
        pass
    migrated = state.migrate_source_v16()
    if migrated:
        print(f"Bronmigratie: {migrated} oude Zwaailicht-meldingen verwijderd")
    removed = state.purge_out_of_scope()
    if removed:
        print(f"Scope cleanup: {removed} meldingen buiten het actuele profiel verwijderd")
    Handler.state = state
    httpd = QuietThreadingHTTPServer((config["bind"], int(config["port"])), Handler)

    def shutdown(*_):
        state.stop_event.set()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if not args.no_poll:
        FeedPoller(state).start()
        FeedWatchdog(state).start()
    else:
        state.feed_status = "disabled"

    # Vehicle sync is intentionally asynchronous. The monitor is usable within
    # milliseconds with the local seed/number plan while selected regional exact
    # labels are refreshed quietly in the background.
    state.start_vehicle_sync(force=False)
    threading.Thread(target=github_update_worker, args=(state,), daemon=True, name="github-update-worker").start()
    threading.Thread(target=github_settings_worker, args=(state,), daemon=True, name="github-settings-worker").start()

    print(f"P2000 Monitor {APP_VERSION} running on http://{config['bind']}:{config['port']}")
    print(f"Lichtkrant: http://localhost:{config['port']}/")
    print(f"Control:   http://localhost:{config['port']}/control")
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        state.stop_event.set()
        httpd.server_close()


if __name__ == "__main__":
    main()
