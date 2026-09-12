"""Landelijke P2000 parserlaag voor P2000 Monitor v4.5.5.

Deze module is expres los van server.py gehouden. De updater kan hem daardoor bovenop
oudere compatibility-builds installeren zonder de historische update-bridge opnieuw
te hoeven genereren. ``install_national_parser(globals())`` vervangt alleen de parser-
primitieven; database-, feed-, updater- en UI-code blijven onaangeraakt.

Ontwerp:
- syntax/metadata eerst, betekenis daarna;
- geselecteerde regio heeft geen invloed op het kunnen parseren van een andere regio;
- onbekende tokens worden behouden als locatie/object in plaats van weggegooid;
- numerieke politie/ambulance-ID's worden nooit stilletjes brandweervoertuigen;
- elke override heeft een fallback naar de bestaande parser.
"""
from __future__ import annotations

import re
from typing import Callable

_NS: dict = {}
_ORIG: dict[str, Callable] = {}

# BNN/BON/BMD/BNH/BAD/BDH/BRT/BZB/BOB/BLB plus SNH/KAZ en varianten als BNH-inci-201.
FIRE_CHANNEL_RE = re.compile(r"\b(?:B[A-Z]{2}|S[A-Z]{2}|KAZ)(?:-INCI)?-\d{1,3}\b", re.I)
PRIO_RE = re.compile(r"^\s*(?:P\s*[1-5]|PRIO\s*[1-5]|A[012]|B[12])\b", re.I)
AMB_RE = re.compile(r"^\s*(?:A[012]|B[12])\b", re.I)
POLICE_BUNDLE_RE_V455 = re.compile(r"^\s*P\s*[1-5]\s+\d{4,7}\b", re.I)
ICNUM_RE = re.compile(r"\bIC\s*NUM\b|\bICNUM\b", re.I)
POLICE_SLASH_RE_V455 = re.compile(r"^\s*(?:ongeval|verkeer|politie)(?:/[^\s]+){1,4}\s+prio\s*[1-5]\b", re.I)
RWS_RE = re.compile(r"^\s*PRIO\s*[1-5]\b.*\b(?:WEGVERKEER|BIJZONDERE\s+VERKEERSZAKEN)\b", re.I)
POSTCODE_RE_LOCAL = re.compile(r"\b\d{4}\s?[A-Z]{2}\b", re.I)
FIRE_BARE_CALLSIGN_RE = re.compile(r"(?<!\d)(\d{2})[- ]?(\d{4})(?!\d)")
FIRE_EXT_CALLSIGN_RE = re.compile(r"(?<!\d)(\d{2})[- ](\d{2})[- ](\d{3})(?!\d)")
NL_FIRE_PREFIXES = {f"{i:02d}" for i in range(1, 26)} | {"26", "28"}

# Afkortingen die in meldkamer-/RAV-teksten als zelfstandige plaatscode voorkomen.
# De BAG-index blijft primair; dit is vooral een first-boot/raw-text fallback.
CITY_CODES = {
    "SGRAVH": "Den Haag", "DELFT": "Delft", "DELIER": "De Lier", "LEIDDM": "Leidschendam",
    "VOORBG": "Voorburg", "POELDK": "Poeldijk", "WATERI": "Wateringen", "MAASSL": "Maassluis",
    "SPIJKN": "Spijkenisse", "ROTTDM": "Rotterdam", "BLEISW": "Bleiswijk", "CAPIJS": "Capelle aan den IJssel",
    "SCHIDM": "Schiedam", "KRIMLK": "Krimpen aan de Lek", "REEUWK": "Reeuwijk", "HENDIA": "Hendrik-Ido-Ambacht",
    "ZWIJND": "Zwijndrecht", "STWILL": "St. Willebrord", "RHOON": "Rhoon",
    "OUDNHN": "Oudenhoorn", "HELLVS": "Hellevoetsluis", "HEERJD": "Heerjansdam", "PUTTHK": "Puttershoek",
    "LEERDM": "Leerdam", "BERGAB": "Bergambacht", "LEKKKK": "Lekkerkerk", "OEGSTG": "Oegstgeest",
    "ALPHRN": "Alphen aan den Rijn", "ZEVHZH": "Zevenhuizen", "TRHEIN": "Terheijden", "OUDDRP": "Ouddorp",
    "BREDA": "Breda", "RIEL": "Riel", "TILBRG": "Tilburg", "EINDHV": "Eindhoven", "EEMNES": "Eemnes",
    "AMSTDM": "Amsterdam", "UTRECH": "Utrecht", "GRONIN": "Groningen", "ARNHEM": "Arnhem", "NIJMEG": "Nijmegen",
}
CODE_FOR_CITY = {v.casefold(): k for k, v in CITY_CODES.items()}
PROVINCE_TAIL = {"ZH", "NH", "NB", "LB", "LI", "FR", "GR", "DR", "OV", "UT", "FL", "GLD", "GE", "ZE"}

# Phrases that are stronger than upstream RSS categories.
POLICE_INCIDENT_RE = re.compile(
    r"(?:^|\s)(?:SCHIET(?:PARTIJ|INCIDENT)|STEEK(?:PARTIJ|INCIDENT)|ACHTERVOLGING|OVERVAL|BEROVING|"
    r"INBRAAK(?:\s+BEDRIJF)?|DEMONSTRATIE|VERMISSING|VERDACHTE\s+SITUATIE|AANRIJDING\s+LETSEL|"
    r"ONGEVAL(?:/|\s+)(?:WEGVERVOER(?:/|\s+))?(?:LETSEL|MATERIEEL)|LETSEL)(?:\s|$)", re.I)
FIRE_CONTROL_RE = re.compile(
    r"\b(?:GAARNE\s+)?CONTACT\s+MKB\b|\bTELEFONISCH\s+CONTACT\s+(?:MKB|MELDKAMER\s+BRANDWEER)\b|"
    r"\bCONTACT\s+MELDKAMER\s+BRANDWEER\b|\bKAZERNECOORDINATOR\b|\bHERBEZET\.?/?KAZERNEREN\b|"
    r"\bHERBEZETTING\b|\bHERBEVOORRADING\b|\bGRAAG\s+MELDEN\s+VOOR\s+INZET\b", re.I)
