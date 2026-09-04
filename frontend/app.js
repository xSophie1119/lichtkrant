'use strict';

const CLIENT_VERSION='4.4.15';
const DISPLAY_ROWS=3;
const BODY_ROWS=2;
const PAGE_MS=6500;
const MULTI_MESSAGE_PAGE_MS=5000;
const MESSAGE_ROTATE_MS=10*1000;
const BUSY_MESSAGE_ROTATE_MS=5*1000;
const BUSY_WINDOW_MS=5*60*1000;
const BUSY_THRESHOLD=10;
const REPLAY_MS=60*1000;
const SIGNATURE_MEMORY_MS=15*60*1000;
const DEFAULTS={
  name:'P2000 Monitor',
  services:['brandweer','ambulance','politie','lifeliner','knrm'],
  cities:[],keywords:[],
  nightMode:true,nightStart:'23:00',nightEnd:'07:00',
  idleStyle:'normal',idleLayout:'center',idleHeadline:'',idleSubline:'P2000 MELDINGEN HEBBEN DIRECT VOORRANG',idleShowName:true,idleShowDate:true,idleShowSeconds:true,idleShowStatus:true,idleClockScale:100,messageDisplayMode:'raw',idleDimEnabled:true,idleDimStart:'21:30',idleDimEnd:'07:00',idleDimMin:0.42,
  idleSunsetDim:false,idleDimEarliest:'20:30',smartSilenceEnabled:true,smartSilenceMinutes:30,postIncidentQuietEnabled:true,postIncidentQuietSeconds:20,
  messageMinutes:3,maxAgeMinutes:5,
  dateFormat:'dd-mm-yyyy',idleCentered:true,
  burnInProtection:true,burnInPixels:12,
  autoTextSize:true,darkLedPercent:4,vehicleHeader:true,
  displaySleep:false,
  speechEnabled:true,speechMode:'normal',masterVolume:100,speechCities:[],speechRate:0.96,speechPitch:1.0,speechEngine:'online',
  speechDeviceVolumeDay:38,speechDeviceVolumeNight:20,speechDeviceVolumeUrgent:55,
  dispatchTuneEnabled:true,dispatchTuneDefault:'youtube',dispatchTuneBrandweer:'inherit',dispatchTuneAmbulance:'inherit',dispatchTunePolitie:'inherit',dispatchTuneLifeliner:'inherit',dispatchTuneKnrm:'inherit',dispatchTuneUrgent:'youtube',dispatchTuneYoutubeUrl:'https://www.youtube.com/watch?v=VleijwaD_-U',dispatchTuneYoutubeSeconds:5,dispatchTuneVolume:80,dispatchTuneCustomVersion:0,
  mapEnabled:true,mapZoom:16,backgroundStyle:'black',backgroundColor:'#020506',backgroundPhotoVersion:0,backgroundPhotoDarkness:.60,backgroundPhotoFit:'cover',kioskMonitor:'primary',
  locationAliases:{'Prof. Asserweg':'Professor Asserweg','Prof Asserweg':'Professor Asserweg'},
  ttsDictionary:{'Prof.':'Professor','OvD-G':'Officier van Dienst Geneeskundig','OvD-B':'Officier van Dienst Brandweer','MMT':'Mobiel Medisch Team','TS':'tankautospuit','HW':'hoogwerker'},
  capcodeMap:{'1220803':{label:'OvD-G 803 - Officier van Dienst Geneeskundig',speech:'Officier van Dienst Geneeskundig 803'},'1220804':{label:'OvD-G 804 - Officier van Dienst Geneeskundig',speech:'Officier van Dienst Geneeskundig 804'},'1220805':{label:'OvD-G 805 - Officier van Dienst Geneeskundig',speech:'Officier van Dienst Geneeskundig 805'}}
};
const state={
  settings:loadSettings(),setupProfile:{},messages:[],status:null,knownIds:new Set(),started:false,
  activeMessage:null,activeMessages:[],activeMessageIndex:0,activeUntil:0,lastDisplayedMessage:null,page:0,lastStep:Date.now(),lastMessageSwitch:Date.now(),arrivalSeq:0,liveExpiryTimer:null,liveExpiryAt:0,
  recentSignatures:new Map(),incidentMemory:new Map(),lastPowerWanted:null,lastTestToken:null,
  vehicleDb:{},vehicleDbMeta:null,vehiclePostMap:{},spokenIds:new Set(),currentSpeechAudio:null,speechRequestSeq:0,testBlackoutUntil:0,testIdleUntil:0,
  speechQueue:[],speechCurrent:null,speechJobTimer:null,speechJobSeq:0,
  audioStats:{attempts:0,successes:0,failures:0,fallbacks:0,lastError:'',lastMode:'',lastSuccessAt:0,unlocked:false},
  audioBus:{armed:false,locked:false,arming:null,primeUrl:'',blockedJobs:0},currentTuneStop:null,
  activityEvents:[],activityIds:new Map(),carouselShownAt:new Map(),
  lastRefreshAt:0,
  mapCache:new Map(),mapFailureCache:new Map(),currentMapKey:'',currentMapUrl:'',currentMapData:null,mapFetchKey:'',mapVisible:false,
  idleReturnBlackUntil:0,idleReturnFadeUntil:0,postIncidentQuietUntil:0,bootAt:Date.now(),lastP2000ActivityAt:0,
  renderPerf:{samples:[],lastMs:0}
};
const $=s=>document.querySelector(s);
const FONT={
' ':[0,0,0,0,0,0,0],
'A':[14,17,17,31,17,17,17],'B':[30,17,17,30,17,17,30],'C':[14,17,16,16,16,17,14],'D':[30,17,17,17,17,17,30],
'E':[31,16,16,30,16,16,31],'F':[31,16,16,30,16,16,16],'G':[14,17,16,23,17,17,15],'H':[17,17,17,31,17,17,17],
'I':[31,4,4,4,4,4,31],'J':[7,2,2,2,18,18,12],'K':[17,18,20,24,20,18,17],'L':[16,16,16,16,16,16,31],
'M':[17,27,21,21,17,17,17],'N':[17,25,21,19,17,17,17],'O':[14,17,17,17,17,17,14],'P':[30,17,17,30,16,16,16],
'Q':[14,17,17,17,21,18,13],'R':[30,17,17,30,20,18,17],'S':[15,16,16,14,1,1,30],'T':[31,4,4,4,4,4,4],
'U':[17,17,17,17,17,17,14],'V':[17,17,17,17,17,10,4],'W':[17,17,17,21,21,27,17],'X':[17,17,10,4,10,17,17],
'Y':[17,17,10,4,4,4,4],'Z':[31,1,2,4,8,16,31],
'0':[14,17,19,21,25,17,14],'1':[4,12,4,4,4,4,14],'2':[14,17,1,2,4,8,31],'3':[30,1,1,14,1,1,30],
'4':[2,6,10,18,31,2,2],'5':[31,16,16,30,1,1,30],'6':[14,16,16,30,17,17,14],'7':[31,1,2,4,8,8,8],
'8':[14,17,17,14,17,17,14],'9':[14,17,17,15,1,1,14],
':':[0,4,4,0,4,4,0],'.':[0,0,0,0,0,12,12],',':[0,0,0,0,4,4,8],'-':[0,0,0,31,0,0,0],
'/':[1,2,2,4,8,8,16],'+':[0,4,4,31,4,4,0],'(':[2,4,8,8,8,4,2],')':[8,4,2,2,2,4,8],
'=':[0,0,31,0,31,0,0],'?':[14,17,1,2,4,0,4],'!':[4,4,4,4,4,0,4],"'": [4,4,0,0,0,0,0],
'#':[10,31,10,10,31,10,0],'&':[12,18,20,8,21,18,13]
};
function cleanServiceSettings(v){const allowed=new Set(['brandweer','ambulance','politie','lifeliner','knrm','overig']);const rows=(Array.isArray(v)?v:DEFAULTS.services).filter(x=>allowed.has(String(x)));return rows.length?rows:[...DEFAULTS.services]}
function loadSettings(){try{const merged={...DEFAULTS,...JSON.parse(localStorage.getItem('p2000MonitorSettingsV4')||'{}'),idleSunsetDim:false};merged.services=cleanServiceSettings(merged.services);merged.speechEngine='online';return merged}catch{return {...DEFAULTS,speechEngine:'online'}}}
function norm(v){return String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[–—]/g,'-').replace(/[^A-Za-z0-9 :.,\-\/+()=?!'#&]/g,' ').replace(/\s+/g,' ').trim().toUpperCase()}
function asciiFold(v){return String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[–—]/g,'-')}
function normalizeLocationBase(v){
  return asciiFold(v).toLowerCase()
    .replace(/[.,;:()]/g,' ')
    .replace(/\bprof\.?\b/g,'professor')
    .replace(/\bburg\.?\b/g,'burgemeester')
    .replace(/\bdr\.?\b/g,'dokter')
    .replace(/\bst\.?\b/g,'sint')
    .replace(/\bgen\.?\b/g,'generaal')
    .replace(/\bkon\.?\b/g,'koningin')
    .replace(/\bpr\.?\b/g,'prins')
    .replace(/[^a-z0-9 -]/g,' ')
    .replace(/\s+/g,' ')
    .trim();
}
function normalizeLocationKey(v){
  let s=normalizeLocationBase(v);
  const aliases=state.settings?.locationAliases||{};
  for(const [from,to] of Object.entries(aliases)){
    if(normalizeLocationBase(from)===s){s=normalizeLocationBase(to);break;}
  }
  return s;
}
function sortDictEntries(d){return Object.entries(d||{}).sort((a,b)=>String(b[0]).length-String(a[0]).length)}
function escapeRegexText(s){return String(s||'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}
function applySpeechDictionary(text){
  let out=String(text||'').trim(); if(!out)return '';
  const dict={...(DEFAULTS.ttsDictionary||{}),...((state.settings&&state.settings.ttsDictionary)||{})};
  for(const [from,to] of sortDictEntries(dict)){
    const src=String(from||'').trim(),dst=String(to||'').trim();
    if(!src||!dst)continue;
    const pattern=escapeRegexText(src).replace(/\ /g,'\\s+');
    out=out.replace(new RegExp(`\\b${pattern}\\b`,'gi'), dst);
  }
  return out.replace(/\s+/g,' ').replace(/ ,/g,',').trim();
}
function capcodeConfig(){return {...(DEFAULTS.capcodeMap||{}),...((state.settings&&state.settings.capcodeMap)||{})}}
function parseCapcodeHits(m){
  const hay=`${m?.title||''} ${m?.summary||''} ${(m?.units||[]).join(' ')}`;
  const hits=[],seen=new Set();
  for(const match of hay.matchAll(/(?<!\d)(\d{7})(?!\d)/g)){
    const code=match[1]; if(seen.has(code))continue; seen.add(code); hits.push(code);
  }
  return hits;
}
function capcodeDetails(m){
  const cfg=capcodeConfig(),out=[];
  for(const code of parseCapcodeHits(m)){
    const meta=cfg[code]; if(!meta)continue;
    if(typeof meta==='string') out.push({key:`cap:${code}`,header:`${code} - ${meta}`,speech:meta,type:'CAPCODE'});
    else out.push({key:`cap:${code}`,header:meta.label?`${code} - ${meta.label}`:code,speech:meta.speech||meta.label||code,type:'CAPCODE'});
  }
  return out;
}
const BACKGROUND_PRESETS={black:'#020506',nightblue:'#04111d',graphite:'#111417',deepgreen:'#06140f',deepred:'#190809'};
function validHexColor(v){return /^#[0-9a-f]{6}$/i.test(String(v||''))?String(v):''}
function monitorBackgroundColor(){const style=String(state.settings?.backgroundStyle||'black').toLowerCase();if(style==='custom')return validHexColor(state.settings?.backgroundColor)||'#020506';return BACKGROUND_PRESETS[style]||BACKGROUND_PRESETS.black}
const backgroundPhoto={img:null,key:'',loaded:false,failed:false};
function backgroundPhotoWanted(){return String(state.settings?.backgroundStyle||'').toLowerCase()==='photo'&&Number(state.settings?.backgroundPhotoVersion||0)>0}
function syncBackgroundPhoto(){if(!backgroundPhotoWanted()){backgroundPhoto.img=null;backgroundPhoto.key='';backgroundPhoto.loaded=false;backgroundPhoto.failed=false;return}const version=Number(state.settings.backgroundPhotoVersion)||0,key=String(version);if(backgroundPhoto.key===key&&(backgroundPhoto.loaded||backgroundPhoto.img))return;const img=new Image();backgroundPhoto.img=img;backgroundPhoto.key=key;backgroundPhoto.loaded=false;backgroundPhoto.failed=false;img.decoding='async';img.onload=()=>{if(backgroundPhoto.img!==img)return;backgroundPhoto.loaded=true;backgroundPhoto.failed=false;invalidateIdleStatic();render()};img.onerror=()=>{if(backgroundPhoto.img!==img)return;backgroundPhoto.loaded=false;backgroundPhoto.failed=true;invalidateIdleStatic();render()};img.src=`/api/background/image?v=${encodeURIComponent(key)}`}
function drawBackgroundPhoto(c,w,h){if(!backgroundPhotoWanted()||!backgroundPhoto.loaded||!backgroundPhoto.img?.naturalWidth)return false;const img=backgroundPhoto.img,fit=String(state.settings.backgroundPhotoFit||'cover');const iw=img.naturalWidth,ih=img.naturalHeight;let dw,dh,dx,dy;if(fit==='contain'){const scale=Math.min(w/iw,h/ih);dw=iw*scale;dh=ih*scale;dx=(w-dw)/2;dy=(h-dh)/2}else{const scale=Math.max(w/iw,h/ih);dw=iw*scale;dh=ih*scale;dx=(w-dw)/2;dy=(h-dh)/2}c.drawImage(img,dx,dy,dw,dh);const dark=Math.max(0,Math.min(.9,Number(state.settings.backgroundPhotoDarkness??.60)));if(dark>0){c.fillStyle=`rgba(0,0,0,${dark})`;c.fillRect(0,0,w,h)}return true}
function drawMonitorBackground(c,w,h){c.fillStyle=monitorBackgroundColor();c.fillRect(0,0,w,h);if(backgroundPhotoWanted()){syncBackgroundPhoto();drawBackgroundPhoto(c,w,h)}}
function mapEnabled(){return state.settings.mapEnabled!==false}
function mapCanRender(){return mapEnabled()&&Math.max(Number(globalThis.innerWidth)||0,document.documentElement?.clientWidth||0)>920}
function mapPanelElements(){return {panel:$('#incidentMapPanel'),frame:$('#incidentMapFrame'),title:$('#incidentMapTitle'),city:$('#incidentMapCity'),meta:$('#incidentMapMeta'),loading:$('#incidentMapLoading'),route:$('#incidentMapRoute'),routeFrom:$('#incidentMapRouteFrom'),routeDistance:$('#incidentMapRouteDistance'),routeLink:$('#incidentMapRouteLink')}}
function hideIncidentMap(){
  const els=mapPanelElements(); if(!els.panel)return;
  els.panel.hidden=true; els.panel.classList.remove('visible');
  state.mapVisible=false; state.currentMapKey=''; state.currentMapUrl=''; state.currentMapData=null;
}
function locationWithoutCitySuffix(location,city){
  let out=String(location||'').trim(),place=String(city||'').trim();
  if(!out||!place)return out;
  const escaped=escapeRegex(place);
  // Keep the backslashes doubled: this is a RegExp *string*, not a regex literal.
  out=out.replace(new RegExp(`(?:[,\\s•–—-]+)?${escaped}\\s*$`,'i'),'').trim();
  return out;
}
function currentMapQuery(){
  if(!mapCanRender()||!activeVisible()||!state.activeMessage)return null;
  const m=state.activeMessage,city=String(speechCity(m)||m.city||'').trim();
  let location=locationWithoutCitySuffix(String(m.location||'').trim(),city);
  if(!location)location=locationWithoutCitySuffix(String(speechLocation(m)||'').trim(),city);
  if(!city&&!location)return null;
  const zoom=Math.max(12,Math.min(18,Number(state.settings.mapZoom)||16));
  return {city,location,zoom,key:`${normalizeLocationKey(city)}|${normalizeLocationKey(location)}|z${zoom}`};
}
function showMapLoading(q,message='Kaart laden…'){
  const els=mapPanelElements();if(!els.panel)return;
  const firstShow=!state.mapVisible||state.currentMapKey!==q.key;
  els.panel.hidden=false;els.panel.classList.add('visible');
  els.title.textContent=q.location||q.city||'Locatie';
  if(els.city)els.city.textContent=q.city||'';
  els.meta.textContent='Incidentlocatie bepalen…';
  if(els.route)els.route.hidden=true;
  if(els.loading){els.loading.hidden=false;els.loading.textContent=message;els.loading.classList.remove('error')}
  if(els.frame){els.frame.hidden=true}
  state.mapVisible=true;state.currentMapKey=q.key;
  if(firstShow)render();
}
function rememberMapFailure(key,message){
  state.mapFailureCache.set(key,{until:Date.now()+60*1000,message:String(message||'tijdelijk niet beschikbaar').slice(0,180)});
  while(state.mapFailureCache.size>100){const first=state.mapFailureCache.keys().next().value;if(!first)break;state.mapFailureCache.delete(first)}
}
function showMapError(q,message){
  const els=mapPanelElements();if(!els.panel)return;
  showMapLoading(q,'Kaart niet beschikbaar');
  if(els.loading){els.loading.hidden=false;els.loading.classList.add('error');els.loading.textContent='Kaart niet beschikbaar'}
  els.meta.textContent=`${q.city||''}${message?` • ${String(message).slice(0,110)}`:''}`;
}
function routeHomeQuery(){
  const label=String(state.setupProfile?.standplaats||'').trim(),city=String(state.setupProfile?.standplaats_city||'').trim();
  if(!label&&!city)return null;
  const same=label&&city&&normalizeLocationKey(label)===normalizeLocationKey(city);
  return {label:label||city,city:city||label,location:same?'':label,key:`home:${normalizeLocationKey(city||label)}|${normalizeLocationKey(same?'':label)}`};
}
function crowDistanceKm(a,b){
  const toRad=x=>Number(x)*Math.PI/180,lat1=toRad(a?.lat),lat2=toRad(b?.lat),dLat=lat2-lat1,dLon=toRad(Number(b?.lon)-Number(a?.lon));
  const h=Math.sin(dLat/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 6371*2*Math.atan2(Math.sqrt(Math.max(0,h)),Math.sqrt(Math.max(0,1-h)));
}
function routeMapData(map,home){
  if(!map||!home||!Number.isFinite(Number(home.lat))||!Number.isFinite(Number(home.lon)))return map;
  const distance=crowDistanceKm(home,map),label=routeHomeQuery()?.label||home.display_name||'standplaats';
  const navigationUrl=`https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(`${home.lat},${home.lon}`)}&destination=${encodeURIComponent(`${map.lat},${map.lon}`)}&travelmode=driving`;
  let embedUrl=map.embed_url;
  try{const u=new URL(embedUrl,location.origin);u.searchParams.set('originLat',String(home.lat));u.searchParams.set('originLon',String(home.lon));u.searchParams.set('originLabel',label);embedUrl=`${u.pathname}${u.search}`}catch{}
  return {...map,embed_url:embedUrl,route:{origin_label:label,origin_lat:Number(home.lat),origin_lon:Number(home.lon),distance_km:distance,navigation_url:navigationUrl}};
}
function applyMapData(q,map){
  const els=mapPanelElements(); if(!els.panel||!map||!map.embed_url)return;
  const wasVisible=state.mapVisible,changed=state.currentMapKey!==q.key||state.currentMapUrl!==map.embed_url;
  els.title.textContent=q.location||map.display_name||q.city||'Locatie';
  if(els.city)els.city.textContent=q.city||'';
  els.meta.textContent='Marker: incident • blauwe stip: standplaats';
  const route=map.route||null;
  if(els.route){els.route.hidden=!route;if(route){if(els.routeFrom)els.routeFrom.textContent=`Vanaf ${route.origin_label}`;if(els.routeDistance)els.routeDistance.textContent=`± ${route.distance_km<10?route.distance_km.toFixed(1):Math.round(route.distance_km)} km hemelsbreed`;if(els.routeLink){els.routeLink.href=route.navigation_url;els.routeLink.hidden=!route.navigation_url;}}}
  if(els.loading){els.loading.hidden=true;els.loading.classList.remove('error')}
  if(els.frame){els.frame.hidden=false;if(els.frame.dataset.src!==map.embed_url){els.frame.src=map.embed_url; els.frame.dataset.src=map.embed_url;}}
  els.panel.hidden=false; els.panel.classList.add('visible');
  state.mapVisible=true; state.currentMapKey=q.key; state.currentMapUrl=map.embed_url; state.currentMapData=map;
  if(!wasVisible||changed)render();
}
async function syncIncidentMap(){
  if(!activeVisible()){if(state.mapVisible||state.currentMapKey)hideIncidentMap();return}
  const q=currentMapQuery(); if(!q){hideIncidentMap(); return;}
  if(state.mapCache.has(q.key)){applyMapData(q,state.mapCache.get(q.key)); return;}
  const failed=state.mapFailureCache.get(q.key);
  if(failed&&Date.now()<failed.until){showMapError(q,failed.message||'tijdelijk niet beschikbaar');return;}
  if(failed)state.mapFailureCache.delete(q.key);
  if(state.mapFetchKey===q.key)return;
  showMapLoading(q);
  state.mapFetchKey=q.key;
  try{
    const homeQ=routeHomeQuery(),homeCached=homeQ?state.mapCache.get(homeQ.key):null;
    const incidentPromise=json(`/api/geocode?city=${encodeURIComponent(q.city)}&location=${encodeURIComponent(q.location)}&zoom=${encodeURIComponent(q.zoom)}`);
    const homePromise=!homeQ?Promise.resolve(null):homeCached?Promise.resolve({map:homeCached}):json(`/api/geocode?city=${encodeURIComponent(homeQ.city)}&location=${encodeURIComponent(homeQ.location)}&zoom=14`).catch(()=>null);
    const [d,homeData]=await Promise.all([incidentPromise,homePromise]);
    if(homeQ&&homeData?.map&&!homeCached)state.mapCache.set(homeQ.key,homeData.map);
    if(d?.map){const map=routeMapData(d.map,homeData?.map||homeCached);state.mapFailureCache.delete(q.key);state.mapCache.set(q.key,map);if(state.mapCache.size>250){const first=state.mapCache.keys().next().value;if(first)state.mapCache.delete(first)} if((currentMapQuery()||{}).key===q.key)applyMapData(q,map);}
    else{rememberMapFailure(q.key,'geen kaartresultaat');if((currentMapQuery()||{}).key===q.key)showMapError(q,'geen kaartresultaat');}
  }catch(e){
    console.warn('Locatiekaart laden mislukt',e);
    const message=e?.message||String(e);rememberMapFailure(q.key,message);
    if((currentMapQuery()||{}).key===q.key)showMapError(q,message);
  }finally{if(state.mapFetchKey===q.key)state.mapFetchKey='';}
}
function localDate(v){return v?new Date(v):null}
function pad2(n){return String(n).padStart(2,'0')}
function hhmm(v){const d=localDate(v)||new Date();return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`}
function hhmmss(v){const d=localDate(v)||new Date();return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`}
function formatDate(v){const d=localDate(v)||new Date();const dd=String(d.getDate()).padStart(2,'0'),mm=String(d.getMonth()+1).padStart(2,'0'),yyyy=d.getFullYear();if(state.settings.dateFormat==='yyyy-mm-dd')return `${yyyy}-${mm}-${dd}`;if(state.settings.dateFormat==='weekday'){const wd=['ZO','MA','DI','WO','DO','VR','ZA'][d.getDay()],mon=['JAN','FEB','MRT','APR','MEI','JUN','JUL','AUG','SEP','OKT','NOV','DEC'][d.getMonth()];return `${wd} ${dd} ${mon} ${yyyy}`}return `${dd}-${mm}-${yyyy}`}
function publishedMs(m){const ms=new Date(m?.published||0).getTime();return Number.isFinite(ms)?ms:0}
function ingestedMs(m){const ms=new Date(m?.ingested_at||0).getTime();return Number.isFinite(ms)?ms:0}
function compareMessageNewest(a,b){return publishedMs(b)-publishedMs(a)||ingestedMs(b)-ingestedMs(a)||messageArrivalSeq(b)-messageArrivalSeq(a)}
function messageAgeMs(m){const ms=publishedMs(m);return ms?Math.max(0,Date.now()-ms):Infinity}
function maxAgeMs(){return Math.max(.25,Number(state.settings.maxAgeMinutes)||5)*60*1000}
function visibleMs(){return Math.max(.25,Number(state.settings.messageMinutes)||3)*60*1000}
function isFresh(m){return messageAgeMs(m)<=maxAgeMs()}
const MMT_RESOURCES={
  '13991':{team:1,kind:'helicopter',label:'Lifeliner 1'},'13901':{team:1,kind:'car',label:'MMT-auto 1'},
  '17992':{team:2,kind:'helicopter',label:'Lifeliner 2'},'17902':{team:2,kind:'car',label:'MMT-auto 2'},'17901':{team:2,kind:'car',label:'MMT-auto 2'},
  '08993':{team:3,kind:'helicopter',label:'Lifeliner 3'},'08903':{team:3,kind:'car',label:'MMT-auto 3'}
};
function mmtResourceInfo(m){
  const hay=`${m?.title||''} ${m?.summary||''} ${(m?.units||[]).join(' ')}`;
  for(const [digits,meta] of Object.entries(MMT_RESOURCES)){const spaced=`${digits.slice(0,2)}[- ]?${digits.slice(2)}`;if(new RegExp(`(?<!\\d)${spaced}(?!\\d)`,'i').test(hay))return {code:digits,...meta}}
  const hit=/\b(?:life\s*liner|lifeliner|mmt|lfl|ll)\s*[- ]?0?([123])\b/i.exec(hay);
  return hit?{code:'',team:Number(hit[1]),kind:'helicopter',label:`Lifeliner ${hit[1]}`}:null;
}
function isLL23(m){return !!mmtResourceInfo(m)}
function llNumber(m){return mmtResourceInfo(m)?.team||null}
function ovdgNumber(m){const h=`${m.title||''} ${m.summary||''}`;const x=/12[- ]?2080([345])/.exec(h);return x?`80${x[1]}`:null}
function filterMessage(m){let svc=String(m?.service||'').toLowerCase();const resource=mmtResourceInfo(m);if(resource)svc=resource.kind==='helicopter'?'lifeliner':'ambulance';if(state.settings.services?.length&&!state.settings.services.includes(svc))return false;const cs=(state.settings.cities||[]).map(x=>x.toLowerCase()).filter(Boolean);if(cs.length&&!cs.some(c=>(m.city||'').toLowerCase().includes(c)))return false;const ks=(state.settings.keywords||[]).map(x=>x.toLowerCase()).filter(Boolean);if(ks.length){const hay=`${m.title||''} ${m.summary||''} ${m.city||''} ${m.location||''}`.toLowerCase();if(!ks.some(k=>hay.includes(k)))return false}return true}
function filteredMessages(){return state.messages.filter(filterMessage).sort(compareMessageNewest)}
function latestMessage(){return filteredMessages()[0]||null}
function cleanCandidate(value,m){let s=norm(value||'');const ll=llNumber(m),ovd=ovdgNumber(m);s=s.replace(/\(\s*DIA\s*:\s*(?:JA|NEE)\s*\)/g,' ').replace(/\bDIA\s*:?\s*(?:JA|NEE)?\b/g,' ');s=s.replace(/\b(?:P\s*[123]|A[012]|B[12])\b/g,' ');s=s.replace(/\b(?:AMBU|AMBULANCE|BRW|BRANDWEER|POLITIE|P2000)\b/g,' ');s=s.replace(/\b(?:RIT|BON)\s*:?\s*\d+\b/g,' ').replace(/\bREGIO\s*\d+\b/g,' ');s=s.replace(/\b\d{4}\s*[A-Z]{2}\b/g,' ');s=s.replace(/\b(?:13991|13901|17992|17902|17901|08993|08903|1220803|1220804|1220805)\b/g,' ');s=s.replace(/\b12[- ]?2080[345]\b/g,' ');s=s.replace(/\b[A-Z]{2,5}-\d{2}\b/g,' ');s=s.replace(/\b\d{5,8}\b/g,' ');s=s.replace(/\b(?:INZET|MELDING)\b(?=\s*$)/g,' ');s=s.replace(/\s+/g,' ').trim();if(ovd){s=s.replace(/\bOVD-?G\b/g,' ').replace(/\s+/g,' ').trim();s=`OVD-G ${ovd} ${s}`}if(ll&&!s.includes(`LIFELINER ${ll}`))s=`LIFELINER ${ll} ${s.replace(/\bMMT\s*(?:2|3)?\b/g,' ')}`;for(let i=0;i<3;i++)s=s.replace(/\b([A-Z0-9-]{2,})\s+\1\b/g,'$1');return norm(s)}
function cleanedCore(m){const title=cleanCandidate(m.title,m);const summary=cleanCandidate(m.summary,m);const generic=/^(?:MMT|LIFELINER [23])?(?: INZET)?$/;let s=title;if(summary&&!generic.test(summary)&&summary.length>title.length*.7){const titleWords=new Set(title.split(' '));const overlap=summary.split(' ').filter(w=>titleWords.has(w)).length;if(overlap>=Math.min(3,summary.split(' ').length))s=title.length>=summary.length?title:summary}return s||summary||norm(m.city||'MELDING')}
function rawScore(value){const s=norm(value||'');if(!s)return -999;let score=0;if(/^(?:P\s*[123]|A[012]|B[12])\b/.test(s))score+=8;if(/\b(?:B[A-Z]{2}-\d+|DIA|RIT\s*:|DIRECTE INZET|BR\s|OMS\s|MELDKAMER|OC\s|GRIP\s*[1-5])\b/.test(s))score+=5;if(/\b(?:\d{6,8}|\d{5,6})\b/.test(s))score+=3;if(/\b(?:TS|HV|HW|AL|RV|OVD|HOVD|AGS|VEBS|WTS?|WTH|MMT|AMBU?)?[- ]?\d{5,6}\b/.test(s))score+=2;if(/\b(?:MET SPOED NAAR|GEALARMEERD VOOR INCIDENT|ONGEVAL MET LETSEL OP|BRAND OP)\b/.test(s))score-=7;if(/^(?:AMBULANCE|BRANDWEER|TRAUMAHELI) MET SPOED/.test(s))score-=8;return score}
function rawDisplayText(v){return String(v??'').replace(/[\r\n\t]+/g,' ').replace(/\s+/g,' ').trim()}
function originalMessage(m){const title=rawDisplayText(m?.title||''),summary=rawDisplayText(m?.summary||''),titleNorm=norm(title),summaryNorm=norm(summary);if(/^(?:P\s*[1-5]|PRIO\s*[1-5]|A[012]|B[12])\b/i.test(title))return title;const ts=rawScore(titleNorm),ss=rawScore(summaryNorm);if(ss>ts)return summary;if(ts>ss)return title;if(summary&&summary!==title&&summary.length>title.length*1.25)return summary;return title||summary||rawDisplayText(m?.city||'MELDING')}
function displayMessageText(m){
  let s=rawDisplayText(originalMessage(m));
  s=s.replace(/https?:\/\/\S+/gi,' ')
    .replace(/\b(?:RIT|BON|RUN|MELDING|INCIDENT)(?:NUMMER|NR)?\s*:?\s*[A-Z0-9-]{4,}\b/gi,' ')
    .replace(/\(\s*DIA\s*:\s*(?:JA|NEE)\s*\)/gi,' ')
    .replace(/\bDIA\s*:?\s*(?:JA|NEE)?\b/gi,' ')
    .replace(/\b\d{4}\s*[A-Z]{2}\b/g,' ')
    .replace(/(?<!\d)\d{6,8}(?!\d)/g,' ');
  s=stripCallsignsForSpeech(s,m)
    .replace(/\s*[-|•;,]+\s*(?:BRON|RSS|P2000)\s*:?\s*$/i,' ')
    .replace(/\s+([,.;:])/g,'$1').replace(/\s+/g,' ').trim();
  return s||cleanedCore(m)||String(m?.city||'Melding');
}

// De meegeleverde JSON is slechts een optionele seed-cache. Onbekende landelijke
// brandweerroepnummers blijven generiek leesbaar en worden in Diagnose verzameld,
// zodat de monitor nooit afhankelijk is van een complete landelijke voertuiglijst.
const FALLBACK_VEHICLES={};

const CAPCODE_FALLBACK={...(DEFAULTS.capcodeMap||{})};
const FIRE_TYPE_DIGIT={
  '0':'DA/DB','1':'Waterongevallen','2':'OGS','3':'TS','4':'TS natuurbrand',
  '5':'Redvoertuig','6':'Bijzonder blusvoertuig','7':'HV','8':'Overig materieel','9':'Commando'
};
const FIRE_REGION_LABELS={
  '01':'Groningen','02':'Fryslân','03':'Drenthe','04':'IJsselland','05':'Twente','06':'Noord- en Oost-Gelderland','07':'Gelderland-Midden','08':'Gelderland-Zuid','09':'Utrecht','10':'Noord-Holland Noord','11':'Zaanstreek-Waterland','12':'Kennemerland','13':'Amsterdam-Amstelland','14':'Gooi en Vechtstreek','15':'Haaglanden','16':'Hollands Midden','17':'Rotterdam-Rijnmond','18':'Zuid-Holland Zuid','19':'Zeeland','20':'Midden- en West-Brabant','21':'Brabant-Noord','22':'Brabant-Zuidoost','23':'Limburg-Noord','24':'Zuid-Limburg','25':'Flevoland','26':'Landelijk/NIPV','28':'Defensie'
};
function vehicleByDigits(digits){return state.vehicleDb?.[digits]||FALLBACK_VEHICLES[digits]||null}
function rebuildVehiclePostMap(){
  const buckets={};
  for(const [digits,v] of Object.entries(state.vehicleDb||{})){
    if(!/^\d{6,7}$/.test(digits)||!v?.station)continue;
    const key=digits.slice(0,4),name=String(v.station).trim();if(!name)continue;
    (buckets[key]??={})[name]=((buckets[key]||{})[name]||0)+1;
  }
  const map={};for(const [key,counts] of Object.entries(buckets)){map[key]=Object.entries(counts).sort((a,b)=>b[1]-a[1])[0]?.[0]||''}state.vehiclePostMap=map;
}
function inferredFireVehicle(digits){
  if(!/^\d{6}$/.test(digits))return null;
  const region=digits.slice(0,2),tail=digits.slice(2),post=digits.slice(2,4),type=FIRE_TYPE_DIGIT[digits[4]]||'Brandweer';
  if(!FIRE_REGION_LABELS[region])return null;
  const station=state.vehiclePostMap?.[digits.slice(0,4)]||'';
  // A number-plan inference tells us the broad vehicle class, not the exact
  // station. Never present ``post 94`` as if it were verified vehicle data.
  const display=station?`${type} ${station}`:type;
  return {callsign:`${region}-${tail}`,type:type.startsWith('TS')?'TS':type==='HV'?'HV':'BRW',label:type,station,display,inferred:true,region:FIRE_REGION_LABELS[region]};
}
async function loadSetupProfile(){
  try{const d=await json('/api/setup');state.setupProfile=d.setup||{};return state.setupProfile}catch(e){state.setupProfile={};return state.setupProfile}
}

async function loadVehicleDb(){
  try{
    const data=await json('/api/vehicles');
    state.vehicleDb=(data&&data.vehicles)||{};
    state.vehicleDbMeta=(data&&data.meta)||null;
    rebuildVehiclePostMap();
  }catch(e){
    state.vehicleDb={};state.vehiclePostMap={};state.vehicleDbMeta={error:String(e),count:Object.keys(FALLBACK_VEHICLES).length};
    console.warn('Voertuigdatabase niet geladen; nummerplan-fallback actief',e);
  }
}
function vehicleDisplayLabel(v){
  if(!v)return '';
  if(v.api_primary||String(v.source||'').includes('SW Mediaproducties')){
    const code=String(v.function_code||v.type||'').trim(),name=String(v.function_name||v.label||code||'Brandweervoertuig').trim(),station=String(v.station_name||v.station||'').trim();
    const withCode=code&&name.toLocaleUpperCase('nl-NL')!==code.toLocaleUpperCase('nl-NL')?`${name} (${code})`:name;
    return `${withCode}${station?` — ${station}`:''}`.trim();
  }
  return String(v.display||[v.type,v.station].filter(Boolean).join(' '));
}
function vehicleHeaderFor(v,callsign){
  const natural=vehicleDisplayLabel(v);
  return (v?.api_primary||String(v?.source||'').includes('SW Mediaproducties'))?natural:`${callsign} - ${natural}`;
}
function vehicleSpeechLabel(v){
  if(!v)return '';
  const type=String(v.type||'').toUpperCase();
  const expanded={
    'TS':'tankautospuit','TS-RES':'reserve tankautospuit','HW':'hoogwerker','AL':'autoladder',
    'RV':'redvoertuig','HV':'hulpverleningsvoertuig','OVD-B':'Officier van Dienst Brandweer','DA-OVD':'Officier van Dienst Brandweer',
    'HOVD-B':'Hoofdofficier van Dienst Brandweer','OVD':'Officier van Dienst','HOVD':'Hoofdofficier van Dienst',
    'AGS':'Adviseur Gevaarlijke Stoffen','VEBS':'Verkenningseenheid Brandweer','WTS':'watertransportsysteem',
    'WTH':'watertankhaakarmbak','WTH-M':'watertankhaakarmbak','WTH-NWS':'watertankhaakarmbak natuurbrand',
    'WT':'watertankwagen','SB':'schuimblusvoertuig','WO':'waterongevallenvoertuig','HVT-KR':'hulpverleningsvoertuig met kraan',
    'TS-WS':'tankautospuit met waterscherm','TST-NB':'tankautospuit natuurbrandbestrijding','HW-32':'hoogwerker','HA':'haakarmvoertuig',
    'DPA':'dompelpomp en slangenwagen','DA':'dienstauto','DB':'dienstbus','DB-VEB':'verkenningseenheid brandweer','HA-K':'haakarmvoertuig','PM':'personeel-materieelvoertuig','FRB':'fast rescue boat',
    'AMB':'ambulance','MC':'medium care ambulance','MICU':'mobiele intensive care unit','RR':'rapid responder','BSH':'brandweer ondersteuningsvoertuig','GM':'groot materieelvoertuig','VW-LO':'logistiek voertuig','DV-DT':'drone-team voertuig'
  };
  let label=expanded[type]||String(v.label||v.display||type||'voertuig').replace(/\bTS-RES\b/i,'reserve tankautospuit').replace(/\bTS\b/i,'tankautospuit').replace(/\bHW\b/i,'hoogwerker').replace(/\bOVD-B\b/i,'Officier van Dienst Brandweer');
  if(type==='TS'&&/reserve/i.test(String(v.label||'')))label='reserve tankautospuit';
  const station=String(v.station||'').trim();
  // OvD-B/HOvD-B are mobile regional functions and have no fixed station.
  if(type==='OVD-B'||type==='HOVD-B'||type==='DA-OVD')return label;
  return [label,station].filter(Boolean).join(' ').replace(/\s+/g,' ').trim();
}
function vehicleDetails(m){
  const hay=`${m?.title||''} ${m?.summary||''} ${(m?.units||[]).join(' ')}`;
  const out=[],seen=new Set();
  const add=(key,header,speech,meta={})=>{key=String(key||header);if(!header||seen.has(key))return;seen.add(key);out.push({key,header,speech:speech||header,...meta})};
  for(const [digits,meta] of Object.entries(MMT_RESOURCES)){
    const spaced=`${digits.slice(0,2)}[- ]?${digits.slice(2)}`;
    if(new RegExp(`(?<!\\d)${spaced}(?!\\d)`,'i').test(hay)){
      const callsign=digits;
      add(digits,`${callsign} - ${meta.label}`,meta.kind==='helicopter'?meta.label:`Mobiel Medisch Team auto ${meta.team}`,{type:meta.kind==='helicopter'?'MMT-HELI':'MMT-AUTO',mmt:meta});
    }
  }
  const ovdSpecials=[
    [/(?<!\d)(?:1220803|12[- ]?20803)(?!\d)/i,'1220803','OvD-G 803 - Officier van Dienst Geneeskundig','Officier van Dienst Geneeskundig 803'],
    [/(?<!\d)(?:1220804|12[- ]?20804)(?!\d)/i,'1220804','OvD-G 804 - Officier van Dienst Geneeskundig','Officier van Dienst Geneeskundig 804'],
    [/(?<!\d)(?:1220805|12[- ]?20805)(?!\d)/i,'1220805','OvD-G 805 - Officier van Dienst Geneeskundig','Officier van Dienst Geneeskundig 805']
  ];
  for(const [re,key,header,speech] of ovdSpecials)if(re.test(hay))add(key,header,speech,{type:'OVD-G',isOfficer:true});
  // Any exact SW/local catalogue hit is a real unit regardless of discipline.
  // This makes future ambulance/police/KNRM API rows immediately useful too,
  // without teaching the frontend a new hardcoded number plan.
  for(const match of hay.matchAll(/(?<!\d)(\d{2}(?:[- ]?\d{2}[- ]?\d{3}|[- ]?\d{3,5}))(?!\d)/g)){
    const digits=String(match[1]||'').replace(/\D/g,''),v=vehicleByDigits(digits);if(!v)continue;
    const callsign=v?.callsign||match[1],type=String(v.type||'UNIT').toUpperCase();
    add(digits,vehicleHeaderFor(v,callsign),vehicleSpeechLabel(v),{type,station:v.station||'',isOfficer:/^(?:OVD|HOVD|DA-OVD|DB-OVD|AGS|VEBS)/.test(type)});
  }
  const fireService=String(m?.service||'').toLowerCase()==='brandweer';
  for(const match of hay.matchAll(/(?<!\d)(\d{2})[- ](\d{2})[- ](\d{3})(?!\d)/g)){
    const digits=`${match[1]}${match[2]}${match[3]}`,v=vehicleByDigits(digits),callsign=v?.callsign||`${match[1]}-${match[2]}-${match[3]}`;
    if(!fireService&&!v)continue;
    if(v){const type=String(v.type||'BRW').toUpperCase();add(digits,vehicleHeaderFor(v,callsign),vehicleSpeechLabel(v),{type,station:v.station||''})}
    else add(digits,`${callsign} - Brandweer ${FIRE_REGION_LABELS[match[1]]||''}`.trim(),`brandweervoertuig ${FIRE_REGION_LABELS[match[1]]||''}`.trim(),{type:'BRW'});
  }
  for(const match of hay.matchAll(/(?<!\d)(\d{2})[- ]?(\d{4})(?!\d)/g)){
    const digits=`${match[1]}${match[2]}`,exact=vehicleByDigits(digits);
    if(!fireService&&!exact)continue;
    const v=exact||inferredFireVehicle(digits),callsign=v?.callsign||`${match[1]}-${match[2]}`;
    if(v){
      let header=vehicleHeaderFor(v,callsign);
      let speech=vehicleSpeechLabel(v);
      if(digits==='200064'&&/\bASS\.?\s*AMBU\s*\(\s*REDDINGSKUSSEN\s*\)/i.test(norm(hay))){header=`${callsign} - Sprongredder Breda`;speech='sprongredder Breda'}
      const type=String(v.type||'').toUpperCase();
      add(digits,header,speech,{type,station:v.station||'',isOfficer:/^(?:OVD|HOVD|DA-OVD|DB-OVD|AGS|VEBS)/.test(type)});
    }else{const type=FIRE_TYPE_DIGIT[digits[4]]||'Brandweer';add(digits,`${callsign} - ${type}`,type,{type:'UNKNOWN'})}
  }
  // Landelijk ambulance-nummerplan: regiocode + drie cijfers. Exacte ambulance
  // labels zijn optioneel; deze database is primair voor brandweer.
  if(String(m?.service||'').toLowerCase()==='ambulance')for(const match of hay.matchAll(/(?<!\d)(\d{2})[- ]?(\d{3})(?!\d)/g)){
    const digits=`${match[1]}${match[2]}`,v=vehicleByDigits(digits),callsign=v?.callsign||`${match[1]}-${match[2]}`;
    if(v){
      const type=String(v.type||'AMB').toUpperCase();
      add(digits,vehicleHeaderFor(v,callsign),vehicleSpeechLabel(v),{type,station:v.station||''});
    }else add(digits,`${callsign} - Ambulance`,'ambulance',{type:'AMB'});
  }
  for(const raw of (m?.units||[])){
    const unit=String(raw||'').trim();if(!unit)continue;
    const mmt=Object.entries(MMT_RESOURCES).find(([digits])=>unit.replace(/\D/g,'').includes(digits));
    if(mmt&&!seen.has(mmt[0])){const [digits,meta]=mmt;const callsign=digits;add(digits,`${callsign} - ${meta.label}`,meta.kind==='helicopter'?meta.label:`Mobiel Medisch Team auto ${meta.team}`,{type:meta.kind==='helicopter'?'MMT-HELI':'MMT-AUTO',mmt:meta})}
    else if(/\b(?:LIFELINER|MMT)[ -]?[123]\b/i.test(unit)&&!out.some(x=>x.header.toLowerCase().includes(unit.toLowerCase())))add(`unit:${unit.toLowerCase()}`,unit,unit.replace(/MMT/i,'Mobiel Medisch Team'),{type:'MMT'});
  }
  for(const item of capcodeDetails(m)){if(!seen.has(item.key)){seen.add(item.key);out.push(item)}}
  return out.slice(0,30);
}
function compactVehicleHeader(m){return vehicleDetails(m).map(v=>v.header).join('  •  ')}
function dutchCount(n,singular,plural){const words={1:'één',2:'twee',3:'drie',4:'vier',5:'vijf',6:'zes',7:'zeven',8:'acht',9:'negen',10:'tien',11:'elf',12:'twaalf'};return `${words[n]||n} ${n===1?singular:plural}`}
function joinSpeechParts(parts){if(!parts.length)return'';if(parts.length===1)return parts[0];if(parts.length===2)return `${parts[0]} en ${parts[1]}`;return `${parts.slice(0,-1).join(', ')} en ${parts.at(-1)}`}
function vehicleSpeechPhrase(m){
  const details=vehicleDetails(m),labels=details.map(v=>v.speech).filter(Boolean);
  if(!labels.length)return '';
  if(labels.length<=6){if(labels.length===1)return `Gealarmeerd voertuig: ${labels[0]}.`;if(labels.length===2)return `Gealarmeerde voertuigen: ${labels[0]} en ${labels[1]}.`;return `Gealarmeerde voertuigen: ${labels.slice(0,-1).join(', ')} en ${labels.at(-1)}.`}
  const counts={ts:0,hw:0,hv:0,water:0,officers:0,mmtHeli:0,mmtCar:0,other:0};
  for(const v of details){const t=String(v.type||'').toUpperCase();if(/^(?:TS|TS-RES|TST-NB|TS-WS)/.test(t))counts.ts++;else if(/^(?:HW|AL|RV)/.test(t))counts.hw++;else if(/^(?:HV|HVT-KR)/.test(t))counts.hv++;else if(/^(?:WT|WTS|WTH|DPA)/.test(t))counts.water++;else if(v.isOfficer)counts.officers++;else if(t==='MMT-HELI')counts.mmtHeli++;else if(t==='MMT-AUTO')counts.mmtCar++;else counts.other++}
  const parts=[];
  if(counts.ts)parts.push(dutchCount(counts.ts,'tankautospuit','tankautospuiten'));
  if(counts.hw)parts.push(dutchCount(counts.hw,'hoogwerker','hoogwerkers'));
  if(counts.hv)parts.push(dutchCount(counts.hv,'hulpverleningsvoertuig','hulpverleningsvoertuigen'));
  if(counts.water)parts.push(counts.water===1?'watertransport':'meerdere watertransporteenheden');
  if(counts.mmtHeli)parts.push(dutchCount(counts.mmtHeli,'MMT-helikopter','MMT-helikopters'));
  if(counts.mmtCar)parts.push(dutchCount(counts.mmtCar,'MMT-auto','MMT-auto’s'));
  if(counts.officers)parts.push(counts.officers===1?'één leidinggevende':'meerdere leidinggevenden');
  if(counts.other)parts.push(dutchCount(counts.other,'overige eenheid','overige eenheden'));
  return `Gealarmeerde inzet: ${joinSpeechParts(parts)}.`;
}
function detectOvdHeader(hay){
  let m=/(?<!\d)(?:1220803|12[- ]?20803)(?!\d)/.exec(hay);if(m)return 'OvD-G 803 - Officier van Dienst Geneeskundig';
  m=/(?<!\d)(?:1220804|12[- ]?20804)(?!\d)/.exec(hay);if(m)return 'OvD-G 804 - Officier van Dienst Geneeskundig';
  m=/(?<!\d)(?:1220805|12[- ]?20805)(?!\d)/.exec(hay);if(m)return 'OvD-G 805 - Officier van Dienst Geneeskundig';
  return '';
}
function priorityRank(p){return {P3:1,P2:2,P1:3,B2:1,B1:2,A2:2,A1:3,A0:4}[norm(p)]||0}
function bodyFor(m){return displayMessageText(m)}

function escapeRegex(v){return String(v??'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}
function speechScale(m){
  const h=norm(`${m?.scale||''} ${originalMessage(m)}`),parts=[];
  if(/\bZEER\s+(?:GROTE|GR\.?)\s+(?:BR|BRAND)\b/.test(h))parts.push('Zeer grote brand');
  else if(/\b(?:GROTE|GR\.?)\s+(?:BR|BRAND)\b/.test(h))parts.push('Grote brand');
  else if(/\bMIDDEL\s*(?:BR|BRAND)\b/.test(h))parts.push('Middelbrand');
  const grip=/\bGRIP\s*([1-5])\b/.exec(h);if(grip)parts.push(`GRIP ${grip[1]}`);
  if(parts.length<=1)return parts[0]||'';
  return `${parts.slice(0,-1).join(', ')} en ${parts.at(-1)}`;
}
function speechCity(m){
  const allowed=(state.settings.speechCities||[]).map(x=>String(x).trim()).filter(Boolean);
  const explicit=String(m?.city||'').trim();
  // De backend handhaaft het gekozen installatieprofiel. Een lege extra spraaklijst
  // betekent daarom: spreek iedere melding die door regio/discipline-filtering komt.
  if(!allowed.length)return explicit;
  const direct=allowed.find(c=>c.toLocaleLowerCase('nl-NL')===explicit.toLocaleLowerCase('nl-NL'));
  if(direct)return direct;
  const raw=`${m?.title||''} ${m?.summary||''}`;
  return allowed.find(c=>new RegExp(`\\b${escapeRegex(c)}\\b`,'i').test(raw))||'';
}
function parentheticalValues(m){
  const raw=originalMessage(m),out=[];
  for(const hit of raw.matchAll(/\(([^)]{1,80})\)/g)){
    let v=String(hit[1]||'').trim();if(!v)continue;
    const up=norm(v);
    if(/^(?:DIA\s*:|KW\s*\d+|UITBR\s*:|SOORT\s+THV\s*:|THV\s*:|MELDING\b|GRIP\s*[1-5]\b|MIDDEL\s+(?:BR|BRAND)|(?:GROTE|GR\.?)\s+(?:BR|BRAND)|ZEER\s+(?:GROTE|GR\.?)\s+(?:BR|BRAND))/.test(up))continue;
    out.push(v);
  }
  return out;
}
function firstUsefulSubtype(m,max=42){
  const v=parentheticalValues(m)[0]||'';
  return !v||v.length>max?'':sentenceCaseSpeech(v);
}
function roadFireSubtype(m){
  const h=norm(originalMessage(m));
  const hit=/\b(?:BR|BRAND)\s+WEGVERVOER\s*\(\s*([^)]+?)\s*\)/.exec(h);
  if(!hit)return '';
  let v=String(hit[1]||'').replace(/^(?:SOORT\s+)?(?:VOERTUIG|WEGVERVOER)\s*:\s*/i,'').trim();
  if(!v||v.length>32||/\b(?:KW|UITBR|SOORT\s+THV|THV|MELDING)\b/i.test(v))return '';
  return sentenceCaseSpeech(v);
}
function assistSubtype(m,kind){
  const h=norm(originalMessage(m));
  const re=kind==='politie'?/\bASS\.?\s*POL\s*\(\s*([^)]+?)\s*\)/:/\bASS\.?\s*AMBU\s*\(\s*([^)]+?)\s*\)/;
  const hit=re.exec(h);if(!hit)return '';
  let v=String(hit[1]||'').trim();
  if(!v||v.length>48||/\b(?:KW|UITBR|SOORT\s+THV|THV|MELDING|MIDDEL|GROTE\s+BR)\b/i.test(v))return '';
  return sentenceCaseSpeech(v);
}
function assistAmbuType(m){
  const sub=assistSubtype(m,'ambulance'),u=norm(sub);
  if(!sub)return 'Assistentie ambulance';
  if(/REDDINGSKUSSEN|SPRONGRED/.test(u))return 'Assistentie ambulance met reddingskussen';
  if(/AFHIJS|HIJSASSIST|AFHIJSEN/.test(u))return 'Assistentie ambulance bij afhijsen';
  if(/TILASSIST|TILHULP|TILLEN/.test(u))return 'Assistentie ambulance met tilhulp';
  if(/TOEGANG|DEUR|BUIITENSLUIT/.test(u))return 'Assistentie ambulance voor toegang';
  return `Assistentie ambulance, ${sub.toLocaleLowerCase('nl-NL')}`;
}
function assistPoliceType(m){
  const h=norm(originalMessage(m)),sub=assistSubtype(m,'politie'),u=norm(sub);
  if(/ZICHTSCHERM(?:EN)?/.test(h)||/ZICHTSCHERM(?:EN)?/.test(u))return 'Assistentie politie met zichtschermen';
  if(!sub)return 'Assistentie politie';
  return `Assistentie politie, ${sub.toLocaleLowerCase('nl-NL')}`;
}
function industryFireType(m){
  const h=norm(originalMessage(m));
  if(/\(\s*WATERSCHERM\s*\)/.test(h))return 'Industriebrand met waterscherm';
  return 'Industriebrand';
}
function stormDamageType(m){
  const raw=String(originalMessage(m)||'');
  const hit=/STORMSCHADE\s*\(\s*SOORT\s+GEVAAR\s*:\s*([^)]+?)\s*\)/i.exec(raw);
  if(!hit)return 'Stormschade';
  const sub=String(hit[1]||'').trim().toLocaleLowerCase('nl-NL');
  if(!sub)return 'Stormschade';
  if(/\bboom\b/i.test(sub))return 'Stormschade door boom';
  return `Stormschade door ${sub}`;
}
function naturalRoadSpeechLocation(v){
  let s=String(v||'').trim();
  // Rijkswegnotatie is landelijk compact. Spreek de betekenis uit zonder de
  // originele P2000-regel op het scherm te herschrijven.
  s=s.replace(/\b([AN]\d{1,3})\s+li\s+(\d{1,3})[,.](\d)\b/ig,'$1 links hectometer $2 komma $3');
  s=s.replace(/\b([AN]\d{1,3})\s+re\s+(\d{1,3})[,.](\d)\b/ig,'$1 rechts hectometer $2 komma $3');
  s=s.replace(/\b([AN]\d{1,3})\s+li\b/ig,'$1 links');
  s=s.replace(/\b([AN]\d{1,3})\s+re\b/ig,'$1 rechts');
  s=s.replace(/(^|[\s-])kp\.?\s+/ig,'$1knooppunt ');
  s=s.replace(/\bst\.\s*(?=[a-zà-ÿ])/ig,'Sint ');
  s=s.replace(/\s+-\s+/g,' - ').replace(/\s+/g,' ').trim();
  return s;
}
function contextualFireType(m,base){
  const sub=firstUsefulSubtype(m),u=norm(sub);
  if(!sub)return base;
  const exact=[
    [/^DAK$/, 'Dakbrand'],[/SCHOORSTEEN/, 'Schoorsteenbrand'],[/METERKAST/, 'Brand in meterkast'],
    [/^KEUKEN$/, 'Keukenbrand'],[/^ZOLDER$/, 'Zolderbrand'],[/^KELDER$/, 'Kelderbrand'],[/^GARAGE$/, 'Garagebrand'],
    [/^BALKON$/, 'Balkonbrand'],[/^SCHUUR$/, 'Schuurbrand'],[/^LOODS$/, 'Loodsbrand'],[/^STAL$/, 'Stalbrand'],
    [/^APPARTEMENT$/, 'Appartementbrand'],[/^FLAT$/, 'Flatbrand'],[/^PORTIEK$/, 'Portiekbrand'],[/^BIJGEBOUW$/, 'Brand bijgebouw']
  ];
  for(const [re,label] of exact)if(re.test(u))return label;
  if(/^(?:TUSSEN|HOEK|VRIJSTAANDE?)WONING$/.test(u))return `${base} in ${sub.toLocaleLowerCase('nl-NL')}`;
  return base;
}
function speechIncidentInfo(m){
  const h=norm(originalMessage(m)),roadSubtype=roadFireSubtype(m);
  const rules=[
    [/\bSCHIET(?:PARTIJ|INCIDENT)\b/,'Schietpartij',true,true],
    [/\bSTEEK(?:PARTIJ|INCIDENT)\b/,'Steekpartij',true,true],
    [/\bASS\.?\s*AMBU\b/,()=>assistAmbuType(m),true,false],
    [/\bASS\.?\s*POL\b/,()=>assistPoliceType(m),true,false],
    [/\bZICHTSCHERM(?:EN)?\b/,'Zichtschermen',true,false],
    [/\b(?:OMS|PAC)\b(?:\s+(?:BRANDMELDING|MELDING))?|\bAUTOMATISCH(?:E)?\s+BRAND(?:ALARM|MELDING)\b|\bBRANDMELDINSTALLATIE\b/,'Automatische brandmelding',true,false],
    [/\bHANDMELDER\b/,'Handbrandmelder',true,false],
    [/\bNACONTROLE\b/,'Nacontrole brand',true,false],
    [/\bBRANDGERUCHT\b/,'Brandgerucht',true,false],
    [/\bROOKONTWIKKELING\b/,'Rookontwikkeling',true,false],
    [/\b(?:CO|KOOLMONOXIDE)[ -]?(?:MELDER|MELDING)?\b/,'Koolmonoxidemelding',true,false],
    [/\bGAS(?:LUCHT|LEKKAGE|LEK)\b/,'Gaslucht',true,false],
    [/\bSTANK\s*\/?\s*HIND\.?\s+LUCHT\b|\bSTANKOVERLAST\b/,'Stank- of hinderlijke lucht',true,false],
    [/\b(?:IBGS|OGS|GEVAARLIJKE\s+STOFFEN|LEKKAGE\s+GEVAARLIJKE\s+STOF)\b/,'Incident gevaarlijke stoffen',true,false],
    [/\bPERSOON\s+TE\s+WATER\b/,'Persoon te water',true,false],
    [/\bVOERTUIG\s+TE\s+WATER\b/,'Voertuig te water',true,false],
    [/\bDIER\s+TE\s+WATER\b/,'Dier te water',true,false],
    [/\b(?:WATERONGEVAL|ONGEVAL\s+WATER|HV\s+WATER)\b/,'Waterongeval',true,false],
    [/\bPERSOON\s+(?:OP|VAN)\s+HOOGTE\b/,'Persoon op hoogte',true,false],
    [/\bPERSOON\s+BEKNELD\b|\bBEKNELLING\b/,'Persoon bekneld',true,false],
    [/\bLIFT(?:OPSLUITING|INS\s*LUITING)?\b|\bHV\s+LIFT\b/,'Liftopsluiting',true,false],
    [/\b(?:DIER\s+IN\s+PROBLEMEN|HV\s+DIER)\b/,'Dier in problemen',true,false],
    [/\b(?:STORMSCHADE|HV\s+STORM)\b/,()=>stormDamageType(m),true,false],
    [/\b(?:WATEROVERLAST|HV\s+WATEROVERLAST)\b/,'Wateroverlast',true,false],
    [/\b(?:BUITENSLUITING|BUITEN\s+SLUITING|HV\s+BUITENSLUITING)\b/,'Buitensluiting',true,false],
    [/\b(?:AFHIJSEN|AFHIJSING)\b/,'Afhijsen',true,false],
    [/\b(?:TILASSISTENTIE|TILHULP)\b/,'Tilhulp',true,false],
    [/\b(?:BR|BRAND)\s+WEGVERVOER\b/,roadSubtype?`Brand wegvervoer ${roadSubtype.toLocaleLowerCase('nl-NL')}`:'Brand wegvervoer',true,false],
    [/\bONGEVAL\s+WEGVERVOER\b/,'Ongeval wegvervoer',true,false],
    [/\bONGEVAL\s+(?:SPOORVERVOER|TREIN)\b/,'Ongeval spoorvervoer',true,false],
    [/\bONGEVAL\s+(?:SCHEEPVAART|VAARTUIG)\b/,'Ongeval scheepvaart',true,false],
    [/\bONGEVAL\s+LUCHTVAART\b/,'Ongeval luchtvaart',true,false],
    [/\b(?:BR|BRAND)\s+NATUUR\b/,'Natuurbrand',true,false],
    [/\b(?:BR|BRAND)\s+BOS\b/,'Bosbrand',true,false],
    [/\b(?:BR|BRAND)\s+(?:HEIDE|RIET|BOSSAGE)\b/,'Natuurbrand',true,false],
    [/\b(?:BR|BRAND)\s+INDUSTRIE\b/,()=>industryFireType(m),true,false],
    [/\b(?:BR|BRAND)\s+SCHEEPVAART\b/,'Brand scheepvaart',true,false],
    [/\b(?:BR|BRAND)\s+(?:VAARTUIG|BOOT)\b/,'Vaartuigbrand',true,false],
    [/\b(?:BR|BRAND)\s+(?:SPOORVERVOER|TREIN)\b/,'Brand spoorvervoer',true,false],
    [/\b(?:BR|BRAND)\s+LUCHTVAART\b/,'Brand luchtvaart',true,false],
    [/\b(?:BR|BRAND)\s+(?:AFVAL|VUILNIS)\b/,'Afvalbrand',true,false],
    [/\b(?:BR|BRAND)\s+CONTAINER\b/,'Containerbrand',true,false],
    [/\b(?:BR|BRAND)\s+BERM\b/,'Bermbrand',true,false],
    [/\b(?:BR|BRAND)\s+(?:AUTO|PERSONENAUTO|BESTELBUS|VRACHTWAGEN|BUS|MOTOR|SCOOTER)\b/,'Voertuigbrand',true,false],
    [/\b(?:BR|BRAND)\s+WONING\b/,()=>contextualFireType(m,'Woningbrand'),false,false],
    [/\b(?:BR|BRAND)\s+GEBOUW\b/,()=>contextualFireType(m,'Gebouwbrand'),false,false],
    [/\b(?:BR|BRAND)\s+BIJGEBOUW\b/,'Brand bijgebouw',false,false],
    [/\b(?:BR|BRAND)\s+SCHUUR\b/,'Schuurbrand',false,false],
    [/\b(?:BR|BRAND)\s+LOODS\b/,'Loodsbrand',false,false],
    [/\b(?:BR|BRAND)\s+AGRARISCH\b/,'Agrarische brand',false,false],
    [/\b(?:BR|BRAND)\s+BUITEN\b/,'Buitenbrand',false,false],
    [/\b(?:BR|BRAND)\s+VOERTUIG\b/,'Voertuigbrand',false,false],
    [/\bONGEVAL\b/,'Ongeval',true,false],
    [/\bREANIMATIE\b/,'Reanimatie',true,false],
    [/\bLETSEL\b/,'Ongeval met letsel',true,false],
    [/\bOVERVAL\b/,'Overval',true,false],
    [/\bBEROVING\b/,'Beroving',true,false],
    [/\bVECHTPARTIJ\b/,'Vechtpartij',true,false],
    [/\bVERDACHTE\s+SITUATIE\b/,'Verdachte situatie',true,false],
    [/\bVERMISSING\b/,'Vermissing',true,false],
    [/\bONGEVAL\s+(?:LETSEL|BEKNELLING)\b/,'Ongeval',true,false],
    [/\b(?:LIFELINER|MMT)\b|(?<!\d)(?:13991|13901|17992|17902|17901|08993|08903)(?!\d)/,'Mobiel Medisch Team',true,false],
    [/\bAMBU\b/,'Medische inzet',true,false],
    [/\bHV\s+OVERIG\b/,'Hulpverlening',true,false],
    [/\b(?:BR|BRAND)\b/,'Brand',false,false]
  ];
  for(const [regex,type,trigger,always] of rules)if(regex.test(h))return {type:typeof type==='function'?type():type,trigger,always:!!always,regex};
  return {type:'Incident',trigger:false,always:false,regex:null};
}
function urgencyInfo(m){
  const h=norm(`${m?.scale||''} ${originalMessage(m)}`),info=speechIncidentInfo(m);
  const grip=/\bGRIP\s*([1-5])\b/.exec(h);
  if(grip)return {rank:5,label:`GRIP ${grip[1]}`,special:true,volume:100,speechPriority:100,carouselWeight:3};
  if(/\bSCHIET(?:PARTIJ|INCIDENT)\b/.test(h))return {rank:5,label:'SCHIETPARTIJ',special:true,volume:100,speechPriority:98,carouselWeight:3};
  if(/\bSTEEK(?:PARTIJ|INCIDENT)\b/.test(h))return {rank:5,label:'STEEKPARTIJ',special:true,volume:100,speechPriority:98,carouselWeight:3};
  if(/\bZEER\s+(?:GROTE|GR\.?)\s+(?:BR|BRAND)\b/.test(h))return {rank:4,label:'ZEER GROTE BRAND',special:true,volume:92,speechPriority:88,carouselWeight:2};
  if(mmtResourceInfo(m))return {rank:3,label:mmtResourceInfo(m).kind==='helicopter'?'MMT HELIKOPTER':'MMT AUTO',special:false,volume:84,speechPriority:76,carouselWeight:2};
  if(/\b(?:WATEROVERLAST|STORMSCHADE|LIFTOPSLUITING|DIER IN PROBLEMEN)\b/.test(h)||/^(?:Wateroverlast|Stormschade|Liftopsluiting)/i.test(info.type))return {rank:1,label:'',special:false,volume:55,speechPriority:30,carouselWeight:1};
  return {rank:2,label:'',special:false,volume:72,speechPriority:50,carouselWeight:1};
}

// Night audio curve for P2000 announcements. The firehouse screen may be awake
// all night, but ordinary dispatches should not hit daytime volume at 03:00.
// Grote brand+, GRIP and shootings deliberately bypass the reduction.
function nightSpeechExempt(m){
  const h=norm(`${m?.scale||''} ${originalMessage(m)}`);
  return /\bGRIP\s*[1-5]\b/.test(h)
    || /\bSCHIET(?:PARTIJ|INCIDENT)\b/.test(h)
    || /\b(?:ZEER\s+)?GROTE\s+(?:BR|BRAND)\b/.test(h)
    || /\bZEER\s+GR\.?\s+(?:BR|BRAND)\b/.test(h);
}
function nightSpeechFactor(now=new Date()){
  const minute=now.getHours()*60+now.getMinutes()+now.getSeconds()/60;
  // 07:00-22:00: full daytime level.
  if(minute>=7*60&&minute<22*60)return 1;
  // 22:00 -> 02:00: gently descend from 85% to 65%.
  if(minute>=22*60){const p=(minute-22*60)/(4*60);return .85-.20*Math.max(0,Math.min(1,p));}
  if(minute<2*60){const p=(minute+2*60)/(4*60);return .85-.20*Math.max(0,Math.min(1,p));}
  // 02:00-04:30: deepest-night plateau.
  if(minute<4*60+30)return .65;
  // 04:30 -> 07:00: slowly return from 65% to normal.
  const p=(minute-(4*60+30))/(2.5*60);return .65+.35*Math.max(0,Math.min(1,p));
}
function speechVolumeForTime(m,baseVolume,now=new Date()){
  const master=Math.max(0,Math.min(100,Number(state.settings.masterVolume??100)))/100;
  const base=Math.max(0,Math.min(100,Number.isFinite(Number(baseVolume))?Number(baseVolume):0));
  if(master<=0)return 0;
  if(nightSpeechExempt(m))return Math.round(base*master);
  const factor=nightSpeechFactor(now);
  if(factor>=.999)return Math.round(base*master);
  // Keep a normal low-priority dispatch audible even at the quietest point.
  const nightAdjusted=Math.max(38,Math.min(base,Math.round(base*factor)));
  return Math.round(nightAdjusted*master);
}
function speechDeviceVolumeForTime(){
  // Laat de globale OS-volumemixer ongemoeid. Alleen het volume van het
  // media-element in het lichtkrant-tabblad wordt aangepast.
  return null;
}
function linkedAgencyServices(m){
  if(!m)return [];
  const at=publishedMs(m)||Date.now(),city=norm(m.city||''),loc=normalizeLocationKey(m.location||''),services=new Set([String(m.service||'overig')]);
  for(const x of (state.messages||[])){
    if(!x||x.id===m.id||Math.abs((publishedMs(x)||0)-at)>10*60*1000)continue;
    const sameIncident=!!m.incident_key&&m.incident_key===x.incident_key;
    const xcity=norm(x.city||''),xloc=normalizeLocationKey(x.location||'');
    const samePlace=city&&city===xcity&&loc&&xloc&&(loc===xloc||loc.includes(xloc)||xloc.includes(loc));
    if(sameIncident||samePlace){const svc=String(x.service||'overig').toLowerCase();if(svc!=='ambulance'&&filterMessage(x))services.add(svc);}
  }
  return [...services].filter(Boolean);
}
function multiAgencyLabel(m){const services=linkedAgencyServices(m);if(services.length<2)return'';const map={brandweer:'BRW',politie:'POL',ambulance:'AMB',lifeliner:'MMT',knrm:'KNRM'};return `MULTI-AGENCY  •  ${services.map(s=>map[s]||String(s).toUpperCase()).join(' + ')}`}
function speechWindowOpen(now=new Date()){
  const d=now instanceof Date?now:new Date(now);
  // Since v2.11.2 P2000 speech is available 24/7. Night-time quietness is
  // handled by speechVolumeForTime() instead of muting ordinary incidents.
  return !Number.isNaN(d.getTime());
}
function priorityModeEligible(m){
  const u=urgencyInfo(m),raw=norm(originalMessage(m)).toUpperCase();
  if(Number(u?.rank)>=3||Number(m?.scale_score||0)>=1)return true;
  return /\b(?:MIDDEL|GROTE|ZEER\s+GROTE)\s+(?:BR|BRAND)\b|\bGRIP\s*[1-5]\b|SCHIET|STEEK|BR\s+(?:NATUUR|BOS|INDUSTRIE)|ONGEVAL\s+WEGVERVOER|ASS\.?\s*POL/i.test(raw);
}
function shouldSpeakMessage(m,now=new Date()){
  if(!state.settings.speechEnabled||Number(state.settings.masterVolume??100)<=0||!speechCity(m))return false;
  const mode=String(state.settings.speechMode||'normal').toLowerCase();
  if(mode==='mute')return false;
  if(mode==='priority'&&!priorityModeEligible(m))return false;
  return speechWindowOpen(now);
}
function sentenceCaseSpeech(v){
  const s=String(v||'').trim().toLocaleLowerCase('nl-NL');
  return s?s.charAt(0).toLocaleUpperCase('nl-NL')+s.slice(1):'';
}
function stripCallsignsForSpeech(value,m){
  let s=String(value||'');
  // First remove every exact unit recognised by the current SW/local catalogue.
  for(const item of vehicleDetails(m)){
    const digits=String(item?.key||'').replace(/\D/g,'');if(!/^\d{5,7}$/.test(digits))continue;
    let pattern='';
    if(digits.length===7)pattern=`${digits.slice(0,2)}[- ]?${digits.slice(2,4)}[- ]?${digits.slice(4)}`;
    else if(digits.length===6)pattern=`${digits.slice(0,2)}[- ]?${digits.slice(2)}`;
    else pattern=`${digits.slice(0,2)}[- ]?${digits.slice(2)}`;
    s=s.replace(new RegExp(`(?<!\\d)(?:${digits}|${pattern})(?!\\d)`,'g'),' ');
  }
  // Native brandweer rows end in six/seven digit roepnummers. Once the service
  // is known as brandweer these are bookkeeping, never spoken address text.
  if(String(m?.service||'').toLowerCase()==='brandweer'){
    s=s.replace(/(?<!\d)(?:\d{2}[- ]?\d{2}[- ]?\d{3}|\d{7}|\d{2}[- ]?\d{4}|\d{6})(?!\d)/g,' ');
  }
  return s.replace(/\s+/g,' ').trim();
}
function speechLocation(m,info=speechIncidentInfo(m),city=speechCity(m)){
  let raw=norm(originalMessage(m));
  raw=raw
    .replace(/^\s*(?:P\s*[123]|A[012]|B[12])\b\s*/i,' ')
    .replace(/^\s*\(\s*DIA(?:\s*:\s*(?:JA|NEE))?\s*\)\s*/i,' ')
    .replace(/^\s*DIA(?:\s*:\s*(?:JA|NEE))?\b\s*/i,' ')
    .replace(/\b(?:B[A-Z]{2}|S[A-Z]{2}|KAZ)-\d{1,3}\b/ig,' ')
    .replace(/\(\s*GRIP\s*[1-5]\s*\)/ig,' ')
    .replace(/\(\s*(?:MIDDEL|GROTE|GR\.?|ZEER\s+(?:GROTE|GR\.?))\s+(?:BR|BRAND)\s*\)/ig,' ')
    .replace(/\bGRIP\s*[1-5]\b/ig,' ')
    .replace(/\b(?:MIDDEL|GROTE|GR\.?|ZEER\s+(?:GROTE|GR\.?))\s+(?:BR|BRAND)\b/ig,' ')
    .replace(/\s+/g,' ').trim();
  // Strip the incident phrase before generic number cleanup. This is important
  // for MMT rows where the incident detector itself is the 17992/08993 code.
  if(info?.regex){
    const re=new RegExp(info.regex.source,info.regex.flags.replace('g',''));
    const hit=re.exec(raw);
    if(hit)raw=raw.slice(hit.index+hit[0].length).trim();
  }
  raw=raw
    .replace(/^\s*(?:AMBU|AMBULANCE|POLITIE)\b\s*/ig,' ')
    // Police incident/bundle id (e.g. 366315) and ambulance/MMT resources.
    .replace(/^(?:\s*\d{4,7}\s+)+(?=[A-ZÀ-ÖØ-Þ])/i,' ')
    .replace(/(?<!\d)(?:13[- ]?\d{3}|17[- ]?\d{3}|08[- ]?\d{3}|122080[345]|12[- ]?2080[345])(?!\d)/g,' ')
    .replace(/\b(?:BON|RIT)\s*:?\s*\d+\b.*$/ig,' ')
    .replace(/\b\d{4}\s*[A-Z]{2}\b/ig,' ')
    .replace(/\([^)]*\)/g,' ')
    .replace(/\s+/g,' ').trim();
  raw=stripCallsignsForSpeech(raw,m);
  if(city){
    const reCity=new RegExp(`\\b${escapeRegex(norm(city))}\\b`,'i');
    const hit=reCity.exec(raw);
    if(hit)raw=raw.slice(0,hit.index).trim();
  }
  raw=raw
    .replace(/\(?ZICHTSCHERM(?:EN)?\)?/ig,' ')
    .replace(/\bASS\.?\s*POL\b/ig,' ')
    .replace(/^[-,.:()\s]+|[-,.:()\s]+$/g,' ')
    .replace(/\s+/g,' ').trim();
  if(!raw){
    raw=norm(m?.location||'');
    if(city)raw=raw.replace(new RegExp(`\\b${escapeRegex(norm(city))}\\b`,'ig'),' ');
    raw=stripCallsignsForSpeech(raw,m).replace(/\b\d{4}\s*[A-Z]{2}\b/ig,' ').replace(/\s+/g,' ').trim();
  }
  return naturalRoadSpeechLocation(sentenceCaseSpeech(raw));
}
function serviceSpeechName(service){return ({brandweer:'brandweer',politie:'politie',ambulance:'geneeskundige dienst',lifeliner:'Mobiel Medisch Team',knrm:'KNRM'})[String(service||'').toLowerCase()]||String(service||'hulpdienst')}
function spokenIncidentWhere(city,location){
  city=String(city||'').trim();location=String(location||'').trim();
  if(!location)return city?` in ${city}`:'';
  // Proper street/object names such as "De Wetering" already contain their
  // article; avoid saying "aan de De Wetering".
  const prep=/^(?:de|het)\s+/i.test(location)?' aan ':' aan de ';
  return `${prep}${location}${city?` in ${city}`:''}`;
}
function incidentDeltaFor(m){
  if(!m||m.__test)return null;
  const key=m.incident_key||dedupeKey(m),at=publishedMs(m)||Date.now();
  let prev=state.incidentMemory.get(key)||null;
  if(prev&&Math.abs(at-prev.at)>30*60*1000)prev=null;
  if(!prev)return null;
  if(Number(prev.at||0)>at+1000)return {noChange:true,speech:'',outOfOrder:true};
  const details=vehicleDetails(m),currentKeys=new Set(details.map(v=>String(v.key||v.header))),prevKeys=new Set(prev.unitKeys||[]);
  const newVehicles=details.filter(v=>!prevKeys.has(String(v.key||v.header)));
  const currentService=String(m.service||'').toLowerCase(),prevServices=new Set(prev.services||[]),newService=currentService&&!prevServices.has(currentService)?currentService:'';
  const scaleScore=Number(m.scale_score)||0,priorityScore=priorityRank(m.priority),scaleRaised=scaleScore>Number(prev.scale||0),priorityRaised=priorityScore>Number(prev.priority||0);
  const info=speechIncidentInfo(m),currentType=String(info?.type||''),typeChanged=!!(prev.incidentType&&currentType&&prev.incidentType!==currentType);
  if(!scaleRaised&&!priorityRaised&&!newService&&!newVehicles.length&&!typeChanged)return {noChange:true,speech:''};
  const city=speechCity(m),location=speechLocation(m,info,city),where=spokenIncidentWhere(city,location);
  const parts=[];
  if(scaleRaised){const scale=speechScale(m)||m.scale||'';if(scale)parts.push(`${info.type}${where} is opgeschaald naar ${String(scale).toLocaleLowerCase('nl-NL')}.`)}
  else if(typeChanged)parts.push(`${info.type}${where}.`);
  else if(priorityRaised)parts.push(`${info.type}${where} heeft nu prioriteit ${m.priority}.`);
  if(newService&&!scaleRaised)parts.push(`Ook ${serviceSpeechName(newService)} is gealarmeerd.`);
  const labels=newVehicles.map(v=>v.speech).filter(Boolean);
  if(labels.length===1)parts.push(`Aanvullend gealarmeerd: ${labels[0]}.`);
  else if(labels.length>1)parts.push(`Aanvullend gealarmeerd: ${joinSpeechParts(labels)}.`);
  const speech=applySpeechDictionary(parts.join(' '));
  return {scaleRaised,priorityRaised,typeChanged,newService,newVehicles:newVehicles.map(v=>v.header),speech};
}
function speechPhrase(m){
  if(m?.__incidentDelta?.speech)return m.__incidentDelta.speech;
  const city=speechCity(m),info=speechIncidentInfo(m),scale=speechScale(m);
  if(!city)return '';
  const location=speechLocation(m,info,city);
  const where=spokenIncidentWhere(city,location);
  const incident=scale?`${info.type}${where} is opgeschaald naar ${scale.toLocaleLowerCase('nl-NL')}.`:`${info.type}${where}.`;
  const vehicles=vehicleSpeechPhrase(m);
  return applySpeechDictionary(vehicles?`${incident} ${vehicles}`:incident);
}
function voiceScore(v){
  const lang=String(v?.lang||''),name=String(v?.name||'');
  let score=0;
  if(/^nl-NL$/i.test(lang))score+=120;else if(/^nl(?:-|_)/i.test(lang))score+=100;
  if(/natural|neural|premium|enhanced/i.test(name))score+=70;
  if(/google|microsoft/i.test(name))score+=45;
  if(/colette|fenna|xander|maarten|claire|ellen|frank/i.test(name))score+=25;
  if(/espeak|festival|pico|flite|mbrola/i.test(name))score-=100;
  if(v?.localService===false)score+=5;
  return score;
}
function bestDutchVoice(){
  const synth=globalThis.speechSynthesis;
  const voices=typeof synth?.getVoices==='function'?synth.getVoices():[];
  return voices.filter(v=>/^nl(?:-|_)/i.test(v.lang||'')||/dutch|nederlands/i.test(v.name||''))
    .sort((a,b)=>voiceScore(b)-voiceScore(a))[0]||null;
}
function cleanupSpeechAudio(entry){
  if(!entry)return;
  const audio=entry.audio;
  try{if(audio){audio.onended=null;audio.onerror=null;audio.onplaying=null;audio.onstalled=null;audio.onwaiting=null;audio.pause();audio.removeAttribute('src');audio.load();}}catch{}
  try{if(entry.url)URL.revokeObjectURL(entry.url)}catch{}
  if(state.currentSpeechAudio===entry)state.currentSpeechAudio=null;
}
function noteAudioFailure(error,mode='online'){
  const msg=String(error?.message||error||'onbekende audiofout').slice(0,240);
  state.audioStats.failures++;state.audioStats.lastError=msg;state.audioStats.lastMode=mode;
  return msg;
}
function noteAudioSuccess(mode){state.audioStats.successes++;state.audioStats.lastError='';state.audioStats.lastMode=mode;state.audioStats.lastSuccessAt=Date.now();state.audioStats.unlocked=true}
function waitMs(ms){return new Promise(resolve=>setTimeout(resolve,ms))}
function audioLockedError(error=null){const e=new Error(String(error?.message||error||'Browser blokkeert geluid'));e.name='AudioLockedError';e.code='AUDIO_LOCKED';return e}
function isAudioLockedError(error){return error?.code==='AUDIO_LOCKED'||error?.name==='AudioLockedError'||/NotAllowedError|user gesture|autoplay/i.test(String(error?.name||'')+' '+String(error?.message||error||''))}
function setAudioUnlockVisible(visible,message=''){
  const el=$('#audioUnlockOverlay'),msg=$('#audioUnlockText');if(!el)return;
  el.hidden=!visible;if(msg&&message)msg.textContent=message;
  state.audioBus.locked=!!visible;
}
function silentWavBlob(durationMs=120){
  const sampleRate=8000,frames=Math.max(80,Math.round(sampleRate*durationMs/1000)),bytes=frames*2,buf=new ArrayBuffer(44+bytes),v=new DataView(buf);
  const put=(o,t)=>{for(let i=0;i<t.length;i++)v.setUint8(o+i,t.charCodeAt(i))};
  put(0,'RIFF');v.setUint32(4,36+bytes,true);put(8,'WAVE');put(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sampleRate,true);v.setUint32(28,sampleRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);put(36,'data');v.setUint32(40,bytes,true);
  return new Blob([buf],{type:'audio/wav'});
}
async function armAudioBus({gesture=false}={}){
  if(state.audioBus.armed)return true;
  if(state.audioBus.arming)return state.audioBus.arming;
  const audio=$('#lightkrantSpeechAudio');if(!audio)throw new Error('lichtkrant-audiospeler ontbreekt');
  state.audioBus.arming=(async()=>{
    let url='';
    try{
      // The file itself is silent, but the media element is deliberately NOT muted
      // and uses volume 1. That means a successful play genuinely proves that
      // unmuted autoplay is allowed for this kiosk/origin.
      url=URL.createObjectURL(silentWavBlob(130));state.audioBus.primeUrl=url;
      try{audio.pause()}catch{}
      audio.muted=false;audio.volume=1;audio.playbackRate=1;audio.src=url;audio.load();
      const playPromise=audio.play();if(playPromise&&typeof playPromise.then==='function')await playPromise;
      await waitMs(90);
      try{audio.pause();audio.removeAttribute('src');audio.load()}catch{}
      state.audioBus.armed=true;state.audioBus.locked=false;state.audioStats.unlocked=true;state.audioStats.lastError='';state.audioStats.lastMode='audio-bus-armed';
      setAudioUnlockVisible(false);
      return true;
    }catch(error){
      state.audioBus.armed=false;state.audioBus.locked=true;state.audioStats.unlocked=false;
      const locked=isAudioLockedError(error);state.audioStats.lastMode=locked?'autoplay-locked':'audio-bus-error';state.audioStats.lastError=String(error?.message||error||'audio init mislukt').slice(0,240);const msg=locked?'Browser blokkeert automatisch geluid. Klik één keer om de omroep permanent voor dit tabblad in te schakelen.':`Audio initialiseren mislukt: ${String(error?.message||error)}`;
      setAudioUnlockVisible(true,msg);
      if(locked)throw audioLockedError(error);throw error;
    }finally{
      try{if(url)URL.revokeObjectURL(url)}catch{};state.audioBus.primeUrl='';state.audioBus.arming=null;
    }
  })();
  return state.audioBus.arming;
}
function youtubeVideoId(url){
  const raw=String(url||'').trim();if(!raw)return '';
  try{const u=new URL(raw,location.href);if(/youtu\.be$/i.test(u.hostname))return String(u.pathname.split('/').filter(Boolean)[0]||'').replace(/[^A-Za-z0-9_-]/g,'').slice(0,20);if(/youtube\.com$/i.test(u.hostname)||/\.youtube\.com$/i.test(u.hostname)){if(u.pathname.startsWith('/shorts/'))return String(u.pathname.split('/')[2]||'').replace(/[^A-Za-z0-9_-]/g,'').slice(0,20);return String(u.searchParams.get('v')||'').replace(/[^A-Za-z0-9_-]/g,'').slice(0,20)}}catch{}return '';
}
function dispatchTuneChoice(service='',urgent=false,force=false){
  if(!force&&state.settings.dispatchTuneEnabled===false)return 'none';
  let choice='inherit';
  if(urgent)choice=String(state.settings.dispatchTuneUrgent||'inherit');
  if(choice==='inherit'){
    const key=String(service||'').toLowerCase();
    const map={brandweer:'dispatchTuneBrandweer',ambulance:'dispatchTuneAmbulance',politie:'dispatchTunePolitie',lifeliner:'dispatchTuneLifeliner',knrm:'dispatchTuneKnrm'};
    choice=String(state.settings[map[key]]||'inherit');
  }
  if(choice==='inherit')choice=String(state.settings.dispatchTuneDefault||'none');
  return choice||'none';
}
function dispatchTuneVolume(jobVolume=100){const bv=Number(state.settings.dispatchTuneVolume??80),sv=Number(jobVolume);const base=Math.max(0,Math.min(100,Number.isFinite(bv)?bv:80));const speech=Math.max(0,Math.min(100,Number.isFinite(sv)?sv:100));return Math.round(base*(speech/100))}
function stopCurrentTune(){const stop=state.currentTuneStop;state.currentTuneStop=null;if(stop){try{stop()}catch{}}}
async function playBuiltinDispatchTune(choice,volume=80){
  const AC=globalThis.AudioContext||globalThis.webkitAudioContext;if(!AC)return false;
  let ctx;try{ctx=new AC();if(ctx.state==='suspended')await ctx.resume()}catch{return false}
  const patterns={
    'builtin:classic':[[780,150],[0,60],[980,210]],
    'builtin:double':[[900,160],[0,85],[900,160]],
    'builtin:rising':[[720,120],[900,120],[1120,180]],
    'builtin:urgent':[[940,115],[1160,115],[1380,190]],
  },pattern=patterns[choice];if(!pattern){try{await ctx.close()}catch{};return false}
  const gain=ctx.createGain();{const vv=Number(volume);gain.gain.value=Math.max(0,Math.min(.24,(Number.isFinite(vv)?vv:80)/100*.18))};gain.connect(ctx.destination);
  let t=ctx.currentTime+.03,total=0,settled=false,resolver=null;
  const promise=new Promise(resolve=>{resolver=resolve});
  for(const [freq,dur] of pattern){if(freq){const o=ctx.createOscillator();o.type='sine';o.frequency.value=freq;o.connect(gain);o.start(t);o.stop(t+dur/1000)}t+=dur/1000;total+=dur}
  const timer=setTimeout(async()=>{if(settled)return;settled=true;state.currentTuneStop=null;try{await ctx.close()}catch{};resolver(true)},Math.max(100,total+90));
  state.currentTuneStop=()=>{if(settled)return;settled=true;clearTimeout(timer);try{ctx.close()}catch{};resolver(false)};
  return promise;
}
async function playYoutubeDispatchTune(volume=80){
  const id=youtubeVideoId(state.settings.dispatchTuneYoutubeUrl);if(!id)return false;
  const seconds=Math.max(1,Math.min(15,Number(state.settings.dispatchTuneYoutubeSeconds)||5));
  let settled=false,started=false,resolver=null,playTimer=null,startTimer=null,iframe=document.createElement('iframe');const promise=new Promise(resolve=>{resolver=resolve});
  iframe.title='P2000 YouTube-deuntje';iframe.setAttribute('aria-hidden','true');iframe.setAttribute('allow','autoplay; encrypted-media');iframe.tabIndex=-1;
  iframe.style.cssText='position:absolute;width:1px;height:1px;left:-9999px;top:0;border:0;opacity:.01;pointer-events:none';
  const playerId=`p2000-${Date.now()}`;
  iframe.src=`https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?autoplay=1&controls=0&playsinline=1&enablejsapi=1&rel=0&modestbranding=1&origin=${encodeURIComponent(location.origin)}`;
  const command=(func,args=[])=>{try{iframe.contentWindow?.postMessage(JSON.stringify({event:'command',id:playerId,func,args}),'https://www.youtube-nocookie.com')}catch{}};
  const finish=(ok)=>{if(settled)return;settled=true;clearTimeout(playTimer);clearTimeout(startTimer);window.removeEventListener('message',onMessage);state.currentTuneStop=null;try{command('stopVideo')}catch{};try{iframe.remove()}catch{};resolver(ok)};
  const markPlaying=()=>{if(started)return;started=true;clearTimeout(startTimer);playTimer=setTimeout(()=>finish(true),seconds*1000)};
  const onMessage=e=>{if(e.source!==iframe.contentWindow||!/youtube(?:-nocookie)?\.com$/i.test(String(e.origin||'')))return;let d=e.data;try{if(typeof d==='string')d=JSON.parse(d)}catch{return}if(!d||typeof d!=='object')return;if(d.event==='onReady'){const vv=Number(volume);command('setVolume',[Math.max(0,Math.min(100,Number.isFinite(vv)?vv:80))]);command('playVideo')}const playerState=Number(d.data??d.info?.playerState);if((d.event==='onStateChange'||d.event==='infoDelivery')&&playerState===1)markPlaying()};
  window.addEventListener('message',onMessage);
  iframe.addEventListener('load',()=>{setTimeout(()=>{try{iframe.contentWindow?.postMessage(JSON.stringify({event:'listening',id:playerId}),'https://www.youtube-nocookie.com')}catch{}const vv=Number(volume);command('setVolume',[Math.max(0,Math.min(100,Number.isFinite(vv)?vv:80))]);command('playVideo')},150)},{once:true});
  document.body.appendChild(iframe);startTimer=setTimeout(()=>finish(false),6500);
  state.currentTuneStop=()=>finish(false);return promise;
}
async function playCustomDispatchTune(volume=80){
  await armAudioBus();const audio=$('#lightkrantSpeechAudio');if(!audio)return false;
  stopCurrentTune();try{audio.pause()}catch{}
  const src=`/api/tune/audio?v=${encodeURIComponent(Number(state.settings.dispatchTuneCustomVersion)||0)}`;
  return new Promise(resolve=>{
    let settled=false;const finish=(ok)=>{if(settled)return;settled=true;clearTimeout(timer);audio.onended=null;audio.onerror=null;audio.onplaying=null;try{audio.pause();audio.removeAttribute('src');audio.load()}catch{};if(state.currentTuneStop===stop)state.currentTuneStop=null;resolve(ok)};
    const stop=()=>finish(false);state.currentTuneStop=stop;audio.preload='auto';{const vv=Number(volume);audio.volume=Math.max(0,Math.min(1,(Number.isFinite(vv)?vv:80)/100));}audio.playbackRate=1;audio.src=src;audio.load();audio.onended=()=>finish(true);audio.onerror=()=>finish(false);audio.onplaying=()=>{state.audioStats.unlocked=true};const timer=setTimeout(()=>finish(true),15000);
    try{const p=audio.play();if(p&&typeof p.catch==='function')p.catch(()=>finish(false))}catch{finish(false)}
  });
}
async function playDispatchTuneForJob(job){
  const choice=String(job?.tuneChoice||dispatchTuneChoice(job?.cueService,!!job?.cueUrgent,!!job?.forceAudio));if(choice==='none')return false;
  const volume=dispatchTuneVolume(job?.volume);
  try{
    if(choice.startsWith('builtin:'))return await playBuiltinDispatchTune(choice,volume);
    if(choice==='youtube')return await playYoutubeDispatchTune(volume);
    if(choice==='custom')return await playCustomDispatchTune(volume);
  }catch(e){console.warn('Deuntje afspelen mislukt',e)}
  return false;
}
async function browserAttentionCue(service='',urgent=false,volume=100){
  const AC=globalThis.AudioContext||globalThis.webkitAudioContext;if(!AC)return false;
  let ctx=null;
  try{
    ctx=new AC();if(ctx.state==='suspended')await ctx.resume();
    const serviceKey=String(service||'').toLowerCase();
    const tones=urgent?[[950,115],[1150,115],[1350,165]]:serviceKey==='ambulance'?[[880,115],[1050,145]]:(serviceKey==='politie'||serviceKey==='lifeliner')?[[1000,105],[1250,145]]:[[820,115],[1030,145]];
    const numericVolume=Number(volume),safeVolume=Math.max(0,Math.min(100,Number.isFinite(numericVolume)?numericVolume:72));
    if(safeVolume<=0)return false;
    const gain=ctx.createGain();gain.gain.value=Math.min(.18,safeVolume/100*.13);gain.connect(ctx.destination);
    let t=ctx.currentTime+.02;
    for(const [freq,dur] of tones){const o=ctx.createOscillator();o.frequency.value=freq;o.type='sine';o.connect(gain);o.start(t);o.stop(t+dur/1000);t+=dur/1000+.045}
    await waitMs(Math.max(120,Math.round((t-ctx.currentTime)*1000)+30));
    return true;
  }catch{return false}finally{try{await ctx?.close?.()}catch{}}
}
async function waitForDutchVoice(timeoutMs=900){
  const synth=globalThis.speechSynthesis;if(!synth?.getVoices)return null;
  let voice=bestDutchVoice();if(voice)return voice;
  await new Promise(resolve=>{
    let done=false;const finish=()=>{if(done)return;done=true;try{synth.removeEventListener?.('voiceschanged',finish)}catch{};resolve()};
    try{synth.addEventListener?.('voiceschanged',finish,{once:true})}catch{}
    setTimeout(finish,timeoutMs);
    try{synth.getVoices()}catch{}
  });
  return bestDutchVoice();
}
async function browserSpeakPromise(text,volume=100){
  const synth=globalThis.speechSynthesis,Utterance=globalThis.SpeechSynthesisUtterance;
  if(!synth||!Utterance)throw new Error('Nederlandse browserstem niet beschikbaar');
  const voice=await waitForDutchVoice();
  // Cruciaal: zonder expliciete Nederlandse stem NIET SpeechSynthesis laten
  // gokken. Chromium kiest dan op sommige Windows-installaties de Engelse
  // standaardstem, die vervolgens Nederlands met een Brits accent voorleest.
  if(!voice)throw new Error('Geen Nederlandse browserstem (nl-NL) beschikbaar');
  const voiceLang=String(voice.lang||'');
  if(!/^nl(?:-|_)/i.test(voiceLang)&&!/dutch|nederlands/i.test(String(voice.name||'')))throw new Error(`Niet-Nederlandse browserstem geweigerd: ${voice.name||'onbekend'} (${voiceLang||'geen taal'})`);
  return await new Promise((resolve,reject)=>{
    let settled=false,watchdog=null;
    const finish=(ok,error=null)=>{if(settled)return;settled=true;if(watchdog)clearTimeout(watchdog);ok?resolve({mode:'browser-voice',completed:true}):reject(error||new Error('browserstem gestopt'))};
    try{
      const numericVolume=Number(volume),safeVolume=Math.max(0,Math.min(100,Number.isFinite(numericVolume)?numericVolume:100));
      const u=new Utterance(text);u.lang='nl-NL';u.rate=Math.max(.65,Math.min(1.25,Number(state.settings.speechRate)||.96));u.pitch=Math.max(.75,Math.min(1.3,Number(state.settings.speechPitch)||1));u.volume=safeVolume/100;
      u.voice=voice;
      u.onstart=()=>{state.audioStats.unlocked=true};u.onend=()=>finish(true);u.onerror=e=>finish(false,new Error(`browserstem: ${e?.error||'afspeelfout'}`));
      synth.cancel();synth.resume?.();synth.speak(u);
      watchdog=setTimeout(()=>{try{synth.cancel()}catch{};finish(false,new Error('browserstem timeout'))},estimateSpeechMs(text)+8000);
    }catch(e){finish(false,e)}
  });
}
async function fetchTtsBlob(text,timeoutMs=16000,cueService='',cueUrgent=false){
  const controller=typeof AbortController!=='undefined'?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),timeoutMs):null;
  try{
    const body={text,service:String(cueService||'brandweer'),urgent:!!cueUrgent,attention:!!(cueService||cueUrgent),rate:Math.max(.65,Math.min(1.25,Number(state.settings.speechRate)||.96))};
    const r=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store',signal:controller?.signal});
    if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.error||`TTS HTTP ${r.status}`)}
    const blob=await r.blob();if(blob.size<100)throw new Error('lege TTS-audio');
    return {blob,engine:String(r.headers.get('X-P2000-TTS-Engine')||'audio-file')};
  }catch(e){if(e?.name==='AbortError')throw new Error('TTS render duurde te lang');throw e}
  finally{if(timer)clearTimeout(timer)}
}
async function tryPlayMediaElement(audio,url,entry,volume,rate){
  const numericVolume=Number(volume),safeVolume=Math.max(0,Math.min(100,Number.isFinite(numericVolume)?numericVolume:100));
  audio.preload='auto';audio.volume=safeVolume/100;entry.outputVolume=safeVolume;entry.masterAtStart=Math.max(0,Math.min(100,Number(state.settings.masterVolume??100)));audio.playbackRate=rate;
  try{audio.preservesPitch=true;audio.mozPreservesPitch=true;audio.webkitPreservesPitch=true}catch{}
  audio.src=url;audio.load();
  return await new Promise((resolve,reject)=>{
    let settled=false,started=false,startTimer=null,hardTimer=null;
    const clear=()=>{if(startTimer)clearTimeout(startTimer);if(hardTimer)clearTimeout(hardTimer)};
    const finish=(ok,error=null)=>{if(settled)return;settled=true;clear();entry.finish=null;cleanupSpeechAudio(entry);ok?resolve({mode:'online-media',completed:true}):reject(error||new Error('browseraudio gestopt'))};
    entry.finish=(ok=false)=>{if(settled)return;settled=true;clear();entry.finish=null;cleanupSpeechAudio(entry);resolve({mode:'cancelled',completed:true,stopped:!ok})};
    audio.onplaying=()=>{started=true;state.audioStats.unlocked=true;if(startTimer){clearTimeout(startTimer);startTimer=null}};
    audio.onended=()=>finish(true);audio.onerror=()=>finish(false,new Error('browser kon de TTS-audio niet decoderen/afspelen'));
    audio.onstalled=()=>{if(!started)finish(false,new Error('TTS-audio bleef hangen voor afspelen'))};
    startTimer=setTimeout(()=>{if(!started)finish(false,new Error('TTS-audio startte niet binnen 4 seconden'))},4000);
    hardTimer=setTimeout(()=>finish(false,new Error('TTS-audio afspeeltimeout')),estimateSpeechMs(entry.text||'')+12000);
    const attempt=async()=>{
      let last=null;
      for(let i=0;i<3&&!settled;i++){
        try{const p=audio.play();if(p&&typeof p.then==='function')await p;return}catch(e){last=e;if(!/AbortError|NotAllowedError|NotSupportedError/i.test(String(e?.name||e)))break;await waitMs(180+i*240)}
      }
      if(!settled){const err=last||new Error('audio.play mislukt');finish(false,isAudioLockedError(err)?audioLockedError(err):err)};
    };
    attempt();
  });
}
async function playOnlineAudioInBrowser(text,requestSeq,volume=100,cueService='',cueUrgent=false){
  if(typeof fetch!=='function')throw new Error('browseraudio niet beschikbaar');
  state.audioStats.attempts++;
  await armAudioBus();
  if(requestSeq!==state.speechRequestSeq)return {mode:'cancelled',completed:true};
  const rendered=await fetchTtsBlob(text,16000,cueService,cueUrgent);
  if(requestSeq!==state.speechRequestSeq)return {mode:'cancelled',completed:true};
  // SAPI-WAV already contains the attention tone, so the browser performs only
  // ONE actual media play operation for the whole dispatch. The cloud fallback
  // has no embedded cue; add one only in that exceptional path.
  if(!/^(?:windows-sapi|linux-espeak)-wav/i.test(rendered.engine)&&(cueService||cueUrgent))await browserAttentionCue(cueService,cueUrgent,volume);
  const url=URL.createObjectURL(rendered.blob),audio=$('#lightkrantSpeechAudio');
  if(!audio){URL.revokeObjectURL(url);throw new Error('lichtkrant-audiospeler ontbreekt')}
  try{audio.pause()}catch{}
  const entry={audio,url,finish:null,text};state.currentSpeechAudio=entry;
  const rate=/^(?:windows-sapi|linux-espeak)-wav/i.test(rendered.engine)?1:Math.max(.72,Math.min(1.22,Number(state.settings.speechRate)||.96));
  try{
    const result=await tryPlayMediaElement(audio,url,entry,volume,rate);noteAudioSuccess(rendered.engine||'audio-file');return result;
  }catch(error){if(isAudioLockedError(error)){state.audioBus.armed=false;setAudioUnlockVisible(true,'Browser blokkeert automatisch geluid. Klik één keer om de omroep in te schakelen.');throw audioLockedError(error)}throw error}
}
async function onlineSpeakText(text,requestSeq=++state.speechRequestSeq,volume=100,cueService='',cueUrgent=false,deviceVolume=null){
  // Alles blijft eigendom van het lichtkrant-tabblad. Primair speelt het tabblad
  // één lokaal gerenderd WAV-bestand; alleen als renderen echt mislukt wordt
  // in hetzelfde tabblad nog een browserstem als laatste noodfallback gebruikt.
  try{return await playOnlineAudioInBrowser(text,requestSeq,volume,cueService,cueUrgent)}
  catch(e){
    if(requestSeq!==state.speechRequestSeq)return {mode:'cancelled',completed:true};
    if(isAudioLockedError(e))throw e;
    noteAudioFailure(e,'audio-file');state.audioStats.fallbacks++;
    console.warn('Lokale/online audiobestand-route mislukt; browserstem wordt laatste fallback',e);
    const result=await browserSpeakPromise(text,volume);noteAudioSuccess('browser-voice-last-resort');return result;
  }
}
function estimateSpeechMs(text){const words=String(text||'').trim().split(/\s+/).filter(Boolean).length,rate=Math.max(.65,Math.min(1.25,Number(state.settings.speechRate)||.96));return Math.max(3500,Math.min(35000,Math.round((words/(2.2*rate))*1000+2200)))}
function clearSpeechTimer(){if(state.speechJobTimer!==null)clearTimeout(state.speechJobTimer);state.speechJobTimer=null}
function finishSpeechJob(id,result={ok:true,detail:'Omroep afgespeeld'}){if(!state.speechCurrent||state.speechCurrent.id!==id)return;const job=state.speechCurrent;clearSpeechTimer();state.speechCurrent=null;try{job.onResult?.(result)}catch{};startNextSpeechJob()}
function stopSpeechPlayback({clearQueue=false}={}){
  state.speechRequestSeq++;clearSpeechTimer();stopCurrentTune();globalThis.speechSynthesis?.cancel?.();
  const current=state.currentSpeechAudio;
  if(current){try{current.finish?.(false)}catch{};cleanupSpeechAudio(current)}
  const job=state.speechCurrent;state.speechCurrent=null;try{job?.onResult?.({ok:false,detail:'Omroep gestopt'})}catch{};if(clearQueue){for(const queued of state.speechQueue){try{queued.onResult?.({ok:false,detail:'Omroep geannuleerd'})}catch{}}state.speechQueue=[]}return Promise.resolve(true);
}
function queueSpeech(text,{priority=50,volume=72,deviceVolume=null,kind='p2000',key='',groupKey='',cueService='',cueUrgent=false,forceAudio=false,skipTune=false,onResult=null}={}){
  text=String(text||'').trim();if(!text)return false;
  const numericVolume=Number(volume),safeVolume=Math.max(0,Math.min(100,Number.isFinite(numericVolume)?numericVolume:72));
  const numericDeviceVolume=Number(deviceVolume),safeDeviceVolume=deviceVolume===null?null:Math.max(5,Math.min(100,Number.isFinite(numericDeviceVolume)?numericDeviceVolume:38));
  const id=`speech-${++state.speechJobSeq}`,job={id,text,priority:Number(priority)||0,volume:safeVolume,deviceVolume:safeDeviceVolume,kind,key,groupKey,cueService,cueUrgent:!!cueUrgent,forceAudio:!!forceAudio,skipTune:!!skipTune,onResult:typeof onResult==='function'?onResult:null,queuedAt:Date.now(),retries:0};
  if(key&&(state.speechCurrent?.key===key||state.speechQueue.some(x=>x.key===key)))return false;
  if(groupKey){state.speechQueue=state.speechQueue.filter(x=>!(x.groupKey===groupKey&&job.priority>=x.priority));}
  const cur=state.speechCurrent;
  if(cur&&job.priority>=80&&job.priority>cur.priority){
    stopSpeechPlayback({clearQueue:false}).finally(()=>{state.speechQueue.unshift(job);startNextSpeechJob()});return true;
  }
  state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob();return true;
}
function startNextSpeechJob(){
  if(state.speechCurrent||!state.speechQueue.length)return;
  const job=state.speechQueue.shift();state.speechCurrent=job;const done=(ok=true,detail='Omroep afgespeeld')=>finishSpeechJob(job.id,{ok,detail});
  const seq=++state.speechRequestSeq;
  (async()=>{
    const tuned=job.skipTune?false:await playDispatchTuneForJob(job);
    if(seq!==state.speechRequestSeq||state.speechCurrent?.id!==job.id)return {mode:'cancelled',completed:true};
    return onlineSpeakText(job.text,seq,job.volume,tuned?'':job.cueService,tuned?false:job.cueUrgent,job.deviceVolume);
  })().then(result=>{
    if(state.speechCurrent?.id!==job.id)return;done(true,result?.mode||'Omroep afgespeeld');
  }).catch(e=>{
    if(isAudioLockedError(e)){
      noteAudioFailure(e,'autoplay-locked');
      if(state.speechCurrent?.id===job.id){state.speechCurrent=null;state.speechQueue.unshift(job);state.audioBus.blockedJobs++}
      setAudioUnlockVisible(true,'Omroep staat klaar, maar de browser blokkeert geluid. Klik één keer op OMROEP INSCHAKELEN; de gemiste melding wordt daarna alsnog afgespeeld.');
      return;
    }
    noteAudioFailure(e,'all');console.warn('TTS kon niet in het lichtkrant-tabblad afspelen',e);
    if(Number(job.retries||0)<1&&state.speechCurrent?.id===job.id){
      clearSpeechTimer();state.speechCurrent=null;job.retries=Number(job.retries||0)+1;job.queuedAt=Date.now()+1500;
      setTimeout(()=>{state.speechQueue.push(job);state.speechQueue.sort((a,b)=>b.priority-a.priority||a.queuedAt-b.queuedAt);startNextSpeechJob()},1500);
      startNextSpeechJob();return;
    }
    done(false,String(e?.message||e||'Omroep afspelen mislukt'));
  });
}
function maybeSpeakMessage(m,{force=false}={}){
  if(!m)return false;if(!force&&m?.__incidentDelta?.noChange)return false;if(force){if(!state.settings.speechEnabled||!speechCity(m))return false}else if(!shouldSpeakMessage(m))return false;
  const key=String(m.id||`${m.published||''}|${originalMessage(m)}`);if(!force&&state.spokenIds.has(key))return false;state.spokenIds.add(key);if(state.spokenIds.size>150){const first=state.spokenIds.values().next().value;state.spokenIds.delete(first)}
  const now=new Date(),phrase=speechPhrase(m),urg=urgencyInfo(m),volume=speechVolumeForTime(m,urg.volume,now),deviceVolume=speechDeviceVolumeForTime(m,now);return queueSpeech(phrase,{priority:urg.speechPriority,volume,deviceVolume,kind:'p2000',key:`p2000:${key}`,groupKey:`incident:${m.incident_key||dedupeKey(m)}`,cueService:(/lifeliner/i.test(m?.service||'')?'lifeliner':String(m?.service||'overig')),cueUrgent:urg.rank>=5});
}

