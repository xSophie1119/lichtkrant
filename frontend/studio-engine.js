/* Shared pure logic: live display, editor previews and historical playback. */
(function(root){
'use strict';
const lower=v=>String(v??'').trim().toLocaleLowerCase('nl-NL');
function inside(point,polygon){
 if(!point||!Number.isFinite(point.lat)||!Number.isFinite(point.lon))return null;
 const x=point.lon,y=point.lat;let hit=false;
 for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const [yi,xi]=polygon[i],[yj,xj]=polygon[j];
  const cross=(x-xi)*(yj-yi)-(y-yi)*(xj-xi);
  if(Math.abs(cross)<1e-9&&x>=Math.min(xi,xj)&&x<=Math.max(xi,xj)&&y>=Math.min(yi,yj)&&y<=Math.max(yi,yj))return true;
  if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)hit=!hit;
 }return hit;
}
function resource(m,type){const raw=lower([m.title,m.summary,...(m.units||[])].join(' '));return type==='mmt'?m.service==='lifeliner'||/\b(?:mmt|lifeliner|(?:17|13|08)-?99[123])\b/.test(raw):/\b(?:ovd[ -]?g|officier van dienst geneeskundig|80[345])\b/.test(raw)}
function match(rule,m,zones,geo,now){
 const w=rule.when||{},checks=[];let unknown=false;
 for(const [key,value] of Object.entries(w)){
  if(value===''||value===null)continue;
  let yes;
  if(key==='contains')yes=lower(`${m.title||''} ${m.summary||''}`).includes(lower(value));
  else if(key==='min_scale')yes=Number(m.scale_score||0)>=Number(value);
  else if(key==='resource')yes=resource(m,value);
  else if(key==='zone'){
   const z=zones.find(z=>z.id===value);
   if(!z||z.enabled===false||(z.expires&&now>=z.expires))yes=false;
   else{yes=inside(geo,z.points);if(yes===null)unknown=true}
  }else yes=lower(m[key])===lower(value);
  checks.push({field:key,value,match:yes});
 }
 return {match:checks.some(c=>c.match===false)?false:unknown?null:true,checks};
}
function evaluate(config,m,geo=null,now=Date.now()){
 if(!config?.enabled)return {enabled:false,show:true,speak:true,action:'show',reason:'Bestaande schermfilters',matches:[]};
 const matches=[];let chosen=null;
 for(const r of config.rules||[]){if(r.enabled===false)continue;const result=match(r,m,config.zones||[],geo,now);matches.push({id:r.id,name:r.name,...result});if(chosen===null&&result.match!==false)chosen={r,result}}
 if(chosen?.result.match===null){const show=config.unknown_location!=='hide';return {enabled:true,show,speak:show,action:show?'show':'hide',reason:'Locatie onbekend of onvoldoende nauwkeurig; '+(show?'tonen':'verbergen'),rule:chosen.r.name,unknown:true,matches}}
 const r=chosen?.r,action=r?.action||config.default_action||'show';
 return {enabled:true,show:action!=='hide',speak:action!=='hide'&&action!=='silent',urgent:action==='urgent',action,cue:r?.cue||'auto',rule:r?.name||'',reason:r?'Regel: '+r.name:'Geen regel past; standaard '+(action==='hide'?'verbergen':'tonen'),matches};
}
function legacy(m,s={}){
 if(s.exerciseMode&&!m.__test)return {show:false,reason:'Oefenmodus'};
 if(s.urgentOnly&&!(/^(P1|A0|A1)$/.test(m.priority)||m.service==='lifeliner'||Number(m.scale_score)>0))return {show:false,reason:'Profiel: alleen urgent'};
 if(s.services?.length&&!s.services.includes(m.service))return {show:false,reason:'Dienstenfilter'};
 if(s.cities?.length&&!s.cities.some(x=>lower(m.city).includes(lower(x))))return {show:false,reason:'Plaatsfilter'};
 if(s.keywords?.length&&!s.keywords.some(x=>lower(`${m.title} ${m.summary} ${m.city} ${m.location}`).includes(lower(x))))return {show:false,reason:'Zoekwoordfilter'};
 return {show:true,reason:'Bestaande filters staan deze melding toe'};
}
function decision(config,m,geo,settings={},now=Date.now()){
 const d=evaluate(config,m,geo,now);
 if(settings.exerciseMode&&!m.__test)return {...d,show:false,speak:false,reason:'Oefenmodus'};
 if(settings.urgentOnly&&!d.urgent&&!(/^(P1|A0|A1)$/.test(m.priority)||m.service==='lifeliner'||Number(m.scale_score)>0))return {...d,show:false,speak:false,reason:'Profiel: alleen urgent'};
 return d.enabled?d:{...d,...legacy(m,settings)};
}
function phrase(template,vars){return String(template||'').replace(/\{([a-z_]+)\}/g,(_,k)=>String(vars[k]??'')).replace(/\s+/g,' ').replace(/\s+([.,;])/g,'$1').replace(/(?:\.\s*){2,}/g,'. ').replace(/^[\s.,;]+|[\s,;]+$/g,'').trim()}
function variables(m){const location=m.location||'',city=m.city||'',units=(m.vehicle_labels||m.units||[]).join(', ');return {incident:m.incident||m.incident_type||m.title||'Melding',where:(location?' aan de '+location:'')+(city?' in '+city:''),city,location,scale:m.scale?'Opgeschaald naar '+m.scale+'.':'',units:units?'Gealarmeerde voertuigen: '+units+'.':'',priority:m.priority||'',service:m.service||''}}
function scene(layout,count){return layout?.scenes?.[count===0?'idle':count===1?'single':'multiple']||[]}
function draw(canvas,layout,{message=null,messages=[],now=Date.now(),name='LICHTKRANT',preview=false,units=[]}={}){
 const c=canvas.getContext('2d');if(!c)return [];
 const w=canvas.width,h=canvas.height,boxes=scene(layout,message?Math.max(1,messages.length):0),warnings=[];
 c.save();c.setTransform(1,0,0,1,0,0);c.fillStyle='#081219';c.fillRect(0,0,w,h);
 const min=Number(layout.min_font||24)*w/1920;
 for(const b of boxes){const x=b.x*w/100,y=b.y*h/100,bw=b.w*w/100,bh=b.h*h/100,pad=Math.min(18*w/1920,bw*.04),fs=Math.max(min,Math.min(bw/22,bh/5));
  c.save();c.beginPath();c.rect(x,y,bw,bh);c.clip();c.fillStyle='#12232d';c.fillRect(x,y,bw,bh);c.fillStyle='#65e1bd';c.font=`700 ${Math.max(min*.65,10*w/1920)}px system-ui`;c.textBaseline='top';
  const titles={message:'MELDING',map:'INCIDENTLOCATIE',vehicles:'GEALARMEERDE VOERTUIGEN',clock:name,incidents:'ACTIEVE INCIDENTEN'};c.fillText(titles[b.type],x+pad,y+pad);
  let text='';
  if(b.type==='message')text=message?[message.priority,message.city,message.location,message.screen_text||message.title].filter(Boolean).join('\n'):'Geen actieve melding';
  if(b.type==='vehicles')text=(units.length?units:message?.vehicle_labels||message?.units||[]).join('\n')||'Geen voertuigen herkend';
  if(b.type==='clock')text=new Date(now).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})+'\n'+new Date(now).toLocaleDateString('nl-NL',{weekday:'long',day:'numeric',month:'long'});
  if(b.type==='incidents')text=messages.map(m=>[m.priority,m.city,m.location||m.title].filter(Boolean).join(' · ')).join('\n')||'Geen actieve incidenten';
  if(b.type==='map')text=preview?'Kaart van de incidentlocatie':message?'Kaart laden…':'Geen incidentlocatie';
  c.font=`600 ${fs}px system-ui`;c.fillStyle='#edf7fa';let cy=y+pad+Math.max(min,fs*.8);const lines=[];
  for(const para of text.split('\n')){let line='';for(const word of para.split(/\s+/)){const next=line?line+' '+word:word;if(line&&c.measureText(next).width>bw-2*pad){lines.push(line);line=word}else line=next}if(line)lines.push(line)}
  const capacity=Math.max(0,Math.floor((y+bh-pad-cy)/(fs*1.3))),pages=Math.max(1,Math.ceil(lines.length/Math.max(1,capacity))),offset=capacity?Math.floor(now/6500)%pages*capacity:0;
  if(!capacity)warnings.push(`${titles[b.type]}: blok te klein voor de minimale tekstgrootte`);else if(lines.length>capacity)warnings.push(`${titles[b.type]}: ${pages} tekstpagina’s nodig`);
  for(const line of lines.slice(offset,offset+capacity)){c.fillText(line,x+pad,cy);cy+=fs*1.3}c.restore();
 }c.restore();return warnings;
}
const api={inside,resource,match,evaluate,decision,legacy,phrase,variables,scene,draw};root.P2000StudioEngine=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
