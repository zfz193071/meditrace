// Node 22. Run against a dedicated headless Chrome; never activates a window.
// Usage: node scripts/portfolio_browser_qa.cjs <exported-site> [DevTools port]
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const site = fs.realpathSync(process.argv[2]);
const port = Number(process.argv[3] || 9468);
const origin = 'https://meditrace-portfolio.test';
const output = path.join(site, '..', 'browser-qa');
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.txt': 'text/x-component', '.woff2': 'font/woff2' };

(async () => {
  assert(fs.existsSync(path.join(site, 'demo/index.html')), 'Pass the static portfolio site directory');
  fs.mkdirSync(output, { recursive: true });
  const info = await fetch(`http://127.0.0.1:${port}/json/version`).then(r => r.json());
  const ws = new WebSocket(info.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
  const pending = new Map(); let seq = 0;
  const errors = [], requests = [], checkpoints = [];
  let sessionId, targetId;
  const send = (method, params = {}, session) => new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); }, 30000);
    pending.set(id, { resolve, reject, timer });
    ws.send(JSON.stringify({ id, method, params, sessionId: session }));
  });
  const call = (method, params) => send(method, params, sessionId);
  ws.addEventListener('message', async event => {
    const message = JSON.parse(event.data), task = pending.get(message.id);
    if (task) {
      clearTimeout(task.timer); pending.delete(message.id);
      message.error ? task.reject(Error(JSON.stringify(message.error))) : task.resolve(message.result);
    }
    if (!sessionId || message.sessionId !== sessionId) return;
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
    if (message.method !== 'Fetch.requestPaused') return;
    const { requestId, request } = message.params;
    try {
      const url = new URL(request.url);
      requests.push({ method: request.method, path: url.pathname });
      assert.equal(url.origin, origin, `External request: ${url.origin}`);
      assert.equal(request.method, 'GET', 'Unexpected write request');
      assert(!/^\/(api|workspace|account|login)(\/|$)/.test(url.pathname), 'Unexpected private request');
      let file = path.resolve(site, '.' + decodeURIComponent(url.pathname));
      assert(file === site || file.startsWith(site + path.sep), 'Path outside artifact');
      if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
      if (url.pathname === '/favicon.ico' && !fs.existsSync(file)) {
        await call('Fetch.fulfillRequest', { requestId, responseCode: 204 }); return;
      }
      assert(fs.existsSync(file), `Missing static resource: ${url.pathname}`);
      await call('Fetch.fulfillRequest', { requestId, responseCode: 200,
        responseHeaders: [{ name: 'Content-Type', value: mime[path.extname(file)] || 'application/octet-stream' }],
        body: fs.readFileSync(file).toString('base64') });
    } catch (error) {
      errors.push(String(error));
      await call('Fetch.failRequest', { requestId, errorReason: 'BlockedByClient' }).catch(() => {});
    }
  });
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const until = async expression => {
    for (let n = 0; n < 150; n++) {
      if (await evaluate(`Boolean(${expression})`)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw Error('Timed out: ' + expression);
  };
  const key = async (key, code, keyCode) => {
    await call('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode,
      ...(key === 'Enter' ? { text: '\r', unmodifiedText: '\r' } : key.length === 1 ? { text: key, unmodifiedText: key } : {}) });
    await call('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
  };
  // Reach each control with actual Tab presses, then activate it with Enter.
  const tabTo = async expression => {
    for (let n = 0; n < 100; n++) {
      if (await evaluate(`document.activeElement === (${expression})`)) return;
      await key('Tab', 'Tab', 9);
    }
    throw Error('Control not reachable by keyboard: ' + expression);
  };
  const button = label => `[...document.querySelectorAll('button')].find(b => b.textContent.trim() === ${JSON.stringify(label)})`;
  const activate = async label => { await tabTo(button(label)); await key('Enter', 'Enter', 13); };
  const checkLayout = async (name, selector) => {
    assert.equal(await evaluate('document.documentElement.scrollWidth > innerWidth'), false, 'Horizontal overflow: ' + name);
    const clip = selector ? await evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:Math.min(r.height,1600),scale:1}})()`) : undefined;
    const screenshot = await call('Page.captureScreenshot', { format: 'png', ...(clip ? { captureBeyondViewport: true, clip } : {}) });
    fs.writeFileSync(path.join(output, name + '.png'), Buffer.from(screenshot.data, 'base64'));
    checkpoints.push(name);
    console.log('Checked ' + name);
  };
  try {
    ({ targetId } = await send('Target.createTarget', { url: 'about:blank', background: true }));
    ({ sessionId } = await send('Target.attachToTarget', { targetId, flatten: true }));
    await call('Runtime.enable'); await call('Page.enable');
    // All page HTTP(S) requests are fulfilled locally or rejected, never continued.
    await call('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
    await send('Browser.setDownloadBehavior', { behavior: 'deny' });
    await call('Page.addScriptToEvaluateOnNewDocument', { source: `
      window.__qaDownloads=[];window.__qaPrint=[];
      const create=URL.createObjectURL.bind(URL);URL.createObjectURL=blob=>{window.__qaDownloads.push(blob);return create(blob)};
      document.addEventListener('DOMContentLoaded',()=>{
        const original=document.body.appendChild.bind(document.body);
        document.body.appendChild=element=>{if(element.tagName==='IFRAME'){window.__qaPrint.push(element.srcdoc);return element}return original(element)};
      });
    ` });
    for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 1024, 768], ['mobile', 390, 844]]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
      await call('Page.navigate', { url: origin + '/demo/' });
      await until(`document.querySelectorAll('.rr-source-excerpt mark').length===2`);
      assert.equal(await evaluate('location.pathname'), '/demo/');
      await checkLayout(name + '-items');
      if (name === 'mobile') {
        await activate('Evidence and decision');
        await until(`getComputedStyle(document.querySelector('.rr-review-detail')).display!=='none'`);
        await checkLayout('mobile-evidence', '.rr-review-detail');
        for (let index = 0; index < 2; index++) {
          await activate('Items');
          await tabTo(`document.querySelectorAll('.rr-findings button')[${index}]`);
          await key('Enter', 'Enter', 13);
          await until(`document.activeElement===document.querySelector('.rr-review-detail')`);
          await tabTo(`document.querySelector('#review-action')`);
          await key('k', 'KeyK', 75);
          await until(`document.querySelector('#review-action').value==='defer'`);
          await tabTo(`document.querySelector('#review-reason')`);
          await call('Input.insertText', { text: 'Verify with the referring team.' });
          await activate('Save decision');
          await until(`document.body.innerText.includes('Saved decision: unresolved')&&!document.querySelector('#review-action').disabled`);
        }
        await activate('Confirm reviewed handoff'); await activate('Create confirmed snapshot');
        await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
        await activate('Copy text');
        await until(`document.body.innerText.includes('Confirmed text copied.')||document.body.innerText.includes('Copy is unavailable.')`);
        await activate('Download text');
        const text = await evaluate('window.__qaDownloads[0].text()');
        assert(text.includes('Identity unresolved'));
        fs.writeFileSync(path.join(output, 'confirmed.txt'), text);
        await activate('Print / Save PDF');
        assert(await evaluate(`window.__qaPrint[0].includes('Identity unresolved')`));
        await checkLayout('mobile-confirmed', 'article[aria-label="Confirmed handoff"]');
        await activate('Reset demo'); await until(`document.body.innerText.includes('2 open items')`);
        await activate('02 / Missing claimed report'); await until(`document.body.innerText.includes('1 open items')`);
        await activate('Load prepared revision'); await until(`document.body.innerText.includes('Historical source version. Review decisions')`);
        assert(await evaluate(`${button('Confirm reviewed handoff')}.disabled`));
        await activate('Load prepared result');
        await until(`${button('Prepared result loaded')}`);
        await activate('Evidence and decision'); await until(`document.body.innerText.includes('No findings in this saved result')`);
        await activate('Confirm reviewed handoff'); await activate('Create confirmed snapshot');
        await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
        await activate('03 / Complete referral');
        await until(`document.body.innerText.includes('03 / Complete referral')&&!document.body.innerText.includes('Prepared attachment recovery')`);
        await activate('Evidence and decision'); await until(`document.body.innerText.includes('No findings in this saved result')`);
        await activate('Confirm reviewed handoff'); await activate('Create confirmed snapshot');
        await until(`document.querySelector('article[aria-label="Confirmed handoff"]')`);
        await call('Page.reload'); await until(`document.body.innerText.includes('2 open items')`);
        assert.equal(await evaluate('localStorage.length+sessionStorage.length'), 0);
      }
    }
    for (const route of ['/', '/project/', '/evaluation/']) {
      await call('Page.navigate', { url: origin + route });
      await until(`document.querySelector('h1')`);
      await checkLayout('mobile-' + (route.split('/')[1] || 'home'));
      assert.equal(await evaluate(`!!document.querySelector('a[href^="/workspace"]')`), false);
    }
    await call('Page.navigate', { url: origin + '/' });
    await until(`document.querySelector('.portfolio-hero')`);
    await tabTo(`document.querySelector('a[href^="/demo"]')`);
    await key('Enter', 'Enter', 13);
    await until(`location.pathname==='/demo/'&&document.querySelectorAll('.rr-source-excerpt mark').length===2`);
    await tabTo(`document.querySelector('a[href^="/project"]')`);
    await key('Enter', 'Enter', 13);
    await until(`location.pathname==='/project/'&&document.querySelector('h1')`);
    checkpoints.push('keyboard-client-navigation');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'audit.json'), JSON.stringify({
      artifact: path.basename(path.dirname(site)), browser: info.Browser,
      checkedAt: new Date().toISOString(), checkpoints, requests, errors,
      keyboard: 'Tab/Enter, select typeahead and text input; all three cases, confirmation, copy/download/print/reset',
      transport: 'Static artifact fulfilled by CDP; every unexpected request blocked',
      limits: 'Not public HTTPS acceptance; print HTML inspected without an OS print dialog; downloads inspected as Blob text',
    }, null, 2) + '\n');
    console.log('Passed static portfolio browser acceptance: ' + output);
  } catch (error) {
    const state = await evaluate(`({url:location.href,active:document.activeElement?.outerHTML.slice(0,1000),panels:document.querySelector('.rr-review-grid')?.className,text:document.body.innerText})`).catch(() => null);
    fs.writeFileSync(path.join(output, 'failure.json'), JSON.stringify({ error: String(error), errors, requests, state }, null, 2));
    throw error;
  } finally {
    if (targetId) await send('Target.closeTarget', { targetId }).catch(() => {});
    for (const task of pending.values()) clearTimeout(task.timer);
    ws.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