POLICE_CONTROL_RE = re.compile(r"\bCONTACT\s+(?:OC|MELDKAMER)\s+(?:POLITIE|OOST\s+NEDERLAND)\b|\bGMS\s*\d{4,}\b", re.I)
FIRE_WORD_RE = re.compile(
    r"\b(?:BR(?:AND)?\s+(?:WONING|GEBOUW|BIJGEBOUW|INDUSTRIE|ONDERWIJS|BIJEENKOMST|GEZONDHEIDSZORG|"
    r"WINKEL|AGRARISCH|NATUUR|BOS|HEIDE|RIET|BERM|BUITEN|WEGVERVOER|VOERTUIG|SCHEEPVAART|SPOORVERVOER|"
    r"LUCHTVAART|AFVAL|CONTAINER)|OMS\b|PAC\b|STANK/HIND\.?\s+LUCHT|BRANDGERUCHT|ROOKMELDER|CO-MELDER|"
    r"LIFTOPSLUITING|STORMSCHADE|WATEROVERLAST|ASS\.?\s*(?:AMBU|POL(?:ITIE)?)|DIENSTVERLENING|BIJSTAND|"
    r"PERSOON\s+TE\s+WATER|VOERTUIG\s+TE\s+WATER|DIER\s+(?:OP\s+HOOGTE|TE\s+WATER|IN\s+PROBLEMEN)|"
    r"ONGEVAL\s+GEV\.?\s*STOF)\b", re.I)

# Longest/specific patterns first. Used both for classification and for peeling the
# incident grammar off the address/object segment.
INCIDENT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bPROEFALARM\b", re.I), "Proefalarm"),
    (re.compile(r"\bPOSTEN\b.*\b(?:SVP|AJB)\b|\bGRAAG\s+POSTEN\b", re.I), "Ambulancepostering"),
    (re.compile(r"\bGRAAG\s+MELDEN\s+VOOR\s+INZET\b", re.I), "Melden voor inzet"),
    (re.compile(r"\b(?:GAARNE\s+)?CONTACT\s+MKB\b|\bTELEFONISCH\s+CONTACT\s+(?:MKB|MELDKAMER\s+BRANDWEER)\b|\bCONTACT\s+MELDKAMER\s+BRANDWEER\b", re.I), "Contact meldkamer brandweer"),
    (re.compile(r"\bCONTACT\s+MELDKAMER\b", re.I), "Contact meldkamer"),
    (re.compile(r"\bCONTACT\s+(?:OC|MELDKAMER)\s+(?:POLITIE|OOST\s+NEDERLAND)\b|\bGMS\s*\d{4,}\b", re.I), "Contact politiemeldkamer"),
    (re.compile(r"\bINTREKKEN\s+ALARM\s+BRW\b", re.I), "Alarm ingetrokken"),
    (re.compile(r"\bREANIMATIE\b", re.I), "Reanimatie"),
    (re.compile(r"\bSCHIET(?:PARTIJ|INCIDENT)\b", re.I), "Schietincident"),
    (re.compile(r"\bSTEEK(?:PARTIJ|INCIDENT)\b", re.I), "Steekincident"),
    (re.compile(r"\bACHTERVOLGING\b", re.I), "Achtervolging"),
    (re.compile(r"\bOVERVAL\b", re.I), "Overval"),
    (re.compile(r"\bBEROVING\b", re.I), "Beroving"),
    (re.compile(r"\bINBRAAK\s+BEDRIJF\b", re.I), "Inbraak bedrijf"),
    (re.compile(r"\bINBRAAK\b", re.I), "Inbraak"),
    (re.compile(r"\bDEMONSTRATIE\b", re.I), "Demonstratie"),
    (re.compile(r"\bVERMISSING\b", re.I), "Vermissing"),
    (re.compile(r"\bWEGVERKEER\s+AFGEVALLEN\s+LADING\b|\bAFGEVALLEN\s+LADING\b", re.I), "Afgevallen lading"),
    (re.compile(r"\bBIJZONDERE\s+VERKEERSZAKEN\b", re.I), "Bijzondere verkeerszaken"),
    (re.compile(r"\bWEGVERKEER\s+VERKEERSSTREMMING\b|\bVERKEER/WEGVERKEER/VERKEERSSTREMMING\b", re.I), "Verkeersstremming"),
    (re.compile(r"\bONGEVAL(?:/|\s+)WEGVERVOER(?:/|\s+)MATERIEEL\b", re.I), "Ongeval met materiële schade"),
    (re.compile(r"\b(?:AANRIJDING\s+LETSEL|ONGEVAL(?:/|\s+)WEGVERVOER(?:/|\s+)LETSEL|LETSEL)\b", re.I), "Ongeval met letsel"),
    (re.compile(r"\bONGEVAL\s+WEGVERVOER\b[^\n]{0,80}\(\s*MET\s+BRAND\s*\)", re.I), "Ongeval wegvervoer met brand"),
    (re.compile(r"\bONGEVAL\s+WEGVERVOER\b", re.I), "Ongeval wegvervoer"),
    (re.compile(r"\bONGEVAL\s+GEV\.?\s*STOF\b", re.I), "Incident gevaarlijke stoffen"),
    (re.compile(r"\bASS\.?\s*AMBU\b[^\n]{0,80}\(\s*REDDINGSKUSSEN\s*\)", re.I), "Assistentie ambulance met reddingskussen"),
    (re.compile(r"\bASS\.?\s*AMBU\b[^\n]{0,80}\(\s*DEUR\s+OPENEN\s*\)", re.I), "Assistentie ambulance deur openen"),
    (re.compile(r"\bASS\.?\s*AMBU\b[^\n]{0,80}\(\s*(?:AFHIJSEN|TILASSISTENTIE|TILHULP)\s*\)", re.I), "Assistentie ambulance afhijsen"),
    (re.compile(r"\bASS\.?\s*AMBU\b", re.I), "Assistentie ambulance"),
    (re.compile(r"\bONGEVAL\s+(?:AFHIJSEN|TILASSISTENTIE)\b|\bAFHIJSEN\b", re.I), "Afhijsen"),
    (re.compile(r"\bASS\.?\s*POL(?:ITIE)?\b", re.I), "Assistentie politie"),
    (re.compile(r"\bOMS\s+GEV\.?\s*STOF\b", re.I), "OMS gevaarlijke stoffen"),
    (re.compile(r"\bOMS\s+HANDMELDER\b", re.I), "OMS handmelder"),
    (re.compile(r"\bOMS\s+BEHEERSSYSTEEM\b", re.I), "OMS beheerssysteem"),
    (re.compile(r"\bOMS(?:\s+BRANDMELDING)?\b|\bPAC\s+BRANDMELDING\b", re.I), "Automatische brandmelding"),
    (re.compile(r"\bSTANK\s*/?\s*HIND\.?\s+LUCHT\b|\bSTANKOVERLAST\b|\bGAS(?:LUCHT|LEKKAGE|LEK)\b", re.I), "Stank- of gaslucht"),
    (re.compile(r"\bCO-MELDER\b|\bKOOLMONOXIDE\b", re.I), "CO-melding"),
    (re.compile(r"\bROOKMELDER\b", re.I), "Rookmelder"),
    (re.compile(r"\bLUID/OPTISCH\s+ALARM\b", re.I), "Luid/optisch alarm"),
    (re.compile(r"\bBRANDGERUCHT\b", re.I), "Brandgerucht"),
    (re.compile(r"\bNACONTROLE\b", re.I), "Nacontrole"),
    (re.compile(r"\bSTORMSCHADE\b", re.I), "Stormschade"),
    (re.compile(r"\bWATEROVERLAST\b", re.I), "Wateroverlast"),
    (re.compile(r"\bLIFTOPSLUITING\b", re.I), "Liftopsluiting"),
    (re.compile(r"\bHERBEZET\.?/?KAZERNEREN\b|\bHERBEZETTING\b", re.I), "Herbezetting"),
    (re.compile(r"\bHERBEVOORRADING\b", re.I), "Herbevoorrading"),
    (re.compile(r"\bBIJSTAND\b", re.I), "Bijstand"),
    (re.compile(r"\bDIENSTVERLENING\b", re.I), "Dienstverlening"),
    (re.compile(r"\bDIER\s+IN\s+PUT/KELDER\b", re.I), "Dier in put of kelder"),
    (re.compile(r"\bDIER\s+OP\s+HOOGTE\b", re.I), "Dier op hoogte"),
    (re.compile(r"\bDIER\s+TE\s+WATER\b", re.I), "Dier te water"),
    (re.compile(r"\bDIER\s+IN\s+PROBLEMEN\b|\bLOSLOPENDE\s+DIEREN\b", re.I), "Dier in problemen"),
    (re.compile(r"\bPERSOON\s+IN\s+DRIJFZAND\b", re.I), "Persoon in drijfzand"),
    (re.compile(r"\bVOERTUIG\s+TE\s+WATER\b", re.I), "Voertuig te water"),
    (re.compile(r"\bPERSOON\s+TE\s+WATER\b|\bWATERONGEVAL\b|\bONGEVAL\s+OP\s+WATER\b", re.I), "Waterongeval"),
    (re.compile(r"\bSCHIP/WATERSP\.?\s+IN\s+PROBLEMEN\b", re.I), "Vaartuig of watersporter in problemen"),
    (re.compile(r"\bBR\s+WONING\b[^\n]{0,60}\(\s*DAK\s*\)", re.I), "Dakbrand"),
    (re.compile(r"\bBR\s+INDUSTRIE\b|\bINDUSTRIEBRAND\b", re.I), "Industriebrand"),
    (re.compile(r"\bBR\s+ONDERWIJS\b", re.I), "Brand onderwijs"),
    (re.compile(r"\bBR\s+BIJEENKOMST\b", re.I), "Brand bijeenkomstgebouw"),
    (re.compile(r"\bBR\s+GEZONDHEIDSZORG\b", re.I), "Brand gezondheidszorg"),
    (re.compile(r"\bBR\s+AGRARISCH\b", re.I), "Agrarische brand"),
    (re.compile(r"\bBR\s+WINKEL\b", re.I), "Winkelbrand"),
    (re.compile(r"\bBR\s+WONING\b|\bWONINGBRAND\b", re.I), "Woningbrand"),
    (re.compile(r"\bBR\s+(?:GEBOUW|BIJGEBOUW|SCHUUR|LOODS)\b|\bGEBOUWBRAND\b", re.I), "Gebouwbrand"),
    (re.compile(r"\bBR\s+(?:NATUUR|BOS|HEIDE|RIET|BOSSAGE|BERM(?:/BOSS?CH?AGE)?)\b|\bNATUURBRAND\b", re.I), "Natuurbrand"),
    (re.compile(r"\bBR\s+SCHEEPVAART\b", re.I), "Brand scheepvaart"),
    (re.compile(r"\bBR\s+SPOORVERVOER\b", re.I), "Brand spoorvervoer"),
    (re.compile(r"\bBR\s+LUCHTVAART\b", re.I), "Brand luchtvaart"),
    (re.compile(r"\bBR\s+(?:WEGVERVOER|VOERTUIG)\b|\bVOERTUIGBRAND\b", re.I), "Voertuigbrand"),
    (re.compile(r"\bBR\s+(?:AFVAL|VUILNIS|CONTAINER)\b", re.I), "Afval- of containerbrand"),
    (re.compile(r"\bBR\s+BUITEN\b|\bBUITENBRAND\b", re.I), "Buitenbrand"),
]

