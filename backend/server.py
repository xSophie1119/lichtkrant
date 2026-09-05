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

V451_SERVER_SHA = "34cfa04906379cf6c07d3b49185cf9bb4be541fc9414807ff7f36cdb715766fc"
V453_SERVER_SHA = "cc3fbd4e5085bf4dd604acc54d59de20cfc3b9f884b3aa69e0c47a42a5d22f7a"
V451_APP_SHA = "1f1f6b474ee6d7c9fc0f03712bed4e9e7150b6004c5a6f67e47c2acccf61cd53"
V453_APP_SHA = "ce473e00459ed8011f4c11b8b9127a8ca7bcaa3079f8d96a2b9570647afc3f90"
V451_INDEX_SHA = "5ebbeaae58409bdda4393e1ee76add55b6d6888a43a2ee3adbace061d20e7014"
V453_INDEX_SHA = "84b57f64a78e2d10b0bac85b3b73a5b9f495e7da3c42d3dfb518bafcb87185da"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f"v4.5.3 hotfix vond {label} meerdere keren")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"v4.5.3 hotfix kon {label} niet vinden")


def _verify(path: Path, expected: str, label: str) -> bytes:
    data = path.read_bytes()
    if compat.sha256_bytes(data) != expected:
        raise RuntimeError(f"v4.5.3 {label} heeft onverwachte SHA-256")
    return data


def _apply_v453_hotfix() -> None:
    server = HERE / "server.py"
    server_data = server.read_bytes()
    server_sha = compat.sha256_bytes(server_data)
    if server_sha == V453_SERVER_SHA:
        compat.atomic_write(ROOT / "VERSION", b"4.5.3\n")
        return
    if server_sha != V451_SERVER_SHA:
        raise RuntimeError("v4.5.3 basis-server heeft onverwachte SHA-256")
    server_text = server_data.decode("utf-8")
    server_text = _replace_once(server_text, 'APP_VERSION = "4.5.1"', 'APP_VERSION = "4.5.3"', "backendversie")
    new_server = server_text.encode("utf-8")
    if compat.sha256_bytes(new_server) != V453_SERVER_SHA:
        raise RuntimeError("v4.5.3 backend eindhash klopt niet")
    compat.atomic_write(server, new_server)

    app = ROOT / "frontend" / "app.js"
    app_data = _verify(app, V451_APP_SHA, "basis-app.js")
    text = app_data.decode("utf-8")
    text = _replace_once(text, "const CLIENT_VERSION='4.5.0';", "const CLIENT_VERSION='4.5.3';", "frontendversie")
    text = _replace_once(
        text,
        "function localKioskHost(){const h=String(location.hostname||'').toLowerCase();return h==='127.0.0.1'||h==='localhost'||h==='::1'}\nasync function windowsHostSpeakFallback",
        "function localKioskHost(){const h=String(location.hostname||'').toLowerCase();return h==='127.0.0.1'||h==='localhost'||h==='::1'}\nfunction windowsKioskHost(){const p=String(navigator.userAgent||navigator.platform||'');return localKioskHost()&&/Windows/i.test(p)}\nasync function windowsHostSpeakFallback",
        "Windows-kioskdetectie",
    )
    text = _replace_once(
        text,
        "  try{return await playOnlineAudioInBrowser(text,requestSeq,volume,cueService,cueUrgent)}",
        "  // Lokale Windows-kiosk: direct SAPI/SoundPlayer, browseraudio alleen fallback.\n  if(windowsKioskHost()){\n    try{const host=await windowsHostSpeakFallback(text,requestSeq,volume,cueService,cueUrgent);noteAudioSuccess(host.mode||'windows-host-audio');setAudioUnlockVisible(false);return host}\n    catch(hostError){noteAudioFailure(hostError,'windows-host');state.audioStats.fallbacks++;console.warn('Directe Windows host-TTS mislukt; browseraudio wordt fallback',hostError)}\n  }\n  try{return await playOnlineAudioInBrowser(text,requestSeq,volume,cueService,cueUrgent)}",
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
    text = _replace_once(text, "    startTimer=setTimeout(()=>{if(!started)finish(false,new Error('TTS-audio startte niet binnen 4 seconden'))},4000);", "    startTimer=setTimeout(()=>{if(!started)finish(false,new Error('TTS-audio startte niet binnen 1,2 seconde'))},1200);", "browseraudio starttimeout")
    text = _replace_once(text, "      for(let i=0;i<3&&!settled;i++){", "      for(let i=0;i<2&&!settled;i++){", "browseraudio retries")
    text = _replace_once(text, "await waitMs(180+i*240)", "await waitMs(80+i*100)", "browseraudio retry-wacht")
    text = _replace_once(text, "job.queuedAt=Date.now()+1500;", "job.queuedAt=Date.now()+250;", "omroep retry timestamp")
    text = _replace_once(text, "setTimeout(()=>{state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob()},1500);", "setTimeout(()=>{state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob()},250);", "omroep retry timer")
    old_reload = """function runtimeReloadReason(status,currentIdentity=null){\n  const version=String(status?.version||'').trim();\n  if(version&&version!==CLIENT_VERSION)return'version';\n  const id=runtimeIdentity(status);if(!id)return'';\n  if(currentIdentity&&id!==currentIdentity)return'instance';\n  return'';\n}"""
    new_reload = """function runtimeReloadReason(status,currentIdentity=null){\n  // v4.5.3: runtime changes are handled live through SSE/polling. Never force a\n  // browser reload here: a stale cached app.js used to create an endless loop\n  // on both Windows and Linux whenever backend/client versions differed.\n  return '';\n}"""
    text = _replace_once(text, old_reload, new_reload, "runtime reload-loop")
    new_app = text.encode("utf-8")
    if compat.sha256_bytes(new_app) != V453_APP_SHA:
        raise RuntimeError("v4.5.3 app.js eindhash klopt niet")
    compat.atomic_write(app, new_app)

    index = ROOT / "frontend" / "index.html"
    index_data = _verify(index, V451_INDEX_SHA, "basis-index.html")
    html = index_data.decode("utf-8")
    html = _replace_once(
        html,
        "const script=document.createElement('script');script.src='/app.js?v=45000';script.defer=true;document.body.appendChild(script);",
        "const assetKey=Date.now().toString(36);const css=document.querySelector('link[rel=\"stylesheet\"]');if(css)css.href=`/lightkrant.css?v=${assetKey}`;const script=document.createElement('script');script.src=`/app.js?v=${assetKey}`;script.defer=true;document.body.appendChild(script);",
        "dynamische asset-cachekey",
    )
    new_index = html.encode("utf-8")
    if compat.sha256_bytes(new_index) != V453_INDEX_SHA:
        raise RuntimeError("v4.5.3 index.html eindhash klopt niet")
    compat.atomic_write(index, new_index)
    compat.atomic_write(ROOT / "VERSION", b"4.5.3\n")


def _apply_v451_then_v453() -> None:
    _original_apply_v451_hotfix()
    _apply_v453_hotfix()


compat.apply_v451_hotfix = _apply_v451_then_v453
compat.TARGET_VERSION = "4.5.3"

if __name__ == "__main__":
    compat.main()
