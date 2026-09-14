/* Integration uses the same rule/scene engine as the editor. */
(function(){
'use strict';let hooks=null;const json=(...a)=>hooks.json(...a);let design={revision:0,config:{}},loaded=false,pending=null;const geoCache=new Map(),reports=new Set();
const E=()=>window.P2000StudioEngine;
async function load(){if(pending)return pending;pending=(async()=>{try{apply(await json('/api/remote/studio/config'));loaded=true}catch(e){console.warn('Studio laden mislukt',e)}finally{pending=null}})();return pending}
function apply(d){if(!d?.config)return;const previous=design;design=d;loaded=true;if(!window.P2000_STUDIO_PREVIEW){try{localStorage.setItem('p2000StudioDesign',JSON.stringify(d))}catch{};if(hooks?.state&&previous.revision!==d.revision&&hooks.state.activeMessage&&!hooks.state.activeMessage.__test&&!hooks.filterMessage(hooks.state.activeMessage)){hooks.clearPin();hooks.clearActiveMessages();hooks.stopSpeechPlayback({clearQueue:true})}hooks?.render()}}
try{const saved=JSON.parse(localStorage.getItem('p2000StudioDesign')||'null');if(saved?.config)design=saved}catch{}
function result(m){return E()?.evaluate(design.config,m,m?.__studioGeo)||{enabled:false,show:true,speak:true}}
async function prepare(m){
 if(!m||!E()||!design.config.enabled)return m;
 const d=result(m);if(!d.unknown||!m.city||!m.location)return m;
 const key=m.city+'|'+m.location,old=geoCache.get(key);
 if(old&&old.expires>Date.now()){m.__studioGeo=old.geo;return m}
 let geo=null;
 try{const data=await json('/api/geocode?city='+encodeURIComponent(m.city)+'&location='+encodeURIComponent(m.location),{timeoutMs:2500});const g=data.map;if(g&&Number.isFinite(g.lat)&&Number.isFinite(g.lon)&&Number(g.confidence||0)>=.8)geo={lat:g.lat,lon:g.lon,source:g.source||''}}catch{}
 geoCache.set(key,{geo,expires:Date.now()+(geo?1800000:60000)});if(geoCache.size>300)geoCache.delete(geoCache.keys().next().value);m.__studioGeo=geo;return m;
}
async function prepareAll(messages){let i=0;await Promise.all(Array.from({length:Math.min(4,messages.length)},async()=>{while(i<messages.length)await prepare(messages[i++])}));return messages}
function report(m,shown,reason){
 if(!m?.id||m.__test||m.__archive)return;
 const key=m.id+'|'+reason;if(reports.has(key))return;reports.add(key);if(reports.size>1000)reports.delete(reports.values().next().value);
 const d=result(m);json('/api/remote/studio/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:m.id,client_id:hooks.clientId,shown,reason,rule:d.rule||'',revision:design.revision,geo:m.__studioGeo}),timeoutMs:5000}).catch(()=>{});
}
function speech(m){if(!design.config.speech?.enabled||!E())return null;const city=hooks.speechCity(m),info=hooks.speechIncidentInfo(m),location=hooks.speechLocation(m,info,city),scale=hooks.speechScale(m),labels=hooks.vehicleDetails(m).map(v=>v.speech).filter(Boolean);return hooks.applySpeechDictionary(E().phrase(design.config.speech.template,{incident:info.type,where:hooks.spokenIncidentWhere(city,location),city,location,scale:scale?'Opgeschaald naar '+scale+'.':'',units:labels.length?'Gealarmeerde voertuigen: '+hooks.joinSpeechParts(labels)+'.':'',priority:m.priority||'',service:m.service||''}))}
function cue(m,normal){const d=result(m);if(d.cue==='none'||design.config.speech?.enabled&&design.config.speech.cue===false)return '';return d.cue&&d.cue!=='auto'?d.cue:normal}
function drawCustom(){if(!design.config.layout?.enabled||!E()||hooks.trueBlack()||Date.now()<hooks.state.testBlackoutUntil)return false;E().draw(hooks.canvas,design.config.layout,{message:hooks.activeVisible()?hooks.state.activeMessage:null,messages:hooks.state.activeMessages||[],name:hooks.state.settings.name||'LICHTKRANT',units:hooks.activeVisible()?hooks.vehicleDetails(hooks.state.activeMessage).map(v=>v.header):[]});return true}
function mapBox(){if(!design.config.layout?.enabled||!E())return undefined;return E().scene(design.config.layout,hooks.activeVisible()?Math.max(1,(hooks.state.activeMessages||[]).length):0).find(x=>x.type==='map')||null}
function placeMap(){const el=document.querySelector('#incidentMapPanel'),box=mapBox();if(!el)return;if(box){Object.assign(el.style,{left:box.x+'%',top:box.y+'%',width:box.w+'%',height:box.h+'%',right:'auto',bottom:'auto'});el.classList.add('studio-map')}else{el.classList.remove('studio-map');for(const k of ['left','top','width','height','right','bottom'])el.style[k]='';if(box===null)hooks.hideIncidentMap()}}
window.P2000StudioLive={init:adapter=>{hooks=adapter},load,apply,prepare,prepareAll,result,report,speech,cue,drawCustom,mapBox,placeMap,get design(){return design},get loaded(){return loaded}};
})();
