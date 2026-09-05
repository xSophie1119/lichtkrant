# v4.4.12 — Windows/Linux stability hardening

- Herkent en beëindigt een vastgelopen eigen backend op Windows én Linux zonder een onbekende poortgebruiker aan te raken.
- Windows-launchers proberen een mislukte backendstart één keer gecontroleerd opnieuw en controleren of Edge/Chrome blijft draaien.
- De supervisor gebruikt een atomisch, proces-geverifieerd PID-bestand; stopscripts doden geen hergebruikte PID meer.
- Linux sluit alleen het kioskprofiel en laat configuratie-/instellingenvensters met rust.
- Linux-autostart leest de grafische sessieomgeving opnieuw terwijl het op de desktop wacht.
- Veilige gebruikerscache-runtime als `XDG_RUNTIME_DIR` ontbreekt of niet bruikbaar is.
- Eindige browser- en API-time-outs voorkomen onbeperkt wachtende clients en overlappende statusverzoeken.
- Instellingenwrites en identieke online TTS-cachemisses zijn race-vrij gemaakt.
- Nieuwe platform- en concurrentieregressietests toegevoegd.
