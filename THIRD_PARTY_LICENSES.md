# Third-party notices

## QRCode for JavaScript

The local QR generator in `frontend/qr-local.js` is derived from **QRCode for JavaScript** by Kazuhiko Arase.

Copyright (c) 2009 Kazuhiko Arase

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE.

## gTTS and bundled Python dependencies

The optional Dutch online speech fallback bundles these Python libraries so a separate `pip install` is not required:

- gTTS 2.5.4
- Requests 2.32.5
- urllib3 2.7.0
- idna 3.17
- certifi 2026.5.20
- charset-normalizer 3.4.7
- Click 8.1.8

Their original license files are included under `vendor/licenses/`. The normal Windows route first tries to render Dutch speech locally to WAV; gTTS is only a fallback when no usable Dutch local voice is available.

## Public data/services

The monitor can request public P2000 RSS data from **Alarmeringen.nl**. Alarmeringen.nl states on its webfeeds page that its RSS feeds are supplied under a Creative Commons licence. Users remain responsible for complying with the current terms of the source.

The optional exact brandweer roepnummer cache is refreshed from the publicly published **Tomzulu10 landelijke brandweervoertuigenoverzicht**. This is supplemental recognition data: the monitor does not require it for dispatch parsing and falls back to the national callsign number plan when exact data is unavailable. Source data can change independently of this software.

For maps/geocoding the monitor can use public **PDOK/Kadaster** services, including the Location API, Locatieserver, BGT public-space labels and PDOK background map tiles. OpenStreetMap/Nominatim is used only as a final geocoding/tile fallback where configured by the application. Current provider usage policies and attribution requirements apply.