function updateLastP2000ActivityFromMessages(){
  let latest=Number(state.lastP2000ActivityAt)||0;
  for(const m of state.messages||[]){if(m?.__test)continue;latest=Math.max(latest,publishedMs(m)||0,ingestedMs(m)||0)}
  state.lastP2000ActivityAt=latest;
  return latest;
}
function lastP2000ActivityMs(){
  if(!(state.messages||[]).length&&!(state.activityEvents||[]).length)return state.bootAt||Date.now();
  return Number(state.lastP2000ActivityAt)||updateLastP2000ActivityFromMessages()||(state.bootAt||Date.now());
}
function smartSilenceActive(now=new Date()){
  if(state.settings.smartSilenceEnabled===false)return false;
  const mins=Math.max(5,Math.min(180,Number(state.settings.smartSilenceMinutes)||30));
  return now.getTime()-lastP2000ActivityMs()>=mins*60*1000;
}
function postIncidentQuietActive(now=Date.now()){return state.settings.postIncidentQuietEnabled!==false&&now<Number(state.postIncidentQuietUntil||0)}
function solarGlowY(){return 505}
function semanticSignature(m){const loc=normalizeLocationKey(m?.location||'');return norm(`${norm(m.city||'')} ${cleanedCore(m)} ${loc}`).replace(/\b(?:P[123]|A[012]|B[12]|MIDDELBRAND|GROTE BRAND|ZEER GROTE BRAND|GRIP [1-5])\b/g,' ').replace(/\s+/g,' ').trim()}
function dedupeKey(m){return semanticSignature(m)||m.id}
function rememberMessage(m){
  const now=Date.now(),at=publishedMs(m)||now,sig=dedupeKey(m);state.recentSignatures.set(sig,at);const key=m.incident_key||sig;
  let prev=state.incidentMemory.get(key)||null;if(prev&&Math.abs(at-prev.at)>30*60*1000)prev=null;
  const base=prev||{scale:0,priority:0,sig:'',unitKeys:[],services:[],incidentType:''};
  const unitKeys=new Set(base.unitKeys||[]);for(const v of vehicleDetails(m))unitKeys.add(String(v.key||v.header));
  const services=new Set(base.services||[]);if(m.service)services.add(String(m.service).toLowerCase());
  state.incidentMemory.set(key,{scale:Math.max(base.scale,Number(m.scale_score)||0),priority:Math.max(base.priority,priorityRank(m.priority)),sig,at:Math.max(Number(base.at)||0,at),unitKeys:[...unitKeys].slice(-80),services:[...services],incidentType:String(speechIncidentInfo(m)?.type||base.incidentType||'')});
  for(const [k,t] of state.recentSignatures)if(now-t>SIGNATURE_MEMORY_MS)state.recentSignatures.delete(k);for(const [k,v] of state.incidentMemory)if(now-v.at>60*60*1000)state.incidentMemory.delete(k)
}
function shouldTrigger(m){if(!filterMessage(m)||!isFresh(m))return false;const sig=dedupeKey(m),t=state.recentSignatures.get(sig),at=publishedMs(m)||Date.now();const key=m.incident_key||sig;let prev=state.incidentMemory.get(key)||null;if(prev&&Math.abs(at-prev.at)>30*60*1000)prev=null;const escalated=!!prev&&((Number(m.scale_score)||0)>prev.scale||priorityRank(m.priority)>prev.priority);const duplicate=!!t&&Math.abs(at-t)<SIGNATURE_MEMORY_MS;return escalated||!duplicate}
function wrapText(text,cols){const words=norm(text).split(' ').filter(Boolean),lines=[];let line='';for(let word of words){while(word.length>cols){if(line){lines.push(line);line=''}lines.push(word.slice(0,cols));word=word.slice(cols)}if(!word)continue;if(!line)line=word;else if(line.length+1+word.length<=cols)line+=' '+word;else{lines.push(line);line=word}}if(line)lines.push(line);return lines.length?lines:['GEEN MELDING']}
function chooseCols(m){if(!state.settings.autoTextSize)return 20;const text=bodyFor(m);for(const cols of [14,16,18,20,22,24,28])if(wrapText(text,cols).length<=BODY_ROWS)return cols;return 28}
function messageLayout(m){const cols=chooseCols(m),lines=wrapText(bodyFor(m),cols),pages=[];for(let i=0;i<lines.length;i+=BODY_ROWS)pages.push(lines.slice(i,i+BODY_ROWS));return {cols,pages:pages.length?pages:[['GEEN MELDING']]}}