# Prefix grammar. Unlike the old one this includes national building-use classes and
# control messages, and it accepts slash taxonomies.
LOCATION_INCIDENT_PREFIXES = [
    r"ONGEVAL(?:/|\s+)WEGVERVOER(?:/|\s+)(?:LETSEL|MATERIEEL)", r"ONGEVAL(?:/|\s+)WEGVERVOER",
    r"ONGEVAL\s+GEV\.?\s*STOF", r"ONGEVAL\s+OP\s+WATER", r"ONGEVAL\s+(?:AFHIJSEN|TILASSISTENTIE)", r"ONGEVAL",
    r"BR(?:AND)?\s+(?:GEZONDHEIDSZORG|ONDERWIJS|BIJEENKOMST|INDUSTRIE|AGRARISCH|WINKEL|WONING|GEBOUW|BIJGEBOUW|SCHUUR|LOODS|"
    r"NATUUR|BOS|HEIDE|RIET|BOSSAGE|BERM(?:/BOSS?CH?AGE)?|SCHEEPVAART|SPOORVERVOER|LUCHTVAART|WEGVERVOER|VOERTUIG|AFVAL|VUILNIS|CONTAINER|BUITEN)",
    r"OMS(?:\s+(?:BRANDMELDING|BEHEERSSYSTEEM|HANDMELDER|GEV\.?\s*STOF))?", r"PAC(?:\s+BRANDMELDING)?",
    r"STANK\s*/?\s*HIND\.?\s+LUCHT", r"STANKOVERLAST", r"GAS(?:LUCHT|LEKKAGE|LEK)", r"CO-MELDER", r"ROOKMELDER",
    r"BRANDGERUCHT", r"NACONTROLE", r"STORMSCHADE", r"WATEROVERLAST", r"LIFTOPSLUITING", r"LUID/OPTISCH\s+ALARM",
    r"ASS\.?\s*(?:AMBU|POL(?:ITIE)?)", r"REANIMATIE", r"AFHIJSEN", r"TILASSISTENTIE", r"TILHULP", r"DIENSTVERLENING", r"BIJSTAND",
    r"PERSOON\s+(?:TE\s+WATER|IN\s+DRIJFZAND)", r"VOERTUIG\s+TE\s+WATER", r"DIER\s+(?:TE\s+WATER|OP\s+HOOGTE|IN\s+PROBLEMEN|IN\s+PUT/KELDER)", r"LOSLOPENDE\s+DIEREN",
    r"SCHIP/WATERSP\.?\s+IN\s+PROBLEMEN", r"PROEFALARM", r"HERBEZET\.?/?KAZERNEREN", r"HERBEZETTING", r"HERBEVOORRADING",
    r"WEGVERKEER\s+(?:VERKEERSSTREMMING|AFGEVALLEN\s+LADING)", r"BIJZONDERE\s+VERKEERSZAKEN",
    r"SCHIET(?:PARTIJ|INCIDENT)", r"STEEK(?:PARTIJ|INCIDENT)", r"ACHTERVOLGING", r"OVERVAL", r"BEROVING", r"INBRAAK(?:\s+BEDRIJF)?",
    r"DEMONSTRATIE", r"VERMISSING", r"VERDACHTE\s+SITUATIE", r"AANRIJDING\s+LETSEL", r"LETSEL",
]
LOCATION_INCIDENT_PREFIX_RE = re.compile(r"^(?:" + "|".join(LOCATION_INCIDENT_PREFIXES) + r")\b\s*", re.I)


