/* Render exact external holdout summary into local bilingual SVGs. */
const fs = require("node:fs");
const path = require("node:path");

function render(data, zh = false) {
  const e = v => String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[c]));
  const methodLabels = {"precision_field4":"R2F Precision Field", "v1_contextual":"R2F v1 Contextual",
                        "sqlite_unicode4":"SQLite Unicode (4:1)"};
  const methods = ["precision_field4", "v1_contextual", "sqlite_unicode4"];
  const colors = ["#007F83", "#466B89", "#9A6B32"];
  const labels = {programmers:"Programmers",stats:"Stats",scifact:"SciFact",nasa:"NASA Science Repos"};
  const order = ["programmers","stats","scifact","nasa"];
  const format = x => Number(x).toFixed(4);
  const sign = x => (x >= 0 ? "+" : "") + format(x);
  const title = zh ? "外部保留集：排序质量与竞争基线" : "External holdouts: ranking quality vs. baselines";
  const sub = zh ? "开发集选型后冻结参数 · 同语料、同查询、同 Top-10 · 0–1 坐标"
                 : "Frozen after development · same corpus, queries and top-10 · 0–1 scale";
  const W = 1120, H = 750, pW = 525, pH = 250;
  let o = '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 '+W+' '+H+'">\n';
  o += '<title id="title">'+e(title)+'</title><desc id="desc">'+e(sub)+"</desc>\n";
  o += '<rect width="'+W+'" height="'+H+'" rx="16" fill="#F7FAFC"/>\n';
  const txt = (x,y,t,size=16,weight="400",color="#243B53",anchor="start") =>
    '<text x="'+x+'" y="'+y+'" font-family="Arial, Noto Sans CJK SC, sans-serif" font-size="'+size+'" font-weight="'+weight+'" fill="'+color+'" text-anchor="'+anchor+'">'+e(t)+'</text>\n';
  o += txt(30,42,title,28,"700") + txt(30,72,sub,15,"400","#526577");
  order.forEach((name,i)=>{
    const x = 24+(i%2)*552, y = 96+Math.floor(i/2)*264, report=data.reports[name];
    o += '<rect x="'+x+'" y="'+y+'" width="'+pW+'" height="'+pH+'" rx="12" fill="#FFFFFF" stroke="#D9E3EB"/>\n';
    o += txt(x+18,y+31,labels[name],21,"700");
    if(!report) {
      o += txt(x+18,y+67,zh?"未取得可验证结果":"No verified result",17,"600","#965A20");
      return;
    }
    o += txt(x+18,y+56,report.documents.toLocaleString("en-US")+(zh?" 文档 · ":" documents · ")+report.queries+(zh?" 查询":" queries"),14,"400","#526577");
    methods.forEach((m,k)=>{
      const v=report.methods[m]["ndcg@10"], yy=y+82+k*36;
      o += txt(x+18,yy+14,methodLabels[m],14,k===0?"700":"400");
      o += '<rect x="'+(x+184)+'" y="'+yy+'" width="250" height="16" rx="4" fill="#E9EFF3"/>\n';
      o += '<rect data-dataset="'+name+'" data-method="'+m+'" data-metric="ndcg@10" data-value="'+v+'" x="'+(x+184)+'" y="'+yy+'" width="'+(250*v)+'" height="16" rx="4" fill="'+colors[k]+'"/>\n';
      o += txt(x+505,yy+14,format(v),14,"700","#243B53","end");
    });
    const ci=report.paired_ndcg.precision_field4_vs_sqlite_unicode4;
    const color=ci.ci95_low>0?"#007F83":ci.ci95_high<0?"#A34E3D":"#526577";
    o += txt(x+18,y+205,(zh?"相对 SQLite 的差值：":"Delta vs SQLite: ")+sign(ci.mean_delta),15,"700",color);
    o += txt(x+18,y+230,"95% CI ["+sign(ci.ci95_low)+", "+sign(ci.ci95_high)+"]",14,"400",color);
  });
  const tok=data.tokenizer;
  const feature=tok.precision_feature_parity;
  o += '<rect x="24" y="638" width="1072" height="65" rx="10" fill="#E7F3F2"/>\n';
  o += txt(40,664,(zh?"基础分词：":"Base tokenizer: ")+tok.speedup.toFixed(2)+"×  |  "+(zh?"精确特征提取：":"Precision features: ")+feature.speedup.toFixed(2)+"×",19,"700","#00696B");
  o += txt(40,686,zh?"4,096 篇真实文档、五次配对重复、词项序列完全一致；不是整个修复流程加速。":"4,096 real documents, five paired repeats, identical token sequences; not whole-workflow speedup.",14,"400","#526577");
  o += txt(24,727,zh?"置信区间为逐数据集配对 Bootstrap，未做多重比较校正；不是 Agent 修复率或排行榜。":"Pointwise paired bootstrap intervals; no multiplicity adjustment. Not agent repair rate or leaderboard.",13,"400","#526577");
  return o+"</svg>\n";
}

if (require.main === module) {
  const snapshot=JSON.parse(fs.readFileSync(path.join(__dirname,"independent-snapshot.json"),"utf8"));
  for(const zh of [false,true]) {
    const file=path.join(__dirname,"independent-holdout"+(zh?".zh-CN":"")+".svg");
    const actual=render(snapshot,zh);
    if(process.argv.includes("--check")) {
      if(fs.readFileSync(file,"utf8")!==actual) throw Error("Stale figure: "+file);
    } else fs.writeFileSync(file,actual);
  }
}
module.exports={render};
