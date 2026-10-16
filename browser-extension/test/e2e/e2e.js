const fs=require('fs');const {get,connect,sleep}=require('./cdp');
const EXT='amdjccohichaelneokgaaeahahfdnepi';
(async()=>{
 const v=await get('http://localhost:9222/json/version');const br=await connect(v.webSocketDebuggerUrl);
 let t=(await br.send('Target.getTargets')).result.targetInfos.find(x=>x.type==='service_worker'&&x.url.includes(EXT));
 if(!t){console.log('SW not running, waking via options page');const o=await br.send('Target.createTarget',{url:`chrome-extension://${EXT}/options.html`});await sleep(1500);t=(await br.send('Target.getTargets')).result.targetInfos.find(x=>x.type==='service_worker'&&x.url.includes(EXT));}
 console.log('SW target',!!t);
 const a=await br.send('Target.attachToTarget',{targetId:t.targetId,flatten:true});
 const sid=a.result.sessionId;
 const sw={ev:async(expr)=>{const r=await br.send('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true,sessionId:sid});if(r.error)throw new Error(JSON.stringify(r.error));if(r.result.exceptionDetails)throw new Error(JSON.stringify(r.result.exceptionDetails));return r.result.result.value}};
 // raw send with session: patch connect's send
 br.send=((orig)=>(m,p={})=>m==='Runtime.evaluate'&&p.sessionId?orig(m,p):orig(m,p))(br.send);
 console.log('libs loaded:',await sw.ev("typeof Detect+','+typeof Client+','+typeof sendItem"));
 console.log('detecting listener:',await sw.ev("syncListener()"));
 const code=fs.readFileSync('code.txt','utf8');
 console.log('pair:',await sw.ev(`Client.pair(fetch,17653,'${code}').then(async r=>{if(r.ok)await api.storage.local.set({token:r.data.token});return JSON.stringify({ok:r.ok,err:r.error})})`));
 // open demo page
 const pg=await br.send('Target.createTarget',{url:'http://127.0.0.1:8099/'});await sleep(3500);
 const media=await sw.ev("api.storage.session.get(null).then(x=>JSON.stringify(Object.fromEntries(Object.entries(x).map(([k,v])=>[k,v.map(i=>i.kind+' '+i.url.replace('http://127.0.0.1:8099','')+' '+i.size)]))))");
 console.log('detected:',media);
 const tabs=JSON.parse(await sw.ev("api.tabs.query({url:'http://127.0.0.1:8099/*'}).then(t=>JSON.stringify(t.map(x=>({id:x.id,url:x.url,title:x.title}))))"));
 console.log('tab',tabs[0]);
 console.log('badge:',await sw.ev(`api.action.getBadgeText({tabId:${tabs[0].id}})`));
 // popup page with patched tabs.query
 const pt=await br.send('Target.createTarget',{url:'about:blank'});
 const pa=await br.send('Target.attachToTarget',{targetId:pt.result.targetId,flatten:true});const ps=pa.result.sessionId;
 const P=(m,p={})=>br.send(m,Object.assign({sessionId:ps},p));
 await P('Page.enable');
 await P('Emulation.setDeviceMetricsOverride',{width:380,height:480,deviceScaleFactor:2,mobile:false});
 await P('Page.addScriptToEvaluateOnNewDocument',{source:`(()=>{const q=chrome.tabs.query.bind(chrome.tabs);chrome.tabs.query=async(o)=>o&&o.active?[${JSON.stringify(tabs[0])}]:q(o)})()`});
 await P('Page.navigate',{url:`chrome-extension://${EXT}/popup.html`});await sleep(2500);
 const pev=async(e)=>(await P('Runtime.evaluate',{expression:e,awaitPromise:true,returnByValue:true})).result.result.value;
 console.log('popup rows:',await pev("[...document.querySelectorAll('.item')].map(i=>i.querySelector('.pill').textContent+' | '+i.querySelector('.name').textContent).join('\\n')"));
 console.log('status:',await pev("document.getElementById('status').textContent"));
 let shot=await P('Page.captureScreenshot',{format:'png'});fs.writeFileSync('popup-before.png',Buffer.from(shot.result.data,'base64'));
 await pev("document.querySelectorAll('.item button')[1].click()");await sleep(1500);
 await pev("document.querySelectorAll('.item button')[0].click()");await sleep(1500);
 console.log('notice:',await pev("document.getElementById('notice').textContent"));
 shot=await P('Page.captureScreenshot',{format:'png'});fs.writeFileSync('popup-after.png',Buffer.from(shot.result.data,'base64'));
 console.log('context-menu code path:',await sw.ev("sendItem({url:'http://127.0.0.1:8099/clip.mp4',pageUrl:'http://127.0.0.1:8099/',title:'ctx',kind:'link'}).then(r=>JSON.stringify(r))"));
 console.log('file: url:',await sw.ev("sendItem({url:'file:///etc/passwd',pageUrl:'',title:'',kind:'link'}).then(r=>JSON.stringify(r))"));
 process.exit(0);
})().catch(e=>{console.error('ERR',e);process.exit(1)});
