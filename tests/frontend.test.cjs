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

test('Pairing QR is generated locally and contains an authenticated fragment',async()=>{
  const instance=dom('remote.html','http://127.0.0.1:8765/remote'),{window}=instance;
  window.HTMLCanvasElement.prototype.getContext=()=>({fillStyle:'',fillRect(){}});
  window.P2000Auth={ready:Promise.resolve({local:true}),request:async(url)=>url==='/api/remote/info'?{ok:true,local:true,enabled:true,urls:['http://192.168.1.5:8765/remote'],token:'a'.repeat(43)}:{ok:true,settings:{},messages:[],displays:[]}};
  window.eval(read('qr-local.js'));window.eval(read('remote.js'));await settle();
  assert.ok(window.document.querySelector('#pairQr canvas'));
  assert.equal(window.document.querySelector('#pairCode').value,'a'.repeat(43));
  assert.equal(window.document.querySelector('#pairDetails').hidden,false);instance.window.close();
});

test('Pairing removes the token from history and sends it only in an admin header',async()=>{
  const token='b'.repeat(43), instance=dom('remote.html',`http://192.168.1.5:8765/remote#token=${token}`),{window}=instance,calls=[];
  window.fetch=async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({ok:true,local:false})}};
  window.eval(read('auth.js'));await window.P2000Auth.ready;
  assert.equal(window.location.hash,'');assert.equal(calls[0].url,'/api/remote/session');assert.equal(calls[0].options.headers['X-P2000-Admin-Token'],token);
  assert.equal(window.localStorage.length,0);instance.window.close();
});
