/* Real Chromium layout smoke test with isolated HTTP fixtures; no live audio. */
(async function browserSmoke(){
  const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
  const root=path.resolve(__dirname,'..'),output=path.join(root,'browser-artifacts');fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true});
  const settings={name:'Tilburg112',masterVolume:70,speechEnabled:false,speechMode:'normal',speechCities:[],mapEnabled:false,nightMode:false,activeProfile:'normal',services:['brandweer','politie','ambulance'],messageDisplayMode:'parsed'};
  const config={enabled:false,default_action:'show',unknown_location:'show',rules:[],zones:[],speech:{enabled:false,template:'{incident}{where}. {units}',cue:true},layout:{enabled:false,aspect:'16:9',min_font:24,scenes:{idle:[],single:[],multiple:[]}},corrections:[],examples:[]};
  const message={id:'example',__test:true,published:new Date().toISOString(),title:'P 1 BR Woning Hoofdstraat Tilburg 20-9432',summary:'P 1 BR Woning Hoofdstraat Tilburg 20-9432',service:'brandweer',priority:'P1',city:'Tilburg',location:'Hoofdstraat',units:['209432']};
  try{
    for(const width of [390,768,1440]){
      const context=await browser.newContext({viewport:{width,height:width===390?844:1000}});
      await context.addInitScript(()=>{window.EventSource=class{constructor(){this.readyState=1}addEventListener(){}close(){this.readyState=2}}});
      const page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.route('**/*',async route=>{
        const u=new URL(route.request().url()),p=u.pathname;
        if(p==='/auth.js')return route.fulfill({contentType:'text/javascript',body:"window.P2000Auth={ready:Promise.resolve({local:false,role:'controller'}),request:async(u,o)=>{const r=await fetch(u,o);if(!r.ok)throw Error('HTTP '+r.status);return r.json()}};"});
        if(p.startsWith('/api/')){
          let data={ok:true,settings,messages:[],exists:false};
          if(p==='/api/remote/status')data={ok:true,version:'4.8.1',settings,feed_status:'online',messages:[message],displays:[{online:true,client_id:'tv',display_name:'Woonkamer',master_volume:70,speech_mode:'normal'}],profiles:[{id:'normal',label:'Normaal'},{id:'night',label:'Nacht'},{id:'exercise',label:'Oefening'},{id:'urgent',label:'Urgent'}],diagnostics:{sources:[]},metrics:{stages:{},process:[]}};
          if(p==='/api/remote/info')data={ok:true,local:false};
          if(p==='/api/remote/studio/config')data={ok:true,revision:1,config};
          if(p==='/api/remote/studio/records')data={ok:true,records:[]};
          if(p==='/api/remote/studio/recordings')data={ok:true,recordings:[]};
          if(p==='/api/setup')data={ok:true,setup:{setup_complete:true,standplaats_city:'Tilburg'}};
          return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
        }
        if(u.hostname!=='127.0.0.1')return route.fulfill({status:204,body:''});
        const name=p==='/remote'?'remote.html':p==='/control'?'control.html':p==='/'?'index.html':p.slice(1),file=path.join(root,'frontend',name);
        if(!file.startsWith(path.join(root,'frontend')+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:'Missing fixture file'});
        const ext=path.extname(file),mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json'}[ext]||'application/octet-stream';
        return route.fulfill({contentType:mime,body:fs.readFileSync(file)});
      });
      await page.goto('http://127.0.0.1/remote');
      await page.locator('#connection[data-online=true]').waitFor();
      const nav=width<=720?'.bottom-nav':'.panel-nav';
      for(const name of ['overview','sound','messages','management']){
        await page.locator(nav+' [data-page="'+name+'"]').click();
        await page.waitForFunction(name=>[...document.querySelectorAll('[data-panel]')].every(x=>x.hasAttribute('data-page-hidden')===(x.dataset.panel!==name)),name);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'remote overflow '+width+' '+name);
        await page.screenshot({path:path.join(output,'remote-'+width+'-'+name+'.png'),fullPage:true});
      }
      await page.goto('http://127.0.0.1/control');
      await page.locator('[data-category][aria-current]').waitFor();
      await page.locator('#nameInput').fill('Eigen titel');
      for(const name of ['audio','filters','vehicles','system','appearance']){
        await page.locator('[data-category="'+name+'"]').click();
        await page.waitForFunction(name=>document.querySelector('[data-category="'+name+'"]').hasAttribute('aria-current'),name);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'control overflow '+width+' '+name);
      }
      assert.equal(await page.locator('#nameInput').inputValue(),'Eigen titel');
      await page.screenshot({path:path.join(output,'settings-'+width+'.png'),fullPage:true});
      await page.goto('http://127.0.0.1/studio.html');
      await page.locator('#saveState').filter({hasText:/Opgeslagen|Toegepast/}).waitFor();
      for(const name of ['areas','rules','log','speech','corrections','layout','replay']){
        await page.locator('[data-tab="'+name+'"]').click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'studio overflow '+width+' '+name);
      }
      await page.locator('[data-tab="speech"]').click();
      await page.screenshot({path:path.join(output,'studio-'+width+'.png'),fullPage:true});
      assert.deepEqual(errors,[],'Browser errors at '+width);
      await context.close();
    }
    const context=await browser.newContext({viewport:{width:1920,height:1080}});
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',async route=>{
      const p=new URL(route.request().url()).pathname;
      if(p==='/auth.js')return route.fulfill({contentType:'text/javascript',body:'window.P2000Auth={ready:Promise.resolve({local:true})};'});
      const file=path.join(root,'frontend',p.slice(1));
      if(!file.startsWith(path.join(root,'frontend')+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
      return route.fulfill({contentType:{'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.extname(file)]||'application/json',body:fs.readFileSync(file)});
    });
    await page.goto('http://127.0.0.1/studio-preview.html');
    await page.waitForFunction(()=>!!window.P2000SpeechPreview);
    await page.evaluate(({message,settings})=>{
      window.__visualMessage=message;window.__visualSettings=settings;
      window.eval('Object.assign(state.settings,window.__visualSettings);state.activeMessage=window.__visualMessage;state.activeMessages=[window.__visualMessage];state.activeUntil=Date.now()+60000;resizeCanvas();drawActiveSolid(1920,1080);');
    },{message,settings});
    await page.screenshot({path:path.join(output,'tv-1920.png')});
    const phrase=await page.evaluate(({message,config,settings})=>window.P2000SpeechPreview.format(message,{revision:1,config},settings),{message,config,settings});
    assert.match(phrase,/Tilburg/);assert.deepEqual(errors,[]);
    await context.close();
    console.log('Browser checks passed: 390/768/1440 px navigation, no page overflow, no uncaught errors, real TV canvas and speech formatter.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
