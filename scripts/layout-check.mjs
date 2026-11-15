// layout-check.mjs: render Eagle Eye at phone, laptop, 1080p, ultrawide, right-half and 720p in Chromium, WebKit and
// Firefox; fail if any two regions (eye, hunts, roosts, mark) overlap, leave the screen, or the page scrolls.
//   npm i -D playwright && npx playwright install chromium webkit firefox
//   node scripts/layout-check.mjs http://localhost:8000/ shots
import { createRequire } from 'module';
const require = createRequire(process.env.PLAYWRIGHT_DIR || process.cwd()+'/node_modules/');
const pw = require('playwright');
const [,, url, outdir, ...rest] = process.argv;
const sizes = [[390,844],[1440,900],[1920,1080],[3440,1440],[960,1080],[1280,720]];
const browsers = (process.env.BROWSERS||'chromium,webkit,firefox').split(',');
const fs = require('fs'); fs.mkdirSync(outdir,{recursive:true});
const results = [];
for (const b of browsers) {
  const br = await pw[b].launch();
  for (const [w,h] of sizes) {
    const ctx = await br.newContext({viewport:{width:w,height:h}, reducedMotion:'reduce'});
    const pg = await ctx.newPage();
    const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
    await pg.goto(url+(url.includes('?')?'&':'?')+'t=10',{waitUntil:'load'}); await pg.waitForTimeout(+(process.env.SETTLE||6000));
    // the eye must have drawn (a slow software renderer can take seconds at 3440 wide): wait up to 20 s, else fail
    let eyeLit=false; for(let k=0;k<40&&!eyeLit;k++){ eyeLit = await pg.evaluate(()=>{ const c=document.querySelector('canvas.main'); if(!c) return false;
      const g=document.createElement('canvas'); g.width=g.height=32; const x=g.getContext('2d'); const e=document.querySelector('#eyebox').getBoundingClientRect(), k=c.width/innerWidth; x.drawImage(c,(e.left+e.width*.4)*k,(e.top+e.height*.3)*k,e.width*.2*k,e.height*.4*k,0,0,32,32);
      const d=x.getImageData(0,0,32,32).data; let m=0; for(let i=0;i<d.length;i+=4) m+=d[i]+d[i+1]+d[i+2]; return m/(32*32*3) > 30; }); if(!eyeLit) await pg.waitForTimeout(500); }
    if(!eyeLit) errs.push('eye never drew');
    await pg.waitForTimeout(1200);
    await pg.screenshot({path:`${outdir}/${b}-${w}x${h}.png`});
    const r = await pg.evaluate(()=>{
      const vis = el=>{const s=getComputedStyle(el); const r=el.getBoundingClientRect(); return s.visibility!=='hidden'&&s.display!=='none'&&+s.opacity>0.05&&r.width>2&&r.height>2;};
      // overlap among marked layout regions
      const regs=[...document.querySelectorAll('[data-region]')].filter(vis).map(e=>({n:e.dataset.region,r:e.getBoundingClientRect()}));
      const ov=[];
      for(let i=0;i<regs.length;i++)for(let j=i+1;j<regs.length;j++){const a=regs[i].r,b=regs[j].r;const x=Math.min(a.right,b.right)-Math.max(a.left,b.left),y=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);if(x>1&&y>1)ov.push(`${regs[i].n}∩${regs[j].n} ${Math.round(x)}x${Math.round(y)}`);}
      const off=regs.filter(g=>g.r.left<-1||g.r.top<-1||g.r.right>innerWidth+1||g.r.bottom>innerHeight+1).map(g=>g.n);
      const scroll = document.documentElement.scrollHeight>innerHeight+1||document.documentElement.scrollWidth>innerWidth+1;
      return {regions:regs.map(g=>g.n+':'+[g.r.left,g.r.top,g.r.width,g.r.height].map(Math.round).join(',')),ov,off,scroll};
    });
    results.push({b,w,h,errs,...r});
    console.log(b,`${w}x${h}`,'overlap:',r.ov.join('; ')||'none','off:',r.off.join(',')||'none','scroll:',r.scroll, errs.length?'ERR '+errs[0]:'');
    await ctx.close();
  }
  await br.close();
}
fs.writeFileSync(`${outdir}/results.json`,JSON.stringify(results,null,1));
const bad=results.filter(r=>r.ov.length||r.off.length||r.scroll||r.errs.length);
console.log(bad.length?`FAIL ${bad.length}/${results.length}`:`PASS ${results.length}/${results.length}`);
process.exit(bad.length?1:0);
