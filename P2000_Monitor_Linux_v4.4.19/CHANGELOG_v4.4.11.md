# v4.4.11 — Linux startup/cache hotfix

- Fix startup crash when a pre-existing SW Mediaproducties vehicle cache is present (`normalize_space`).
- Fix `/api/vehicles/unknown` crash caused by the removed `FIRE_TYPE_DIGIT` symbol.
- Runtime identity now includes an install-id, so two copies of the same version in different folders cannot be mistaken for one backend.
- Linux installer stops old P2000 supervisors/backends and removes stale duplicate P2000 desktop/autostart launchers.
- Added upgrade regression coverage with a pre-existing SW cache and unknown-callsign rows.
