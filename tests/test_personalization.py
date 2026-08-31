from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def ck(name,ok): checks.append((name,bool(ok)))
html=(ROOT/'frontend/control.html').read_text(encoding='utf-8')
js=(ROOT/'frontend/control.js').read_text(encoding='utf-8')
app=(ROOT/'frontend/app.js').read_text(encoding='utf-8')
start=(ROOT/'START_P2000.bat').read_text(encoding='utf-8')
server=(ROOT/'backend/server.py').read_text(encoding='utf-8')
ck('speech cities input', 'speechCitiesInput' in html and 'parseList' in js and 'speechCities:parseList' in js)
ck('speech cities not reset', "speechCities:[]" not in js[js.find('function formToSettings'):js.find('function renderSettings')])
ck('background controls', all(x in html for x in ['backgroundStyleInput','backgroundColorInput','backgroundPhotoInput','backgroundPhotoDarknessInput','backgroundPhotoFitInput']))
ck('background canvas helper', 'monitorBackgroundColor()' in app and 'BACKGROUND_PRESETS' in app and 'drawMonitorBackground' in app and '/api/background/image' in app)
ck('background upload API', '/api/background/upload' in server and 'MAX_BACKGROUND_BYTES' in server and 'background.webp' in server)
ck('monitor selector', 'kioskMonitorInput' in html and '/api/display/info' in js)
ck('windows monitor API', 'EnumDisplayMonitors' in server and 'selected_monitor' in server)
ck('kiosk positioning', '--window-position=%P2000_WINDOW_POSITION%' in start and '--window-size=%P2000_WINDOW_SIZE%' in start)
ck('launcher helper', (ROOT/'tools/kiosk_display.py').exists())
failed=[name for name,ok in checks if not ok]
print({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed})
raise SystemExit(1 if failed else 0)