def _norm(value: str) -> str:
    fn = _NS.get("normalize_space")
    return fn(str(value or "")) if callable(fn) else re.sub(r"\s+", " ", str(value or "")).strip()


def _city_key(value: str) -> str:
    fn = _NS.get("_nl_place_match_key") or _NS.get("normalize_city_token")
    return fn(value) if callable(fn) else re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _display(value: str) -> str:
    fn = _NS.get("normalize_location_display_case")
    return fn(value) if callable(fn) else _norm(value)


def _categories_service(categories: list[str]) -> str:
    aliases = _NS.get("SERVICE_ALIASES", {})
    for cat in categories or []:
        key = _norm(cat).casefold()
        if key in aliases:
            return aliases[key]
    return ""


def _gazetteer_anywhere(raw: str) -> str:
    key = _city_key(raw)
    if not key:
        return ""
    display = _NS.get("_NL_PLACE_DISPLAY", {})
    sorted_places = _NS.get("_NL_PLACE_SORTED", [])
    # Longest names are already first. Prefer the right-most valid occurrence so an
    # object named after another town does not beat the incident locality at the tail.
    best = None
    for place_key in sorted_places:
        m = list(re.finditer(rf"(?<!\w){re.escape(place_key)}(?!\w)", key, re.I))
        if not m:
            continue
        hit = m[-1]
        cand = (hit.end(), len(place_key), display.get(place_key, ""))
        if best is None or cand[:2] > best[:2]:
            best = cand
    return _norm(best[2]) if best else ""


def _city_code(raw: str) -> tuple[str, str]:
    tokens = re.findall(r"(?<![A-Z0-9])([A-Z]{5,7})(?![A-Z0-9])", raw.upper())
    for token in reversed(tokens):
        if token in CITY_CODES:
            return CITY_CODES[token], token
    return "", ""


def _strip_tail_ids(s: str) -> str:
    s = _norm(s)
    # Compact ambulance form: ``straat plaatscode : 16155 mmt2``. The colon
    # makes the number operational bookkeeping rather than a house number.
    s = re.sub(r"\s*:\s*\d{4,7}(?:\s+MMT\s*\d+)?\s*$", "", s, flags=re.I)
    # BON/RIT/GMS/ICnum/regio are bookkeeping boundaries, never the address.
    s = re.sub(r"\s+IC\s*NUM\s*[:#-]?\s*[A-Z0-9-]*\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+ICNUM\s*[:#-]?\s*[A-Z0-9-]*\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+(?:BON|RIT)\s*:?[ ]*\d+[A-Z0-9-]*\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s+GMS\s*\d+\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s*/?\s*(?:REGIO|REG)\s*\d+\b.*$", "", s, flags=re.I)
    # A plain 4-6 digit job number is common after Amsterdam/Limburg ambulance rows.
    s = re.sub(r"(?<=\D)\s+\d{4,6}\s*$", "", s)
    # Real fire callsigns at the tail; accept only Dutch region prefixes.
    while True:
        before = s
        s = re.sub(r"\s+\d{2}[- ]\d{2}[- ]\d{3}\s*$", "", s)
        m = re.search(r"\s+(\d{2})[- ]?(\d{4})\s*$", s)
        if m and m.group(1) in NL_FIRE_PREFIXES:
            s = s[:m.start()].rstrip()
        if s == before:
            break
    return _norm(s.strip(" ,-–—:#"))


def _strip_city(s: str, city: str, code: str = "", *, prefer_tail: bool = True) -> str:
    s = _norm(s)
    if code:
        s = re.sub(rf"(?<![\wÀ-ÿ-]){re.escape(code)}(?![\wÀ-ÿ-])", " ", s, flags=re.I)
    if city:
        forms = [city]
        if city.casefold() == "den haag": forms += ["'s-Gravenhage", "s-Gravenhage", "SGRAVH"]
        for c, name in CITY_CODES.items():
            if name.casefold() == city.casefold():
                forms.append(c)
        # Remove the right-most locality occurrence, preserving similarly named object text earlier.
        matches = []
        for form in forms:
            for m in re.finditer(rf"(?<![\wÀ-ÿ-]){re.escape(form)}(?![\wÀ-ÿ-])", s, re.I):
                matches.append((m.start(), m.end()))
        if matches:
            a, b = (max(matches, key=lambda x: x[1]) if prefer_tail else min(matches, key=lambda x: x[0]))
            s = s[:a] + " " + s[b:]
    return _norm(s)


def _strip_front_metadata(raw: str, *, service: str = "") -> str:
    s = _norm(raw)
    s = re.sub(r"^\s*(?:P\s*[1-5]|PRIO\s*[1-5])\b\s*", "", s, flags=re.I)
    if service == "ambulance":
        s = re.sub(r"^\s*(?:A[012]|B[12])\b\s*", "", s, flags=re.I)
    s = FIRE_CHANNEL_RE.sub(" ", s, count=1)
    # Numeric P-bundle is police bookkeeping, not a fire callsign.
    if service == "politie":
        s = re.sub(r"^\s*\d{4,7}\b\s*", "", s)
    # DIA variants can appear before or after AMBU/unit.
    for _ in range(3):
        before = s
        s = re.sub(r"^\s*\(?\s*DIA(?:\s*:\s*(?:JA|NEE|BA|[A-Z]{1,3}))?\s*\)?\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*(?:AMBU|AMBULANCE)\b\s*", "", s, flags=re.I)
        if service == "ambulance":
            s = re.sub(r"^\s*\d{5}\b\s*[-:]?\s*", "", s)  # 07127 / 17126 / 13166
        if s == before:
            break
    # Scale/GRIP and purely operational qualifiers at the front.
    for _ in range(8):
        before = s
        s = re.sub(r"^\s*(?:KLEINE|MIDDEL|GROTE|ZEER\s+GROTE|ZEER\s+GR\.?)\s+(?:BRAND|BR)\b\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*\(\s*(?:KLEINE|MIDDEL|GROTE|ZEER\s+(?:GROTE|GR\.?))\s+(?:BRAND|BR)\s*\)\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*\(\s*GRIP\s*[0-5]\s*\)\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*\(\s*(?:AFSTEMVERZOEK|OEFENING|TESTMELDING|INTREKKEN\s+ALARM\s+BRW)\s*\)\s*", "", s, flags=re.I)
        s = re.sub(r"^\s*VE\s*:\s*\d+\b\s*", "", s, flags=re.I)
        if s == before:
            break
    return _norm(s)


