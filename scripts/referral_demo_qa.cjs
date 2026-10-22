// Offline component/browser harness. No Next/FastAPI service and no model calls.
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const root = path.resolve(__dirname, '..'), front = path.join(root, 'src/frontend');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'meditrace-mt16-qa-'));
const w = require(path.join(front, 'node_modules/next/dist/compiled/webpack/webpack'));
fs.writeFileSync(path.join(out, 'entry.tsx'), `
import React from 'react'; import {createRoot} from 'react-dom/client';
import {DemoWorkspace} from ${JSON.stringify(path.join(front, 'components/referral/DemoWorkspace'))};
import Home from ${JSON.stringify(path.join(front, 'app/page'))};
window.__qaCalls=[];window.fetch=async (...args)=>{window.__qaCalls.push(String(args[0]));throw Error('Demo must not fetch');};
window.__qaDownloads=[];const original=URL.createObjectURL;URL.createObjectURL=function(blob){window.__qaDownloads.push(blob);return original.call(this,blob);};
createRoot(document.getElementById('root')).render(location.hash==='#home'?<Home/>:<main className="rr-workspace"><DemoWorkspace/></main>);
`);
fs.writeFileSync(path.join(out, 'loader.cjs'), `const ts=require(${JSON.stringify(path.join(front, 'node_modules/typescript'))});module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;};`);
fs.writeFileSync(path.join(out,'css.cjs'), 'module.exports=function(){return "";};');
w.webpack({mode:'production',entry:path.join(out,'entry.tsx'),output:{path:out,filename:'demo-qa.js'},resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(front,'node_modules'),'node_modules']},module:{rules:[{test:/\.tsx?$/,exclude:/node_modules/,use:path.join(out,'loader.cjs')},{test:/\.css$/,use:path.join(out,'css.cjs')}]},optimization:{minimize:false}},(error,stats)=>{
 if(error||stats.hasErrors()){console.error(error||stats.toString({all:false,errors:true}));process.exitCode=1;return;}
 const css=['app/workspace/workspace.css','app/portfolio.css'].map(p=>fs.readFileSync(path.join(front,p),'utf8')).join('\n');
 fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MT-16 offline component QA</title><style>body{margin:0;font-family:Arial,sans-serif}*{box-sizing:border-box}h1,h2,h3,p{margin:0}${css}</style><body><div id="root"></div><script>window.process={env:{NODE_ENV:"production"}}</script><script src="./demo-qa.js"></script></body></html>`);
 console.log(path.join(out,'index.html'));
});
