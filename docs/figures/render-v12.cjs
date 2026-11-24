"use strict";
const fs = require("node:fs");
const path = require("node:path");
function render(s,zh){
 const r=s.relative_recall, rows=Object.entries(r.scenarios), min=Math.min(...rows.map(x=>x[1].p50_speedup)),max=Math.max(...rows.map(x=>x[1].p50_speedup)),lo=Math.min(...rows.map(x=>x[1].sample_query_peak_reduction))*100,hi=Math.max(...rows.map(x=>x[1].sample_query_peak_reduction))*100;
 const labels=zh?["BM25 · 稀疏","BM25 · 混合","BM25 · 密集","Precision Field · 稀疏","Precision Field · 混合","Precision Field · 密集"]:["BM25 · sparse","BM25 · mixed","BM25 · dense","Precision Field · sparse","Precision Field · mixed","Precision Field · dense"];
 const esc=v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
 const t=(x,y,v,size=20,color="#e7edf7",weight=400,anchor="start")=>`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}" text-anchor="${anchor}">${esc(v)}</text>`;
 const rect=(x,y,w,h,fill,rx=10)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}"/>`;
 const cards=[[`${min.toFixed(2)}–${max.toFixed(2)}×`,zh?"P50 召回速度提升":"faster median recall"],[`${lo.toFixed(1)}–${hi.toFixed(1)}%`,zh?"样本峰值分配减少":"less sample peak allocation"],[`${r.exact_parity_queries}/${r.exact_parity_queries}`,zh?"完整输出严格一致":"exact output parity"]];
 let a=[`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 690" role="img" aria-labelledby="title desc" font-family="system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">`,`<title id="title">${zh?"精确召回加速实测":"Exact recall acceleration"}</title>`,`<desc id="desc">${zh?"五千篇生成文档，六种负载，完整结果一致。横条表示中位延迟加速倍数；内存是单查询样本。":"Five thousand generated documents, six workloads, exact full results. Bars show median latency speedup; memory is one sampled query per workload."}</desc>`,rect(0,0,1040,690,"#101a2c",22),t(36,42,"RESEARCH TO FIX  /  v1.2.0",15,"#69d6cf",700),t(36,92,zh?"相同结果，更少计算。":"Same answers. Less work.",42,"#ffffff",750),t(36,126,zh?"精确阈值计数 + 有界 Top-K + 延迟解释":"Exact threshold count + bounded Top-K + deferred explanations",19,"#b2c3d9")];
 cards.forEach(([v,l],i)=>{let x=36+i*326;a.push(rect(x,153,316,106,"#1e2d43",14),t(x+18,201,v,35,"#72e0d3",730),t(x+18,233,l,16,"#c8d5e6",500));});
 a.push(t(36,299,zh?"六种负载 · 中位延迟加速（倍）":"Six workloads · median latency speedup (×)",21,"#ffffff",650),t(1010,299,zh?"旧版 = 1×":"old path = 1×",15,"#a6b8cf",400,"end"));
 const x=315,w=585;for(let n=0;n<=5;n++){let xx=x+w*n/5;a.push(`<line x1="${xx}" y1="321" x2="${xx}" y2="593" stroke="${n===1?"#7d91ab":"#293b53"}" stroke-width="${n===1?2:1}" stroke-dasharray="${n===1?"5 4":"none"}"/>`,t(xx,614,String(n),14,"#a6b8cf",400,"middle"));}
 rows.forEach(([key,v],i)=>{let y=329+i*43;let color=i<3?"#69d6cf":"#7ba8fa";a.push(t(36,y+22,labels[i],17,"#e7edf7",500),`<rect x="${x}" y="${y}" width="${(w*v.p50_speedup/5).toFixed(3)}" height="27" rx="5" fill="${color}" data-scenario="${key}" data-value="${v.p50_speedup}"/>`,t(x+w*v.p50_speedup/5+12,y+20,`${v.p50_speedup.toFixed(2)}×`,17,"#f0f5ff",650));});
 a.push(t(36,648,zh?"5,000 篇生成文档 · 每种 48 查询 · 3 次重复 · 预分词热索引":"5,000 generated documents · 48 queries/workload · 3 repeats · prepared-token warm index",15,"#b2c3d9"),t(36,671,zh?"内存为每种负载的单查询样本；不代表端到端修复率或全部索引内存。":"Allocation is one sampled query/workload; not end-to-end repair accuracy or total index memory.",14,"#a6b8cf"),"</svg>");return a.join("\n")+"\n";
}
const snap = JSON.parse(fs.readFileSync(path.join(__dirname, "v12-snapshot.json"), "utf8"));
for (const zh of [false, true]) {
  const out = path.join(__dirname, "v12-recall" + (zh ? ".zh-CN" : "") + ".svg");
  const expected = render(snap, zh);
  if (process.argv.includes("--check")) {
    if (fs.readFileSync(out, "utf8") !== expected) throw Error("Stale v1.2 figure: " + out);
  } else fs.writeFileSync(out, expected, "utf8");
}

