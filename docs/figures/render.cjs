// Regenerate vector figures from the frozen, source-linked benchmark JSON.
// Development only: node docs/figures/render.cjs [--check]
"use strict";
const fs = require("node:fs");
const path = require("node:path");
function renderFigures(data){
  const ink="#18334D",muted="#526579",subtle="#718399",teal="#007F83",blue="#315B9A",amber="#A8661C",gray="#8290A1",line="#D9E3EC",soft="#F5F8FB",light="#E6F3F3",warm="#FFF5E7",white="#FFFFFF";
  const font="Inter, Arial, 'Noto Sans CJK SC', 'Microsoft YaHei', 'PingFang SC', sans-serif";
  const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const num=n=>Number(n.toFixed(4));
  const rect=(x,y,w,h,fill=white,stroke="none",rx=10,extra="")=>`<rect x="${x}" y="${y}" width="${num(w)}" height="${num(h)}" rx="${rx}" fill="${fill}" stroke="${stroke}"${extra?` ${extra}`:""}/>`;
  const tx=(x,y,s,size=20,weight=400,color=ink,anchor="start",extra="")=>`<text x="${x}" y="${y}" font-family="${esc(font)}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}"${extra?` ${extra}`:""}>${esc(s)}</text>`;
  const path=(d,color=muted,arrow=true,dash=false)=>`<path d="${d}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"${arrow?` marker-end="url(#${color===teal?"arrow-teal":"arrow"})"`:""}${dash?' stroke-dasharray="7 6"':""}/>`;
  const rule=(x1,y1,x2,y2,stroke=line,dash=false)=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="1.2"${dash?' stroke-dasharray="3 5"':""}/>`;
  function wrap(w,h,title,desc,body){
    return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="title description">\n<title id="title">${esc(title)}</title>\n<desc id="description">${esc(desc)}</desc>\n<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6.5" refY="3.5" orient="auto" markerUnits="strokeWidth"><path d="M0 0 L7 3.5 L0 7 z" fill="${muted}"/></marker><marker id="arrow-teal" markerWidth="8" markerHeight="8" refX="6.5" refY="3.5" orient="auto" markerUnits="strokeWidth"><path d="M0 0 L7 3.5 L0 7 z" fill="${teal}"/></marker></defs>\n${rect(0,0,w,h,"#F8FAFC","none",0)}\n${rect(1,1,w-2,h-2,"none","#D6E0E9",13)}\n${body.join("\n")}\n</svg>\n`;
  }
  const all={};
  for(const zh of [false,true]){
    const L=(en,cn)=>zh?cn:en;
    const suffix=zh?".zh-CN":"";
    const save=(name,w,h,title,desc,b)=>{all[`${name}${suffix}.svg`]=wrap(w,h,title,desc,b)};
    function header(b,id,title,subtitle,w=1180){
      b.push(rect(30,25,7,62,teal,"none",3),tx(52,49,title,31,700),tx(52,78,subtitle,18,400,muted),tx(w-31,43,id,14,700,teal,"end"));
    }
    function footer(b,h,text,w=1180){
      b.push(rule(32,h-43,w-32,h-43),tx(33,h-18,text,14,400,muted));
    }
    function stage(b,x,y,w,h,k,title,lines,tone=blue){
      const fill=tone===teal?"#F2FBFA":tone===amber?"#FFFAF1":white;
      b.push(rect(x,y,w,h,fill,line,10),rect(x,y,5,h,tone,"none",3),tx(x+17,y+25,k,14,700,tone),tx(x+17,y+53,title,21,700));
      lines.forEach((l,i)=>b.push(tx(x+17,y+79+i*23,l,16,400,muted)));
    }
    // Figure 1: system-level workflow. Solid arrows are evidence/workflow edges; dashed arrow is the failed-test feedback.
    {
      const b=[];
      const title=L("From uncertain failures to evidence-backed repairs","从不确定的故障到可复核的循证修复");
      header(b,"FIG. 01",title,L("Agent-led research and execution · deterministic local evidence helpers","宿主 Agent 负责研究与执行 · 本地工具负责确定性证据处理"));
      b.push(tx(40,123,L("INPUT","输入"),14,700,subtle),tx(306,123,L("PARALLEL EVIDENCE PATHS","并行证据路径"),14,700,subtle),tx(607,123,L("DECISION","决策"),14,700,subtle),tx(886,123,L("EXPERIMENT","实验"),14,700,subtle));
      // Edges drawn before boxes so only the connecting segments are visible.
      b.push(path("M275 270 H290 V200 H306"),path("M290 270 V331 H306"),path("M576 200 H592 V270 H607"),path("M576 331 H592 V270"),path("M855 270 H886"),path("M1013 353 V447",teal),path("M1140 270 H1154 V413 H441 V390",muted,true,true));
      stage(b,40,191,235,162,"01",L("Fingerprint","问题指纹"),[L("Symptom + environment","症状 + 环境"),L("Minimal reproduction","最小复现"),L("Acceptance criteria","验收标准")],blue);
      stage(b,306,145,270,111,"02a",L("Local case recall","本地案例召回"),[L("Validated history · ranked leads","已校验历史 · 相关候选")],teal);
      stage(b,306,266,270,124,"02b",L("External research","外部研究"),[L("Issues · docs · papers","Issue · 文档 · 论文"),L("Source + applicability","来源与适用性")],blue);
      stage(b,607,191,248,162,"03",L("Evidence mapping","证据映射"),[L("Local code + conditions","本地代码 + 条件"),L("Compare candidate fixes","比较候选方案"),L("Falsifiable hypothesis","可证伪假设")],blue);
      stage(b,886,191,254,162,"04",L("Repair & validate","修复与验证"),[L("Same before / after checks","同一前后验证标准"),L("Regression + test IDs","回归测试 + 测试 ID"),L("Measure cost / limits","衡量开销与边界")],amber);
      b.push(rect(585,397,360,28,"#F8FAFC","none",4),tx(765,416,L("Failed check → refine hypothesis / research again","验证失败 → 修正假设 / 再研究"),16,500,muted,"middle"));
      b.push(rect(40,447,536,157,white,line,10),tx(58,475,L("TRUST BOUNDARY","责任与信任边界"),14,700,subtle));
      b.push(rect(59,488,498,40,"#EDF2F9","none",6),tx(72,514,L("Host agent: research + authorized code / test execution","宿主 Agent：研究 + 授权代码 / 测试执行"),17,600,blue));
      b.push(rect(59,539,498,40,light,"none",6),tx(72,565,L("Offline helpers: plan, recall, validate, review, seal","离线工具：规划、召回、校验、复核、封存"),17,600,teal));
      b.push(rect(607,447,533,157,light,"#B6D9DA",10),tx(625,475,"05–06",14,700,teal),tx(625,503,L("Reviewable evidence & reusable case","可复核证据与可复用案例"),22,700));
      b.push(tx(625,531,L("case.json · logs · source snapshots · SHA-256 manifest","case.json · 日志 · 源码快照 · SHA-256 清单"),16,400,muted));
      const statuses=[["solved",teal,"#FFFFFF"],["partial",amber,"#FFFFFF"],["blocked",muted,"#FFFFFF"]];
      statuses.forEach(([s,c,f],i)=>b.push(rect(625+i*112,549,99,31,f,"#C9D9DF",5),tx(674.5+i*112,570,s,16,600,c,"middle")));
      footer(b,652,L("Solid arrows: evidence flow. Dashed arrow: iteration. Validation and hashes check consistency, not truth or causality.","实线：证据流程。虚线：失败后迭代。结构与哈希校验不能证明事实真实性或因果。"));
      save("workflow",1180,652,title,L("Problem fingerprint branches into local recall and external research, then evidence mapping, local repair and tests, review and evidence packaging. Failed checks feed back into research.","问题指纹分流到本地召回与外部研究，映射证据后修复、测试、复核并封存；失败后重新研究。"),b);
    }
    // Figure 2: one-shot and reusable snapshot architecture.
    {
      const b=[];
      const title=L("Two paths, one consistent retrieval contract","双路径检索，同一套评分与验收契约");
      header(b,"FIG. 02",title,L("Low-startup single recall · validated in-memory index for repeated queries","低启动成本单次召回 · 多查询复用一次校验的内存索引"));
      b.push(path("M275 255 H296 V177 H316"),path("M296 255 V330 H316"),path("M565 177 H596"),path("M565 330 H596"),path("M840 177 H859 V255 H880"),path("M840 330 H859 V255",teal));
      stage(b,40,176,235,157,L("CASE CORPUS","案例语料"),L("Read & validate","读取与校验"),[L("Explicit local directory","显式本地目录"),L("Solved records only","仅合规 solved 记录"),L("Deduplication + tokenization","去重 + 分词")],blue);
      stage(b,316,116,249,121,L("SINGLE QUERY","单次查询"),L("One-shot scan","一次性扫描"),[L("Avoid full index startup","避免完整索引启动"),L("Calculate needed scores","计算所需评分")],blue);
      stage(b,596,116,244,121,L("COLD PATH","冷启动路径"),L("Rank candidates","候选排序"),[L("Same BM25 formula","同一 BM25 公式"),L("Stable tie-breaking","确定性平分排序")],blue);
      stage(b,316,269,249,122,L("BATCH QUERIES","批量查询"),L("Reusable snapshot","可复用内存快照"),[L("Validate corpus once","语料只校验一次"),L("1–128 local queries","1–128 条本地查询")],teal);
      stage(b,596,269,244,122,L("WARM PATH","热查询路径"),L("Packed postings","紧凑倒排索引"),[L("Precomputed contributions","预计算词项贡献"),L("Compact arrays · Top-K","紧凑数组 · Top-K")],teal);
      stage(b,880,176,260,157,L("SHARED OUTPUT","共享输出"),L("Ranked case leads","排序后的案例线索"),[L("Matching terms + scores","命中词 + 分数"),L("Version facts + limits","版本事实 + 局限"),L("No forced weak matches","不强凑弱相关候选")],amber);
      b.push(rect(40,424,1100,66,white,line,8),tx(57,449,L("RANKING OPTIONS","可选排序模式"),14,700,subtle));
      const tags=["BM25 (default)","Technical","Stemmed","Hybrid","Contextual"];
      tags.forEach((s,i)=>{const x=235+i*175;b.push(rect(x,438,162,36,i===0?light:soft,"#D7E4E9",5),tx(x+81,461,zh&&i===0?"BM25（默认）":s,17,600,i===0?teal:ink,"middle"))});
      footer(b,535,L("All paths remain local and lexical; snapshots are rebuilt after changes. Ranking is not repair success.","两条路径均为本地词项检索；案例修改后重建快照。检索排名不等于修复成功。"));
      save("retrieval-architecture",1180,535,title,L("Single query scan and batch snapshot compact index share deterministic ranking and evidence summaries.","单次扫描和批量内存快照共享确定性排序与案例摘要。"),b);
    }
    const methodNames={legacy_scan:L("Legacy BM25","旧版 BM25"),indexed_bm25:L("Indexed BM25","倒排 BM25"),technical:"R2F Technical",stemmed:"R2F Stemmed",hybrid:"R2F Hybrid",contextual:"R2F Contextual",sqlite_fts5:"SQLite FTS5",sqlite_fts5_porter:"SQLite FTS5 Porter"};
    const color=id=>id==="legacy_scan"?gray:id.startsWith("sqlite")?amber:id==="indexed_bm25"?blue:teal;
    const percent=v=>(100*v).toFixed(2)+"%";
    function rankChart(name,report,real){
      const b=[],W=1180,H=638;
      const title=real?L("Real-world duplicate-issue retrieval","真实公开 Issue：重复问题检索对比"):L("Synthetic retrieval accuracy","合成数据集：检索准确性对比");
      const subtitle=real?L("44 public issue titles · 18 labeled queries · same Top-5 evaluation","44 个公开 Issue 标题 · 18 条有标签查询 · 同一 Top-5 评测"):L("40 diagnostic descriptions · 80 positive + 3 unrelated queries · fixed Top-5","40 个故障描述 · 80 条正例 + 3 条无关查询 · 固定 Top-5");
      header(b,real?"FIG. 04":"FIG. 03",title,subtitle);
      // Exact values follow visible bars; all axes start at zero.
      const order=real?["sqlite_fts5_porter","stemmed","contextual","hybrid","indexed_bm25","technical","legacy_scan","sqlite_fts5"]:["hybrid","stemmed","contextual","technical","indexed_bm25","legacy_scan","sqlite_fts5_porter","sqlite_fts5"];
      const panels=real?[{x:263,w:207,valueX:486,title:"MRR@5 ↑",max:1,metric:"mrr@5",fmt:percent},{x:548,w:207,valueX:771,title:"Recall@5 ↑",max:1,metric:"recall@5",fmt:percent},{x:830,w:212,valueX:1059,title:L("P50 latency ↓","P50 延迟 ↓"),max:60,metric:"query_p50_ms",transform:v=>v*1000,fmt:v=>v.toFixed(1)+" µs"}]:[{x:275,w:325,valueX:619,title:"MRR@5 ↑",max:1,metric:"mrr@5",fmt:percent},{x:735,w:325,valueX:1079,title:"Recall@5 ↑",max:1,metric:"recall@5",fmt:percent}];
      b.push(tx(39,126,L("METHOD","方法"),15,700,muted));
      for(const p of panels){
        b.push(tx(p.x,126,p.title,21,700));
        const ticks=p.max===1?[0,.25,.5,.75,1]:[0,15,30,45,60];
        for(const t of ticks){const x=p.x+p.w*t/p.max;b.push(rule(x,151,x,527,line,t!==0),tx(x,145,p.max===1?`${t*100}%`:`${t}`,12,400,subtle,"middle"))}
      }
      order.forEach((id,i)=>{
        const y=167+i*45; const m=report.methods[id];
        if(!m||m.status!=="completed")throw Error("Incomplete method "+id);
        if((!real&&id==="hybrid")||(real&&id==="stemmed"))b.push(rect(27,y-9,1126,40,"#E8F5F3","none",5));
        b.push(rect(40,y+2,6,21,color(id),"none",2),tx(54,y+19,methodNames[id],19,id==="stemmed"||id==="hybrid"?700:500));
        for(const p of panels){
          const value=(p.transform||((v)=>v))(m[p.metric]);
          b.push(rect(p.x,y+2,p.w*value/p.max,19,color(id),"none",3,`data-method="${id}" data-metric="${p.metric}" data-value="${m[p.metric]}"`));
          b.push(tx(p.valueX,y+18,p.fmt(value),16,600,ink));
        }
      });
      // legend and study limits
      let ly=554;
      [[teal,L("R2F rankers","R2F 增强排序")],[blue,L("Indexed default","倒排默认排序")],[gray,L("Legacy","旧版")],[amber,L("SQLite baselines","SQLite 基线")]].forEach(([c,s],i)=>b.push(rect(40+i*244,ly-12,16,13,c,"none",2),tx(64+i*244,ly,s,16,500,muted)));
      const note=real?L("Stemmed matches Porter Recall@5 (83.33%); Porter has higher MRR. Unjudged distractors; development sample.","Stemmed 与 Porter 的 Recall@5 均为 83.33%；Porter 的 MRR 更高。未标注干扰项；开发样本。"):L("Hybrid: MRR@5, Recall@5 and nDCG@5 = 1.00. All tested methods abstained on the 3 unrelated queries.","Hybrid：MRR@5、Recall@5、nDCG@5 均为 1.00；各方法对 3 条无关查询均返回空结果。");
      b.push(tx(40,585,note,15,500,muted));
      footer(b,H,L("Source: GitHub Actions run "+data.source.run_id+" · Linux / Python "+report.python+" · fixed development fixture, not held-out.","来源：GitHub Actions "+data.source.run_id+" · Linux / Python "+report.python+" · 固定开发数据集，非独立盲测。"));
      save(name,W,H,title,real?L("MRR, recall, and median ranking latency for all eight methods; SQLite Porter has highest MRR on this sample, Stemmed has same recall.","八种方法的 MRR、召回率和中位检索延迟；SQLite Porter 的 MRR 最高，Stemmed 召回率相同。"):L("All eight methods, zero-based bars for MRR@5 and Recall@5; Hybrid reaches 100% on the fixed synthetic fixture.","八种方法的 MRR@5 与 Recall@5 零基线条形图；Hybrid 在固定合成样本中达 100%。"),b);
    }
    rankChart("synthetic-ranking",data.synthetic,false);
    rankChart("github-ranking",data.github,true);
    // Figure 5: comparable paired workloads and explicit measurement units.
    {
      const b=[],W=1180,H=506;
      const title=L("Retrieval throughput and memory efficiency","检索吞吐与索引内存效率");
      header(b,"FIG. 05",title,L("Paired comparisons on generated workloads · lower measured time / allocations are better","同环境生成负载配对实验 · 实测耗时与分配内存越低越好"));
      const batch=data.scale.batch_recall,index=data.scale.index_scale,old=index.index_memory.tuple_postings.retained_bytes,newv=index.index_memory.packed_postings.retained_bytes;
      const configs=[
        {title:L("A  End-to-end batch","A  端到端批量召回"),subtitle:L("120 cases · 32 queries","120 案例 · 32 查询"),large:batch.speedup.toFixed(2)+"×",unit:L("faster","加速"),a:L("Repeated one-shot","重复单次召回"),b:L("Batch snapshot","批量内存快照"),av:batch.one_shot_total_median_ms,bv:batch.batch_total_median_ms,fmt:v=>v.toFixed(2)+" ms",note:L("Includes file reads & validation","包含文件读取与校验")},
        {title:L("B  Warm index queries","B  热索引查询"),subtitle:L("5,000 docs · 64 sparse queries","5,000 文档 · 64 稀疏查询"),large:index.warm_query_speedup.toFixed(2)+"×",unit:L("faster","加速"),a:L("Full scan","全量扫描"),b:L("Packed index","紧凑索引"),av:index.scan_total_ms,bv:index.index_total_ms,fmt:v=>v.toFixed(2)+" ms",note:L("Excludes index construction","不含索引构建时间")},
        {title:L("C  Retained index memory","C  索引常驻分配内存"),subtitle:L("5,000 generated documents","5,000 份生成文档"),large:(100*(1-newv/old)).toFixed(1)+"%",unit:L("less","下降"),a:L("Tuple postings","元组式倒排"),b:L("Packed arrays","紧凑数组"),av:old,bv:newv,fmt:v=>(v/1e6).toFixed(2)+" MB",note:L("Python allocations; excludes input","Python 分配量；不含输入语料")}
      ];
      configs.forEach((c,i)=>{
        const x=31+i*379,w=360;
        b.push(rect(x,113,w,330,white,line,10),tx(x+17,144,c.title,20,700),tx(x+17,168,c.subtitle,15,400,muted),tx(x+17,220,c.large,43,700,teal),tx(x+17,243,c.unit,17,600,teal));
        const max=Math.max(c.av,c.bv);
        [[c.a,c.av,gray],[c.b,c.bv,teal]].forEach(([label,value,col],j)=>{
          const y=273+j*66;
          b.push(tx(x+17,y,label,16,600,ink),tx(x+w-17,y,c.fmt(value),16,600,ink,"end"),rect(x+17,y+11,w-34,17,"#EDF2F6","none",3),rect(x+17,y+11,(w-34)*value/max,17,col,"none",3));
        });
        b.push(tx(x+17,422,c.note,14,400,muted));
      });
      footer(b,H,L("Source: GitHub Actions run "+data.source.run_id+" · exact batch reports and Top-10 scores matched; timing is workload-specific.","来源：GitHub Actions "+data.source.run_id+" · 批量报告与 Top-10 评分完全一致；加速比仅对应此负载。"));
      save("efficiency",W,H,title,L("Batch 683.454 ms versus 25.266 ms; warm queries 848.813 ms versus 7.763 ms; retained allocation 22.01 MB versus 5.18 MB.","批量 683.454 ms 对 25.266 ms；热查询 848.813 ms 对 7.763 ms；常驻分配 22.01 MB 对 5.18 MB。"),b);
    }
  }
  return all;
}
const data=JSON.parse(fs.readFileSync(path.join(__dirname,"benchmark-snapshot.json"),"utf8"));
const files=renderFigures(data);
const check=process.argv.includes("--check");
for (const [name,svg] of Object.entries(files)) {
  const target=path.join(__dirname,name);
  if(check){if(!fs.existsSync(target)||fs.readFileSync(target,"utf8")!==svg){console.error("Stale figure: "+name);process.exitCode=1;}}else{fs.writeFileSync(target,svg,"utf8");console.log("Wrote "+name);}
}
if(check&&!process.exitCode) console.log("All "+Object.keys(files).length+" generated figures match the frozen report.");
