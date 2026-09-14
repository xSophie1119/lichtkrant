(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const api = window.P2000Auth.request;
  let current = {}, timer, busy = false, local = false, pairLink = '', noticeTimer;
  let commandQueue = Promise.resolve(), pendingVolume = null, volumeTimer, volumeWriting = false;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const labels = {online: 'Online', starting: 'Starten', disabled: 'Testmodus', degraded: 'Deels online', fallback: 'Reservebron', error: 'Storing'};
  function notice(text, error = false) {
    clearTimeout(noticeTimer); $('#feedback').hidden = false; $('#feedback').textContent = text; $('#feedback').dataset.error = error;
    noticeTimer = setTimeout(() => { $('#feedback').hidden = true; }, error ? 10000 : 4500);
  }
  const post = (path, payload = {}) => api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  function serialize(task) {
    const result = commandQueue.then(task);
    commandQueue = result.catch(() => {});
    return result;
  }
  function navigate() {
    const hash=location.hash.slice(1),panel=document.getElementById(hash);
    const page=['overview','sound','messages','management'].includes(hash)?hash:panel?.dataset.panel||'overview';
    for(const el of document.querySelectorAll('[data-panel]'))el.toggleAttribute('data-page-hidden',el.dataset.panel!==page);
    for(const link of document.querySelectorAll('[data-page]')){if(link.dataset.page===page)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
  }
  window.addEventListener('hashchange',navigate);navigate();
  async function restoreStandard(kind){
    const design=await api('/api/remote/studio/config');
    if(!design?.config)throw new Error('Studio-instellingen konden niet worden opgehaald.');
    const config=JSON.parse(JSON.stringify(design.config));config[kind].enabled=false;
    await post('/api/remote/studio/config',{config,revision:design.revision});
    try{
      const patch=kind==='layout'?{messageDisplayMode:'parsed'}:{speechEnabled:true,speechMode:'normal'};
      const result=await post('/api/settings',patch);renderSettings(result.settings);
      notice(kind==='layout'?'Rustige standaardweergave toegepast.':'Standaardomroep ingeschakeld. Controleer het geluid met Test omroep.');
    }catch(error){throw new Error('Eigen '+(kind==='layout'?'indeling':'omroepopbouw')+' staat uit. Overige instellingen niet opgeslagen: '+error.message);}
  }
  function renderSettings(settings) {
    current = settings || {};
    $('#monitorName').textContent = current.name || 'Je lichtkrant, binnen handbereik.';
    if (pendingVolume === null && !volumeWriting && document.activeElement !== $('#volume')) {
      $('#volume').value = current.masterVolume ?? 100;
      $('#volumeValue').textContent = `${$('#volume').value}%`;
    }
    const places=(current.speechCities||[]).filter(Boolean);
    $('#audioExplanation').textContent=places.length?'Omroep beperkt tot: '+places.join(', ')+'.':'Geen extra plaatsfilter voor de omroep.';
    const mode = current.speechEnabled === false ? 'mute' : current.speechMode || 'normal';
    document.querySelectorAll('[data-mode]').forEach(button => { button.classList.toggle('active', button.dataset.mode === mode); button.setAttribute('aria-pressed', String(button.dataset.mode === mode)); });
    $('#modeHint').textContent = {normal: 'Alle ingestelde meldingen worden omgeroepen.', priority: 'Alleen prioriteitsmeldingen worden omgeroepen.', mute: 'Meldingen blijven zichtbaar; de omroep staat stil.'}[mode] || '';
    for (const element of document.querySelectorAll('[data-setting]')) {
      if (document.activeElement === element) continue;
      const value = current[element.dataset.setting];
      if (element.type === 'checkbox') element.checked = value !== false;
      else element.value = value || 'route';
    }
  }
  function timeLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('nl-NL', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
  }
  let messagesFingerprint = '', stream=null;
  function showInvite(invite){$('#pairCode').value=invite.token;pairLink=`${$('#pairAddress').value}#token=${encodeURIComponent(invite.token)}`;$('#pairDetails').hidden=false;drawQr(pairLink);}
  function connectStatus(){if(document.hidden||!window.EventSource||stream)return;stream=new EventSource('/api/remote/events');stream.onopen=()=>clearTimeout(timer);stream.onmessage=event=>{try{render(JSON.parse(event.data));$('#connection').textContent='● Verbonden';$('#connection').dataset.online='true';clearTimeout(timer)}catch{}};stream.onerror=()=>{if(!document.hidden)refresh()};stream.addEventListener('revoked',()=>{stream.close();location.reload()});}

  function render(data) {
    renderSettings(data.settings);
    window.P2000RemotePlus?.update(data);
    $('#feedState').textContent = labels[data.feed_status] || data.feed_status || 'Onbekend';
    $('#feedState').title = data.last_error || '';
    document.querySelector('.status-strip').dataset.feed=data.feed_status||'unknown';
    const displays = (data.displays || []).filter(row => row.online);
    $('#screenState').textContent = displays.length ? `${displays.length} verbonden` : 'Geen scherm';
    $('#version').textContent = `v${data.version}`;
    $('#lastRefresh').textContent = new Date().toLocaleTimeString('nl-NL', {hour: '2-digit', minute: '2-digit'});
    const messages = data.messages || [], fingerprint = JSON.stringify(messages);
    if (fingerprint === messagesFingerprint) return;
    messagesFingerprint = fingerprint;
    $('#messageCount').textContent = `${messages.length} MELDINGEN`;
    $('#messageList').innerHTML = messages.length ? messages.map(message => `<article class="message-row"><div class="message-top"><span class="service-label" data-service="${escape(message.service)}">${escape(message.service || 'Melding')} ${escape(message.priority)}</span><time>${escape(timeLabel(message.published))}</time></div><h3>${escape(message.title || message.summary)}</h3><p>${escape([message.city, message.location].filter(Boolean).join(' · '))}</p></article>`).join('') : '<p class="empty">Nog geen meldingen ontvangen. Nieuwe meldingen verschijnen hier automatisch.</p>';
  }
  async function refresh() {
    clearTimeout(timer);
    if (busy || document.hidden) return;
    busy = true;
    try {
      const data = await api('/api/remote/status'); render(data);
      $('#connection').textContent = '● Verbonden'; $('#connection').dataset.online = 'true';
    } catch (error) {
      $('#connection').textContent = error.status === 401 ? 'Opnieuw koppelen' : 'Verbinding herstellen…'; $('#connection').dataset.online = 'false';
      $('#screenPreview').dataset.stale='true';
      if (error.status === 401) { location.reload(); return; }
    } finally { busy = false; if (!document.hidden && stream?.readyState!==1) timer = setTimeout(refresh, 5000); }
  }
  async function action(name, payload = {}) {
    return serialize(async () => {
      const data = await post('/api/quick-action', {action: name, ...payload});
      if (data.settings) renderSettings(data.settings);
      if (name !== 'volume') notice(data.queued ? 'Opdracht bewaard; de lichtkrant haalt hem bij de volgende verbinding op.' : 'Opdracht verzonden naar de lichtkrant.');
      return data;
    });
  }
  async function flushVolume() {
    clearTimeout(volumeTimer);
    if (volumeWriting || pendingVolume === null) return;
    volumeWriting = true;
    try {
      while (pendingVolume !== null) {
        const value = pendingVolume; pendingVolume = null;
        await action('volume', {value});
      }
    } catch (error) { notice(`Volume niet opgeslagen: ${error.message}`, true); }
    finally { volumeWriting = false; if (pendingVolume !== null) flushVolume(); }
  }
  async function test(mode, text = '') {
    const token = `phone-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    let payload = {token, mode, service: 'brandweer', priority: 'P1', speak: mode !== 'tune-only', force_audio: true, host_speak: false, duration_ms: 60000};
    if (mode === 'speech-only') payload.speech_text = 'Dit is een test van de omroep. Je bedient de lichtkrant vanaf je telefoon.';
    else if (mode === 'tune-only') payload.tune_choice = current.dispatchTuneDefault || 'builtin:classic';
    else {
      const result = await post('/api/parser/debug', {raw: text}); const parsed = result.parse || {};
      payload = {...payload, title: text, summary: text, city: parsed.city || '', location: parsed.location || '', service: parsed.service || 'brandweer', priority: parsed.priority || 'P1', speech_text: parsed.speech_text || text, scale: parsed.scale || '', scale_score: parsed.scale_score || 0};
    }
    await post('/api/test-message', payload);
    $('#testResult').textContent = 'Test verzonden. Wachten op bevestiging van de lichtkrant…';
    const deadline = Date.now() + 40000;
    while (Date.now() < deadline && !document.hidden) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const {result = {}} = await api(`/api/test-status?token=${encodeURIComponent(token)}`);
      if (result.status === 'completed' || result.status === 'error') {
        $('#testResult').textContent = (result.ok ? 'Test geslaagd. ' : 'Test mislukt. ') + (result.detail || '');
        return;
      }
    }
    $('#testResult').textContent = 'Nog geen afspeelbevestiging. Controleer of het lichtkrantscherm open is en browseraudio is toegestaan.';
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const input = document.createElement('textarea'); input.value = text; document.body.append(input); input.select();
      const ok = document.execCommand('copy'); input.remove(); if (!ok) throw new Error('Kopiëren lukt niet. Selecteer en kopieer de tekst handmatig.');
    }
    notice('Gekopieerd.');
  }
  function drawQr(link) {
    const qr = new window.LocalQRCode(0, window.LocalQRErrorCorrectLevel.M); qr.addData(link); qr.make();
    const count = qr.getModuleCount(), scale = Math.max(3, Math.floor(228 / (count + 8)));
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = (count + 8) * scale;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = '#102119';
    for (let row = 0; row < count; row++) for (let col = 0; col < count; col++) if (qr.isDark(row, col)) ctx.fillRect((col + 4) * scale, (row + 4) * scale, scale, scale);
    $('#pairQr').replaceChildren(canvas);
  }
  async function pairing() {
    const data = await api('/api/remote/info'); local = data.local;
    $('#pairing').hidden = !local; $('#logout').hidden = local;
    if (!local) return;
    $('#enableRemote').hidden = data.enabled; $('#inviteForm').hidden = !data.enabled; if(!data.enabled)$('#pairDetails').hidden=true;
    const url = data.urls?.[0];
    if (!url) { $('#pairHelp').textContent = 'Geen lokaal netwerkadres gevonden. Verbind de pc eerst met wifi of een netwerkkabel.'; $('#pairDetails').hidden = true; return; }
    $('#pairAddress').value = url;
  }
  async function setRemote(enabled) {
    await post('/api/remote/config', {enabled});
    notice('Opgeslagen. De backend herstart; even geduld…');
    await new Promise(resolve => setTimeout(resolve, 2500));
    for (let attempt = 0; attempt < 12; attempt++) {
      try { await pairing(); await refresh(); return; } catch { await new Promise(resolve => setTimeout(resolve, 1000)); }
    }
    notice('Herstart duurt langer. Herlaad dit paneel zodra de backend weer beschikbaar is.', true);
  }
  function bindButton(button, task) {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try { await task(); }
      catch (error) { notice(error.name === 'AbortError' ? 'Geen antwoord ontvangen. Controleer de verbinding voordat je opnieuw probeert.' : error.message, true); }
      finally { button.disabled = false; }
    });
  }
  async function init() {
    const session=await window.P2000Auth.ready;
    await window.P2000RemotePlus?.init({api,post,notice,bind:bindButton,settings:renderSettings,session,showInvite});
    for (const button of document.querySelectorAll('[data-action]')) bindButton(button, () => {
      const name = button.dataset.action;
      if (name.startsWith('restart-') && !confirm(name === 'restart-backend' ? 'Backend nu herstarten?' : 'Lichtkrantscherm nu sluiten en opnieuw openen?')) return;
      return action(name);
    });
    for (const button of document.querySelectorAll('[data-power]')) bindButton(button, async () => { await post('/api/display/power', {state: button.dataset.power, manual: true}); notice('Schermopdracht uitgevoerd.'); });
    for (const button of document.querySelectorAll('[data-test]')) bindButton(button, () => test(button.dataset.test));
    for (const element of document.querySelectorAll('[data-setting]')) element.addEventListener('change', async () => {
      element.disabled = true;
      try { await serialize(async () => { const result = await post('/api/settings', {[element.dataset.setting]: element.type === 'checkbox' ? element.checked : element.value}); renderSettings(result.settings); }); notice('Instelling opgeslagen.'); }
      catch (error) { notice(error.message, true); await refresh(); }
      finally { element.disabled = false; }
    });
    $('#volume').addEventListener('input', event => { pendingVolume = Number(event.target.value); $('#volumeValue').textContent = `${pendingVolume}%`; clearTimeout(volumeTimer); volumeTimer = setTimeout(flushVolume, 180); });
    $('#volume').addEventListener('change', flushVolume);
    bindButton($('#calmDisplay'),()=>serialize(()=>restoreStandard('layout')));
    bindButton($('#restoreSpeech'),()=>serialize(()=>restoreStandard('speech')));
    bindButton($('#sendTest'), () => { const text = $('#testText').value.trim(); if (!text) throw new Error('Vul eerst een testmelding in.'); return test('message', text); });
    bindButton($('#reconnect'), async () => { await post('/api/feeds/reconnect'); notice('Bronnen worden opnieuw verbonden.'); });
    bindButton($('#enableRemote'), () => setRemote(true)); bindButton($('#disableRemote'), () => setRemote(false));
    bindButton($('#copyPair'), () => copy(pairLink)); bindButton($('#copyCode'), () => copy($('#pairCode').value));
    bindButton($('#logout'), async () => { await post('/api/remote/logout'); location.reload(); });
    document.addEventListener('visibilitychange', () => { clearTimeout(timer); if (!document.hidden){refresh();connectStatus()}else{stream?.close();stream=null;flushVolume()} });
    window.addEventListener('online', ()=>{refresh();connectStatus()});
    window.addEventListener('pagehide',()=>{stream?.close();stream=null;clearTimeout(timer)});
    await Promise.allSettled([refresh(), pairing().catch(error => notice(error.message, true))]);
    connectStatus();
  }
  init().catch(error => notice(error.message, true));
})();
