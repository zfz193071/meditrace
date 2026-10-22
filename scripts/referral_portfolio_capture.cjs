// Run only against a dedicated headless Chrome on port 9456. Leaves other browser sessions untouched.
const fs=require('node:fs');
const root=require('node:path').resolve(__dirname,'..'),entry=process.argv[3];
if(!entry?.startsWith('file:'))throw Error('Pass the offline harness file URL as argument 3');
(async()=>{
 const info=await fetch('http://127.0.0.1:9456/json/version').then(r=>r.json());
 const ws=new WebSocket(info.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));
 ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.method==='Runtime.exceptionThrown')console.error(JSON.stringify(x.params));});const pending=new Map();let seq=0;ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(pending.has(x.id)){const p=pending.get(x.id);pending.delete(x.id);x.error?p.reject(new Error(JSON.stringify(x.error))):p.resolve(x.result);}});
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,sessionId}));});
 const mode='audit';
 const {targetId}=await send('Target.createTarget',{url:entry+(mode==='home'?'#home':''),background:true});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});const call=(m,p={})=>send(m,p,sessionId);
 const network=[];ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.sessionId===sessionId&&x.method==='Network.requestWillBeSent')network.push(x.params.request.url);});
 await call('Network.enable');
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 const until=async expression=>{for(let i=0;i<150;i++){if(await ev(`Boolean(${expression})`))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timeout '+expression);};
 const click=async label=>{if(!await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b||b.disabled)return false;b.click();return true})()`))throw Error('Button unavailable '+label);};
 const key=async(key,code,n)=>{await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:n,...(key.length===1?{text:key}:{})});await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:n});};

 const out=root+'/docs/portfolio/media';fs.mkdirSync(out,{recursive:true});
 await call('Emulation.setDeviceMetricsOverride',{width:1440,height:800,deviceScaleFactor:1,mobile:false});
 await until(`document.querySelectorAll('.rr-source-excerpt mark').length===2`);
 const shots=[];
 async function shot(name,selector){
  await ev(selector?`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`:'scrollTo(0,0)');
  await new Promise(r=>setTimeout(r,150));
  const y=selector?await ev(`Math.max(0,document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().top+scrollY-40)`):0;
  const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y,width:1440,height:800,scale:1}});fs.writeFileSync(out+'/'+name+'.png',Buffer.from(image.data,'base64'));
  shots.push({name,body:await ev('document.body.innerText')});
 }
 await shot('01-intro');await shot('02-evidence','.rr-evidence-grid');
 for(let i=0;i<2;i++){
  await ev(`document.querySelectorAll('.rr-findings button')[${i}].click()`);
  await until(`document.querySelector('#review-action')&&!document.querySelector('#review-action').disabled`);
  await ev(`document.querySelector('#review-action').focus()`);await key('k','KeyK',75);
  await until(`document.querySelector('#review-action').value==='defer'`);
  await ev(`document.querySelector('#review-reason').focus()`);await call('Input.insertText',{text:i===0?'Verify the date of birth with the referring team.':'Request the missing report from the sender.'});
  if(i===0)await shot('03-decision','fieldset');
  await click('Save decision');await until(`document.body.innerText.includes('Saved decision: unresolved')&&!document.querySelector('#review-action').disabled`);
 }
 await click('Confirm reviewed handoff');await click('Create confirmed snapshot');await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
 await shot('04-handoff','article[aria-label="Confirmed handoff"]');
 await click('Download text');const exported=await ev('window.__qaDownloads[0].text()');
 if(!exported.includes('Identity unresolved'))throw Error('Export warning missing');fs.writeFileSync(out+'/confirmed-demo.txt',exported);
 await click('02 / Missing claimed report');await until(`document.body.innerText.includes('1 open items')`);
 await click('Load prepared revision');await until(`document.body.innerText.includes('Historical source version. Review decisions')`);
 await shot('06-stale','#evidence-review');
 await click('Load prepared result');await until(`document.body.innerText.includes('No findings in this saved result')`);
 await shot('07-prepared','#evidence-review');
 await click('Confirm reviewed handoff');await click('Create confirmed snapshot');await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
 await click('Download text');const prepared=await ev('window.__qaDownloads.at(-1).text()');
 if(!prepared.includes('Source version 2'))throw Error('Prepared export revision mismatch');fs.writeFileSync(out+'/prepared-demo.txt',prepared);
 await shot('05-export','article[aria-label="Confirmed handoff"]');
 await call('Page.navigate',{url:entry+'?view=evaluation#evaluation'});await until(`document.querySelector('.eval-comparison')`);
 await shot('08-evaluation');
 const calls=await ev('window.__qaCalls');if(calls.length||network.some(url=>/^https?:/.test(url)))throw Error('Unexpected network');
 fs.writeFileSync(out+'/capture-audit.json',JSON.stringify({entry,kind:'edited still-frame rough cut from actual offline UI',model_calls:0,network,shots},null,2));
 console.log('Captured eight real UI states and confirmed text; no model calls.');
 await send('Target.closeTarget',{targetId});ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
