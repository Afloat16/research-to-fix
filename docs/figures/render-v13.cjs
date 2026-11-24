"use strict";
const fs = require("node:fs"), path = require("node:path");
function render(s,zh){
 const esc=x=>String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"),t=(x,y,l,size=20,c="#e7edf7",weight=400,anchor="start")=>`<text x="${x}" y="${y}" font-size="${size}" fill="${c}" font-weight="${weight}" text-anchor="${anchor}">${esc(l)}</text>`,rect=(x,y,w,h,f,rx=10)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${f}"/>`;
 const c=s.capture,r=s.repair,p=s.planning, m=p.overall.methods,old=m.legacy,now=m.coverage;
 const a=[`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 690" role="img" aria-labelledby="title desc" font-family="system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">`,`<title id="title">${zh?"v1.3 真实执行与证据复核":"v1.3 real execution and evidence review"}</title>`,`<desc id="desc">${zh?"实际 Python 子进程、命名故障注入和模拟检索状态的三组有边界实验。":"Three bounded experiments: actual local Python subprocesses, named evidence perturbations and simulated search statuses."}</desc>`,rect(0,0,1040,690,"#101a2c",22),t(36,42,"RESEARCH TO FIX  /  v1.3.0",15,"#69d6cf",700),t(36,91,zh?"修复不靠猜，验证不靠自述。":"Repair with evidence, not assertions.",38,"#ffffff",750),t(36,124,zh?"冻结测试 · 原始执行结果 · 独立摘要 · 研究覆盖":"Frozen tests · observed outcomes · independent digests · research coverage",18,"#b2c3d9")];
 const cards=[[`${r.subprocess_test_runs}`,zh?"真实 Python 子进程":"actual Python test runs"],[`${r.actual_test_outcomes}`,zh?"方法级测试结果":"test-method outcomes"],[`${r.audited_bundles}/${r.candidate_comparisons}`,zh?"证据包通过一致性审计":"consistent evidence bundles"]];
 cards.forEach(([value,label],i)=>{const x=36+326*i;a.push(rect(x,148,316,102,"#1e2d43",14),t(x+18,196,value,35,"#72e0d3",730),t(x+18,228,label,16,"#c8d5e6",500));});
 const bar=(x,y,v,max,width,key,color,label,display)=>{a.push(t(x,y-9,label,15,"#c8d5e6",500),rect(x,y,width,20,"#2a3950",5),`<rect x="${x}" y="${y}" width="${(width*v/max).toFixed(3)}" height="20" rx="5" fill="${color}" data-metric="${key}" data-value="${v}"/>`,t(x+width+12,y+16,display,16,"#fff",650));};
 a.push(rect(36,268,476,217,"#1b293e",14),rect(528,268,476,217,"#1b293e",14),t(54,302,zh?"13 类证据不一致 · 拒绝数量":"13 evidence faults · rejected",21,"#fff",650),t(546,302,zh?"7 个缺陷 · 不完整修复误放行":"7 defects · incomplete fixes accepted",20,"#fff",650));
 bar(54,343,c.rejected_faults.verify_unpinned,c.fault_types,345,"capture.verify_unpinned","#8897ad",zh?"未独立固定摘要：仅校验哈希":"Unpinned hash verification",`${c.rejected_faults.verify_unpinned}/${c.fault_types}`);
 bar(54,401,c.rejected_faults.audit_unpinned,c.fault_types,345,"capture.audit_unpinned","#69d6cf",zh?"未独立固定摘要：语义审计":"Unpinned semantic audit",`${c.rejected_faults.audit_unpinned}/${c.fault_types}`);
 const narrow=r.narrow_candidates_rejected_by_full_suite;
 bar(546,343,r.symptom_only_accepted-r.full_suite_accepted,narrow,345,"repair.symptom_only_incomplete","#e9aa70",zh?"仅通过原症状测试":"Original symptom only",`${narrow}/${narrow}`);
 bar(546,401,r.rows.filter(x=>x.variant==="narrow"&&x.full_suite_accept).length,narrow,345,"repair.full_suite_incomplete","#69d6cf",zh?"完整冻结测试":"Full frozen suite",`0/${narrow}`);
 a.push(t(54,457,zh?"独立固定摘要：两种方式均拒绝全部 13 类。":"Pinned manifest: both reject all 13 faults.",14,"#a6b8cf"),t(546,457,zh?"完整测试同时接受 7/7 个预设正确修复。":"Full suite also accepts all 7 designed fixes.",14,"#a6b8cf"),rect(36,501,968,134,"#1b293e",14),t(54,532,zh?`${p.pairs} 组配对模拟 · 完整六阶段覆盖`:`${p.pairs} paired simulations · all six stages completed`,20,"#fff",650));
 bar(54,570,old.all_stages_completed,1,327,"planning.legacy_all_stages","#8897ad",zh?"旧策略":"Legacy",`${(100*old.all_stages_completed).toFixed(1)}%`);
 bar(546,570,now.all_stages_completed,1,327,"planning.coverage_all_stages","#69d6cf",zh?"覆盖优先":"Coverage-first",`${(100*now.all_stages_completed).toFixed(1)}%`);
 a.push(t(54,617,zh?"固定模拟状态，不是实时检索成功率。":"Fixed simulated statuses, not live search success.",14,"#a6b8cf"),t(36,664,zh?"控制实验不代表模型修复率、通用攻击检测或真实性认证。":"Controlled diagnostics, not agent repair accuracy, general attack detection or authenticity.",15,"#a6b8cf"),"</svg>");return a.join("\n")+"\n";
}
const snap = JSON.parse(fs.readFileSync(path.join(__dirname, "v13-snapshot.json"), "utf8"));
for (const zh of [false, true]) {
  const out = path.join(__dirname, "v13-evidence" + (zh ? ".zh-CN" : "") + ".svg");
  const expected = render(snap, zh);
  if (process.argv.includes("--check")) {
    if (fs.readFileSync(out, "utf8") !== expected) throw Error("Stale v1.3 figure: " + out);
  } else fs.writeFileSync(out, expected, "utf8");
}
