// Run only against a dedicated headless Chrome on port 9456. Leaves other browser sessions untouched.
const fs=require('node:fs');
const root=require('node:path').resolve(__dirname,'..'),entry=process.argv[3];
if(!entry?.startsWith('file:'))throw Error('Pass the offline harness file URL as argument 3');
(async()=>{
 const info=await fetch('http://127.0.0.1:9456/json/version').then(r=>r.json());
 const ws=new WebSocket(info.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));
 ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.method==='Runtime.exceptionThrown')console.error(JSON.stringify(x.params));});const pending=new Map();let seq=0;ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(pending.has(x.id)){const p=pending.get(x.id);pending.delete(x.id);x.error?p.reject(new Error(JSON.stringify(x.error))):p.resolve(x.result);}});
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,sessionId}));});
 const mode=process.argv[2]||'audit';
 const {targetId}=await send('Target.createTarget',{url:entry+(mode==='home'?'#home':''),background:true});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});const call=(m,p={})=>send(m,p,sessionId);
 const network=[];ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.sessionId===sessionId&&x.method==='Network.requestWillBeSent')network.push(x.params.request.url);});
 await call('Network.enable');
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 const until=async expression=>{for(let i=0;i<150;i++){if(await ev(`Boolean(${expression})`))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timeout '+expression);};
 const click=async label=>{if(!await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b||b.disabled)return false;b.click();return true})()`))throw Error('Button unavailable '+label);};
 const key=async(key,code,n)=>{await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:n,...(key.length===1?{text:key}:{})});await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:n});};
 const out=root+'/docs/referral-review/evidence/MT-16';fs.mkdirSync(out,{recursive:true});
 await until(mode==='home'?`document.querySelector('.portfolio-hero')`:`document.querySelectorAll('.rr-source-excerpt mark').length===2`);
 const screenshots=[];
 for(const [name,width,height] of [['desktop',1440,900],['tablet',1024,768],['mobile',390,844]]){
  await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:name==='mobile'});
  if(mode!=='home'&&name==='mobile')await click('Evidence and decision');
  const overflow=await ev('document.documentElement.scrollWidth>innerWidth');if(overflow)throw Error('Overflow '+name);
  const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/'+mode+'-'+name+'.png',Buffer.from(shot.data,'base64'));
  if(mode!=='home'){
   const rect=await ev(`(()=>{const r=document.querySelector('.rr-review-detail').getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:Math.min(r.height,1700)}})()`);
   const detail=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{...rect,scale:1}});fs.writeFileSync(out+'/evidence-'+name+'.png',Buffer.from(detail.data,'base64'));
  }
  screenshots.push({name,width,height,overflow});
 }
 let text='';
 if(mode!=='home'){
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  for(let i=0;i<2;i++){
   await ev(`document.querySelectorAll('.rr-findings button')[${i}].click()`);
   await until(`document.querySelector('#review-action')&&!document.querySelector('#review-action').disabled`);
   await ev(`document.querySelector('#review-action').focus()`);await key('k','KeyK',75);
   await until(`document.querySelector('#review-action').value==='defer'`);
   await ev(`document.querySelector('#review-reason').focus()`);await call('Input.insertText',{text:'Verify with the referring team.'});
   await click('Save decision');await until(`document.body.innerText.includes('Saved decision: unresolved')&&!document.querySelector('#review-action').disabled`);
  }
  await click('Confirm reviewed handoff');await click('Create confirmed snapshot');await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
  await click('Copy text');await until(`document.body.innerText.includes('Confirmed text copied.')||document.body.innerText.includes('Copy is unavailable.')`);
  await click('Download text');text=await ev(`window.__qaDownloads[0].text()`);if(!text.includes('Identity unresolved'))throw Error('Lost identity warning');fs.writeFileSync(out+'/confirmed.txt',text);
  // Inspect print document without opening an OS dialog.
  await ev(`window.__qaPrint=[];window.print=()=>{};const append=document.body.appendChild.bind(document.body);document.body.appendChild=function(el){if(el.tagName==='IFRAME'){window.__qaPrint.push(el.srcdoc);el.onload=()=>{};}return append(el);};`);
  await click('Print / Save PDF');if(!await ev(`window.__qaPrint[0].includes('Identity unresolved')`))throw Error('Print warning missing');
  await click('Reset demo');await until(`document.body.innerText.includes('2 open items')`);
  await click('02 / Missing claimed report');await until(`document.body.innerText.includes('1 open items')`);
  await click('Load prepared revision');await until(`document.body.innerText.includes('Historical source version. Review decisions')`);
  if(!await ev(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirm reviewed handoff').disabled`))throw Error('Stale confirm enabled');
  await click('Load prepared result');await until(`document.body.innerText.includes('No findings in this saved result')`);
  await click('Confirm reviewed handoff');await click('Create confirmed snapshot');await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
  await click('03 / Complete referral');await until(`document.body.innerText.includes('No findings in this saved result')`);
  await click('Confirm reviewed handoff');await click('Create confirmed snapshot');await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
  await call('Page.reload');await until(`document.body.innerText.includes('2 open items')`);
 }
 const audit=await ev(`({url:location.href,calls:window.__qaCalls,localEntries:localStorage.length,sessionEntries:sessionStorage.length})`);
 if(audit.calls.length||audit.localEntries||audit.sessionEntries||network.some(x=>/^https?:/.test(x)))throw Error('Unexpected network/storage');
 fs.writeFileSync(out+'/'+mode+'-audit.json',JSON.stringify({...audit,screenshots,network,identityExportWarning:text.includes('Identity unresolved')},null,2));
 console.log(JSON.stringify({...audit,screenshots,network}));await send('Target.closeTarget',{targetId});ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