def _strip_control_prefix(s: str) -> str:
    patterns = [
        r"^(?:GAARNE\s+)?CONTACT\s+MKB\b", r"^TELEFONISCH\s+CONTACT\s+(?:MKB|MELDKAMER\s+BRANDWEER)\b",
        r"^CONTACT\s+MELDKAMER(?:\s+BRANDWEER)?\b", r"^GRAAG\s+CONTACT\s+(?:OC|MELDKAMER)\s+OOST\s+NEDERLAND\b",
        r"^GRAAG\s+MELDEN\s+VOOR\s+INZET\b",
    ]
    for pat in patterns:
        s2 = re.sub(pat, "", s, flags=re.I).strip(" ,-–—:")
        if s2 != s:
            # Control rows often carry a role in parentheses directly after MKB,
            # e.g. ``Contact MKB (TD) Kazerne ...``. It is metadata, not address.
            s2 = re.sub(r"^\s*\([^)]{1,40}\)\s*", "", s2)
            s2 = re.sub(r"^(?:KAZERNECOORDINATOR|OVD-BZ|OVD-B|HOVD-B|AGS)\b[, :;-]*", "", s2, flags=re.I)
            return _norm(s2)
    return s


def _strip_incident_prefix(s: str) -> str:
    for _ in range(6):
        before = s
        s = LOCATION_INCIDENT_PREFIX_RE.sub("", s, count=1)
        # Parenthetical operational qualifier directly after the incident type.
        s = re.sub(r"^\s*\([^)]{1,90}\)\s*", "", s, count=1)
        s = re.sub(r"^\s*VE\s*:\s*\d+\b\s*", "", s, flags=re.I)
        s = _norm(s)
        if s == before:
            break
    return s


def _cleanup_location(s: str) -> str:
    s = _norm(s)
    s = POSTCODE_RE_LOCAL.sub(" ", s)
    # Remove city abbreviations remaining after full city removal.
    for code in CITY_CODES:
        s = re.sub(rf"(?<![\wÀ-ÿ-]){re.escape(code)}(?![\wÀ-ÿ-])", " ", s, flags=re.I)
    s = re.sub(r"\b(?:BON|RIT|VWS)\b\s*[:#-]?\s*\d+\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+VWS\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+[hH]\s*$", "", s)
    s = re.sub(r"\s+(?:ZH|NH|NB|LB|LI|FR|GR|DR|OV|UT|FL|GLD|GE|ZE)\s*$", "", s, flags=re.I)
    collapse = _NS.get("_collapse_location_repeats")
    if callable(collapse):
        s = collapse(s)
    return _display(_norm(s.strip(" ,-–—/:")))


def is_fire_dispatch_context_v455(title: str, summary: str, units: list[str] | None = None) -> bool:
    raw = _norm(" ".join([title or "", summary or "", " ".join(units or [])]))
    if not raw:
        return False
    if AMB_RE.search(title or "") or AMB_RE.search(summary or ""):
        # Baarle exception is handled by the discipline firewall, not by calling an A1 row fire.
        return False
    if POLICE_BUNDLE_RE_V455.search(title or "") and POLICE_INCIDENT_RE.search(raw):
        return False
    if ICNUM_RE.search(raw) or POLICE_SLASH_RE_V455.search(raw) or POLICE_CONTROL_RE.search(raw):
        return False
    if FIRE_CHANNEL_RE.search(raw):
        return True
    if FIRE_CONTROL_RE.search(raw):
        return True
    if re.search(r"^\s*(?:P\s*[1-5]\s+)?(?:BR(?:AND)?\b|OMS\b|PAC\b)", raw, re.I):
        return True
    if FIRE_WORD_RE.search(raw):
        # Require a P-priority, a Dutch callsign, or explicit brandweer text for ambiguous words.
        if re.match(r"^\s*(?:P\s*[1-5])\b", raw, re.I) or re.search(r"\bBRANDWEER\b", raw, re.I):
            return True
        for m in FIRE_EXT_CALLSIGN_RE.finditer(raw):
            if m.group(1) in NL_FIRE_PREFIXES:
                return True
        for m in FIRE_BARE_CALLSIGN_RE.finditer(raw):
            if m.group(1) in NL_FIRE_PREFIXES:
                return True
    orig = _ORIG.get("is_fire_dispatch_context")
    try:
        return bool(orig(title, summary, units)) if orig else False
    except Exception:
        return False


def detect_service_v455(title: str, summary: str, categories: list[str]) -> str:
    raw = _norm(f"{title} {summary}")
    if AMB_RE.search(title or "") or AMB_RE.search(summary or ""):
        return "ambulance"
    if re.match(r"^\s*(?:GRAAG\s+)?POSTEN\b", raw, re.I) or re.search(r"\bPOSTEN\b.*\b(?:SVP|AJB)\b", raw, re.I):
        return "ambulance"
    if POLICE_BUNDLE_RE_V455.search(title or "") or ICNUM_RE.search(raw) or POLICE_SLASH_RE_V455.search(raw):
        return "politie"
    if POLICE_CONTROL_RE.search(raw):
        return "politie"
    if RWS_RE.search(title or ""):
        # Keep historic UI behaviour: road-management/prio-4 rows live with police-like operational traffic.
        return "politie"
    if re.match(r"^\s*(?:AANRIJDING\s+LETSEL|ONGEVAL(?:/|\s+)(?:WEGVERVOER(?:/|\s+))?(?:LETSEL|MATERIEEL)|"
                r"SCHIET(?:PARTIJ|INCIDENT)|STEEK(?:PARTIJ|INCIDENT)|ACHTERVOLGING|LOSLOPENDE\s+DIEREN)\b", raw, re.I):
        return "politie"
    if is_fire_dispatch_context_v455(title, summary):
        return "brandweer"
    cat_service = _categories_service(categories)
    if cat_service:
        return cat_service
    if re.search(r"\b(?:LIFELINER|TRAUMAHELI|MMT)\b", raw, re.I):
        return "lifeliner"
    if re.search(r"\b(?:KNRM|KUSTWACHT)\b", raw, re.I):
        return "knrm"
    orig = _ORIG.get("detect_service")
    try:
        return orig(title, summary, categories) if orig else "overig"
    except Exception:
        return "overig"


def detect_priority_v455(title: str, summary: str) -> str:
    orig = _ORIG.get("detect_priority")
    try:
        value = orig(title, summary) if orig else ""
    except Exception:
        value = ""
    if value:
        return value
    raw = _norm(f"{title} {summary}")
    m = re.match(r"^\s*([1-5])\s+", raw)
    if m and (ICNUM_RE.search(raw) or POLICE_INCIDENT_RE.search(raw)):
        return f"P{m.group(1)}"
    m = re.search(r"\bPRIO\s*([1-5])\b", raw, re.I)
    return f"P{m.group(1)}" if m else ""