function solidMessagePages(m){
  // v4.1.1: de moderne incidentkaart toont de bronregel compact op één regel.
  // Eén pagina voorkomt zinloze redraws om de 6,5 seconden.
  return [[String(bodyFor(m)||'GEEN MELDING')]];
}
function fitSolidFont(lines,maxWidth,maxHeight){
  let size=Math.min(112,Math.max(46,maxHeight/(Math.max(1,lines.length)*1.22)));
  ctx.font=`800 ${size}px ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace`;
  const widest=()=>Math.max(1,...lines.map(line=>ctx.measureText(line).width));
  while(size>42&&widest()>maxWidth){size-=2;ctx.font=`800 ${size}px ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace`}
  return size;
}
function canvasRoundRect(x,y,w,h,r){
  r=Math.max(0,Math.min(r,w/2,h/2));ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();
}
function serviceDisplayName(service,m=null){const key=String(service||'').toLowerCase();if(key==='lifeliner'){const info=mmtResourceInfo(m);if(info?.kind==='helicopter')return `MMT HELIKOPTER ${info.team}`;if(info?.kind==='car')return `MMT AUTO ${info.team}`;return 'MMT'}return({brandweer:'BRANDWEER',ambulance:'GENEESKUNDIG',politie:'POLITIE',knrm:'KNRM'})[key]||'P2000'}
function messageRegion(m){const cats=Array.isArray(m?.categories)?m.categories:[];const hit=cats.find(x=>/^regio\s+/i.test(String(x||'')));return hit?String(hit).replace(/^regio\s+/i,'').trim():''}
function serviceTheme(service){
  const key=String(service||'').toLowerCase();
  if(key==='politie')return {key,bg0:'#03132d',bg1:'#01050d',glow:'rgba(31,126,255,.22)',bar:'#2788ff',badgeBg:'rgba(39,136,255,.16)',badgeStroke:'rgba(83,164,255,.45)',accent:'#52a0ff',accentStrong:'#2788ff',accentSoft:'rgba(116,181,255,.86)',body:'#54a4ff',bodyShadow:'rgba(26,111,255,.30)',footer:'rgba(121,187,255,.58)',priority:'rgba(196,225,255,.94)'};
  if(key==='lifeliner')return {key,bg0:'#221c00',bg1:'#050400',glow:'rgba(255,213,0,.20)',bar:'#ffd400',badgeBg:'rgba(255,212,0,.16)',badgeStroke:'rgba(255,224,72,.46)',accent:'#ffe14d',accentStrong:'#ffd400',accentSoft:'rgba(255,231,116,.88)',body:'#ffd91f',bodyShadow:'rgba(255,210,0,.25)',footer:'rgba(255,230,115,.62)',priority:'rgba(255,246,196,.96)'};
  if(key==='ambulance')return {key,bg0:'#042016',bg1:'#010806',glow:'rgba(26,218,130,.16)',bar:'#21d884',badgeBg:'rgba(33,216,132,.14)',badgeStroke:'rgba(75,235,160,.38)',accent:'#62e7aa',accentStrong:'#21d884',accentSoft:'rgba(135,240,190,.82)',body:'#46df98',bodyShadow:'rgba(21,202,116,.22)',footer:'rgba(123,232,178,.52)',priority:'rgba(211,255,235,.94)'};
  if(key==='knrm')return {key,bg0:'#071a22',bg1:'#010507',glow:'rgba(0,198,230,.16)',bar:'#00b9df',badgeBg:'rgba(0,185,223,.14)',badgeStroke:'rgba(65,214,241,.38)',accent:'#61d9ef',accentStrong:'#00b9df',accentSoft:'rgba(145,231,245,.84)',body:'#47d1e9',bodyShadow:'rgba(0,185,223,.22)',footer:'rgba(130,220,235,.54)',priority:'rgba(213,249,255,.94)'};
  return {key:'brandweer',bg0:'#120605',bg1:'#000000',glow:'rgba(255,55,35,.12)',bar:'#ff432e',badgeBg:'rgba(255,83,59,.12)',badgeStroke:'rgba(255,101,77,.28)',accent:'#ff7e6a',accentStrong:'#ff654d',accentSoft:'rgba(255,153,137,.82)',body:'#ff654d',bodyShadow:'rgba(255,62,38,.25)',footer:'rgba(255,137,119,.48)',priority:'rgba(255,213,205,.9)'};
}
function vehicleHeaderLines(m,maxWidth=Infinity,fontSize=16,maxLines=4){
  const rows=vehicleDetails(m).map(v=>v.header);if(!rows.length)return [];
  ctx.font=`720 ${fontSize}px system-ui,Arial,sans-serif`;
  const fitRow=(value)=>{let out=String(value||'');if(!(maxWidth<Infinity))return out;if(ctx.measureText(out).width<=maxWidth)return out;while(out.length>10&&ctx.measureText(out+'…').width>maxWidth)out=out.slice(0,-1);return out+(out.length<String(value||'').length?'…':'')};
  const lines=[];let current='';
  for(const rawRow of rows){
    const row=fitRow(rawRow);
    const candidate=current?`${current}  •  ${row}`:row;
    if(current&&ctx.measureText(candidate).width>maxWidth){lines.push(current);current=row}else current=candidate;
    if(lines.length>=maxLines)break;
  }
  if(current&&lines.length<maxLines)lines.push(current);
  if(lines.length===maxLines){
    const consumed=lines.join(' • ');
    if(rows.some(r=>!consumed.includes(r))&&!lines.at(-1).endsWith('…'))lines[lines.length-1]+='  …';
  }
  return lines;
}
function specialVisualLabel(m){const h=norm(`${m?.scale||''} ${originalMessage(m)}`),parts=[];if(/\bSCHIET(?:PARTIJ|INCIDENT)\b/.test(h))parts.push('SCHIETPARTIJ');if(/\bSTEEK(?:PARTIJ|INCIDENT)\b/.test(h))parts.push('STEEKPARTIJ');if(/\bZEER\s+(?:GROTE|GR\.?)\s+(?:BR|BRAND)\b/.test(h))parts.push('ZEER GROTE BRAND');const grip=/\bGRIP\s*([1-5])\b/.exec(h);if(grip)parts.push(`GRIP ${grip[1]}`);return parts.join('  •  ')}
function drawUrgencyFrame(m,w,h,theme){const label=specialVisualLabel(m);if(!label)return;ctx.save();ctx.strokeStyle=theme.accentStrong;ctx.lineWidth=Math.max(6,Math.min(14,w*.006));ctx.shadowColor=theme.glow;ctx.shadowBlur=24;ctx.strokeRect(ctx.lineWidth/2,ctx.lineWidth/2,w-ctx.lineWidth,h-ctx.lineWidth);ctx.shadowBlur=0;ctx.fillStyle=theme.accentStrong;ctx.fillRect(0,0,w,h*.043);ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=theme.key==='lifeliner'||theme.key==='brandweer'?'#100':'#fff';if(theme.key==='politie')ctx.fillStyle='#fff';ctx.font=`950 ${Math.max(13,Math.min(24,w*.0125))}px system-ui,Arial,sans-serif`;ctx.fillText(`⚠  ${label}  ⚠`,w*.5,h*.0215);ctx.restore()}
function fitOneLineFont(text,maxWidth,startSize,minSize,weight=800,family='system-ui,Arial,sans-serif'){
  let size=Math.max(minSize,startSize);ctx.font=`${weight} ${size}px ${family}`;
  while(size>minSize&&ctx.measureText(String(text||'')).width>maxWidth){size-=2;ctx.font=`${weight} ${size}px ${family}`}
  return size;
}
function displayLocationParts(m){
  const city=String(m?.city||'').trim();
  const rawLocation=String(m?.location||'').trim();
  const location=locationWithoutCitySuffix(rawLocation,city);
  const sameAsCity=city&&normalizeLocationKey(location)===normalizeLocationKey(city);
  return {location:(!sameAsCity&&location)||city||'Locatie onbekend',city:city&&location&&!sameAsCity?city:''};
}
function drawPill(text,x,y,{fontSize=14,padX=14,height=34,fill='rgba(255,255,255,.06)',stroke='rgba(255,255,255,.15)',color='#fff',weight=800}={}){
  ctx.font=`${weight} ${fontSize}px system-ui,Arial,sans-serif`;const width=ctx.measureText(text).width+padX*2;
  canvasRoundRect(x,y,width,height,height/2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=1;ctx.stroke();ctx.fillStyle=color;ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillText(text,x+padX,y+height/2+.5);return width;
}
function canvasWrappedLines(text,maxWidth,maxLines,font){ctx.font=font;const words=rawDisplayText(text).split(' ').filter(Boolean),lines=[];let line='';for(const word of words){const next=line?`${line} ${word}`:word;if(!line||ctx.measureText(next).width<=maxWidth){line=next;continue}lines.push(line);line=word;if(lines.length>=maxLines-1)break}if(line&&lines.length<maxLines)lines.push(line);const consumed=lines.join(' ').split(' ').length;if(consumed<words.length&&lines.length){let last=lines[lines.length-1];while(last.length>8&&ctx.measureText(last+'…').width>maxWidth)last=last.slice(0,-1);lines[lines.length-1]=last+'…'}return lines}
function drawActiveSolid(w,h){
  const m=state.activeMessage;
  const mapReserve=state.mapVisible&&mapCanRender()?Math.min(w*.34,620):0;
  const left=w*.047,right=w*.958-mapReserve,contentW=Math.max(280,right-left),theme=serviceTheme(m.service),urg=urgencyInfo(m),info=speechIncidentInfo(m),loc=displayLocationParts(m);
  ctx.save();
  // Deep neutral base; discipline colour is reserved for accents instead of tinting the whole screen.
  drawMonitorBackground(ctx,w,h);
  const ambient=ctx.createRadialGradient(left,h*.34,0,left,h*.34,Math.max(w*.48,h*.8));ambient.addColorStop(0,theme.glow);ambient.addColorStop(.55,'rgba(8,16,20,.24)');ambient.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=ambient;ctx.fillRect(0,0,w,h);
  const topWash=ctx.createLinearGradient(0,0,0,h*.27);topWash.addColorStop(0,'rgba(255,255,255,.035)');topWash.addColorStop(1,'rgba(255,255,255,0)');ctx.fillStyle=topWash;ctx.fillRect(0,0,w,h*.32);
  ctx.fillStyle=theme.accentStrong;ctx.fillRect(0,0,Math.max(6,w*.005),h);drawUrgencyFrame(m,w,h,theme);

  // Header / live identity.
  const headerY=h*.065;ctx.textAlign='left';ctx.textBaseline='middle';ctx.font=`900 ${Math.max(19,Math.min(32,w*.016))}px system-ui,Arial,sans-serif`;ctx.fillStyle='#f2f7f9';ctx.fillText(state.settings.name||'P2000 Monitor',left,headerY);
  let pillX=left,pillY=h*.105;const pillFont=Math.max(10,Math.min(14,w*.0072)),pillH=Math.max(28,Math.min(36,h*.038));
  pillX+=drawPill(serviceDisplayName(m.service,m),pillX,pillY,{fontSize:pillFont,height:pillH,fill:theme.badgeBg,stroke:theme.badgeStroke,color:theme.accent})+8;
  const pri=String(m.priority||'').toUpperCase();if(pri)pillX+=drawPill(pri,pillX,pillY,{fontSize:pillFont,height:pillH,fill:'rgba(255,255,255,.055)',stroke:'rgba(255,255,255,.14)',color:'#f7fbfc'})+8;
  const region=messageRegion(m);if(region&&pillX<right-150)pillX+=drawPill(region.toUpperCase(),pillX,pillY,{fontSize:Math.max(9,pillFont-1),height:pillH,fill:'rgba(255,255,255,.035)',stroke:'rgba(255,255,255,.10)',color:'rgba(218,232,238,.78)',weight:750})+8;
  ctx.textAlign='right';ctx.font=`800 ${Math.max(24,Math.min(42,w*.022))}px ui-monospace,SFMono-Regular,Menlo,monospace`;ctx.fillStyle=theme.accent;ctx.fillText(hhmm(m.published),right,headerY);

  // By default the lightkrant shows the actual pager row prominently. Parsed
  // fields remain underneath for readability, but the source message is not
  // rewritten into a synthetic headline.
  const rawDisplayMode=String(state.settings.messageDisplayMode||'raw')!=='parsed',rawOriginal=displayMessageText(m);
  if(rawDisplayMode){
    const labelY=h*.205;ctx.textAlign='left';ctx.font=`900 ${Math.max(16,Math.min(25,w*.013))}px system-ui,Arial,sans-serif`;ctx.fillStyle=theme.accentStrong;ctx.fillText('P2000-MELDING',left,labelY);
    let rawSize=Math.max(28,Math.min(47,w*.0245)),lines=[];for(;rawSize>=27;rawSize-=2){const font=`780 ${rawSize}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`;lines=canvasWrappedLines(rawOriginal,contentW,3,font);if(lines.length<=2||rawSize<=31){ctx.font=font;break}}
    const startY=h*.285,lh=rawSize*1.28;ctx.fillStyle='#f7fbfc';ctx.shadowColor='rgba(0,0,0,.72)';ctx.shadowBlur=8;lines.forEach((line,i)=>ctx.fillText(line,left,startY+i*lh));ctx.shadowBlur=0;
    const parsed=[String(info?.type||'P2000-melding'),loc.location,loc.city].filter(Boolean).join('  •  ');ctx.font=`750 ${Math.max(16,Math.min(25,w*.013))}px system-ui,Arial,sans-serif`;ctx.fillStyle='rgba(207,225,232,.68)';ctx.fillText(parsed,left,h*.505);
  }else{
    const incidentTitle=String(info?.type||'P2000-melding').toUpperCase();
    const titleY=h*.225;const titleSize=fitOneLineFont(incidentTitle,contentW,Math.min(54,w*.030),24,900);ctx.textAlign='left';ctx.font=`900 ${titleSize}px system-ui,Arial,sans-serif`;ctx.fillStyle=theme.accentStrong;ctx.fillText(incidentTitle,left,titleY);
    const locationY=h*.355;const locationSize=fitOneLineFont(loc.location,contentW,Math.min(88,w*.046),34,850);ctx.font=`850 ${locationSize}px system-ui,Arial,sans-serif`;ctx.fillStyle='#f6f8f9';ctx.shadowColor='rgba(0,0,0,.7)';ctx.shadowBlur=8;ctx.fillText(loc.location,left,locationY);ctx.shadowBlur=0;
    if(loc.city){ctx.font=`800 ${Math.max(22,Math.min(38,w*.020))}px system-ui,Arial,sans-serif`;ctx.fillStyle='rgba(211,225,231,.68)';ctx.fillText(loc.city.toUpperCase(),left,h*.425);}
  }

  // Units get their own quiet card so they remain legible without competing with the incident.
  let afterUnits=rawDisplayMode?h*.61:h*.49;
  if(state.settings.vehicleHeader!==false){
    const boxTop=rawDisplayMode?h*.585:h*.475,lh=Math.max(21,Math.min(29,h*.029));
    let size=Math.max(12,Math.min(18,w*.0094));
    let vehicleLines=vehicleHeaderLines(m,Math.max(120,contentW-32),size,4);
    while(size>11&&vehicleLines.some(x=>{ctx.font=`720 ${size}px system-ui,Arial,sans-serif`;return ctx.measureText(x).width>contentW-32})){size--;vehicleLines=vehicleHeaderLines(m,Math.max(120,contentW-32),size,4)}
    if(vehicleLines.length){
      const boxH=Math.min(h*.19,28+vehicleLines.length*lh);canvasRoundRect(left,boxTop,contentW,boxH,14);ctx.fillStyle='rgba(255,255,255,.035)';ctx.fill();ctx.strokeStyle='rgba(255,255,255,.09)';ctx.stroke();
      ctx.save();canvasRoundRect(left,boxTop,contentW,boxH,14);ctx.clip();
      ctx.textAlign='left';ctx.textBaseline='middle';ctx.font=`800 ${Math.max(11,Math.min(16,w*.0082))}px system-ui,Arial,sans-serif`;ctx.fillStyle='rgba(170,191,200,.62)';ctx.fillText('GEALARMEERDE EENHEDEN',left+16,boxTop+17);
      ctx.font=`720 ${size}px system-ui,Arial,sans-serif`;ctx.fillStyle=theme.accentSoft;vehicleLines.forEach((line,i)=>ctx.fillText(line,left+16,boxTop+40+i*lh));ctx.restore();
      afterUnits=boxTop+boxH+h*.035;
    }
  }

  // De bronregel is alleen nog een compacte referentie. De incidentsoort en
  // locatie staan hierboven al groot; dezelfde tekst nogmaals pagineren was
  // vooral visuele ruis en kon op 1080p tegen de footer aanlopen.
  const raw=String(displayMessageText(m)||'').trim();
  if(raw&&!rawDisplayMode){
    const rawY=Math.min(h*.855,Math.max(afterUnits+h*.025,h*.72));
    ctx.font=`650 ${Math.max(13,Math.min(18,w*.0092))}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`;ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillStyle='rgba(183,201,209,.46)';
    const prefix='P2000  •  ';let shown=raw;const maxW=Math.max(120,contentW-ctx.measureText(prefix).width);
    while(shown.length>18&&ctx.measureText(shown+'…').width>maxW)shown=shown.slice(0,-1);
    ctx.fillStyle='rgba(137,163,175,.42)';ctx.fillText(prefix,left,rawY);ctx.fillStyle='rgba(190,207,214,.54)';ctx.fillText(shown+(shown.length<raw.length?'…':''),left+ctx.measureText(prefix).width,rawY);
  }

  const footerY=h*.942;ctx.fillStyle='rgba(255,255,255,.10)';ctx.fillRect(left,h*.902,contentW,1);ctx.font=`750 ${Math.max(10,Math.min(14,w*.0072))}px system-ui,Arial,sans-serif`;ctx.fillStyle='rgba(179,198,206,.48)';ctx.textAlign='left';const liveCount=!m.__test?activeLiveMessages().length:0,busy=busyPeriodActive(),rotateSec=Math.round(carouselIntervalMs()/1000);ctx.fillText(m.__test?'TESTMELDING  •  LICHTKRANT AUDIO':liveCount>1?`LIVE  •  ${state.activeMessageIndex+1}/${liveCount} MELDINGEN  •  WISSEL ${rotateSec} SEC${busy?'  •  DRUKKE PERIODE':''}`:`LIVE P2000${busy?'  •  DRUKKE PERIODE':''}`,left,footerY);
  const agency=multiAgencyLabel(m);if(agency){ctx.textAlign='right';ctx.fillStyle=theme.accentSoft;ctx.fillText(agency,right,footerY);}
  ctx.restore();
}
function idleDesignRect(w,h){
  const target=16/9,aspect=w/Math.max(1,h);let dw=w,dh=h,x=0,y=0;
  if(Math.abs(aspect-target)>.015){if(aspect>target){dw=h*target;x=(w-dw)/2}else{dh=w/target;y=(h-dh)/2}}
  return {x,y,w:dw,h:dh,s:dw/1920};
}
function drawSpacedText(text,x,y,spacing,{align='center'}={}){
  text=String(text||'');const widths=[...text].map(ch=>ctx.measureText(ch).width),total=widths.reduce((a,b)=>a+b,0)+Math.max(0,text.length-1)*spacing;
  let px=align==='left'?x:align==='right'?x-total:x-total/2;ctx.textAlign='left';for(let i=0;i<text.length;i++){ctx.fillText(text[i],px,y);px+=widths[i]+spacing}
}
let idleStaticCanvas=null,idleStaticContext=null,idleStaticKey='',idleVisibleStaticKey='',idleLastFrameWasClock=false,idleTransitionTimer=null;
function invalidateIdleStatic(){idleStaticKey='';idleVisibleStaticKey=''}
function ensureIdleStaticCanvas(){
  if(idleStaticCanvas)return;
  idleStaticCanvas=document.createElement('canvas');idleStaticCanvas.width=1920;idleStaticCanvas.height=1080;idleStaticContext=idleStaticCanvas.getContext('2d',{alpha:false});
}
function idleStaticSignature(now,mode,clockOnly,dim,shift){const minute=Math.floor(now.getTime()/60000);return [minute,mode,clockOnly?'1':'0',Math.round(dim*100),shift.join(','),state.settings.name||'',state.settings.idleLayout||'center',state.settings.idleHeadline||'',state.settings.idleSubline||'',state.settings.idleShowName!==false?'1':'0',state.settings.idleShowDate!==false?'1':'0',state.settings.idleShowSeconds!==false?'1':'0',state.settings.idleShowStatus!==false?'1':'0',state.settings.idleClockScale||100,state.settings.backgroundStyle||'black',state.settings.backgroundColor||'',state.settings.backgroundPhotoVersion||0,state.settings.backgroundPhotoDarkness??.60,state.settings.backgroundPhotoFit||'cover'].join('|')}
function drawSpacedTextOn(c,text,x,y,spacing,{align='center'}={}){
  text=String(text||'');const widths=[...text].map(ch=>c.measureText(ch).width),total=widths.reduce((a,b)=>a+b,0)+Math.max(0,text.length-1)*spacing;
  let px=align==='left'?x:align==='right'?x-total:x-total/2;c.textAlign='left';for(let i=0;i<text.length;i++){c.fillText(text[i],px,y);px+=widths[i]+spacing}
}
function idleLayoutConfig(clockOnly=false){
  let layout=String(state.settings.idleLayout||'center');if(!['center','left','split','minimal'].includes(layout))layout='center';if(clockOnly)layout='minimal';
  return {layout,headline:rawDisplayText(state.settings.idleHeadline||'')||state.settings.name||'P2000 Monitor',subline:rawDisplayText(state.settings.idleSubline||'')||'P2000 MELDINGEN HEBBEN DIRECT VOORRANG',showName:!clockOnly&&layout!=='minimal'&&state.settings.idleShowName!==false,showDate:!clockOnly&&layout!=='minimal'&&state.settings.idleShowDate!==false,showStatus:!clockOnly&&layout!=='minimal'&&state.settings.idleShowStatus!==false,showSeconds:state.settings.idleShowSeconds!==false,scale:Math.max(.65,Math.min(1.35,Number(state.settings.idleClockScale||100)/100))};
}
function rebuildIdleStaticLayer(now,mode,clockOnly,dim,shift,key){
  ensureIdleStaticCanvas();const c=idleStaticContext,W=1920,H=1080,weekend=now.getDay()===0||now.getDay()===6,cfg=idleLayoutConfig(clockOnly);
  c.save();c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;drawMonitorBackground(c,W,H);
  c.globalAlpha=dim;const glowX=cfg.layout==='left'||cfg.layout==='split'?520:960,glowY=solarGlowY(now),glow=c.createRadialGradient(glowX,glowY,0,glowX,glowY,940);glow.addColorStop(0,'rgba(30,126,169,.105)');glow.addColorStop(.58,'rgba(8,38,54,.026)');glow.addColorStop(1,'rgba(0,0,0,0)');c.fillStyle=glow;c.fillRect(0,0,W,H);
  c.translate(shift[0],shift[1]);c.textBaseline='middle';
  const leftAligned=cfg.layout==='left'||cfg.layout==='split',anchorX=leftAligned?104:960,align=leftAligned?'left':'center';
  if(cfg.showName){c.textAlign=align;c.fillStyle='rgba(91,216,255,.72)';c.font='850 22px system-ui,Arial,sans-serif';c.fillText(cfg.headline,anchorX,94);c.fillStyle='rgba(83,112,126,.42)';c.fillRect(leftAligned?104:92,125,leftAligned?980:1736,1)}
  if(cfg.showDate){const months=['JANUARI','FEBRUARI','MAART','APRIL','MEI','JUNI','JULI','AUGUSTUS','SEPTEMBER','OKTOBER','NOVEMBER','DECEMBER'],days=['ZONDAG','MAANDAG','DINSDAG','WOENSDAG','DONDERDAG','VRIJDAG','ZATERDAG'],dateText=`${days[now.getDay()]} ${String(now.getDate()).padStart(2,'0')} ${months[now.getMonth()]} ${now.getFullYear()}`;c.globalAlpha=dim;c.fillStyle=weekend?'rgba(216,231,237,.92)':'rgba(195,216,225,.80)';const fs=cfg.layout==='split'?38:(weekend?52:44);c.font=`${weekend?720:650} ${fs}px system-ui,Arial,sans-serif`;if(cfg.layout==='split'){c.textAlign='left';c.fillText(dateText,1270,470)}else drawSpacedTextOn(c,dateText,anchorX,cfg.layout==='left'?735:690,leftAligned?1.5:(weekend?2.9:2.2),{align})}
  if(cfg.showStatus){c.globalAlpha=dim*.46;c.fillStyle='rgba(105,145,162,.92)';c.font='650 16px system-ui,Arial,sans-serif';c.textAlign=align;c.fillText(cfg.subline,cfg.layout==='split'?1270:anchorX,cfg.layout==='split'?550:931)}
  c.restore();drawIdleClockBase(c,now,dim,mode,clockOnly,shift);idleStaticKey=key;
}
function idleClockGeometry(c,now,mode,clockOnly){
  const cfg=idleLayoutConfig(clockOnly),rawTime=hhmm(now),parts=rawTime.split(':'),leftDigits=parts[0]||'00',rightDigits=parts[1]||'00',base=mode==='minimal'||clockOnly?342:326,timeSize=Math.round(base*cfg.scale),timeY=cfg.layout==='left'?475:cfg.layout==='split'?500:455;
  const clockFont=`760 ${timeSize}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`;c.font=clockFont;const leftW=c.measureText(leftDigits).width,rightW=c.measureText(rightDigits).width,colonW=c.measureText(':').width,totalW=leftW+colonW+rightW,startX=(cfg.layout==='left'||cfg.layout==='split')?104:960-totalW/2;
  return {leftDigits,rightDigits,timeY,clockFont,leftW,rightW,colonW,totalW,startX,cfg};
}
function drawIdleClockBase(c,now,dim,mode,clockOnly,shift){
  c.save();c.translate(shift[0],shift[1]);c.textBaseline='middle';c.globalAlpha=dim;const g=idleClockGeometry(c,now,mode,clockOnly);
  c.shadowColor='rgba(83,210,247,.09)';c.shadowBlur=15;c.fillStyle='rgba(244,249,251,.97)';c.textAlign='left';c.fillText(g.leftDigits,g.startX,g.timeY);c.fillText(g.rightDigits,g.startX+g.leftW+g.colonW,g.timeY);c.restore();
}
function drawIdleClockDigits(now,dim,mode,clockOnly,shift){
  ctx.save();ctx.translate(shift[0],shift[1]);ctx.textBaseline='middle';const g=idleClockGeometry(ctx,now,mode,clockOnly);
  const hourBoost=now.getMinutes()===0&&now.getSeconds()<4?1+(.12*(1-now.getSeconds()/4)):1;
  if(hourBoost>1){ctx.globalAlpha=dim;ctx.shadowColor='rgba(83,210,247,.12)';ctx.shadowBlur=15*hourBoost;ctx.fillStyle=`rgba(244,249,251,${Math.min(1,.97*hourBoost)})`;ctx.textAlign='left';ctx.fillText(g.leftDigits,g.startX,g.timeY);ctx.fillText(g.rightDigits,g.startX+g.leftW+g.colonW,g.timeY);ctx.shadowBlur=0}
  const breathe=.52+.30*(.5+.5*Math.sin((now.getSeconds()%4)/4*Math.PI*2));ctx.save();ctx.globalAlpha=dim*breathe;ctx.fillStyle='rgba(126,215,241,.92)';ctx.font=g.clockFont;ctx.textAlign='left';ctx.fillText(':',g.startX+g.leftW,g.timeY);ctx.restore();
  if(g.cfg.showSeconds){ctx.globalAlpha=dim;ctx.fillStyle='rgba(91,216,255,.46)';ctx.font=`800 ${Math.max(30,Math.round(47*g.cfg.scale))}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`;ctx.textAlign='left';ctx.fillText(String(now.getSeconds()).padStart(2,'0'),g.startX+g.totalW+24,g.timeY+Math.max(48,67*g.cfg.scale));}ctx.restore();
}
function drawClockIdleModern(w,h){
  const now=new Date(),mode=['minimal','normal','informative'].includes(state.settings.idleStyle)?state.settings.idleStyle:'normal',clockOnly=smartSilenceActive(now)||postIncidentQuietActive(now.getTime()),dim=idleDimFactor(now),shift=burnOffset(),r=idleDesignRect(w,h),key=idleStaticSignature(now,mode,clockOnly,dim,shift);
  ensureIdleStaticCanvas();if(key!==idleStaticKey)rebuildIdleStaticLayer(now,mode,clockOnly,dim,shift,key);
  const transitionActive=Date.now()<Number(state.idleReturnFadeUntil||0),fullPaint=!idleLastFrameWasClock||idleVisibleStaticKey!==key||transitionActive;
  if(fullPaint){drawMonitorBackground(ctx,w,h);ctx.drawImage(idleStaticCanvas,0,0,1920,1080,r.x,r.y,r.w,r.h);idleVisibleStaticKey=key}
  else{
    // Restore only the clock rectangle from the cached static layer. This keeps
    // the one-second clock update cheap on a fixed kiosk display.
    const sx=35,sy=205,sw=1585,sh=500,dx=r.x+sx*r.w/1920,dy=r.y+sy*r.h/1080,dw=sw*r.w/1920,dh=sh*r.h/1080;
    ctx.drawImage(idleStaticCanvas,sx,sy,sw,sh,dx,dy,dw,dh);
  }
  ctx.save();ctx.translate(r.x,r.y);ctx.scale(r.w/1920,r.h/1080);drawIdleClockDigits(now,dim,mode,clockOnly,shift);ctx.restore();idleLastFrameWasClock=true;
}
function scheduleIdleTransitionFrame(){if(idleTransitionTimer)return;idleTransitionTimer=setTimeout(()=>{idleTransitionTimer=null;render()},40)}
function applyIdleReturnTransition(w,h){
  const now=Date.now();let alpha=0;if(now<state.idleReturnBlackUntil)alpha=1;else if(now<state.idleReturnFadeUntil){const span=Math.max(1,state.idleReturnFadeUntil-state.idleReturnBlackUntil),p=(now-state.idleReturnBlackUntil)/span;alpha=Math.max(0,1-p)}else{state.idleReturnBlackUntil=0;state.idleReturnFadeUntil=0;if(idleTransitionTimer){clearTimeout(idleTransitionTimer);idleTransitionTimer=null}return}
  ctx.save();ctx.globalAlpha=alpha;ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);ctx.restore();scheduleIdleTransitionFrame();
}