function renderTransfer(s,zh){
 const v=s.transfer, m=v.methods, names={precision_field4:"R2F Precision Field",v1_contextual:"R2F Contextual",v1_bm25:"R2F BM25",sqlite_unicode4:"SQLite Unicode 4",sqlite_porter:"SQLite Porter",bm25s_native:"BM25S Native",bm25s_matched:"BM25S Matched",rank_bm25_matched:"rank-bm25 Matched"};
 const order=Object.keys(m).sort((a,b)=>m[b]["ndcg@10"]-m[a]["ndcg@10"]),esc=x=>String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"), t=(x,y,l,size=20,c="#e7edf7",weight=400,anchor="start")=>`<text x="${x}" y="${y}" font-size="${size}" fill="${c}" font-weight="${weight}" text-anchor="${anchor}">${esc(l)}</text>`, rect=(x,y,w,h,f,rx=10)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${f}"/>`;
 const a=[`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 735" role="img" aria-labelledby="title desc" font-family="system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">`,`<title id="title">${zh?"真实 Mathematica 检索迁移对照":"Real Mathematica retrieval transfer"}</title>`,`<desc id="desc">${zh?"八种方法的 nDCG@10，展示全部结果及真实查询的严格一致性和加速；不代表实际修复率。":"All eight nDCG@10 scores and exact recall parity/speed on real queries; not agent repair accuracy."}</desc>`,rect(0,0,1040,735,"#101a2c",22),t(36,42,"RESEARCH TO FIX  /  EXTERNAL TRANSFER",15,"#69d6cf",700),t(36,90,zh?"真实语料，全部对照。":"Real corpus. All comparators.",38,"#ffffff",750),t(36,124,zh?"BEIR Mathematica · 16,705 篇文档 · 804 条测试查询 · 预先冻结方法":"BEIR Mathematica · 16,705 documents · 804 test queries · frozen methods",18,"#b2c3d9")];
 const cards=[[`${v.exact_recall.p50_speedup.toFixed(2)}×`,zh?"精确召回 P50 加速":"exact recall P50 speedup"],[`${v.exact_recall.queries}/${v.exact_recall.queries}`,zh?"完整输出一致":"exact full-output parity"],[m.precision_field4["ndcg@10"].toFixed(4),zh?"Precision Field nDCG@10":"Precision Field nDCG@10"]];cards.forEach(([value,label],i)=>{let x=36+i*326;a.push(rect(x,151,316,102,"#1e2d43",14),t(x+18,199,value,35,"#72e0d3",730),t(x+18,231,label,16,"#c8d5e6",500));});
 a.push(t(36,291,zh?"检索质量 · nDCG@10（从零起）":"Retrieval quality · nDCG@10 (zero baseline)",21,"#fff",650));
 const x=290,w=596,scale=.25;for(let n=0;n<=5;n++){let xx=x+w*n/5;a.push(`<line x1="${xx}" y1="306" x2="${xx}" y2="620" stroke="#304159" stroke-width="1"/>`,t(xx,643,(n*.05).toFixed(2),14,"#a6b8cf",400,"middle"));}
 order.forEach((key,i)=>{let n=m[key]["ndcg@10"],y=313+i*39,color=key==="precision_field4"?"#69d6cf":key.startsWith("v1_")?"#7ba8fa":"#687b96";a.push(t(36,y+20,names[key],17,"#e7edf7",500),`<rect x="${x}" y="${y}" width="${(w*n/scale).toFixed(3)}" height="25" rx="5" fill="${color}" data-method="${key}" data-value="${n}"/>`,t(x+w*n/scale+12,y+20,n.toFixed(4),17,"#f0f5ff",650));});
 a.push(t(36,680,zh?"Precision Field 的区间相对 Unicode 4、rank-bm25 及旧 BM25 为正；其他不确定。":"Positive pointwise intervals vs Unicode 4, rank-bm25 and old BM25; other comparisons inconclusive.",15,"#b2c3d9"),t(36,706,zh?"BM25S 查询更快；召回加速比较旧版解释路径，不是与 BM25S 的速度比。":"BM25S queries are faster; recall speedup compares the old explanation path, not BM25S.",15,"#a6b8cf"),"</svg>");return a.join("\n")+"\n";
}
for (const zh of [false, true]) {
  const out = path.join(__dirname, "v12-transfer" + (zh ? ".zh-CN" : "") + ".svg");
  const expected = renderTransfer(snap, zh);
  if (process.argv.includes("--check")) {
    if (fs.readFileSync(out, "utf8") !== expected) throw Error("Stale v1.2 figure: " + out);
  } else fs.writeFileSync(out, expected, "utf8");
}