def _structural_ambulance_city(raw: str) -> str:
    """Recover locality from A/B rows when the BAG cache is not ready yet."""
    s = _norm(raw)
    if not AMB_RE.search(s):
        return ""
    # Comma form: A0 Ambu 08993 Tilburg, Eduard Meijerslaan, regio 20 ...
    m = re.match(r"^\s*(?:A[012]|B[12])\b(?:\s*\([^)]*\))*\s*(?:AMBU|AMBULANCE)?\s*\d{0,5}\s+([^,]{2,60}),", s, re.I)
    if m:
        first = _norm(m.group(1)).strip(" -")
        if first and not re.search(r"(?:straat|laan|weg|singel|kade|dreef|plein|pad|hof|dijk)$", first, re.I):
            return _display(first)
    # Remove tail metadata before taking the pre-RIT segment.
    core = re.sub(r"\s*/?\s*(?:REGIO|REG)\s*\d+\b.*$", "", s, flags=re.I)
    m = re.search(r"\bRIT\s*:?\s*\d+\b", core, re.I)
    if m:
        left = core[:m.start()]
        left = re.sub(r"^\s*(?:A[012]|B[12])\b", "", left, flags=re.I)
        left = re.sub(r"\b(?:AMBU|AMBULANCE)\b", " ", left, flags=re.I)
        left = re.sub(r"\bDIA(?:\s*:\s*(?:JA|NEE|BA|[A-Z]{1,3}))?\b", " ", left, flags=re.I)
        left = re.sub(r"^\s*\d{5}\b\s*[-:]?", "", _norm(left))
        left = _norm(left.strip(" -,:"))
        known = _gazetteer_anywhere(left)
        if known:
            return known
        words = left.split()
        if len(words) == 1:
            return _display(left)
        # street/object + locality. Grow a multi-word locality left across Dutch connectors.
        streetish = re.search(r"(?:straat|laan|weg|singel|kade|dreef|plein|pad|hof|dijk|gracht|steeg|baan|allee|park|erf|plantsoen)$", words[0], re.I)
        if streetish and len(words) >= 2:
            start = len(words) - 1
            connectors = {"aan","den","de","der","van","het","op","in","en","ter","ten"}
            while start > 1 and words[start-1].casefold().strip(".,") in connectors:
                start -= 1
                if start > 1 and words[start].casefold() in {"aan","van","op","in"}:
                    start -= 1
            return _display(" ".join(words[start:]))
    # A1 <street> <city> <jobid> / regio N. Useful for Amsterdam/Limburg/MMT raw rows.
    core = re.sub(r"\s*/?\s*(?:REGIO|REG)\s*\d+\b.*$", "", s, flags=re.I)
    core = re.sub(r"\s+\d{4,6}\s*$", "", core)
    core = re.sub(r"^\s*(?:A[012]|B[12])\b(?:\s*\([^)]*\))*\s*(?:AMBU|AMBULANCE)?\s*\d{0,5}\s*", "", core, flags=re.I)
    core = _norm(core.strip(" -,:"))
    known = _gazetteer_anywhere(core)
    if known:
        return known
    words = core.split()
    if len(words) >= 2 and re.search(r"(?:straat|laan|weg|singel|kade|dreef|plein|pad|hof|dijk|gracht|steeg|baan|allee|park|erf|plantsoen)$", words[0], re.I):
        start=len(words)-1
        connectors={"aan","den","de","der","van","het","op","in","en","ter","ten"}
        while start>1 and words[start-1].casefold().strip(".,") in connectors:
            start-=1
        return _display(" ".join(words[start:]))
    return ""


def _plausible_old_city(value: str) -> bool:
    value = _norm(value)
    if not value:
        return False
    invalid_city = {"brandweer","politie","ambulance","ambu","meldkamer","mkb","contact","kazernecoordinator","regio","bon","rit","dia","vws"}
    if value.casefold() in invalid_city or value.upper() in PROVINCE_TAIL:
        return False
    # Legacy inference may leave a province suffix attached to the locality,
    # e.g. ``Velp GE``. That is bookkeeping, not part of the woonplaats.
    if any(re.search(rf"\s+{re.escape(code)}$", value, re.I) for code in PROVINCE_TAIL):
        return False
    if re.fullmatch(r"(?:MMT|BON|RIT|GMS)\s*\d*", value, re.I):
        return False
    if re.fullmatch(r"[A-Z]{1,3}", value):
        return False
    return True


def infer_city_v455(categories: list[str], title: str) -> str:
    # Preserve explicit feed category semantics first, unless the legacy parser
    # accidentally returned bookkeeping such as GE/MMT2/BON as a locality.
    orig = _ORIG.get("infer_city")
    try:
        old = _norm(orig(categories, title)) if orig else ""
    except Exception:
        old = ""
    if _plausible_old_city(old):
        return old

    raw = _norm(title)
    any_city = _gazetteer_anywhere(raw)
    if any_city:
        return any_city
    coded, _code = _city_code(raw)
    if coded:
        return coded
    structural_ambu = _structural_ambulance_city(raw)
    if structural_ambu:
        return structural_ambu

    # RIT form: the locality immediately before 'rit' after unit/DIA bookkeeping.
    m = re.search(r"^\s*(?:A[012]|B[12])\b.*?\b([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’ -]{1,45})\s+RIT\s*:?\s*\d+\b", raw, re.I)
    if m:
        candidate = _norm(m.group(1)).strip(" -,")
        # Keep only tail after DIA/unit markers.
        candidate = re.sub(r"^.*?\b(?:DIA|AMBU|AMBULANCE)\b", "", candidate, flags=re.I).strip(" -,")
        candidate = re.sub(r"^\d{5}\s*[-:]?\s*", "", candidate)
        candidate = re.sub(r"\s+(?:ZH|NH|NB|LB|LI|FR|GR|DR|OV|UT|FL|GLD|GE|ZE)\s*$", "", candidate, flags=re.I)
        words = candidate.split()
        if 1 <= len(words) <= 5:
            return _display(candidate)
    # A1 - De Lutte / A1 - Eemnes
    m = re.match(r"^\s*(?:A[012]|B[12])\b\s*(?:AMBU\s+\d{5}\s*)?[-–—]\s*([A-Za-zÀ-ÿ'’ -]{2,50})\s*$", raw, re.I)
    if m:
        return _display(m.group(1))
    # Fire tail 'Ouddorp ZH 179088' – strip province suffix and callsigns, then use final token(s).
    if is_fire_dispatch_context_v455(raw, ""):
        tail = raw
        tail = re.sub(r"(?:\s+(?:\d{2}[- ]\d{2}[- ]\d{3}|\d{6}))+\s*$", "", tail)
        tail = re.sub(r"\s+(?:ZH|NH|NB|LB|LI|FR|GR|DR|OV|UT|FL|GLD|GE|ZE)\s*$", "", tail, flags=re.I)
        # If a known short place appears at the very end, use it. Avoid guessing an object word.
        any_tail = _gazetteer_anywhere(tail)
        if any_tail:
            return any_tail
    return old if _plausible_old_city(old) else ""


