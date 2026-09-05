"""Self-extracting national P2000 parser payload for v4.5.5."""
from __future__ import annotations
import base64 as _b64, gzip as _gz, hashlib as _hashlib
from pathlib import Path as _Path
_RAW_SHA256 = "9303c331ad5464e1be0c0dcab2552318ffc40d26bba7c93198f430426be97bfd"
_PARTS = 4
_base = _Path(__file__).resolve().parent / "p455"
_encoded = "".join((_base / f"{i:02d}").read_text(encoding="ascii").strip() for i in range(_PARTS))
_raw = _gz.decompress(_b64.b64decode(_encoded))
if _hashlib.sha256(_raw).hexdigest() != _RAW_SHA256:
    raise RuntimeError("v4.5.5 parser payload SHA-256 klopt niet")
exec(compile(_raw, __file__ + "<payload>", "exec"), globals(), globals())
del _encoded, _raw
