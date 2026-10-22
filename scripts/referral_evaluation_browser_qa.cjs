// Read-only offline page QA against a dedicated headless Chrome at port 9456.
const fs=require('node:fs'),path=require('node:path');
const entry=process.argv[2],out=path.resolve(__dirname,'../docs/referral-review/evidence/MT-20');
if(!entry?.startsWith('file:'))throw Error('Pass the generated offline harness file URL');
(async()=>{
 const info=await fetch('http://127.0.0.1:9456/json/version').then(r=>r.json());
 const ws=new WebSocket(info.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));
 let sequence=0;const pending=new Map();
 ws.addEventListener('message',e=>{const m=JSON.parse(e.data);const waiter=pending.get(m.id);if(waiter){pending.delete(m.id);m.error?waiter.reject(Error(JSON.stringify(m.error))):waiter.resolve(m.result);}});
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,sessionId}));});
 const {targetId}=await send('Target.createTarget',{url:entry+'#evaluation',background:true});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 const call=(method,params={})=>send(method,params,sessionId);
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error('Page script failed');return r.result.value;};
 let loaded=false;for(let i=0;i<100;i++){if(await evaluate('Boolean(document.querySelector(".eval-comparison"))')){loaded=true;break;}await new Promise(r=>setTimeout(r,100));}if(!loaded)throw Error('Page did not render');
 fs.mkdirSync(out,{recursive:true});const results=[];
 for(const [name,width,height] of [['desktop',1440,900],['tablet',1024,768],['mobile',390,844]]){
  await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:name==='mobile'});
  const audit=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,title:document.querySelector('h1').innerText,blocked:document.body.innerText.includes('Release evaluation is blocked'),cards:document.querySelectorAll('.eval-comparison article').length,limits:document.querySelectorAll('.eval-limitations article').length,calls:window.__qaCalls})`);
  if(audit.scrollWidth>audit.width||!audit.blocked||audit.cards!==3||audit.limits!==4||audit.calls.length)throw Error('Layout/content assertion failed');
  const screenshot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(screenshot.data,'base64'));results.push({name,...audit});
 }
 await evaluate(`document.querySelector('details').open=true`);
 if(!await evaluate(`document.querySelector('details').innerText.includes('Implementation SHA-256')`))throw Error('Version details unavailable');
 fs.writeFileSync(path.join(out,'browser-audit.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 await send('Target.closeTarget',{targetId});ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
