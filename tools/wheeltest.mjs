// Wheel-zoom regression test: drives headless Edge/Chrome over CDP, plays wheel patterns
// (mouse notches, smooth scrolling, trackpad, free-spin) at the map and counts zoom steps.
// Usage: serve the repo on :8765, then  node tools/wheeltest.mjs   (BROWSER=path, URL=page)
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const EDGE = process.env.BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.env.URL || 'http://localhost:8765/#debug';
const port = 9333;
const prof = mkdtempSync(join(tmpdir(), 'vkwheel-'));
const edge = spawn(EDGE, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, '--window-size=1300,800', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(200); } }
const page = targets.find(t => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const waits = new Map();
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && waits.has(d.id)) { waits.get(d.id)(d); waits.delete(d.id); } };
const cdp = (method, params = {}) => new Promise(r => { const i = ++id; const to = setTimeout(() => { console.log("TIMEOUT", method, JSON.stringify(params).slice(0,80)); r({result:{result:{}}}); }, 4000); waits.set(i, d => { clearTimeout(to); r(d); }); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async expr => (await cdp('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.result.value;

await cdp('Page.enable');
await cdp('Page.navigate', { url: URL });
await sleep(2500);

const X = 800, Y = 400;
const wheel = dy => cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: X, y: Y, deltaX: 0, deltaY: dy });
async function run(name, events, expect) {
  await ev(`__vk.map.setView([56.1,10.1], 10, {animate:false}); __vkLog.length = 0; 0`);
  await sleep(300);
  const z0 = await ev('__vk.map.getZoom()');
  const t0 = performance.now();
  // dispatch inside the page for exact timing (CDP input adds ~50 ms per event)
  await ev(`new Promise(res => { const c = __vk.map.getContainer(), r = c.getBoundingClientRect(); const evs = ${JSON.stringify(events)};
    const t0 = performance.now(); let i = 0;
    (function tick(){ const now = performance.now() - t0;
      while (i < evs.length && evs[i][0] <= now){ c.dispatchEvent(new WheelEvent('wheel', { deltaY: evs[i][1], deltaMode: 0, clientX: r.left + 400, clientY: r.top + 300, bubbles: true, cancelable: true })); i++; }
      if (i < evs.length) setTimeout(tick, 1); else res(0); })(); })`);
  await sleep(900);
  const z1 = await ev('__vk.map.getZoom()');
  const log = await ev('__vkLog.join("\\n")');
  const got = z0 - z1; // scrolling down (+dy) zooms out
  const ok = Array.isArray(expect) ? got >= expect[0] && got <= expect[1] : got === expect;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(46)} steps=${got} expected=${expect}`);
  if (!ok || process.env.V) console.log(log.split('\n').map(l => '      ' + l).join('\n'));
  return ok;
}
// smooth train: one notch of `total` px spread over `ms` with ease-out, `n` events
const train = (start, total, ms, n) => { const out = []; let prev = 0; for (let k = 1; k <= n; k++) { const f = 1 - (1 - k / n) ** 3; const v = total * f; out.push([start + ms * k / n, +(v - prev).toFixed(2)]); prev = v; } return out; };
const notches = (n, gap, dy = 100) => Array.from({ length: n }, (_, k) => [k * gap, dy]);

const results = [];
results.push(await run('1 notch (100px)', notches(1, 0), 1));
results.push(await run('5 slow notches, 400ms apart', notches(5, 400), 5));
results.push(await run('5 notches, 150ms apart', notches(5, 150), 5));
results.push(await run('5 fast notches, 60ms apart (spin)', notches(5, 60), 5));
results.push(await run('1 notch sent as 2 events (driver double)', [[0, 100], [8, 100]], 1));
results.push(await run('1 notch 120px (Windows WHEEL_DELTA)', notches(1, 0, 120), 1));
results.push(await run('1 smooth notch: 100px over 250ms, 12 evts', train(0, 100, 250, 12), 1));
results.push(await run('1 smooth notch: 120px over 350ms, 20 evts', train(0, 120, 350, 20), 1));
results.push(await run('3 smooth notches 500ms apart', [...train(0, 100, 250, 12), ...train(500, 100, 250, 12), ...train(1000, 100, 250, 12)], 3));
results.push(await run('3 smooth notches back-to-back (150ms)', [...train(0, 100, 250, 12), ...train(150, 100, 250, 12), ...train(300, 100, 250, 12)], [2, 3]));
results.push(await run('trackpad: 40 x 3px every 16ms', Array.from({ length: 40 }, (_, k) => [k * 16, 3]), [1, 1]));
results.push(await run('free-spin momentum: 400px decaying over 900ms', train(0, 400, 900, 45), [2, 3]));
console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
ws.close(); edge.kill();
process.exit(0);
