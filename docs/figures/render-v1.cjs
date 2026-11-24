const fs = require('node:fs');
const path = require('node:path');
const render = function render(d,zh){
 const W=1180,H=748, fg="#172b40",muted="#526b82",blue="#136f92",green="#087e78",grey="#8fa6b7",light="#eaf1f5",white="#ffffff";
 const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
 let o=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 ${W} ${H}">\n<title id="title">${zh?"v1.0.0 实测研究与算法实验":"v1.0.0 Measured research and algorithm experiments"}</title>\n<desc id="desc">${zh?"两套开发语料检索与配对召回、模拟请求调度和 CPU 注意力实验；不是独立修复成功率。":"Two development retrieval corpora, mock request scheduling and a CPU attention experiment; not independent repair success."}</desc>\n`;
 const rect=(x,y,w,h,c,r=0)=>{o+=`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${c}"/>\n`};
 const t=(x,y,s,size=18,c=fg,weight=400,anchor="start")=>{o+=`<text x="${x}" y="${y}" font-family="Arial, Noto Sans CJK SC, sans-serif" font-size="${size}" fill="${c}" font-weight="${weight}" text-anchor="${anchor}">${esc(s)}</text>\n`};
 const ln=(x1,y1,x2,y2,c="#c5d4de")=>{o+=`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="1"/>\n`};
 rect(0,0,W,H,"#f6f9fb",20);t(36,43,zh?"研究到修复 · v1.0.0 实测":"Research to Fix · v1.0.0 measured results",28,fg,700);
 t(36,70,zh?"相同语料、相同 Top-6 预算；显式论文—代码关系参与排序":"Same corpus and Top-6 budget; explicit paper–code relations inform ranking",16,muted);
 const methods=[["stemmed_bm25","Stemmed BM25",grey],["sqlite_porter","SQLite Porter",blue],["paired_rank",zh?"论文—代码配对":"Paper–code paired",green]];
 for(const [idx,report] of [d.original,d.transfer].entries()){
  const x=36+idx*566;rect(x,92,546,300,white,13);t(x+20,124,idx?(zh?"B · 跨领域 / 双语":"B · Transfer / bilingual"):(zh?"A · 原始算法语料":"A · Original algorithm corpus"),21,fg,700);
  t(x+20,148,`${report.unique_sources} ${zh?"来源身份":"identities"} · ${report.queries} ${zh?"查询":"queries"}`,15,muted);
  for(const [j,key] of ["recall","complete_pair_recall"].entries()){
   const xx=x+20+j*265;t(xx,177,key==="recall"?"Recall@6":zh?"完整配对召回":"Complete pair recall",16,fg,600);
   for(const [i,[k,name,c]] of methods.entries()){
    const y=193+i*54,val=report.methods[k].overall[key];
    t(xx,y+14,name,13,muted,500);rect(xx,y+21,230,13,light,3);
    o+=`<rect x="${xx}" y="${y+21}" width="${(230*val).toFixed(4)}" height="13" rx="3" fill="${c}" data-corpus="${idx?"transfer":"original"}" data-method="${k}" data-metric="${key}" data-value="${val}"/>\n`;
    t(xx+230,y+13,(val*100).toFixed(2)+"%",14,fg,700,"end");
   }ln(xx,361,xx+230,361);t(xx,380,"0",12,muted);t(xx+230,380,"100%",12,muted,400,"end");
  }
 }
 rect(36,410,546,276,white,13);t(56,443,zh?"C · 请求调度（模拟 I/O）":"C · Scheduling (mock I/O)",21,fg,700);
 t(56,467,zh?"6 次请求 · 每次模拟 40 ms · 五次重复":"6 requests · mock 40 ms/request · 5 repetitions",14,muted);
 const sch=d.schedule, mx=sch.sequential_median_ms;
 for(const [i,[label,val,c]] of [[zh?"串行":"Sequential",mx,grey],[zh?"3 个独立工作线程":"3 independent workers",sch.three_workers_median_ms,green]].entries()){
  const y=491+i*55;t(56,y,label,16,fg,600);t(562,y,val.toFixed(2)+" ms",16,fg,600,"end");rect(56,y+12,506,14,light,4);rect(56,y+12,506*val/mx,14,c,4)
 }
 t(56,631,`${sch.speedup.toFixed(2)}× ${zh?"模拟耗时加速":"mock-latency speedup"}`,26,green,700);
 t(56,659,zh?"均衡调度覆盖 6 组 vs 3 组；不是互联网实测延迟":"Balanced: 6 provider groups vs 3; not live network latency",13,muted);
 rect(602,410,542,276,white,13);t(622,443,zh?"D · 精确注意力（CPU Python）":"D · Exact attention (CPU Python)",21,fg,700);t(622,467,zh?"峰值 tracemalloc 分配 · 含输出、不含输入":"Peak traced allocation · output included, inputs excluded",14,muted);
 const cand=d.attention.candidates, base=cand.materialized.metrics.peak_bytes.median;
 for(const [i,[k,label]] of [["materialized",zh?"完整矩阵":"Full matrix"],["rowwise",zh?"逐行":"Row streaming"],["blocked",zh?"分块":"Block merge"],["online",zh?"在线递推":"Online recurrence"]].entries()){
  const y=489+i*40,val=cand[k].metrics.peak_bytes.median;t(622,y,label,14,fg,500);t(1124,y,(val/1024).toFixed(2)+" KiB",14,fg,600,"end");rect(622,y+9,502,10,light,3);rect(622,y+9,502*val/base,10,i===0?grey:green,3)
 }
 t(622,662,`${((1-cand.online.metrics.peak_bytes.median/base)*100).toFixed(2)}% ${zh?"在线递推分配下降；全部精度检查通过":"lower online allocation; all accuracy gates passed"}`,14,green,700);
 t(36,714,zh?"冻结报告：GitHub Actions 45355977079 · 开发语料，不是盲测。CPU 小实验不代表 GPU 加速。":"Frozen report: GitHub Actions 45355977079 · Development fixtures, not held-out. CPU example, not GPU speedup.",14,muted);
 return o+"</svg>\n";
};
const d=JSON.parse(fs.readFileSync(path.join(__dirname,'v1-snapshot.json'),'utf8'));
for(const zh of [false,true]){const f=path.join(__dirname,zh?'release-v1.zh-CN.svg':'release-v1.svg');const output=render(d,zh);if(process.argv.includes('--check')){if(fs.readFileSync(f,'utf8')!==output){console.error('Stale figure: '+f);process.exitCode=1;}}else fs.writeFileSync(f,output);}