function prepareP2000Speech(){return Promise.resolve(null)}
function parseClock(v,fallback){const m=/^(\d{1,2}):(\d{2})$/.exec(v||'');if(!m)return fallback;return Math.min(23,+m[1])*60+Math.min(59,+m[2])}
function inNightWindow(now=new Date()){const mins=now.getHours()*60+now.getMinutes(),start=parseClock(state.settings.nightStart,23*60),end=parseClock(state.settings.nightEnd,7*60);if(start===end)return true;return start<end?(mins>=start&&mins<end):(mins>=start||mins<end)}
function idleDimFactor(now=new Date()){
  if(state.settings.idleDimEnabled===false)return 1;
  const mins=now.getHours()*60+now.getMinutes()+now.getSeconds()/60;
  let start=parseClock(state.settings.idleDimEarliest||state.settings.idleDimStart,20*60+30);
  const end=parseClock(state.settings.idleDimEnd,7*60),minimum=Math.max(.2,Math.min(1,Number(state.settings.idleDimMin)||.42));
  const span=(end-start+1440)%1440;if(span===0)return minimum;
  const pos=(mins-start+1440)%1440;if(pos>=span)return 1;
  const down=Math.max(45,Math.min(150,span*.28)),up=Math.max(45,Math.min(150,span*.24)),holdStart=Math.min(span,down),holdEnd=Math.max(holdStart,span-up);
  if(pos<holdStart){const t=pos/holdStart;return 1-(1-minimum)*(t*t*(3-2*t))}
  if(pos<=holdEnd)return minimum;
  const t=(pos-holdEnd)/Math.max(1,span-holdEnd);return minimum+(1-minimum)*(t*t*(3-2*t));
}

