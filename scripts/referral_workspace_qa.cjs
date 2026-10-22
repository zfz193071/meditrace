// Build an OFFLINE synthetic UI harness. No application service or model request.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const front = path.join(root, 'src/frontend');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'meditrace-mt14-qa-'));
const w = require(path.join(front, 'node_modules/next/dist/compiled/webpack/webpack'));
const entry = `
import React from 'react';
import { createRoot } from 'react-dom/client';
import Workspace from ${JSON.stringify(path.join(front,'components/referral/Workspace'))};
import {packet, revision, caps, session, membership, unknownRun} from ${JSON.stringify(path.join(front,'test-support/workspace'))};
const data = structuredClone(packet);
window.__qaCalls = [];
window.fetch = async (url, init = {}) => {
 const method = init.method || 'GET';
 window.__qaCalls.push(method + ' ' + url);
 if (url.includes('/execute') || (method === 'POST' && url.endsWith('/runs'))) throw new Error('Generation is forbidden in UI QA');
 let value;
 if (url.endsWith('/auth/session')) value=session;
 else if(url.endsWith('/capabilities')) value=caps;
 else if(url.endsWith('/membership')) value=membership;
 else if(url.endsWith('/runs/latest')) value=unknownRun;
 else if(url.endsWith('/review-history')) value={items:[],next_cursor:null};
 else if(url.endsWith('/handoff-draft')) value={draft:null,stale:false};
 else if(url.endsWith('/revisions/1')) value=revision;
 else if(url.endsWith('/draft') && method==='PUT') { const input=JSON.parse(init.body); data.draft={...data.draft,...input,draft_version:data.draft.draft_version+1}; value=data.draft; }
 else if(url.endsWith('/documents') && method==='POST') value=data.documents[0];
 else if(url.endsWith('/packets/'+data.id)) value=data;
 else if(url.endsWith('/packets')) value={items:[data],next_cursor:null};
 else throw new Error('Unexpected offline QA route');
 return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
};
createRoot(document.getElementById('root')).render(<Workspace packetId={location.hash === '#list' ? undefined : data.id}/>);
`;
fs.writeFileSync(path.join(out,'entry.tsx'),entry);
fs.writeFileSync(path.join(out,'loader.cjs'), `const ts=require(${JSON.stringify(path.join(front,'node_modules/typescript'))}); module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;};`);
w.webpack({mode:'production',entry:path.join(out,'entry.tsx'),output:{path:out,filename:'workspace-qa.js'},
 resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(front,'node_modules'),'node_modules']},
 module:{rules:[{test:/\.tsx?$/,exclude:/node_modules/,use:path.join(out,'loader.cjs')}]},optimization:{minimize:false}},(error,stats)=>{
 if(error || stats.hasErrors()){console.error(error || stats.toString({all:false,errors:true}));process.exitCode=1;return;}
 const css=fs.readFileSync(path.join(front,'app/workspace/workspace.css'),'utf8');
 fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MT-14 offline UI QA</title><style>body{margin:0;font-family:Arial,sans-serif}*{box-sizing:border-box}${css}</style><body><aside style="padding:8px;text-align:center;background:#18323d;color:white">Offline synthetic UI QA - no backend or model calls</aside><div id="root"></div><script src="./workspace-qa.js"></script></body></html>`);
 console.log(path.join(out,'index.html'));
});
