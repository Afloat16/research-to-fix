// Development-only deterministic SVG from a frozen, source-linked CI report.
"use strict";
const fs=require("node:fs"), path=require("node:path");
function render(data,zh) {
  const C={ink:"#18334D",muted:"#526579",teal:"#007F83",blue:"#315B9A",grey:"#8290A1",orange:"#A8661C",line:"#D9E3EC",soft:"#F5F8FB",green:"#E6F3F3"};
  const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const txt=(x,y,s,size=17,weight=400,color=C.ink,anchor="start")=>`<text x="${x}" y="${y}" font-family="Inter, Arial, 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}">${esc(s)}</text>`;
  const rect=(x,y,w,h,fill="#fff",stroke="none",rx=8)=>`<rect x="${x}" y="${y}" width="${Math.round(w*1000)/1000}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}"/>`;
  const line=(x1,y1,x2,y2)=>`<path d="M${x1} ${y1}H${x2}V${y2}" fill="none" stroke="${C.line}" stroke-width="2"/>`;
  const arr=(x,y)=>`<path d="M${x} ${y}h22l-7 -6m7 6l-7 6" fill="none" stroke="${C.teal}" stroke-width="2.2" stroke-linejoin="round"/>`;
  const P=v=>(v*100).toFixed(1)+"%";
  const labels=zh?["问题指纹","研究计划","来源检索","证据排序与关联","同条件实测","实施与回归"]:["Fingerprint","Research plan","Source discovery","Rank & link","Compare candidates","Implement & verify"];
  const desc=zh?["任务 / 版本 / 约束","机制 / 替代 / 反证","论文 / GitHub / HF","去重 / 证据缺口","阈值 / Pareto","代码 / 测试 / 案例"]:["Task / version / limits","Mechanism / alternatives","Papers / code / HF","Dedup / evidence gaps","Thresholds / Pareto","Patch / tests / case"];
  const ms=["fixed_order","stemmed_bm25","sqlite_porter","facet_rank","evidence_shortlist"];
  const names=zh?["固定顺序","Stemmed BM25","SQLite Porter","机制分面","R2F 证据短名单"]:["Fixed order","Stemmed BM25","SQLite Porter","Facet rank","R2F evidence shortlist"];
  const metricNames=zh?["召回率 @6","论文+代码覆盖","完整配对召回"]:["Recall @6","Paper + code","Complete pair recall"];
  const metricKeys=["recall","paper_and_code","complete_pair_recall"];
  let s=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="694" viewBox="0 0 1200 694" role="img" aria-labelledby="title desc"><title id="title">${zh?"研究与多方案决策":"Research and multi-solution decision"}</title><desc id="desc">${zh?"研究工作流、八个算法问题的来源排序对照与五次方差修复实测。开发样本，不代表实时检索成功率。":"Workflow, source ranking on eight algorithm tasks and five measured variance replicates. Development fixture, not live search success."}</desc>`;
  s+=rect(0,0,1200,694,C.soft,C.line,12)+txt(30,39,zh?"从论文与开源实现，到可验证的算法决策":"From papers and code to measured algorithm decisions",26,700)+txt(30,65,zh?"研究覆盖 → 证据核验 → 同协议实验 → 有条件的最佳方案":"Research coverage → evidence review → matched experiments → conditional best option",16,400,C.muted);
  for(let i=0;i<6;i++){let x=30+195*i;s+=rect(x,89,164,76,i===5?C.green:"#fff",C.line,8)+txt(x+82,114,labels[i],zh?17:15,700,C.ink,"middle")+txt(x+82,141,desc[i],zh?12:11.5,400,C.muted,"middle");if(i<5)s+=arr(x+169,127)}
  s+=rect(25,185,1150,285,"#fff",C.line,10)+txt(43,213,zh?"A  论文 / 开源来源检索回放（8 个任务 · 16 条查询 · Top-6）":"A  Paper/code retrieval replay (8 tasks · 16 queries · Top-6)",19,700);
  for(let j=0;j<3;j++){let x=267+j*303;s+=txt(x,242,metricNames[j],16,600);s+=txt(x,259,"0",11,400,C.muted)+txt(x+208,259,"100%",11,400,C.muted,"end")}
  for(let i=0;i<5;i++){let y=275+i*34;let method=ms[i];s+=txt(43,y+14,names[i],15,i===4?700:500,i===4?C.teal:C.ink);for(let j=0;j<3;j++){let x=267+j*303;let val=data.discovery.methods[method].overall[metricKeys[j]];s+=rect(x,y,208,17,C.soft,"none",3)+rect(x,y,208*val,17,i===4?C.teal:i===0?C.grey:C.blue,"none",3)+txt(x+217,y+14,P(val),14,600)}}
  s+=txt(43,455,zh?"固定开发语料：32 个真实来源身份，44 条观测；相关性不是修复正确性。":"Fixed development corpus: 32 real source identities, 44 observations; relevance is not repair correctness.",13,400,C.muted);
  s+=rect(25,482,1150,170,"#fff",C.line,10)+txt(43,510,zh?"B  数值方差修复：五次配对测量的中位数":"B  Numerical variance repair: medians across five matched replicates",19,700);
  const cn=zh?["原始矩（未通过）","中心化两遍 ★","在线递推 ★","标准库"]:["Raw moments (failed)","Centered two-pass ★","Online recurrence ★","Standard library"];
  const ids=["naive","centered","online","stdlib"];
  s+=txt(43,538,zh?"候选方案":"Candidate",14,600,C.muted)+txt(448,538,zh?"相对误差":"Relative error",14,600,C.muted)+txt(699,538,zh?"耗时 (ms)":"Latency (ms)",14,600,C.muted)+txt(934,538,zh?"峰值分配 (B)":"Peak alloc. (B)",14,600,C.muted);
  for(let i=0;i<4;i++){let y=548+i*23;let row=data.variance.candidates[ids[i]];let met=row.metrics;if(i===1||i===2)s+=rect(38,y-3,1123,22,C.green,"none",3);s+=txt(43,y+12,cn[i],14,i===1||i===2?700:400,i===0?C.orange:C.ink)+txt(448,y+12,met.relative_error.median===0?"0":met.relative_error.median.toExponential(3),14,500)+txt(699,y+12,met.latency_ms.median.toFixed(3),14,500)+txt(934,y+12,String(met.peak_bytes.median),14,500)}
  s+=txt(30,678,zh?"★ 非支配可行方案。内存仅为 tracemalloc 分配，不含输入；CI 实测，不是全局最优证明。":"★ Eligible Pareto candidates. Traced allocations exclude input; measured CI run, not a global-optimality claim.",13,400,C.muted)+"</svg>\n";
  return s;
}
const data=JSON.parse(fs.readFileSync(path.join(__dirname,"research-snapshot.json"),"utf8"));
for(const zh of [false,true]) {const file=path.join(__dirname,"research-decision"+(zh?".zh-CN":"")+".svg");const svg=render(data,zh);if(process.argv.includes("--check")){if(fs.readFileSync(file,"utf8")!==svg)throw Error("stale figure: "+file);}else fs.writeFileSync(file,svg);}
