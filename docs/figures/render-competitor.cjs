/* Deterministic bilingual BM25S and optional vector-score diagnostics. */
const fs = require("node:fs");
const path = require("node:path");

function render(data, zh = false) {
  const esc = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[c]));
  const ink="#18334D", muted="#526579", teal="#007F83", blue="#315B9A", amber="#A8661C", grey="#8290A1", line="#D9E3EC", bg="#F5F8FB";
  const W=1180, H=645;
  const title=zh?"专用开源检索对照与评分加速":"Specialized retrieval baseline and scoring acceleration";
  const desc=zh?"SciFact 与 NASA 开源仓库诊断；向量化仅加速相同词项的评分路径，非端到端 Agent 修复。":"SciFact and NASA repository diagnostics; vectorization accelerates identical prepared-token scoring, not end-to-end agent repair.";
  const tx=(x,y,t,size=17,weight=400,color=ink,anchor="start")=>'<text x="'+x+'" y="'+y+'" font-family="Arial, Noto Sans CJK SC, Microsoft YaHei, sans-serif" font-size="'+size+'" font-weight="'+weight+'" fill="'+color+'" text-anchor="'+anchor+'">'+esc(t)+'</text>\n';
  const rect=(x,y,w,h,fill="#fff",stroke="none",rx=8,extra="")=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="'+fill+'" stroke="'+stroke+'" rx="'+rx+'" '+extra+'/>\n';
  let o='<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 '+W+' '+H+'">\n<title id="title">'+esc(title)+'</title><desc id="desc">'+esc(desc)+'</desc>\n';
  o+=rect(0,0,W,H,bg,line,14)+tx(28,41,title,27,700)+tx(28,67,zh?"保留集公开后的诊断 · 相同文档和 Top-10 · 质量与速度分开报告":"Post-holdout diagnostic · same documents and Top-10 · quality and speed reported separately",15,400,muted);
  const methods=[["precision_field4","R2F Precision",teal],["v1_contextual","R2F Contextual",blue],["bm25s_native","BM25S English",amber],["bm25s_matched","BM25S Matched",grey],["sqlite_porter","SQLite Porter","#67758E"]];
  for(const [i,ds] of ["scifact","nasa"].entries()){
    const d=data.diagnostics[ds], v=data.vector[ds], x=26+i*569;
    o+=rect(x,86,552,319,"#fff",line,10)+tx(x+18,117,ds==="nasa"?"NASA Science Repos":"SciFact",21,700)+tx(x+18,140,d.documents.toLocaleString("en-US")+(zh?" 文档 · ":" docs · ")+d.queries+(zh?" 查询":" queries"),14,400,muted);
    o+=tx(x+20,168,"nDCG@10 ↑",15,700)+tx(x+475,168,"0–1",13,400,muted);
    for(const [j,[id,label,c]] of methods.entries()){
      const y=182+j*40, val=d.methods[id]["ndcg@10"];
      o+=tx(x+19,y+15,label,14,j===0?700:400);
      o+=rect(x+175,y,285,17,"#E8EEF2","none",3)+rect(x+175,y,285*val,17,c,"none",3,'data-dataset="'+ds+'" data-method="'+id+'" data-value="'+val+'"');
      o+=tx(x+530,y+14,val.toFixed(4),14,600,ink,"end");
    }
    const delta=d.paired_ndcg.precision_field4_vs_bm25s_matched;
    o+=tx(x+18,392,(zh?"差值区间 vs BM25S Matched：":"95% delta vs BM25S Matched: ")+"["+delta.ci95_low.toFixed(4)+", "+delta.ci95_high.toFixed(4)+"]",13,500,muted);
    o+=rect(x,418,552,165,"#fff",line,10)+tx(x+18,449,zh?"相同倒排索引 · 预分词评分 P50":"Same postings · prepared-token score P50",17,700);
    if(v && v.exact_top11_scores_and_ids){
      const base=v.methods.python.p50_ms, fast=v.methods.numpy.p50_ms, max=Math.max(base,fast);
      for(const [k,[label,val,c]] of [[zh?"纯 Python":"Pure Python",base,grey],["NumPy (opt-in)",fast,teal]].entries()){
        const y=469+k*35;
        o+=tx(x+18,y+14,label,14,500)+rect(x+175,y,285,16,"#E8EEF2","none",3)+rect(x+175,y,285*val/max,16,c,"none",3)+tx(x+530,y+14,val.toFixed(3)+" ms",14,600,ink,"end");
      }
      o+=tx(x+18,562,v.p50_speedup.toFixed(2)+"× "+(zh?"评分加速 · 精确 Top-11 ID 与分数一致":"score speedup · exact Top-11 ID/score parity"),15,700,teal);
    }else{o+=tx(x+18,486,zh?"未验证，不发布加速结论":"Not verified; no acceleration claim",15,500,amber);}
  }
  o+=tx(28,610,zh?"BM25S 原始查询速度更快；额外内存、构建成本与端到端效果不在评分计时中。":"BM25S raw queries remain faster; extra memory, construction and end-to-end performance are separate.",13,400,muted);
  o+=tx(28,629,zh?"冻结实测报告："+data.source.run_id+" · 逐数据集区间未经多重比较校正。":"Frozen run "+data.source.run_id+" · pointwise intervals without multiplicity adjustment.",13,400,muted);
  return o+"</svg>\n";
}
if(require.main===module){
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,"competitor-snapshot.json"),"utf8"));
  for(const zh of [false,true]){
    const target=path.join(__dirname,"competitor-diagnostic"+(zh?".zh-CN":"")+".svg");
    const svg=render(data,zh);
    if(process.argv.includes("--check")){if(fs.readFileSync(target,"utf8")!==svg)throw Error("Stale figure: "+target);}
    else fs.writeFileSync(target,svg);
  }
}
module.exports={render};