function messageArrivalSeq(m){return Number(m?.__monitorArrivalSeq)||0}
function sortActiveMessages(rows){return [...rows].sort(compareMessageNewest)}
function registerActivity(m){
  if(!m||m.__test)return;const id=String(m.id||''),at=ingestedMs(m)||publishedMs(m)||Date.now();if(id&&state.activityIds.has(id))return;if(id)state.activityIds.set(id,at);state.lastP2000ActivityAt=Math.max(Number(state.lastP2000ActivityAt)||0,at);state.activityEvents.push(at);const cut=Date.now()-BUSY_WINDOW_MS;state.activityEvents=state.activityEvents.filter(t=>t>=cut);for(const [k,t] of state.activityIds)if(t<cut)state.activityIds.delete(k);
}
function busyPeriodActive(now=Date.now()){const cut=now-BUSY_WINDOW_MS;state.activityEvents=state.activityEvents.filter(t=>t>=cut);return state.activityEvents.length>=BUSY_THRESHOLD}
function carouselIntervalMs(){return busyPeriodActive()?BUSY_MESSAGE_ROTATE_MS:MESSAGE_ROTATE_MS}
function carouselWeight(m){return urgencyInfo(m).carouselWeight||1}
function nextPriorityCarouselIndex(now=Date.now()){
  const rows=state.activeMessages||[];if(rows.length<=1)return 0;let best=-1,bestScore=-Infinity;
  rows.forEach((m,i)=>{if(m.id===state.activeMessage?.id)return;const last=state.carouselShownAt.get(m.id)||0,age=Math.max(1,now-last),score=age*carouselWeight(m)+(publishedMs(m)/1e9);if(score>bestScore){bestScore=score;best=i}});return best>=0?best:(state.activeMessageIndex+1)%rows.length;
}
// Live P2000 items have an absolute deadline.  Feed timestamps can occasionally
// be ahead of the kiosk clock (or be interpreted differently by a source), so
// never let such clock skew keep a message on screen indefinitely.  The earliest
// trustworthy timestamp wins: publication, backend ingestion, or local first-seen.
function localFirstSeenMs(m){
  const existing=Number(m?.__monitorFirstSeenAt)||0;if(existing>0)return existing;
  const now=Date.now();try{Object.defineProperty(m,'__monitorFirstSeenAt',{value:now,writable:false,configurable:true,enumerable:false})}catch{try{m.__monitorFirstSeenAt=now}catch{}}return now
}
function liveMessageStartedAt(m){
  if(!m)return 0;const now=Date.now(),futureTolerance=30*1000,pub=publishedMs(m),ing=ingestedMs(m),seen=localFirstSeenMs(m);
  const trusted=[pub,ing,seen].filter(t=>Number.isFinite(t)&&t>0&&t<=now+futureTolerance);
  if(trusted.length)return Math.min(...trusted);
  const any=[ing,pub,seen].filter(t=>Number.isFinite(t)&&t>0);return any.length?Math.min(...any.map(t=>Math.min(t,now))):now
}
function liveMessageExpiresAt(m){const started=liveMessageStartedAt(m);return started?started+visibleMs():0}
function isLiveMessageActive(m,now=Date.now()){const expires=liveMessageExpiresAt(m);return !!m&&!!expires&&now<expires}
function activeLiveMessages(now=Date.now()){return (state.activeMessages||[]).filter(m=>isLiveMessageActive(m,now))}
function cancelLiveExpiryTimer(){if(state.liveExpiryTimer!==null)clearTimeout(state.liveExpiryTimer);state.liveExpiryTimer=null;state.liveExpiryAt=0}
function scheduleLiveExpiry(force=false){
  const now=Date.now(),deadlines=(state.activeMessages||[]).map(liveMessageExpiresAt).filter(t=>t>now);
  if(!deadlines.length){cancelLiveExpiryTimer();return}
  const next=Math.min(...deadlines);
  // Important on low-power kiosks: activeVisible()/draw() is called often. Do not
  // continuously destroy/recreate the exact same expiry timer.
  if(!force&&state.liveExpiryTimer!==null&&state.liveExpiryAt===next)return;
  cancelLiveExpiryTimer();state.liveExpiryAt=next;
  state.liveExpiryTimer=setTimeout(()=>{state.liveExpiryTimer=null;state.liveExpiryAt=0;const changed=pruneExpiredActiveMessages(Date.now());syncDisplayPower();if(changed||!(state.activeMessages||[]).length)render();},Math.max(0,next-now)+5)
}
function pruneCarouselShownAt(){
  const keep=new Set((state.activeMessages||[]).map(m=>m?.id).filter(Boolean));
  if(state.activeMessage?.id)keep.add(state.activeMessage.id);
  for(const key of state.carouselShownAt.keys())if(!keep.has(key))state.carouselShownAt.delete(key);
}
function pruneKnownIds(){
  if(state.knownIds.size<=2000)return;
  const keep=new Set((state.messages||[]).map(m=>m?.id).filter(Boolean));
  for(const m of state.activeMessages||[])if(m?.id)keep.add(m.id);
  if(state.activeMessage?.id)keep.add(state.activeMessage.id);
  state.knownIds=keep;
}
function clearActiveMessages(){const hadActive=!!state.activeMessage||!!(state.activeMessages||[]).length;cancelLiveExpiryTimer();state.activeMessage=null;state.activeMessages=[];state.carouselShownAt.clear();state.activeMessageIndex=0;state.activeUntil=0;state.page=0;state.lastStep=Date.now();state.lastMessageSwitch=Date.now();hideIncidentMap();if(hadActive){const now=Date.now();state.idleReturnBlackUntil=now+300;state.idleReturnFadeUntil=now+950;const recent=(state.activityEvents||[]).filter(t=>now-t<=BUSY_WINDOW_MS).length;if(state.settings.postIncidentQuietEnabled!==false&&recent>=3)state.postIncidentQuietUntil=now+Math.max(5,Math.min(120,Number(state.settings.postIncidentQuietSeconds)||20))*1000}}
function pruneExpiredActiveMessages(now=Date.now()){
  if(!(state.activeMessages||[]).length)return false;
  const oldCurrent=state.activeMessage?.id||null,oldLength=state.activeMessages.length;
  state.activeMessages=sortActiveMessages(state.activeMessages.filter(m=>isLiveMessageActive(m,now)));
  pruneCarouselShownAt();
  if(!state.activeMessages.length){clearActiveMessages();return oldLength>0}
  let idx=state.activeMessages.findIndex(m=>m.id===oldCurrent);
  const currentExpired=idx<0;if(currentExpired)idx=0;
  state.activeMessageIndex=idx;state.activeMessage=state.activeMessages[idx];
  state.activeUntil=Math.max(...state.activeMessages.map(liveMessageExpiresAt));
  if(currentExpired){state.page=0;state.lastStep=now;state.lastMessageSwitch=now;state.lastDisplayedMessage=state.activeMessage}
  const changed=oldLength!==state.activeMessages.length||currentExpired;if(changed||state.liveExpiryTimer===null)scheduleLiveExpiry();return changed
}
function activeVisible(){
  // Rendering itself enforces the deadline too.  Even if a browser throttles or
  // misses the timeout/tick, an expired live message can never remain visible.
  if((state.activeMessages||[]).length)return !!state.activeMessage&&isLiveMessageActive(state.activeMessage,Date.now());
  return !!state.activeMessage&&Date.now()<state.activeUntil
}
function selectActiveMessage(index,{resetSwitch=true}={}){
  pruneExpiredActiveMessages();const rows=state.activeMessages||[];if(!rows.length){clearActiveMessages();return null}
  state.activeMessageIndex=((index%rows.length)+rows.length)%rows.length;state.activeMessage=rows[state.activeMessageIndex];state.page=0;state.lastStep=Date.now();if(resetSwitch)state.lastMessageSwitch=Date.now();state.lastDisplayedMessage=state.activeMessage;state.carouselShownAt.set(state.activeMessage.id,Date.now());return state.activeMessage
}
function addActiveMessage(m,{showNow=true}={}){
  if(!m||!isLiveMessageActive(m))return false;registerActivity(m);
  pruneExpiredActiveMessages();
  if(!m.__monitorArrivalSeq)Object.defineProperty(m,'__monitorArrivalSeq',{value:++state.arrivalSeq,writable:true,configurable:true,enumerable:false});
  const rows=(state.activeMessages||[]).filter(x=>x.id!==m.id);rows.push(m);state.activeMessages=sortActiveMessages(rows);
  const idx=Math.max(0,state.activeMessages.findIndex(x=>x.id===m.id));
  if(showNow)selectActiveMessage(idx);
  else if(!state.activeMessage)selectActiveMessage(0);
  else state.activeMessageIndex=Math.max(0,state.activeMessages.findIndex(x=>x.id===state.activeMessage.id));
  state.activeUntil=Math.max(...state.activeMessages.map(liveMessageExpiresAt));scheduleLiveExpiry();
  return true
}
function rotateActiveMessage(){
  pruneExpiredActiveMessages();const rows=state.activeMessages||[];if(rows.length<=1)return false;selectActiveMessage(nextPriorityCarouselIndex());render();return true
}
function trueBlack(){return Date.now()>state.testIdleUntil&&!activeVisible()&&state.settings.displaySleep&&state.settings.nightMode&&inNightWindow()}
function centerLine(s,cols){s=norm(s).slice(0,cols);if(!state.settings.idleCentered)return s;const left=Math.max(0,Math.floor((cols-s.length)/2));return ' '.repeat(left)+s}
function idleDisplay(){const cols=16;if(trueBlack())return {cols,lines:['','',''],black:true,idle:true};return {cols,black:false,idle:true,clock:true,lines:[]}}
function displayLayout(){if(!activeVisible())return idleDisplay();const m=state.activeMessage,layout=messageLayout(m);state.page=((state.page%layout.pages.length)+layout.pages.length)%layout.pages.length;const page=layout.pages[state.page];return {cols:layout.cols,black:false,idle:false,vehicle:state.settings.vehicleHeader===false?'':compactVehicleHeader(m),lines:[hhmm(m.published).slice(0,layout.cols),...(page.concat(['','']).slice(0,BODY_ROWS))]}}
function activateMessage(m,{force=false,durationMs=null,appendLive=true}={}){
  state.idleReturnBlackUntil=0;state.idleReturnFadeUntil=0;state.postIncidentQuietUntil=0;
  if(!m||(!m.__test&&!filterMessage(m))||(!force&&!isFresh(m)))return false;
  if(!force&&!shouldTrigger(m)){rememberMessage(m);return false}
  const delta=incidentDeltaFor(m);if(delta){try{Object.defineProperty(m,'__incidentDelta',{value:delta,writable:true,configurable:true,enumerable:false})}catch{m.__incidentDelta=delta}}
  if(m.__test||!appendLive){state.activeMessages=[];state.activeMessageIndex=0;state.activeMessage=m;state.lastDisplayedMessage=m;state.activeUntil=Date.now()+(durationMs||visibleMs());state.page=0;state.lastStep=Date.now();state.lastMessageSwitch=Date.now()}
  else if(!addActiveMessage(m,{showNow:true}))return false;
  rememberMessage(m);syncDisplayPower();render();return true
}
function isNewSinceMonitorStart(m){const at=ingestedMs(m),bootSecond=Math.floor(Number(state.bootAt||0)/1000)*1000;return at>0&&at>=bootSecond}
function finishStartupBaseline(){
  // Database rows are history, even when their P2000 timestamp is only seconds
  // old. Seed duplicate/incident memory, but never show or speak them after a
  // browser, backend or machine restart. Only rows ingested after this page
  // started may enter through processNew().
  const ordered=[...(state.messages||[])].sort((a,b)=>-compareMessageNewest(a,b));
  ordered.forEach(m=>{state.knownIds.add(m.id);rememberMessage(m)});
  clearActiveMessages();state.started=true;pruneKnownIds();syncDisplayPower();render();
}
function replayLast(){const m=state.lastDisplayedMessage||latestMessage();if(m)activateMessage(m,{force:true,durationMs:REPLAY_MS,appendLive:false})}
function shouldDisplayIncoming(m){return !!m&&filterMessage(m)&&isFresh(m)&&isLiveMessageActive(m)}
function processNew(m){if(!m||state.knownIds.has(m.id))return;state.knownIds.add(m.id);pruneKnownIds();if(!isNewSinceMonitorStart(m)){rememberMessage(m);return}if(shouldDisplayIncoming(m)){const stopped=prepareP2000Speech();activateMessage(m,{force:true});if(shouldSpeakMessage(m))stopped.finally(()=>maybeSpeakMessage(m))}else rememberMessage(m)}

