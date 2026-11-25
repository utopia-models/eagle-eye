// knowledge#17946: replay test. The diagram is drawn from the pipelines feed; add/rename a stage in the feed and the HTML
// follows with no edit to lane.html. Run: node test_arch_replay.mjs  (reads ../../../../wi/registry/pipelines.yaml via the feed json)
import fs from 'node:fs'; import vm from 'node:vm'; import path from 'node:path'; import {fileURLToPath} from 'node:url';
const d = path.dirname(fileURLToPath(import.meta.url));
const src = fs.readFileSync(path.join(d,'lane.html'),'utf8');
const blk = src.slice(src.indexOf('// ARCH-RENDER-BEGIN'), src.indexOf('// ARCH-RENDER-END'));
if(!blk) throw new Error('arch block missing');
const ctx = {}; vm.createContext(ctx);
vm.runInContext("const esc = s => String(s==null?'':s).replace(/[&<>\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));"+blk+";this.archHtml=archHtml;", ctx);
const feed = JSON.parse(fs.readFileSync(path.join(d,'../../../../_infra/occ-feeds/pipelines.json'),'utf8'));
let n = 0; const ok = (c,m)=>{ if(!c){ console.error('FAIL',m); process.exit(1);} n++; };
const html = ctx.archHtml(feed, null, '');
for(const pl of feed.pipelines) for(const s of pl.stages) ok(html.includes('data-stage="'+s.stage+'"'), 'stage drawn: '+s.stage);
const f2 = JSON.parse(JSON.stringify(feed)); f2.pipelines[0].stages.push({stage:'ZZ New Stage',tool:'t',owner:'o',machine:'m',handoff:'h'}); f2.pipelines[0].stages[0].stage='Renamed Hunt';
const h2 = ctx.archHtml(f2, null, '');
ok(h2.includes('data-stage="ZZ New Stage"') && h2.includes('data-stage="Renamed Hunt"') && !h2.includes('data-stage="Hunt"'), 'added + renamed stage shows with no code edit');
const up = {applied:[{pipeline:{noVsl:true,stages:[{stage:'SENT',done:true}]}},{pipeline:{stages:[{stage:'SENT',done:true}]}}]};
const h3 = ctx.archHtml({pipelines:[{id:'upwork',title:'U',stages:[{stage:'Sent',tool:'',owner:'',machine:'',handoff:''}]}]}, up, '');
ok(h3.includes('live · 2 jobs') && h3.includes('STUCK 1'), 'live count and stuck marker');
ok(ctx.archHtml(null,null,'').includes('No pipelines feed'), 'honest empty state');
console.log('ok', n, 'assertions');
