# v4.4.10 — Linux backend recovery + deuntjes persistence

- Deuntje-instellingen hebben een eigen duurzame opslag (`data/tunes/settings.json`) en worden niet meer gewist door gedeeltelijke settings-saves.
- Alle deuntjevelden slaan automatisch op; er is ook een expliciete knop **Toontjes nu opslaan**.
- Custom tune upload/remove synchroniseert de opgeslagen versie direct.
- `/api/settings` werkt voortaan merge-safe: gedeeltelijke saves behouden overige instellingen.
- Nieuwe `/api/tune/settings` GET/POST route.
- Linux launcher herstelt een vastgelopen/oude P2000 backend op poort 8765 automatisch, ook als `/api/runtime` niet meer antwoordt.
- Linux start controleert schrijfrechten op `data/` en geeft een concrete rechtenfix in plaats van alleen `BACKEND START NIET`.
- Backendstart krijgt één automatische herstel/retry-poging met duidelijke poort/PID-diagnose.