function runtimeIdentity(status){return status&&status.server_instance?`${status.version||''}:${status.server_instance}`:''}
function runtimeReloadReason(status,currentIdentity=null){
  const version=String(status?.version||'').trim();
  if(version&&version!==CLIENT_VERSION)return'version';
  const id=runtimeIdentity(status);if(!id)return'';
  if(currentIdentity&&id!==currentIdentity)return'instance';
  return'';
}

const canvas=$('#ledCanvas'),ctx=canvas.getContext('2d');
function resizeCanvas(){invalidateIdleStatic();idleLastFrameWasClock=false;const r=canvas.getBoundingClientRect(),pixelBudget=2500000,budgetDpr=Math.sqrt(pixelBudget/Math.max(1,r.width*r.height)),dpr=Math.max(.55,Math.min(1.25,window.devicePixelRatio||1,budgetDpr));canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);draw()}
function drawLed(x,y,r,on){if(on){ctx.save();ctx.shadowColor='rgba(255,46,25,.80)';ctx.shadowBlur=r*1.25;ctx.fillStyle='rgba(255,55,31,.98)';ctx.beginPath();ctx.arc(x,y,r*.90,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;ctx.fillStyle='rgba(255,205,186,.82)';ctx.beginPath();ctx.arc(x-r*.20,y-r*.20,r*.18,0,Math.PI*2);ctx.fill();ctx.restore()}else{const a=Math.max(0,Math.min(30,Number(state.settings.darkLedPercent)||0))/100;ctx.fillStyle=`rgba(70,8,5,${a})`;ctx.beginPath();ctx.arc(x,y,r*.40,0,Math.PI*2);ctx.fill()}}
function matrixFromLines(lines,cols){const charW=6,charH=9,totalCols=cols*charW-1,totalRows=DISPLAY_ROWS*charH-2,cells=Array.from({length:totalRows},()=>Array(totalCols).fill(false));for(let lr=0;lr<DISPLAY_ROWS;lr++){const line=(lines[lr]||'').padEnd(cols,' ').slice(0,cols);for(let ci=0;ci<cols;ci++){const glyph=FONT[line[ci]]||FONT['?'];for(let gy=0;gy<7;gy++){const bits=glyph[gy]||0;for(let gx=0;gx<5;gx++)if(bits&(1<<(4-gx))){const yy=lr*charH+gy,xx=ci*charW+gx;if(cells[yy]?.[xx]!==undefined)cells[yy][xx]=true}}}}return cells}
function burnOffset(){if(activeVisible()||!state.settings.burnInProtection)return [0,0];const px=Math.max(0,Math.min(30,Number(state.settings.burnInPixels)||0)),positions=[[0,0],[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]],p=positions[Math.floor(Date.now()/120000)%positions.length];return [p[0]*px,p[1]*px]}
function drawHeader(layout,w,h,shift){
  const active=!layout.idle,base=Math.max(18,Math.min(48,w*.025));
  ctx.save();ctx.fillStyle='rgba(255,62,38,.98)';ctx.shadowColor='rgba(255,45,25,.42)';ctx.shadowBlur=8;ctx.textBaseline='middle';ctx.font=`700 ${active?base:Math.min(base*1.18,56)}px system-ui,Arial,sans-serif`;
  if(layout.idle&&state.settings.idleCentered){ctx.textAlign='center';ctx.fillText(state.settings.name||'P2000 Monitor',w/2+shift[0],h*.072+shift[1])}
  else{ctx.textAlign='left';ctx.fillText(state.settings.name||'P2000 Monitor',w*.025+shift[0],h*.072+shift[1])}
  if(active&&layout.vehicle){
    let size=Math.max(13,Math.min(26,w*.0135));const maxW=w*.64;ctx.textAlign='right';ctx.font=`600 ${size}px system-ui,Arial,sans-serif`;while(size>12&&ctx.measureText(layout.vehicle).width>maxW){size-=1;ctx.font=`600 ${size}px system-ui,Arial,sans-serif`}ctx.fillStyle='rgba(255,112,88,.94)';ctx.shadowBlur=5;ctx.fillText(layout.vehicle,w*.975,h*.072);
  }ctx.restore();
}
function perfNow(){return typeof globalThis.performance?.now==='function'?globalThis.performance.now():Date.now()}
function recordRenderPerf(started){const ms=Math.max(0,perfNow()-started),rows=state.renderPerf.samples;state.renderPerf.lastMs=ms;rows.push(ms);if(rows.length>120)rows.splice(0,rows.length-120)}
function syncSourceAttribution(){const el=$('#sourceAttribution');if(!el)return;const show=activeVisible()&&String(state.activeMessage?.source||'').toLowerCase().includes('112-nu');el.hidden=!show}
function draw(){
  syncSourceAttribution();const perfStarted=perfNow(),r=canvas.getBoundingClientRect(),w=r.width,h=r.height;
  if(Date.now()<state.testBlackoutUntil){idleLastFrameWasClock=false;ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);recordRenderPerf(perfStarted);return}
  if(activeVisible()){idleLastFrameWasClock=false;drawActiveSolid(w,h);recordRenderPerf(perfStarted);return}
  const layout=idleDisplay();
  if(layout.black){idleLastFrameWasClock=false;ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);recordRenderPerf(perfStarted);return}
  if(layout.clock){drawClockIdleModern(w,h);applyIdleReturnTransition(w,h);recordRenderPerf(perfStarted);return}
  idleLastFrameWasClock=false;drawMonitorBackground(ctx,w,h);
  const shift=burnOffset();drawHeader(layout,w,h,shift);
  const cells=matrixFromLines(layout.lines,layout.cols),cols=cells[0].length,rows=cells.length,top=h*.15,areaH=h*.81,pitchX=(w*.972)/cols,pitchY=(areaH*.94)/rows,radius=Math.min(pitchX*.445,pitchY*.39),ox=(w-(cols-1)*pitchX)/2+shift[0],oy=top+(areaH-(rows-1)*pitchY)/2+shift[1];
  for(let y=0;y<rows;y++)for(let x=0;x<cols;x++)drawLed(ox+x*pitchX,oy+y*pitchY,radius,cells[y][x]);
  recordRenderPerf(perfStarted);
}

