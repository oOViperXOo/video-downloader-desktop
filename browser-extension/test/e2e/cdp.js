const http=require('http');
const get=(u)=>new Promise((res,rej)=>http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)))}).on('error',rej));
async function connect(wsUrl){const ws=new WebSocket(wsUrl);await new Promise(r=>ws.onopen=r);let id=0;const p={};
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&p[m.id]){p[m.id](m);delete p[m.id]}};
 const send=(method,params={})=>new Promise(r=>{const i=++id;p[i]=r;const sessionId=params.sessionId;if(sessionId){params=Object.assign({},params);delete params.sessionId}ws.send(JSON.stringify({id:i,method,params,sessionId}))});
 const ev=async(expr)=>{const r=await send('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true});if(r.result.exceptionDetails)throw new Error(JSON.stringify(r.result.exceptionDetails));return r.result.result.value};
 return {send,ev,ws};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
module.exports={get,connect,sleep};
