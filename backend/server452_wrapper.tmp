#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPAT_PATH = HERE / "compat451.py"

spec = importlib.util.spec_from_file_location("p2000_compat451", COMPAT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("v4.5.1 compatibility bridge kon niet worden geladen")
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)

_original_apply_v451_hotfix = compat.apply_v451_hotfix


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f"v4.5.2 hotfix vond {label} meerdere keren")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"v4.5.2 hotfix kon {label} niet vinden")


def _apply_v452_hotfix() -> None:
    server = HERE / "server.py"
    server_bytes = server.read_bytes()
    expected = getattr(compat, "V451_SERVER_NEW_SHA256", "")
    if expected and compat.sha256_bytes(server_bytes) != expected:
        raise RuntimeError("v4.5.2 hotfix basis-server heeft onverwachte SHA-256")
    server_text = server_bytes.decode("utf-8")
    server_text = _replace_once(
        server_text,
        'APP_VERSION = "4.5.1"',
        'APP_VERSION = "4.5.2"',
        "backendversie",
    )
    compat.atomic_write(server, server_text.encode("utf-8"))

    app = ROOT / "frontend" / "app.js"
    text = app.read_text(encoding="utf-8")
    text = _replace_once(text, "const CLIENT_VERSION='4.4.19';", "const CLIENT_VERSION='4.5.2';", "frontendversie")
    text = _replace_once(
        text,
        "function localKioskHost(){const h=String(location.hostname||'').toLowerCase();return h==='127.0.0.1'||h==='localhost'||h==='::1'}\nasync function windowsHostSpeakFallback",
        "function localKioskHost(){const h=String(location.hostname||'').toLowerCase();return h==='127.0.0.1'||h==='localhost'||h==='::1'}\nfunction windowsKioskHost(){const p=String(navigator.userAgent||navigator.platform||'');return localKioskHost()&&/Windows/i.test(p)}\nasync function windowsHostSpeakFallback",
        "Windows-kioskdetectie",
    )
    text = _replace_once(
        text,
        "  try{return await playOnlineAudioInBrowser(text,requestSeq,volume,cueService,cueUrgent)}",
        "  // Lokale Windows-kiosk: ga direct via SAPI/SoundPlayer. Dit voorkomt eerst\n  // 1-4 seconden wachten op een mislukte Chromium-media poging.\n  if(windowsKioskHost()){\n    try{const host=await windowsHostSpeakFallback(text,requestSeq,volume,cueService,cueUrgent);noteAudioSuccess(host.mode||'windows-host-audio');setAudioUnlockVisible(false);return host}\n    catch(hostError){noteAudioFailure(hostError,'windows-host');state.audioStats.fallbacks++;console.warn('Directe Windows host-TTS mislukt; browseraudio wordt fallback',hostError)}\n  }\n  try{return await playOnlineAudioInBrowser(text,requestSeq,volume,cueService,cueUrgent)}",
        "directe Windows TTS",
    )
    text = _replace_once(
        text,
        "    const tuned=job.skipTune?false:await playDispatchTuneForJob(job);",
        "    let tuned=false;\n    if(!job.skipTune){\n      const tunePromise=playDispatchTuneForJob(job).catch(()=>false);\n      const raced=await Promise.race([tunePromise.then(value=>({done:true,value})),waitMs(900).then(()=>({done:false,value:false}))]);\n      tuned=!!raced.value;\n      if(!raced.done)stopCurrentTune();\n    }",
        "maximale deuntje-wachttijd",
    )
    text = _replace_once(text, "async function waitForDutchVoice(timeoutMs=900){", "async function waitForDutchVoice(timeoutMs=250){", "browserstem-wachttijd")
    text = _replace_once(text, "const rendered=await fetchTtsBlob(text,16000,cueService,cueUrgent);", "const rendered=await fetchTtsBlob(text,8000,cueService,cueUrgent);", "TTS-fetch timeout")
    text = _replace_once(
        text,
        "    startTimer=setTimeout(()=>{if(!started)finish(false,new Error('TTS-audio startte niet binnen 4 seconden'))},4000);",
        "    startTimer=setTimeout(()=>{if(!started)finish(false,new Error('TTS-audio startte niet binnen 1,2 seconde'))},1200);",
        "browseraudio starttimeout",
    )
    text = _replace_once(text, "      for(let i=0;i<3&&!settled;i++){", "      for(let i=0;i<2&&!settled;i++){", "browseraudio retries")
    text = _replace_once(text, "await waitMs(180+i*240)", "await waitMs(80+i*100)", "browseraudio retry-wacht")
    text = _replace_once(text, "job.queuedAt=Date.now()+1500;", "job.queuedAt=Date.now()+250;", "omroep retry timestamp")
    text = _replace_once(
        text,
        "setTimeout(()=>{state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob()},1500);",
        "setTimeout(()=>{state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob()},250);",
        "omroep retry timer",
    )
    compat.atomic_write(app, text.encode("utf-8"))
    compat.atomic_write(ROOT / "VERSION", b"4.5.2\n")


def _apply_v451_then_v452() -> None:
    _original_apply_v451_hotfix()
    _apply_v452_hotfix()


compat.apply_v451_hotfix = _apply_v451_then_v452
compat.TARGET_VERSION = "4.5.2"

if __name__ == "__main__":
    compat.main()