let renderPending=false;function render(){if(renderPending)return;renderPending=true;(globalThis.requestAnimationFrame||((fn)=>setTimeout(fn,0)))(()=>{renderPending=false;draw();syncIncidentMap()})}
async function json(url,opts={}){const {timeoutMs=12000,...fetchOpts}=opts||{},controller=!fetchOpts.signal&&typeof AbortController!=='undefined'?new AbortController():null,timer=controller?setTimeout(()=>controller.abort(),Math.max(500,timeoutMs)):null;try{const r=await fetch(url,{cache:'no-store',...fetchOpts,signal:fetchOpts.signal||controller?.signal});if(!r.ok)throw new Error(`${r.status} ${r.statusText}`);return await r.json()}catch(e){if(e?.name==='AbortError')throw new Error(`Verzoek duurde langer dan ${Math.round(timeoutMs/1000)} seconden`);throw e}finally{if(timer)clearTimeout(timer)}}
let monitorRuntimeIdentity=null,monitorReloading=false,monitorRuntimeFailures=0,monitorEventSource=null,monitorRuntimeRetryTimer=null,monitorRuntimePromise=null,refreshPromise=null;
function hardReloadMonitor(reason='runtime'){
  if(monitorReloading)return false;monitorReloading=true;
  const u=new URL(location.href);u.searchParams.set('_monitor_reload',`${Date.now()}-${Math.random().toString(36).slice(2,8)}`);u.searchParams.set('_client',CLIENT_VERSION);
  try{location.replace(u.toString())}catch{location.href=u.toString()}
  return true;
}
function observeMonitorRuntime(status){
  const reason=runtimeReloadReason(status,monitorRuntimeIdentity);if(reason){hardReloadMonitor(reason);return}
  const id=runtimeIdentity(status);if(!id)return;
  if(monitorRuntimeIdentity===null)monitorRuntimeIdentity=id;
}
function scheduleRuntimeWatch(delay=1000){
  if(monitorRuntimeRetryTimer||monitorReloading)return;
  monitorRuntimeRetryTimer=setTimeout(()=>{monitorRuntimeRetryTimer=null;watchMonitorRuntime()},Math.max(250,delay));
}
async function reportClientHealth(){
  const rows=[...(state.renderPerf.samples||[])].filter(Number.isFinite).sort((a,b)=>a-b),sum=rows.reduce((a,b)=>a+b,0),p95=rows.length?rows[Math.min(rows.length-1,Math.floor((rows.length-1)*.95))]:0;
  const rect=canvas.getBoundingClientRect(),heap=Number(globalThis.performance?.memory?.usedJSHeapSize)||0;
  const a=state.audioStats||{};const payload={viewport:`${Math.round(globalThis.innerWidth||rect.width)}x${Math.round(globalThis.innerHeight||rect.height)}`,canvas:`${canvas.width}x${canvas.height}`,dpr:Number(globalThis.devicePixelRatio)||1,render_avg_ms:rows.length?sum/rows.length:0,render_p95_ms:p95,render_max_ms:rows.length?rows.at(-1):0,render_samples:rows.length,js_heap_used:heap,active:activeVisible(),active_count:(state.activeMessages||[]).length,map_visible:!!state.mapVisible,busy:busyPeriodActive(),visibility:document.visibilityState||'unknown',speech_queue:(state.speechQueue||[]).length,speech_active:!!state.speechCurrent,speech_mode:String(state.settings.speechMode||'normal'),master_volume:Number(state.settings.masterVolume??100),audio_attempts:Number(a.attempts)||0,audio_successes:Number(a.successes)||0,audio_failures:Number(a.failures)||0,audio_fallbacks:Number(a.fallbacks)||0,audio_last_error:String(a.lastError||''),audio_last_mode:String(a.lastMode||''),audio_unlocked:!!a.unlocked,audio_last_success_at:Number(a.lastSuccessAt)||0};
  try{await json('/api/client-health',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),keepalive:true,timeoutMs:8000})}catch{}
}
function watchMonitorRuntime(){if(monitorRuntimePromise)return monitorRuntimePromise;monitorRuntimePromise=(async()=>{try{const d=await json(`/api/runtime?_=${Date.now()}`,{timeoutMs:5000});monitorRuntimeFailures=0;observeMonitorRuntime(d);return true}catch{monitorRuntimeFailures++;if(monitorRuntimeFailures<8)scheduleRuntimeWatch(Math.min(5000,750*monitorRuntimeFailures));return false}})().finally(()=>{monitorRuntimePromise=null});return monitorRuntimePromise}
let sharedSettingsSignature='';
function settingsSignature(settings){try{return JSON.stringify(settings||{})}catch{return''}}
function syncLiveAudioVolume(previousMaster,nextMaster){const entry=state.currentSpeechAudio,audio=entry?.audio;if(!audio)return;const old=Math.max(0,Math.min(100,Number(previousMaster??100))),next=Math.max(0,Math.min(100,Number(nextMaster??100)));if(old>0&&Number.isFinite(Number(entry.outputVolume))){entry.outputVolume=Math.max(0,Math.min(100,Number(entry.outputVolume)*next/old));entry.masterAtStart=next;try{audio.volume=entry.outputVolume/100}catch{}}else if(next<=0){try{audio.volume=0}catch{}}}
function renderMonitorAudioControls(){const value=Math.round(Math.max(0,Math.min(100,Number(state.settings.masterVolume??100)))),mode=String(state.settings.speechMode||'normal');const label=$('#monitorVolumeLabel'),mute=$('#monitorMuteBtn');if(label)label.textContent=`${value}%`;if(mute){mute.textContent=mode==='mute'||value===0?'🔇':'🔊';mute.title=mode==='mute'?'Geluid inschakelen (M)':'Geluid dempen (M)';mute.classList.toggle('active',mode==='mute'||value===0)}}
function applySharedSettings(settings){const previousMaster=Number(state.settings?.masterVolume??100),incoming={...(settings||{})};const merged={...DEFAULTS,...incoming,idleSunsetDim:false};merged.services=cleanServiceSettings(merged.services);merged.speechEngine='online';merged.speechMode=['normal','priority','mute'].includes(String(merged.speechMode))?String(merged.speechMode):'normal';merged.masterVolume=Math.max(0,Math.min(100,Number(merged.masterVolume??100)));sharedSettingsSignature=settingsSignature(incoming);state.settings=merged;syncLiveAudioVolume(previousMaster,merged.masterVolume);renderMonitorAudioControls();syncBackgroundPhoto();try{localStorage.setItem('p2000MonitorSettingsV4',JSON.stringify(state.settings))}catch{};if(merged.speechEnabled!==false&&merged.speechMode!=='mute'&&merged.masterVolume>0&&!state.audioBus.armed)setTimeout(()=>armAudioBus().catch(()=>{}),120);if(merged.speechEnabled===false||merged.speechMode==='mute'||merged.masterVolume<=0){setAudioUnlockVisible(false);stopSpeechPlayback({clearQueue:true})}invalidateIdleStatic();syncDisplayPower();render()}
async function loadSharedSettings(){try{const d=await json('/api/settings'),remote=d.settings||{};if(Object.keys(remote).length){applySharedSettings(remote);return}const local=loadSettings();applySharedSettings(local);const saved=await json('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(local)});applySharedSettings(saved.settings||local)}catch{state.settings=loadSettings()}}
async function pollSharedSettings(){try{const d=await json('/api/settings'),remote=d.settings||{};const sig=settingsSignature(remote);if(Object.keys(remote).length&&sig!==sharedSettingsSignature)applySharedSettings(remote)}catch{}}
async function setDisplayPower(wanted,force=false){if(!force&&!state.settings.displaySleep)return;if(!force&&state.lastPowerWanted===wanted)return;state.lastPowerWanted=wanted;try{const r=await json('/api/display/power',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:wanted})});if(!r?.ok)state.lastPowerWanted=null;else if(r?.held){const retry=Math.max(1,Number(r.retry_after)||5)*1000;setTimeout(()=>{if(state.lastPowerWanted===wanted){state.lastPowerWanted=null;syncDisplayPower()}},retry+250)}}catch{state.lastPowerWanted=null}}
function syncDisplayPower(){if(!state.settings.displaySleep){if(state.lastPowerWanted==='off')setDisplayPower('on',true);state.lastPowerWanted=null;return}setDisplayPower(trueBlack()?'off':'on')}
function refresh(){if(refreshPromise)return refreshPromise;refreshPromise=(async()=>{try{const [status,msgs]=await Promise.all([json('/api/status'),json('/api/messages?limit=100')]);state.lastRefreshAt=Date.now();observeMonitorRuntime(status);state.status=status;state.messages=msgs.messages||[];updateLastP2000ActivityFromMessages();if(!state.started){finishStartupBaseline()}else{const freshNew=filteredMessages().filter(m=>!state.knownIds.has(m.id)&&isFresh(m));freshNew.sort((a,b)=>-compareMessageNewest(a,b)).forEach(processNew);state.messages.forEach(m=>state.knownIds.add(m.id));pruneKnownIds()}syncDisplayPower();render()}catch(e){state.status={feed_status:'error',last_error:String(e)};render()}})().finally(()=>{refreshPromise=null});return refreshPromise}
function incoming(m){if(!m||state.knownIds.has(m.id))return;state.messages=[m,...state.messages.filter(x=>x.id!==m.id)].sort(compareMessageNewest).slice(0,100);processNew(m)}
function connect(){try{monitorEventSource?.close?.()}catch{}const es=new EventSource(`/api/stream?_=${Date.now()}`);monitorEventSource=es;es.onopen=()=>{watchMonitorRuntime();if(state.started)refresh()};es.onmessage=e=>{try{const p=JSON.parse(e.data);if(p.type==='message')incoming(p.message);else if(p.type==='runtime'){monitorRuntimeFailures=0;observeMonitorRuntime(p)}else if(p.type==='status'){state.status={...(state.status||{}),feed_status:p.status,last_error:p.error};}else if(p.type==='settings'){applySharedSettings(p.settings||{})}else if(p.type==='vehicle-db'){loadVehicleDb().then(()=>render()).catch(()=>{})}else if(p.type==='test'){handleTest(p.payload||{})}else if(p.type==='replay'){const m={...(p.message||{}),__test:true};if(m&&m.raw){activateMessage(m,{force:true,durationMs:REPLAY_MS});if(p.speak!==false)maybeSpeakMessage(m,{force:true})}}}catch{}};es.onerror=()=>{state.status={...(state.status||{}),feed_status:'error'};scheduleRuntimeWatch(900)}}
function stepPage(){if(!activeVisible())return;const pages=solidMessagePages(state.activeMessage);if(pages.length>1)state.page=(state.page+1)%pages.length;state.lastStep=Date.now();render()}
function tick(){
  const now=Date.now();
  if((state.activeMessages||[]).length){
    const changed=pruneExpiredActiveMessages(now);
    if(!(state.activeMessages||[]).length){syncDisplayPower();render();return}
    if(changed){syncDisplayPower();render();return}
    const multi=state.activeMessages.length>1;
    if(multi&&now-state.lastMessageSwitch>=carouselIntervalMs()){rotateActiveMessage();return}
    const pageMs=multi?MULTI_MESSAGE_PAGE_MS:PAGE_MS;
    if(now-state.lastStep>=pageMs)stepPage();
    // No redraw here. An active incident screen is static between page/carousel
    // transitions; v2.8.4 needlessly repainted the full canvas every second.
    return
  }
  // Test/replay items are intentionally duration based instead of P2000 timestamp based.
  if(state.activeMessage&&now>=state.activeUntil){clearActiveMessages();syncDisplayPower();render();return}
  if(activeVisible()){if(now-state.lastStep>=PAGE_MS)stepPage();return}
  // Idle clock has visible seconds, so this is the only mode that intentionally
  // renders once per second.
  syncDisplayPower();render()
}
function fullscreen(){if(!document.fullscreenElement)document.documentElement.requestFullscreen?.();else document.exitFullscreen?.()}
async function reportTestResult(payload,ok,detail){const token=String(payload?.token||'').trim();if(!token)return;try{await json('/api/test-result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,ok:!!ok,detail:String(detail||'').slice(0,240)}),timeoutMs:8000})}catch{}}
function handleTest(payload){
  const token=payload?.token||payload?.at||null;if(token&&token===state.lastTestToken)return;if(token)state.lastTestToken=token;
  const mode=String(payload?.mode||'message');
  if(mode==='stop-speech'){
    stopSpeechPlayback({clearQueue:true});return;
  }
  if(mode==='blackout'){
    clearActiveMessages();state.testIdleUntil=0;state.testBlackoutUntil=Date.now()+Math.max(1000,Number(payload?.duration_ms)||10000);render();return;
  }
  if(mode==='idle'){
    clearActiveMessages();state.testBlackoutUntil=0;state.testIdleUntil=Date.now()+Math.max(1000,Number(payload?.duration_ms)||15000);render();return;
  }
  if(mode==='tune-only'){
    (async()=>{try{const choice=String(payload?.tune_choice||dispatchTuneChoice(String(payload?.service||'brandweer'),!!payload?.urgent,true));if(choice==='none'){await reportTestResult(payload,false,'Er is geen deuntje gekozen');return}const played=await playDispatchTuneForJob({volume:100,cueService:String(payload?.service||'brandweer'),cueUrgent:!!payload?.urgent,forceAudio:true,tuneChoice:choice});await reportTestResult(payload,played,played?`Deuntje afgespeeld (${choice})`:`Deuntje kon niet worden afgespeeld (${choice})`)}catch(e){console.warn('Deuntjetest mislukt',e);await reportTestResult(payload,false,e?.message||'Deuntjetest mislukt')}})();return;
  }
  if(mode==='speech-only'){
    const explicit=String(payload?.speech_text||'').trim();
    if(!explicit){reportTestResult(payload,false,'Geen omroeptekst ontvangen');return}
    if(state.settings.speechEnabled===false&&!payload?.force_audio){reportTestResult(payload,false,'P2000 voorlezen staat uit');return}
    const accepted=queueSpeech(explicit,{priority:100,volume:100,kind:'test',key:`speech-only:${token||Date.now()}`,cueService:String(payload?.service||'brandweer'),cueUrgent:false,forceAudio:!!payload?.force_audio,skipTune:true,onResult:r=>reportTestResult(payload,!!r?.ok,r?.detail||'Omroeptest afgerond')});
    if(!accepted)reportTestResult(payload,false,'Omroeptest kon niet aan de wachtrij worden toegevoegd');
    return;
  }
  state.testBlackoutUntil=0;state.testIdleUntil=0;
  const now=new Date(),fallbackCity=String(state.setupProfile?.standplaats_city||state.setupProfile?.standplaats||'Utrecht').trim()||'Utrecht',raw=payload?.title||`P 1 BR woning Hoofdstraat ${fallbackCity}`;
  const m={__test:true,id:`test-${Date.now()}`,published:now.toISOString(),updated:now.toISOString(),title:raw,summary:payload?.summary||raw,url:'',service:payload?.service||'brandweer',priority:payload?.priority||'P1',city:payload?.city||fallbackCity,location:payload?.location||'',units:Array.isArray(payload?.units)?payload.units:[],categories:[payload?.service||'brandweer'],scale:payload?.scale||'',scale_score:Number(payload?.scale_score)||0,incident_key:`test-${Date.now()}`};
  activateMessage(m,{force:true,durationMs:Math.max(5000,Number(payload?.duration_ms)||60000)});
  if(payload?.speak!==false){
    const explicit=String(payload?.speech_text||'').trim();
    if(explicit){
      const urg=urgencyInfo(m),volume=speechVolumeForTime(m,urg.volume,new Date());
      queueSpeech(explicit,{priority:100,volume,kind:'test',key:`test-speech:${token||Date.now()}`,cueService:String(m.service||'overig'),cueUrgent:urg.rank>=5});
    }else maybeSpeakMessage(m,{force:true});
  }
}
let controlsTimer=null;function showControls(){const room=$('#room');room.classList.add('show-controls');clearTimeout(controlsTimer);controlsTimer=setTimeout(()=>room.classList.remove('show-controls'),2200)}
$('#fullscreenBtn').addEventListener('click',fullscreen);$('#lastBtn').addEventListener('click',replayLast);
let monitorVolumeSerial=0,monitorPreviousVolume=50;
async function monitorQuickAction(action,payload={}){const serial=++monitorVolumeSerial;try{const d=await json('/api/quick-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload}),timeoutMs:8000});if(serial===monitorVolumeSerial&&d?.settings)applySharedSettings(d.settings);return d}catch(e){console.warn('Geluidsbediening mislukt',e);return null}}
async function adjustMonitorVolume(delta){const current=Math.round(Math.max(0,Math.min(100,Number(state.settings.masterVolume??100)))),next=Math.max(0,Math.min(100,current+Number(delta||0)));if(next>0)monitorPreviousVolume=next;if(String(state.settings.speechMode||'normal')==='mute'&&next>0)await monitorQuickAction('speech-normal');await monitorQuickAction('volume',{value:next})}
async function toggleMonitorMute(){const mode=String(state.settings.speechMode||'normal'),volume=Math.round(Math.max(0,Math.min(100,Number(state.settings.masterVolume??100))));if(mode==='mute'||volume<=0){const restored=volume>0?volume:Math.max(10,monitorPreviousVolume);if(volume<=0)await monitorQuickAction('volume',{value:restored});await monitorQuickAction('speech-normal')}else{monitorPreviousVolume=volume;await monitorQuickAction('speech-mute')}}
$('#volumeDownBtn')?.addEventListener('click',()=>adjustMonitorVolume(-10));$('#monitorMuteBtn')?.addEventListener('click',toggleMonitorMute);$('#volumeUpBtn')?.addEventListener('click',()=>adjustMonitorVolume(10));renderMonitorAudioControls();
async function unlockTabAudio(){
  try{globalThis.speechSynthesis?.resume?.()}catch{}
  if(state.audioBus.armed){state.audioStats.unlocked=true;return true}
  try{await armAudioBus({gesture:true});state.audioStats.unlocked=true;startNextSpeechJob();return true}catch(e){console.warn('Audio unlock mislukt',e);return false}
}
const audioUnlockBtn=$('#audioUnlockBtn');if(audioUnlockBtn)audioUnlockBtn.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();unlockTabAudio()});
document.addEventListener('mousemove',showControls,{passive:true});document.addEventListener('pointerdown',()=>{if(state.audioBus.locked||!state.audioBus.armed)unlockTabAudio()},{passive:true});document.addEventListener('touchstart',e=>{showControls();if(state.audioBus.locked||!state.audioBus.armed)unlockTabAudio()},{passive:true});
document.addEventListener('keydown',e=>{if(state.audioBus.locked||!state.audioBus.armed)unlockTabAudio();showControls();if(e.key.toLowerCase()==='f')fullscreen();if(e.key.toLowerCase()==='l')replayLast();if(e.key.toLowerCase()==='m')toggleMonitorMute();if(e.key.toLowerCase()==='i')location.assign('/control.html')});
window.addEventListener('resize',resizeCanvas);
window.addEventListener('storage',e=>{if(e.key==='p2000MonitorSettingsV4'){state.settings=loadSettings();syncBackgroundPhoto();invalidateIdleStatic();syncDisplayPower();render()}if(e.key==='p2000TestMessage'&&e.newValue){try{handleTest(JSON.parse(e.newValue))}catch{handleTest({})}}});
try{const bc=new BroadcastChannel('p2000-monitor');bc.onmessage=e=>{if(e.data?.type==='test')handleTest(e.data)}}catch{}
setInterval(tick,1000);setInterval(watchMonitorRuntime,10000);setInterval(reportClientHealth,30000);setInterval(pollSharedSettings,30000);setInterval(refresh,300000);window.addEventListener('online',()=>scheduleRuntimeWatch(250));document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){scheduleRuntimeWatch(250);if(state.settings.speechEnabled!==false&&!state.audioBus.armed)armAudioBus().catch(()=>{});if(state.started&&Date.now()-state.lastRefreshAt>5000)refresh()}});resizeCanvas();setTimeout(reportClientHealth,5000);Promise.all([loadVehicleDb(),loadSharedSettings(),loadSetupProfile()]).then(async()=>{if(state.settings.speechEnabled!==false&&!state.audioBus.armed)setTimeout(()=>armAudioBus().catch(()=>{}),250);await refresh();if(!monitorReloading){connect()}});
