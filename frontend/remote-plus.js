/* Additional dashboard panels. All dynamic text is escaped before rendering. */
(() => {
  'use strict';
  const $=selector=>document.querySelector(selector);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date=value=>value?new Date(typeof value==='number'?value*1000:value).toLocaleString('nl-NL'):'Onbekend';
  let api,post,notice,bind,settings,viewer=false,currentData={},cursor=null,archiveQuery='',restore=null,previewKey='',previewBusy=false,archiveBusy=false;
  const settingLabels={name:'Naam',masterVolume:'Hoofdvolume',speechMode:'Omroepmodus',speechEnabled:'Omroep aan',cities:'Plaatsenfilter',services:'Diensten',keywords:'Zoekwoorden',activeProfile:'Profiel',urgentOnly:'Alleen urgente meldingen',exerciseMode:'Oefenmodus',nightMode:'Nachtregeling',nightStart:'Nacht begint',nightEnd:'Nacht eindigt',displaySleep:'Scherm automatisch slapen',mapEnabled:'Kaart zichtbaar',mapMode:'Kaartweergave',kioskMonitor:'Gekozen scherm',dispatchTuneDefault:'Standaarddeuntje',backgroundColor:'Achtergrondkleur'};
  const stageLabels={fetch:'Bron ophalen',fetch_total:'Ophalen + verwerken',parse:'Meldingen verwerken',map:'Kaart zoeken'};
  function selectedScreen(){return $('#previewScreen').value||'';}
  function update(data){
    if(!api)return;
    currentData=data;
    const displays=data.displays||[],options=displays.filter(x=>x.online);
    const selected=selectedScreen();
    const optionKey=JSON.stringify(options.map(x=>[x.client_id,x.display_name]));
    if($('#previewScreen').dataset.key!==optionKey){
      $('#previewScreen').dataset.key=optionKey;
      $('#previewScreen').innerHTML=options.length?options.map(x=>`<option value="${esc(x.client_id)}">${esc(x.display_name||x.client_id)}</option>`).join(''):'<option value="">Geen scherm verbonden</option>';
      if(options.some(x=>x.client_id===selected))$('#previewScreen').value=selected;
    }
    showPreview();
    const profile=data.settings?.activeProfile||'normal';
    const profiles=data.profiles||[];
    if(!$('#profileButtons').children.length&&profiles.length){
      $('#profileButtons').innerHTML=profiles.map(x=>`<button class="secondary" data-profile="${esc(x.id)}"><strong>${esc(x.label)}</strong><small>${esc(x.description)}</small></button>`).join('');
      for(const button of document.querySelectorAll('[data-profile]'))bind(button,async()=>{
        if(button.dataset.profile==='exercise'&&!confirm('Oefenmodus inschakelen? Live meldingen blijven in het archief, maar verschijnen niet op de lichtkrant.'))return;
        const result=await post('/api/remote/profile',{id:button.dataset.profile});settings(result.settings);notice('Profiel opgeslagen en naar het scherm verzonden.');
      });
    }
    for(const button of document.querySelectorAll('[data-profile]')){button.classList.toggle('active',button.dataset.profile===profile);button.setAttribute('aria-pressed',String(button.dataset.profile===profile));}
    $('#activeProfile').textContent=profiles.find(x=>x.id===profile)?.label||profile;
    $('#profileDescription').textContent=data.settings?.exerciseMode?'Oefenmodus actief: live meldingen worden alleen in het archief bewaard.':'Bij Normaal keer je terug naar je opgeslagen normale volume en weergave. Plaats- en dienstenfilters blijven behouden.';
    const sources=data.diagnostics?.sources||[],online=['online','fallback','degraded'].includes(data.feed_status);
    const sourceState=online?'Bron bereikbaar':data.feed_status==='disabled'?'Bronnen uitgeschakeld':data.feed_status==='starting'?'Bronnen starten':'Bronstoring';
    const sourceDetail=online?`Laatste geslaagde controle: ${date(data.diagnostics?.source_last_success)}. Laatste melding: ${date(data.diagnostics?.last_message)}.`:(data.last_error||'Controleer de verbinding of verbind bronnen opnieuw.');
    const screen=options.find(x=>x.client_id===selectedScreen());
    let audioState='Niet vastgesteld',audioDetail='Verbind eerst een lichtkrantscherm.',audioLevel='unknown';
    if(screen){
      if(data.settings?.speechEnabled===false||screen.speech_mode==='mute'||screen.master_volume===0){audioState='Omroep gedempt';audioDetail='Verhoog het volume of kies Normaal.';}
      else if(screen.audio_last_error){audioState='Audiofout';audioDetail=screen.audio_last_error;audioLevel='error';}
      else if(screen.audio_last_success_at){audioState='Afspelen bevestigd';audioDetail=`Laatst: ${new Date(screen.audio_last_success_at).toLocaleString('nl-NL')}. De software kan niet controleren of de luidspreker fysiek hoorbaar is.`;audioLevel='ok';}
      else {audioState=screen.audio_unlocked?'Audio gereed':'Audio nog niet bevestigd';audioDetail=screen.audio_unlocked?'Voer een omroeptest uit.':'Bij browseraudio kan één tik op het lichtkrantscherm nodig zijn.';}
    }
    if($('#audioSummaryTitle')){$('#audioSummaryTitle').textContent=audioState;$('#audioSummaryDetail').textContent=audioDetail;$('#audioSummary').dataset.state=audioLevel;}
    const diagnostics=[['Bronnen',sourceState,sourceDetail,online?'ok':data.feed_status==='disabled'?'unknown':'error'],['Scherm',screen?'Verbonden':'Geen scherm verbonden',screen?`Hartslag ${screen.heartbeat_age_seconds||0} seconden geleden. ${screen.map_visible?'Kaart zichtbaar.':''}`:'Heropen de lichtkrant; dit telefoonpaneel telt niet als scherm.',screen?'ok':'error'],['Audio',audioState,audioDetail,audioLevel]];
    $('#diagnosticRows').innerHTML=diagnostics.map(([title,state,detail,level])=>`<div class="diagnostic-item" data-state="${level}"><span class="muted">${title}</span><strong>${esc(state)}</strong><p class="muted">${esc(detail)}</p></div>`).join('');
    const commands=data.commands||[];
    $('#commandResults').innerHTML=commands.slice(0,4).map(command=>{
      const rows=Object.entries(command.results||{}),failed=rows.some(([,x])=>x.status==='error'),done=rows.length&&rows.every(([,x])=>x.status==='completed');
      const summary=rows.length?rows.map(([cid,x])=>`${displays.find(d=>d.client_id===cid)?.display_name||cid}: ${x.detail}`).join(' · '):command.expired?'Geen bevestiging binnen één minuut. Controleer het scherm.':'Verzonden; wachten op het scherm…';
      return `<div class="receipt" data-state="${failed?'error':done?'completed':'pending'}"><strong>${esc(command.action)}</strong><div>${esc(summary)}</div></div>`;
    }).join('');
    const metrics=data.metrics||{},stages={...(metrics.stages||{})};
    if(screen?.render_samples)stages.render={samples:screen.render_samples,p50_ms:null,p95_ms:screen.render_p95_ms};
    $('#performanceRows').innerHTML=Object.entries(stages).map(([name,x])=>`<tr><td>${esc(stageLabels[name]||'Scherm tekenen')}</td><td>${x.p50_ms==null?'—':Number(x.p50_ms).toFixed(1)+' ms'}</td><td>${Number(x.p95_ms).toFixed(1)} ms</td><td>${Number(x.samples)}</td></tr>`).join('')||'<tr><td colspan="4">Nog geen metingen beschikbaar.</td></tr>';
    const samples=metrics.process||[],last=samples.at(-1),first=samples[0],mb=x=>(x/1048576).toFixed(1);
    $('#performanceSummary').textContent=last?`Backend CPU ${last.cpu_percent}% · geheugen ${last.rss_bytes==null?'niet beschikbaar':mb(last.rss_bytes)+' MB'} · ${samples.length} meetpunten sinds ${date(first.at)}${last.rss_bytes!=null&&first.rss_bytes!=null?' · verschil '+mb(last.rss_bytes-first.rss_bytes)+' MB':''}${screen?.js_heap_used?' · browser JS-geheugen '+mb(screen.js_heap_used)+' MB':''}`:'De eerste CPU- en geheugenmeting verschijnt na tien seconden.';
  }
  async function showPreview(){
    const cid=selectedScreen(),meta=currentData.screens?.[cid],image=$('#screenPreview');
    $('#previewMode').textContent=meta?.mode||'Geen beeld';
    $('#currentMessage').textContent=meta?.message||'Geen actieve melding in het laatste schermbeeld';
    $('#previewAge').textContent=meta?`Schermbeeld van ${date(meta.at)} · ${Math.round(meta.age_seconds||0)} seconden oud${meta.map_visible?' · kaart staat aan':''}.`:'Wacht maximaal ongeveer tien seconden op een schermbeeld. Bij een externe achtergrondfoto kan de browser delen van het canvas blokkeren.';
    image.dataset.stale=String(!meta||meta.age_seconds>30);
    if(!meta){image.hidden=true;$('#previewEmpty').hidden=false;return;}
    const key=cid+'|'+meta.at;
    if(key===previewKey||previewBusy)return;
    previewBusy=true;
    try{
      const result=await api(`/api/remote/preview?client_id=${encodeURIComponent(cid)}`);
      if(cid!==selectedScreen())return;
      if(result.preview?.image?.startsWith('data:image/jpeg;base64,')){
        image.src=result.preview.image;image.hidden=false;$('#previewEmpty').hidden=true;previewKey=key;
      }
    }catch{}finally{previewBusy=false;}
  }
  async function loadDevices(){
    const result=await api('/api/remote/devices');
    $('#deviceList').innerHTML=(result.devices||[]).map(x=>`<article><strong>${esc(x.name)}</strong><p>${x.role==='viewer'?'Alleen kijken':'Bedienen'} · Laatst gebruikt ${esc(date(x.last_seen))}</p><button class="secondary" data-revoke="${esc(x.id)}">Toegang intrekken</button></article>`).join('')||'<p class="muted">Nog geen apparaten gekoppeld.</p>';
    for(const button of document.querySelectorAll('[data-revoke]'))bind(button,async()=>{if(!confirm('Toegang van dit apparaat intrekken?'))return;await post('/api/remote/revoke',{id:button.dataset.revoke});await loadDevices();notice('Toegang ingetrokken.');});
  }
  async function loadHistory(){
    const result=await api('/api/remote/history');
    $('#historyList').innerHTML=(result.points||[]).map(x=>`<article><strong>${esc(x.description)}</strong><p>${esc(date(x.created_at))}</p><button class="secondary" data-restore="${esc(x.id)}">Wijzigingen bekijken</button></article>`).join('')||'<p class="muted">Nog geen herstelpunten.</p>';
    for(const button of document.querySelectorAll('[data-restore]'))bind(button,async()=>{
      const result=await api(`/api/remote/restore-preview?id=${encodeURIComponent(button.dataset.restore)}`);restore=result.preview;
      $('#restorePreview').hidden=false;
      $('#restoreChanges').innerHTML=restore.changes.map(x=>`<p><strong>${esc(settingLabels[x.key]||x.key)}</strong><br>${esc(JSON.stringify(x.before))} → ${esc(JSON.stringify(x.after))}</p>`).join('')||'<p>Deze instellingen zijn al actief.</p>';
      $('#confirmRestore').disabled=!restore.changes.length;
    });
  }
  async function archive(more=false){
    if(archiveBusy)return;
    if(!more){
      const values=new FormData($('#archiveForm')),params=new URLSearchParams();
      for(const key of ['q','city','service','priority'])if(values.get(key))params.set(key,values.get(key));
      const from=values.get('from'),to=values.get('to');
      if(from&&to&&from>to)throw new Error('De begindatum moet vóór de einddatum liggen.');
      if(from)params.set('since',new Date(from+'T00:00:00').toISOString());
      if(to){const end=new Date(to+'T00:00:00');end.setDate(end.getDate()+1);params.set('until',end.toISOString());}
      archiveQuery=params.toString();cursor=null;
    }
    archiveBusy=true;$('#archiveMore').disabled=true;
    try{
      const result=await api('/api/remote/archive?'+archiveQuery+(more&&cursor?'&cursor='+encodeURIComponent(cursor):''));
      const html=(result.messages||[]).map(x=>`<article class="message-row"><div class="message-top"><span>${esc(x.service)} ${esc(x.priority)}</span><time>${esc(date(x.published))}</time></div><h3>${esc(x.title||x.summary)}</h3><p>${esc([x.city,x.location].filter(Boolean).join(' · '))}</p><div class="archive-actions"><button class="secondary" data-map="${esc(x.id)}">Kaart</button>${viewer?'':`<button class="secondary" data-message="${esc(x.id)}" data-message-action="pin">Vastzetten</button><button class="secondary" data-message="${esc(x.id)}" data-message-action="replay">Opnieuw omroepen</button>`}</div></article>`).join('');
      if(more)$('#archiveResults').insertAdjacentHTML('beforeend',html);else $('#archiveResults').innerHTML=html||'<p class="empty">Geen meldingen gevonden met deze filters.</p>';
      cursor=result.next_cursor;$('#archiveMore').hidden=!cursor;
      for(const button of document.querySelectorAll('#archiveResults button:not([data-bound])')){
        button.dataset.bound='true';
        bind(button,async()=>{
          if(button.dataset.map){
            const data=await api('/api/remote/map?id='+encodeURIComponent(button.dataset.map)),geo=data.map;
            if(!geo||!Number.isFinite(Number(geo.lat))||!Number.isFinite(Number(geo.lon)))throw new Error('Geen kaartlocatie gevonden.');
            const lat=Number(geo.lat),lon=Number(geo.lon),bbox=[lon-.015,lat-.01,lon+.015,lat+.01].join(',');
            $('#archiveMap iframe').src=`https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat},${lon}`;
            $('#archiveMapTitle').textContent='Incidentlocatie';$('#archiveMap').hidden=false;return;
          }
          if(button.dataset.messageAction==='replay'&&!confirm('Deze archiefmelding nu opnieuw laten omroepen?'))return;
          await post('/api/remote/message-action',{id:button.dataset.message,action:button.dataset.messageAction,client_id:selectedScreen()});notice('Opdracht verzonden. De bevestiging verschijnt bij Live meekijken.');
        });
      }
    }finally{archiveBusy=false;$('#archiveMore').disabled=false;}
  }
  async function init(context){
    ({api,post,notice,bind,settings}=context);viewer=context.session?.role==='viewer';
    document.body.classList.toggle('viewer',viewer);$('#viewerNotice').hidden=!viewer;$('#devices').hidden=!context.session?.local;
    $('#previewScreen').addEventListener('change',()=>{previewKey='';update(currentData);});
    bind($('#createInvite'),async()=>{
      const result=await post('/api/remote/invite',{name:$('#deviceName').value||'Telefoon',role:$('#deviceRole').value});
      context.showInvite(result.invite);$('#inviteExpiry').textContent=`Eén keer geldig tot ${date(result.invite.expires_at)}. Maak voor een volgend apparaat een nieuwe code.`;
    });
    bind($('#loadDevices'),loadDevices);bind($('#loadHistory'),loadHistory);
    bind($('#createCheckpoint'),async()=>{await post('/api/remote/checkpoint',{description:$('#checkpointName').value||'Handmatig herstelpunt'});await loadHistory();notice('Herstelpunt opgeslagen.');});
    bind($('#confirmRestore'),async()=>{if(!restore)return;if(!confirm('De getoonde instellingen terugzetten? Je huidige instellingen krijgen eerst een herstelpunt.'))return;const result=await post('/api/remote/restore',{id:restore.id,expected:restore.expected});settings(result.settings);$('#restorePreview').hidden=true;restore=null;await loadHistory();notice('Instellingen teruggezet.');});
    $('#archiveForm').addEventListener('submit',event=>{event.preventDefault();archive().catch(error=>notice(error.message,true));});
    bind($('#archiveMore'),()=>archive(true));
    bind($('#closeArchiveMap'),()=>{$('#archiveMap').hidden=true;$('#archiveMap iframe').removeAttribute('src');});
    bind($('#unpinMessage'),async()=>{await post('/api/remote/message-action',{action:'unpin',client_id:selectedScreen()});notice('Losmaken aangevraagd.');});
    if(context.session?.local)loadDevices().catch(error=>notice(error.message,true));
  }
  window.P2000RemotePlus={init,update};
})();
