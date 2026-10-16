const {get,connect,sleep}=require('./cdp');
(async()=>{const v=await get('http://localhost:9222/json/version');const b=await connect(v.webSocketDebuggerUrl);
const r=await b.send('Target.getTargets');console.log(r.result.targetInfos.filter(t=>/extension/.test(t.url)).map(t=>t.type+' '+t.url));
const l=await b.send('Extensions.loadUnpacked',{path:'/tmp/e2e/ext'});console.log(JSON.stringify(l));process.exit(0)})();
