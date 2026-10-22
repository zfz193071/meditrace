// Build an OFFLINE synthetic UI harness. No application service or model request.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const front = path.join(root, 'src/frontend');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'meditrace-mt15-qa-'));
const w = require(path.join(front, 'node_modules/next/dist/compiled/webpack/webpack'));
const entry = `
import React from 'react';
import { createRoot } from 'react-dom/client';
import Workspace from ${JSON.stringify(path.join(front,'components/referral/Workspace'))};
import {packet, caps, session, membership} from ${JSON.stringify(path.join(front,'test-support/workspace'))};
import {reviewRun, reviewState, pageOne, pageTwo, snapshot, handoffView, otherDid} from ${JSON.stringify(path.join(front,'test-support/review'))};
const data = structuredClone(packet), state=structuredClone(reviewState), run=structuredClone(reviewRun);
data.current_document_ids=state.revision.documents.map(d=>d.id);
data.draft.selected_document_ids=data.current_document_ids;
data.documents=[data.documents[0], {...data.documents[0],id:otherDid,filename:'Synthetic intake note.txt'}];
const history=[];
window.__qaCalls=[];
window.__qaHistorical=()=>{data.current_revision=2;data.draft.base_revision=2;state.stale=true;state.revision.is_current=false;run.stale=true;};
window.fetch=async(url,init={})=>{
 const method=init.method||'GET';window.__qaCalls.push(method+' '+url);
 if(url.includes('/execute')||(method==='POST'&&url.endsWith('/runs')))throw new Error('Generation forbidden');
 let value;
 if(url.endsWith('/auth/session'))value=session;
 else if(url.endsWith('/capabilities'))value=caps;
 else if(url.endsWith('/membership'))value=membership;
 else if(url.endsWith('/runs/latest')||url.endsWith('/runs/'+run.id))value=run;
 else if(url.endsWith('/review'))value=state;
 else if(url.endsWith('/review-history'))value={items:history,next_cursor:null};
 else if(url.includes('/pages/1'))value=url.includes(otherDid)?pageTwo:pageOne;
 else if(url.endsWith('/handoff-draft'))value={draft:null,stale:false};
 else if(url.endsWith('/handoff'))value={...handoffView,historical:state.stale,review_version:data.review_version};
 else if(url.endsWith('/confirm')){
  const input=JSON.parse(init.body);if(state.decisions.length!==2)throw new Error('Open findings');
  data.review_version++;state.review_version=data.review_version;
  value={...snapshot,review_version:data.review_version};history.unshift({id:snapshot.id,packet_id:data.id,revision_id:run.revision_id,run_id:run.id,actor_id:session.user.id,review_version:data.review_version,kind:'confirmation',created_at:new Date().toISOString(),content:{snapshot_id:snapshot.id}});
 }
 else if(url.endsWith('/resolutions')){
  const input=JSON.parse(init.body),fid=url.split('/').at(-2);
  if(window.__qaConflict){window.__qaConflict=false;state.review_version++;data.review_version=state.review_version;return new Response(JSON.stringify({error:{code:'REVIEW_CONFLICT'}}),{status:409});}
  state.review_version++;data.review_version=state.review_version;
  const decision={...input,finding_id:fid,status:{resolve:'resolved',defer:'unresolved',dismiss:'dismissed',reopen:'open'}[input.action],review_version:state.review_version};
  state.decisions=state.decisions.filter(d=>d.finding_id!==fid).concat(decision);
  value={id:crypto.randomUUID(),packet_id:data.id,revision_id:run.revision_id,run_id:run.id,actor_id:session.user.id,review_version:state.review_version,kind:'resolution',created_at:new Date().toISOString(),content:decision};history.unshift(value);
 }
 else if(url.includes('/revisions/'))value={...state.revision,revision_number:data.current_revision,is_current:true,id:state.stale?'ffffffff-ffff-4fff-8fff-ffffffffffff':state.revision.id};
 else if(url.endsWith('/packets/'+data.id))value=data;
 else throw new Error('Unexpected offline QA route');
 return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
};
createRoot(document.getElementById('root')).render(<Workspace packetId={data.id}/>);
`;
fs.writeFileSync(path.join(out,'entry.tsx'),entry);
fs.writeFileSync(path.join(out,'loader.cjs'), `const ts=require(${JSON.stringify(path.join(front,'node_modules/typescript'))}); module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;};`);
w.webpack({mode:'production',entry:path.join(out,'entry.tsx'),output:{path:out,filename:'workspace-qa.js'},
 resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(front,'node_modules'),'node_modules']},
 module:{rules:[{test:/\.tsx?$/,exclude:/node_modules/,use:path.join(out,'loader.cjs')}]},optimization:{minimize:false}},(error,stats)=>{
 if(error || stats.hasErrors()){console.error(error || stats.toString({all:false,errors:true}));process.exitCode=1;return;}
 const css=fs.readFileSync(path.join(front,'app/workspace/workspace.css'),'utf8');
 fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MT-15 offline UI QA</title><style>body{margin:0;font-family:Arial,sans-serif}*{box-sizing:border-box}${css}</style><body><aside style="padding:8px;text-align:center;background:#18323d;color:white">Offline synthetic UI QA - no backend or model calls</aside><div id="root"></div><script src="./workspace-qa.js"></script></body></html>`);
 console.log(path.join(out,'index.html'));
});