def infer_message_city_v455(categories: list[str], title: str, article_url: str = "", source_url: str = "") -> str:
    # 112-nu article URL is exceptionally reliable; preserve old resolver first.
    orig = _ORIG.get("infer_message_city")
    try:
        old = _norm(orig(categories, title, article_url, source_url)) if orig else ""
    except Exception:
        old = ""
    if _plausible_old_city(old):
        return old
    return infer_city_v455(categories, title) or (old if _plausible_old_city(old) else "")


def _ambulance_location(raw: str, city: str) -> str:
    _city, code = _city_code(raw)
    s = _strip_front_metadata(raw, service="ambulance")
    # Explicit 2-2-3 / hyphenated fire callsigns are bookkeeping and never part
    # of an ambulance address. Do *not* strip arbitrary bare six-digit numbers
    # here: BON/RIT/job ids (e.g. 137443 / 271528) have the same shape. Bare
    # cross-discipline callsigns are removed later only when they occur at the
    # dispatch tail and carry a valid Dutch fire-region prefix.
    s = re.sub(r"(?<!\d)\d{2}[- ]\d{2}[- ]\d{3}(?!\d)", " ", s)
    s = re.sub(r"(?<!\d)(\d{2})-(\d{4})(?!\d)", " ", s)
    s = _norm(s)
    # A0/A1 can contain semantic prefixes before the address.
    s = re.sub(r"^(?:AED\s*,?\s*)?(?:REANIMATIE\b\s*)", "", s, flags=re.I)
    s = _strip_incident_prefix(s)
    s = re.sub(r"^AMBULANCEPOST\b\s*", "", s, flags=re.I)
    s = _strip_tail_ids(s)
    # Some RAVs put a compact dispatch/place code directly after the written
    # locality (e.g. ``velp ge`` / ``dalem donc``). Remove that token before the
    # city itself so it cannot become the address. Known mapped codes are handled
    # by _strip_city; this generic form is only accepted immediately after city.
    if city:
        s = re.sub(rf"(?<![\wÀ-ÿ-]){re.escape(city)}(?![\wÀ-ÿ-])\s+[A-Za-z]{{2,7}}(?=\s*(?:$|BON\b|RIT\b|REGIO\b|REG\b|:))", city, s, flags=re.I)
    s = _strip_city(s, city, code)
    s = _strip_tail_ids(s)
    # stand-alone DIA may survive after unit stripping
    s = re.sub(r"^\s*DIA(?:\s*:\s*(?:JA|NEE|BA|[A-Z]{1,3}))?\b\s*", "", s, flags=re.I)
    s = re.sub(r"^\s*[-–—]\s*", "", s)
    # If the line only identified the city, don't invent an address.
    return _cleanup_location(s)


POLICE_TAIL_TAXONOMY_RE = re.compile(
    r"\s+(?:ONGEVAL\s+WEGVERVOER\s+(?:LETSEL|MATERIEEL)|WEGVERKEER\s+VERKEERSSTREMMING|"
    r"BIJZONDERE\s+VERKEERSZAKEN)(?:\s*\([^)]*\))?\s*$", re.I,
)

def _police_tail_location(raw: str, city: str) -> str:
    _coded_city, code = _city_code(raw)
    s = re.sub(r"^\s*PRIO\s*[1-5]\b\s*", "", raw, flags=re.I)
    s = POLICE_TAIL_TAXONOMY_RE.sub("", s)
    s = _strip_city(s, city, code)
    # Feed-specific city code can be unknown to our static map; in this exact
    # grammar it is the compact token directly before the taxonomy and therefore
    # safe to discard from the address.
    s = re.sub(r"\s+[A-Za-z]{5,7}\s*$", "", s)
    return _cleanup_location(s)


def _rws_location(raw: str, city: str) -> str:
    _city, code = _city_code(raw)
    s = re.sub(r"^\s*PRIO\s*[1-5]\b\s*", "", raw, flags=re.I)
    # taxonomy is at the end in RWS rows.
    s = re.sub(r"\s+(?:WEGVERKEER\s+(?:VERKEERSSTREMMING|AFGEVALLEN\s+LADING)|BIJZONDERE\s+VERKEERSZAKEN)\b.*$", "", s, flags=re.I)
    s = _strip_city(s, city, code)
    # Unknown RWS city abbreviations (e.g. REEUWK) occur as the final compact
    # token after the hectometer. Remove only in a road/hectometer-shaped row.
    if re.search(r"\b[AN]\d{1,3}\b|\d{1,3}[,.]\d", s, re.I):
        s = re.sub(r"\s+[A-Za-z]{5,7}\s*$", "", s)
    s = re.sub(r"\s+[a-z]\s*$", "", s, flags=re.I)  # hectometer side suffix
    return _cleanup_location(s)


def infer_structured_location_v455(title: str, city: str) -> str:
    raw = _norm(title)
    if not raw:
        return ""
    service = detect_service_v455(raw, "", [])
    if service == "ambulance" and (re.match(r"^\s*(?:GRAAG\s+)?POSTEN\b", raw, re.I) or re.search(r"\bPOSTEN\b.*\b(?:SVP|AJB)\b", raw, re.I)):
        return _display(city) if city else ""
    if AMB_RE.search(raw):
        return _ambulance_location(raw, city)
    if RWS_RE.search(raw):
        return _rws_location(raw, city)
    if re.match(r"^\s*PRIO\s*[1-5]\b", raw, re.I) and POLICE_TAIL_TAXONOMY_RE.search(raw):
        return _police_tail_location(raw, city)

    _coded_city, city_code = _city_code(raw)
    s = _strip_front_metadata(raw, service=service)
    s = _strip_tail_ids(s)

    # Police ICnum/slash have taxonomy in a different position.
    slash_mode = False
    if POLICE_SLASH_RE_V455.search(raw):
        slash_mode = True
        s = re.sub(r"^\s*(?:ONGEVAL|VERKEER|POLITIE)(?:/[^\s]+){1,4}\s+PRIO\s*[1-5]\b\s*", "", raw, flags=re.I)
        s = _strip_tail_ids(s)
    elif ICNUM_RE.search(raw):
        s = re.sub(r"^\s*[1-5]\s+", "", raw)
        s = _strip_tail_ids(s)
    elif service == "politie" and POLICE_BUNDLE_RE_V455.search(raw):
        s = re.sub(r"^\s*P\s*[1-5]\s+\d{4,7}\b\s*", "", raw, flags=re.I)
        s = _strip_tail_ids(s)

    s = _strip_control_prefix(s)
    s = _strip_incident_prefix(s)
    # Some rows place scale before incident type; peel once more after incident removal.
    s = _strip_front_metadata(s, service="")
    s = _strip_incident_prefix(s)
    s = _strip_city(s, city, city_code, prefer_tail=not slash_mode)
    s = _strip_tail_ids(s)
    return _cleanup_location(s)


