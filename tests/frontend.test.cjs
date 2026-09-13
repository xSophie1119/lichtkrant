/* DOM unit tests; jsdom is only a developer dependency, never a kiosk dependency. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.join(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'frontend', name), 'utf8');
const settle = async () => { for(let i=0;i<12;i++) await new Promise(resolve=>setImmediate(resolve)); };
function dom(name, url='http://192.168.1.5:8765/remote') {
  const instance = new JSDOM(read(name), {url, runScripts:'outside-only', pretendToBeVisual:true});
  instance.window.confirm = () => true;
  return instance;
}
function control() {
  const instance = dom('control.html'); const {window} = instance; const writes = [];
  window.P2000Auth = {ready:Promise.resolve({local:true})};
  let stored = {name:'Tilburg112',cities:['Tilburg'],keywords:['brand'],kioskMonitor:'HDMI-2',masterVolume:80,speechEngine:'native',mapEnabled:true};
  window.fetch = async (url, options={}) => {
    if(options.method==='POST') {
      const payload = JSON.parse(options.body || '{}'); writes.push({url,payload});
      if(url==='/api/quick-action') { if(payload.action==='volume')stored.masterVolume=payload.value; else stored.speechMode='mute'; }
      else if(url==='/api/settings') stored={...stored,...payload};
    }
    const data = url==='/api/settings'||url==='/api/quick-action'?{settings:stored}:{exists:false};
    return {ok:true,status:200,json:async()=>data};
  };
  window.eval(read('control.js').replace(/\ninit\(\)\.catch\([^\n]+\);\s*$/, '') + '\nObject.assign(window,{initTuneSelects,renderSettings,settingPatch,quickAction,save,api});');
  window.initTuneSelects(); window.renderSettings(stored);
  return {instance,window,writes};
}

test('Unchanged settings do not resend defaults or erase city filters and monitor', async()=>{
  const {instance,window}=control();
  assert.equal(window.document.querySelector('#kioskMonitorInput').value,'HDMI-2');
  assert.deepEqual(JSON.parse(JSON.stringify(window.settingPatch())),{});
  window.document.querySelector('#nameInput').value='New name';
  assert.deepEqual(JSON.parse(JSON.stringify(window.settingPatch())),{name:'New name'});
  await settle(); instance.window.close();
});

test('Quick volume leaves an unsaved form edit intact', async()=>{
  const {instance,window,writes}=control();
  window.document.querySelector('#nameInput').value='Unsaved heading';
  await window.quickAction('volume',{value:0});
  assert.equal(window.document.querySelector('#nameInput').value,'Unsaved heading');
  assert.equal(window.document.querySelector('#masterVolumeInput').value,'0');
  assert.deepEqual(JSON.parse(JSON.stringify(window.settingPatch())),{name:'Unsaved heading'});
  assert.equal(writes.length,1); await settle(); instance.window.close();
});

test('A full settings save sends only fields the user changed', async()=>{
  const {instance,window,writes}=control();
  window.document.querySelector('#mapEnabledInput').checked=false;
  await window.save();
  assert.deepEqual(writes[0].payload,{mapEnabled:false});
  assert.equal(window.document.querySelector('#kioskMonitorInput').value,'HDMI-2');
  await settle(); instance.window.close();
});

test('Concurrent control writes are serialized in input order', async()=>{
  const {instance,window}=control(); let active=0,peak=0; const order=[];
  window.fetch=async(url,options)=>{active++;peak=Math.max(active,peak);const value=JSON.parse(options.body).value;await new Promise(resolve=>setImmediate(resolve));order.push(value);active--;return{ok:true,json:async()=>({ok:true})}};
  await Promise.all([window.api('/test',{method:'POST',body:'{"value":1}'}),window.api('/test',{method:'POST',body:'{"value":2}'})]);
  assert.equal(peak,1);assert.deepEqual(order,[1,2]); instance.window.close();
});

test('Mobile dashboard renders safely, changes zero volume and saves toggles', async()=>{
  const instance=dom('remote.html'),{window}=instance,writes=[];
  let settings={name:'Tilburg112',masterVolume:80,speechMode:'normal',mapEnabled:true,nightMode:true,mapMode:'auto'};
  window.P2000Auth={ready:Promise.resolve({local:false}),request:async(url,options={})=>{
    if(options.method==='POST'){const payload=JSON.parse(options.body);writes.push({url,payload});if(url==='/api/quick-action')settings.masterVolume=payload.value;if(url==='/api/settings')settings={...settings,...payload};return{ok:true,settings}}
    if(url==='/api/remote/info')return{ok:true,local:false};
    return{ok:true,version:'4.6.0',settings,feed_status:'online',displays:[{online:true}],messages:[{title:'<img src=x onerror=alert(1)>',city:'Tilburg',published:'2026-09-12T10:00:00Z',service:'brandweer'}]};
  }};
  window.eval(read('remote.js'));await settle();
  assert.equal(window.document.querySelector('#connection').textContent,'● Verbonden');
  assert.equal(window.document.querySelector('#messageList img'),null);
  assert.equal(window.document.querySelector('#mapMode').value,'auto');
  const slider=window.document.querySelector('#volume');slider.value='0';slider.dispatchEvent(new window.Event('input'));slider.dispatchEvent(new window.Event('change'));await settle();
  assert.equal(writes[0].payload.value,0);
  const toggle=window.document.querySelector('#mapEnabled');toggle.checked=false;toggle.dispatchEvent(new window.Event('change'));await settle();
  assert.deepEqual(writes[1].payload,{mapEnabled:false});instance.window.close();
});

test('Pairing QR uses a new single-use invitation created explicitly on the pc',async()=>{
  const instance=dom('remote.html','http://127.0.0.1:8765/remote'),{window}=instance;
  try{
    window.HTMLCanvasElement.prototype.getContext=()=>({fillStyle:'',fillRect(){}});
    window.P2000Auth={ready:Promise.resolve({local:true,role:'admin'}),request:async(url)=>{
      if(url==='/api/remote/info')return{ok:true,local:true,enabled:true,urls:['http://192.168.1.5:8765/remote']};
      if(url==='/api/remote/invite')return{ok:true,invite:{token:'a'.repeat(43),expires_at:Date.now()/1000+300}};
      return{ok:true,settings:{},messages:[],displays:[],devices:[]};
    }};
    window.eval(read('qr-local.js'));window.eval(read('remote-plus.js'));window.eval(read('remote.js'));await settle();
    assert.equal(window.document.querySelector('#pairQr canvas'),null);
    window.document.querySelector('#createInvite').click();await settle();
    assert.ok(window.document.querySelector('#pairQr canvas'));
    assert.equal(window.document.querySelector('#pairCode').value,'a'.repeat(43));
    assert.equal(window.document.querySelector('#pairDetails').hidden,false);
  }finally{window.close();}
});

test('Pairing removes the token from history and sends it only in an admin header',async()=>{
  const token='b'.repeat(43), instance=dom('remote.html',`http://192.168.1.5:8765/remote#token=${token}`),{window}=instance,calls=[];
  window.fetch=async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({ok:true,local:false})}};
  window.eval(read('auth.js'));await window.P2000Auth.ready;
  assert.equal(window.location.hash,'');assert.equal(calls[0].url,'/api/remote/session');assert.equal(calls[0].options.headers['X-P2000-Admin-Token'],token);
  assert.equal(window.localStorage.length,0);instance.window.close();
});

function mobile(role='controller'){
  const instance=dom('remote.html'),{window}=instance,calls=[];
  const status={ok:true,version:'4.7.0',settings:{masterVolume:55,activeProfile:'normal'},messages:[],displays:[],profiles:[{id:'normal',label:'Normaal',description:'Normaal'},{id:'exercise',label:'Oefening',description:'Tests'}],diagnostics:{sources:[]},metrics:{stages:{},process:[]},commands:[]};
  let response=null;
  window.P2000Auth={ready:Promise.resolve({role,local:false}),request:async(url,options={})=>{
    calls.push({url,options});if(response){const result=response(url,options);if(result)return result;}
    if(url==='/api/remote/info')return{ok:true,local:false};
    if(url.startsWith('/api/remote/archive'))return{ok:true,messages:[{id:'<bad-id>',title:'<img src=x onerror=alert(1)>',city:'Tilburg',service:'brandweer',priority:'P1',published:'2026-09-12T10:00:00Z'}]};
    return status;
  }};
  window.eval(read('remote-plus.js'));window.eval(read('remote.js'));
  return{instance,window,calls,status,setResponse:fn=>{response=fn;}};
}

test('Viewer dashboard has read-only controls and archive output is escaped',async()=>{
  const {instance,window,calls}=mobile('viewer');
  try{
    await settle();assert.equal(window.document.body.classList.contains('viewer'),true);
    window.document.querySelector('#archiveForm').dispatchEvent(new window.Event('submit',{cancelable:true}));await settle();
    assert.equal(window.document.querySelector('#archiveResults img'),null);
    assert.equal(window.document.querySelector('#archiveResults [data-message]'),null);
    assert.ok(window.document.querySelector('#archiveResults [data-map]'));
    assert.equal(calls.filter(x=>x.options.method==='POST').length,0);
  }finally{window.close();}
});

test('Archive filters use local day boundaries and selected-screen commands',async()=>{
  const {window,calls,status}=mobile();
  try{
    await settle();status.displays=[{client_id:'screen-2',online:true}];window.P2000RemotePlus.update(status);
    const form=window.document.querySelector('#archiveForm');form.elements.from.value='2026-09-12';form.elements.to.value='2026-09-12';form.elements.city.value='Tilburg';
    form.dispatchEvent(new window.Event('submit',{cancelable:true}));await settle();
    const request=calls.find(x=>x.url.startsWith('/api/remote/archive'));
    assert.match(request.url,/city=Tilburg/);assert.match(request.url,/until=/);
    window.document.querySelector('[data-message-action=pin]').click();await settle();
    const command=calls.find(x=>x.url==='/api/remote/message-action');
    assert.deepEqual(JSON.parse(command.options.body),{id:'<bad-id>',action:'pin',client_id:'screen-2'});
  }finally{window.close();}
});

test('Profiles confirm exercise mode and apply the returned settings',async()=>{
  const {window,calls,setResponse}=mobile();
  try{
    await settle();setResponse(url=>url==='/api/remote/profile'?{ok:true,settings:{masterVolume:50,exerciseMode:true}}:null);
    window.document.querySelector('[data-profile=exercise]').click();await settle();
    assert.equal(JSON.parse(calls.find(x=>x.url==='/api/remote/profile').options.body).id,'exercise');
    assert.equal(window.document.querySelector('#volume').value,'50');
  }finally{window.close();}
});

test('Restore sends the fingerprint from preview and renders values as text',async()=>{
  const {window,calls,setResponse}=mobile();
  try{
    await settle();setResponse(url=>{
      if(url==='/api/remote/history')return{ok:true,points:[{id:'restore1',description:'<script>bad</script>',created_at:'2026-09-12'}]};
      if(url.startsWith('/api/remote/restore-preview'))return{ok:true,preview:{id:'restore1',expected:'fingerprint',changes:[{key:'name',before:'Old',after:'<img src=x>'}]}};
      if(url==='/api/remote/restore')return{ok:true,settings:{masterVolume:55}};
    });
    window.document.querySelector('#loadHistory').click();await settle();window.document.querySelector('[data-restore]').click();await settle();
    assert.equal(window.document.querySelector('#restoreChanges img'),null);
    window.document.querySelector('#confirmRestore').click();await settle();
    assert.deepEqual(JSON.parse(calls.find(x=>x.url==='/api/remote/restore').options.body),{id:'restore1',expected:'fingerprint'});
  }finally{window.close();}
});

test('Live status uses its own stream, closes on hiding and reopens on return',async()=>{
  const instance=dom('remote.html'),{window}=instance,sockets=[];
  try{
    class Stream{constructor(url){this.url=url;this.readyState=1;sockets.push(this)}addEventListener(){}close(){this.closed=true;this.readyState=2}}
    window.EventSource=Stream;window.P2000Auth={ready:Promise.resolve({role:'viewer'}),request:async url=>url==='/api/remote/info'?{local:false}:{ok:true,settings:{},messages:[],displays:[]}};
    window.eval(read('remote.js'));await settle();assert.equal(sockets[0].url,'/api/remote/events');
    Object.defineProperty(window.document,'hidden',{configurable:true,value:true});window.document.dispatchEvent(new window.Event('visibilitychange'));assert.equal(sockets[0].closed,true);
    Object.defineProperty(window.document,'hidden',{configurable:true,value:false});window.document.dispatchEvent(new window.Event('visibilitychange'));await settle();assert.equal(sockets.length,2);
  }finally{window.close();}
});

function monitor(){
  const instance=dom('index.html','http://127.0.0.1:8765/'),{window}=instance;
  window.HTMLCanvasElement.prototype.getContext=()=>new Proxy({measureText:text=>({width:String(text).length*8}),createLinearGradient:()=>({addColorStop(){}})}, {get:(obj,key)=>obj[key]||(()=>{})});
  window.matchMedia=()=>({matches:false});window.requestAnimationFrame=fn=>{fn();return 1;};
  const source=read('app.js').split("let controlsTimer=null;")[0];
  window.eval(source+`\nObject.assign(window,{screenState:state,filterMessage,remoteUrgent,pollDisplayCommands,handleDisplayCommand,handleTest,queueSpeech,finishSpeechJob,HOST_TEST:{},configureScreenTest:hooks=>{if(hooks.activate)activateMessage=hooks.activate;if(hooks.speak)maybeSpeakMessage=hooks.speak;reportClientHealth=async()=>{};commandReceipt=async(seq,status,detail)=>{hooks.receipts.push({seq,status,detail})};render=()=>{};clearActiveMessages=()=>{};},setJson:fn=>{json=fn},setQueueRunner:fn=>{startNextSpeechJob=fn},setTestReporter:fn=>{reportTestResult=fn}});`);
  return{window,instance};
}

test('Screen replay accepts stored title fields, deduplicates and waits for audio result',async()=>{
  const {window}=monitor(),receipts=[],shown=[];let audioDone;
  try{
    window.configureScreenTest({receipts,activate:(m)=>{shown.push(m);return true},speak:(_m,options)=>{audioDone=options.onResult;return true}});
    const cmd={_command_seq:1,type:'replay',message:{id:'archive',title:'P1 brand',city:'Tilburg'},speak:true};
    await window.handleDisplayCommand(cmd);await window.handleDisplayCommand(cmd);
    assert.equal(shown.length,1);assert.equal(receipts.at(-1).status,'displayed');
    audioDone({ok:true,detail:'Afgespeeld'});assert.equal(receipts.at(-1).status,'completed');
  }finally{window.close();}
});

test('Exercise and urgent profiles filter live messages while preserving manual tests',()=>{
  const {window}=monitor();
  try{
    const s=window.screenState;s.settings.services=['brandweer'];s.settings.cities=[];s.settings.keywords=[];
    s.settings.exerciseMode=true;assert.equal(window.filterMessage({service:'brandweer',priority:'P1'}),false);
    assert.equal(window.filterMessage({service:'brandweer',priority:'P1',__test:true}),true);
    s.settings.exerciseMode=false;s.settings.urgentOnly=true;
    assert.equal(window.filterMessage({service:'brandweer',priority:'P2'}),false);assert.equal(window.filterMessage({service:'brandweer',priority:'P1'}),true);
  }finally{window.close();}
});

test('Replaced speech jobs receive cancellation rather than silent disappearance',()=>{
  const {window}=monitor(),results=[];
  try{
    window.setQueueRunner(()=>{});window.queueSpeech('Old',{groupKey:'same',priority:10,onResult:r=>results.push(r)});window.queueSpeech('New',{groupKey:'same',priority:20});
    assert.equal(window.screenState.speechQueue.length,1);assert.equal(results[0].ok,false);
  }finally{window.close();}
});

test('Polling executes queued commands before advancing its cursor',async()=>{
  const {window}=monitor(),receipts=[],shown=[];
  try{
    window.configureScreenTest({receipts,activate:m=>{shown.push(m.id);return true},speak:()=>false});
    window.setJson(async()=>({commands:[{_command_seq:1,type:'replay',message:{id:'one',title:'One'},speak:false},{_command_seq:2,type:'replay',message:{id:'two',title:'Two'},speak:false}],latest_seq:2}));
    await window.pollDisplayCommands();assert.deepEqual(shown,['one','two']);
    await window.handleDisplayCommand({_command_seq:2,type:'replay',message:{id:'duplicate',title:'Duplicate'},speak:false});
    assert.equal(shown.length,2);
  }finally{window.close();}
});