def infer_location_v455(title: str, summary: str, city: str) -> str:
    structured = infer_structured_location_v455(title, city)
    if structured:
        # Never return only a remaining city abbreviation / province suffix / job id.
        if structured.upper() in PROVINCE_TAIL or structured.upper() in CITY_CODES or re.fullmatch(r"\d{4,7}", structured):
            structured = ""
    if structured:
        return structured
    orig = _ORIG.get("infer_location")
    try:
        return orig(title, summary, city) if orig else _display(city)
    except Exception:
        return _display(city)


def infer_units_v455(summary: str, title: str = "") -> list[str]:
    orig = _ORIG.get("infer_units")
    try:
        units = list(orig(summary, title)) if orig else []
    except Exception:
        units = []
    raw = _norm(f"{title} {summary}")
    service = detect_service_v455(title, summary, [])
    baarle_ambu = service == "ambulance" and bool(AMB_RE.search(title or "")) and bool(re.search(r"\bBAARLE[-\s]?(?:NASSAU|HERTOG)\b", raw, re.I))
    if service != "brandweer" and not baarle_ambu:
        return list(dict.fromkeys(units))[:30]

    # Add only Dutch-region callsigns. For ambulance rows this path is reached
    # exclusively for the operational Baarle-Nassau/Hertog exception. This blocks unrelated six-digit incident IDs
    # while still allowing mutual aid from any safety region.
    def digits_key(value: str) -> str:
        return re.sub(r"\D", "", _norm(value))
    seen_digits = {digits_key(x) for x in units if digits_key(x)}
    for m in FIRE_EXT_CALLSIGN_RE.finditer(raw):
        if m.group(1) in NL_FIRE_PREFIXES:
            value=f"{m.group(1)}-{m.group(2)}-{m.group(3)}"; key=digits_key(value)
            if key not in seen_digits:
                units.append(value); seen_digits.add(key)
    for m in FIRE_BARE_CALLSIGN_RE.finditer(raw):
        if m.group(1) in NL_FIRE_PREFIXES:
            digits = m.group(1) + m.group(2)
            if POLICE_BUNDLE_RE_V455.search(title or "") and digits in re.sub(r"\D", "", POLICE_BUNDLE_RE_V455.search(title).group(0)):
                continue
            if digits not in seen_digits:
                units.append(digits); seen_digits.add(digits)
    # Also collapse old-parser duplicates with different punctuation.
    out=[]; seen=set()
    for unit in units:
        key=digits_key(unit) or _norm(unit).casefold()
        if key in seen: continue
        seen.add(key); out.append(_norm(unit))
    return out[:30]


def incident_type_v455(title: str, summary: str = "") -> str:
    raw = _norm(f"{title} {summary}")
    if not raw:
        return "P2000-melding"
    is_exercise = bool(re.search(r"\bOEFENING\b", raw, re.I))
    is_test = bool(re.search(r"\bTESTMELDING\b", raw, re.I))
    for regex, label in INCIDENT_RULES:
        if regex.search(raw):
            if is_exercise and label not in {"Proefalarm", "Alarm ingetrokken"}:
                return f"Oefening – {label.lower()}"
            if is_test and label not in {"Proefalarm", "Alarm ingetrokken"}:
                return f"Testmelding – {label.lower()}"
            # Stormschade subtype remains useful.
            if label == "Stormschade":
                m = re.search(r"\(\s*SOORT\s+GEVAAR\s*:\s*([^)]{2,60})\)", raw, re.I)
                if m:
                    return f"Stormschade door {_norm(m.group(1)).lower()}"
            return label
    if is_exercise:
        return "Oefening"
    if is_test:
        return "Testmelding"
    if re.search(r"\bOPEN\s+U\b", raw, re.I):
        return "Operationele oproep"
    # MMT fallback from old parser.
    orig = _ORIG.get("incident_type_label")
    try:
        return orig(title, summary) if orig else "P2000-melding"
    except Exception:
        return "P2000-melding"


def parser_confidence_v455(title: str, summary: str, categories: list[str], service: str,
                           priority: str, city: str, location: str, units: list[str], scale: str = ""):
    orig = _ORIG.get("parser_confidence_details")
    try:
        score, notes = orig(title, summary, categories, service, priority, city, location, units, scale) if orig else (0, [])
    except Exception:
        score, notes = 0, []
    score = int(score or 0); notes = list(notes or [])
    raw = _norm(f"{title} {summary}")
    if FIRE_CHANNEL_RE.search(raw) and service == "brandweer":
        score += 5; notes.append("landelijk meldkamerkanaal herkend")
    if CITY_CODES and any(re.search(rf"(?<!\w){re.escape(c)}(?!\w)", raw, re.I) for c in CITY_CODES) and city:
        score += 3; notes.append("meldkamer-plaatscode herkend")
    if incident_type_v455(title, summary) != "P2000-melding":
        score += 3
    if location and re.search(r"\b(?:BON|RIT|ICNUM|GMS)\b", location, re.I):
        score -= 18; notes.append("locatie bevat mogelijk resterende boekhouding")
    return max(0, min(100, score)), list(dict.fromkeys(notes))


def install_national_parser(namespace: dict) -> None:
    """Install v4.5.5 parser overrides into the already-built runtime module."""
    global _NS, _ORIG
    if namespace.get("_PARSER_NL_V455_INSTALLED"):
        return
    _NS = namespace
    names = [
        "is_fire_dispatch_context", "detect_service", "detect_priority", "infer_city", "infer_message_city",
        "_infer_structured_dispatch_location", "infer_location", "infer_units", "incident_type_label", "parser_confidence_details",
    ]
    _ORIG = {name: namespace.get(name) for name in names if callable(namespace.get(name))}

    namespace["FIRE_DISPATCH_CODE_RE"] = FIRE_CHANNEL_RE
    namespace["RAW_DISPATCH_START_RE"] = re.compile(
        r"(?<!\w)(?:P\s*[1-5]|PRIO\s*[1-5]|A[012]|B[12])\b|"
        r"^\s*(?:ONGEVAL|VERKEER|POLITIE)(?:/[^\s]+){1,4}\s+PRIO\s*[1-5]\b|"
        r"^\s*[1-5]\s+.+?\bICNUM\b|^\s*(?:GAARNE\s+)?CONTACT\s+(?:MKB|OC)\b", re.I,
    )
    namespace["is_fire_dispatch_context"] = is_fire_dispatch_context_v455
    namespace["detect_service"] = detect_service_v455
    namespace["detect_priority"] = detect_priority_v455
    namespace["infer_city"] = infer_city_v455
    namespace["infer_message_city"] = infer_message_city_v455
    namespace["_infer_structured_dispatch_location"] = infer_structured_location_v455
    namespace["infer_location"] = infer_location_v455
    namespace["infer_units"] = infer_units_v455
    namespace["incident_type_label"] = incident_type_v455
    namespace["parser_confidence_details"] = parser_confidence_v455
    namespace["_PARSER_NL_V455_INSTALLED"] = True
