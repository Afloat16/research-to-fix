# Research to Fix

**从难以定位的故障，到有证据、可验证、可复用的修复。**

[![持续集成](https://github.com/Afloat16/research-to-fix/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/Afloat16/research-to-fix/actions/workflows/checks.yml)
[![性能回归](https://github.com/Afloat16/research-to-fix/actions/workflows/performance.yml/badge.svg?branch=main)](https://github.com/Afloat16/research-to-fix/actions/workflows/performance.yml)
[![MIT License](https://img.shields.io/badge/License-MIT-315B9A.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-007F83.svg)](#安装)

[English](README.md) · **简体中文** · [快速安装](#安装) · [基准实验](#性能与实验) · [详细使用手册](docs/USER_GUIDE.zh-CN.md)

**先研究，再循证修复，最后用实验说话。** Research to Fix 是遵循 [Agent Skills](https://agentskills.io/specification) 格式的循证研究与修复工作流，适用于陌生报错、疑难 Bug、论文复现失败、训练异常和性能退化。它让 Agent 不只是猜测解决方案，而是调查可借鉴的先前工作，将证据映射到当前代码，适配或组合可行方案，并对照原症状和回归测试验证结果。

![图 1：问题指纹、本地召回与外部研究、证据映射、修复验证、复核封存和迭代闭环。](docs/figures/workflow.zh-CN.svg)

*图 1｜宿主 Agent 承担研究和授权执行，本地确定性工具负责案例召回、记录检查与证据封存；验证失败则反馈到研究环节。*

创意与工作流设计：[Afloat16](https://github.com/Afloat16)。MIT 开源。**不要求 Python 第三方运行时依赖、托管搜索服务或向量模型。**


## v1.2.0 — 精确召回加速与研究审计

![精确召回加速：六种负载、加速倍数及严格一致性](docs/figures/v12-recall.zh-CN.svg)

**中位召回加速 2.85–4.83 倍 · 样本峰值分配减少 59.4–65.8% · 288/288 查询结果严格一致。** 新版索引路径保留全部阈值命中计数，仅选择并解释 Top-K 返回项；所有实测查询的评分、文档 ID、计数和解释均与旧版完整解释路径一致。六种生成负载、5,000 篇文档、每种 48 条查询、三次计时重复；比较预分词热索引，不代表端到端修复速度。无新增运行时依赖。

研究账本新增阶段覆盖审计，区分未规划、未完成或混合状态、已完成但无有效观测、已完成且有有效观测；不能把未找到反证当作反证不存在。新增[同条件多臂 Agent 评测协议](benchmarks/AGENT_COMPARISON_PROTOCOL.md)，冻结模型、任务、种子、预算及干预摘要，不把未运行的 Agent 实验当成真实修复成绩。

[真实 CI](https://github.com/Afloat16/research-to-fix/actions/runs/45366494938) · [详细结果与复现](benchmarks/V12_RESULTS.md) · [原始快照](docs/figures/v12-snapshot.json) · [独立迁移协议](benchmarks/TRANSFER_V12_PROTOCOL.md)。

### 新增外部迁移：Mathematica

![Mathematica 八种检索方法对照与精确召回实测](docs/figures/v12-transfer.zh-CN.svg)

**16,705 篇文档 · 804 条真实标签查询 · 八种预先冻结的方法。** 未利用本语料调整排序或参数。Precision Field 的 nDCG@10 = **0.2366**，较 SQLite Unicode 4 提升 9.71%、较真实 rank-bm25 0.2.2 提升 5.87%（点态配对 95% 区间为正）。Contextual 得分 0.2389；相对 Contextual、SQLite Porter 及两种 BM25S 的区间跨零。BM25S 原始查询明显更快。精确相对阈值召回在 **全部 804 条查询**上计数、ID、分数及解释完全一致；单次配对预分词热索引 P50 **35.36 → 7.24 ms（4.88 倍）**。五套公开评测语料合计 101,597 篇文档、2,668 条有标签查询；按语料独立报告，不混合构造排行榜。

[八种方法实测](https://github.com/Afloat16/research-to-fix/actions/runs/45366934273) · [完整指标、区间与复现](benchmarks/V12_RESULTS.md#mathematica-external-transfer) · [原始产物](https://github.com/Afloat16/research-to-fix/actions/runs/45366934273/artifacts/14906654892)。

## v1.1.0 — 外部保留集与精准检索

![外部保留集排序性能与配对区间](docs/figures/independent-holdout.zh-CN.svg)

**84,892 篇文档 · 1,864 条有标签保留查询 · 四套公开语料。** 可选 `precision_field` 融合精确词、词干、有序短语及独立字段归一。在程序设计（+11.52%）、统计学（+11.49%）和 NASA（+8.32%）中，相对开发集预选的 SQLite 对照，nDCG@10 的逐数据集配对 95% 区间为正。SciFact 未证明确切优势，SQLite Porter 的实测分数最高；统计学的旧 Contextual 仍最高。相对旧 Contextual 的四组区间均跨零，因此不替换默认模式。索引构建仍较慢。[实测 CI](https://github.com/Afloat16/research-to-fix/actions/runs/45359141496) · [完整证据与复现实验](benchmarks/INDEPENDENT_RESULTS.md) · [冻结报告](docs/figures/independent-snapshot.json)。

### 专用开源检索对照与精确评分加速

![BM25S 对照及可选精确评分加速](docs/figures/competitor-diagnostic.zh-CN.svg)

保留集公开后，对真实 BM25S 0.2.14、R2F 和 SQLite 进行同语料诊断。NASA 上 Precision Field 实测最高（nDCG@10 0.4665 vs BM25S Matched 0.4389，+6.27%，点态配对 95% 区间 [0.0036, 0.0525]）；SciFact 未证实 R2F 优势。BM25S 原始查询与索引构建更快。可选 NumPy 评分适配器使同索引预分词评分中位耗时加速 5.22× / 6.70×，512 条真实查询 Top-11 文档 ID 与分数完全一致，不含额外适配器初始化、内存和建索引成本。默认工具无强制依赖；不是 Agent 修复率。[完整对照与代价](benchmarks/COMPETITOR_RESULTS.md) · [真实 CI](https://github.com/Afloat16/research-to-fix/actions/runs/45361899401)。

## v1.0.0 — 多轮研究与可核验决策

![v1.0.0 论文—代码配对排序、模拟调度和精确注意力实测](docs/figures/release-v1.zh-CN.svg)

**98.44% / 95.83% Recall@6**（原始与跨领域算法开发语料，显式论文—代码配对策略）；**2.93×** 模拟请求调度加速；**96.06%** 本地 CPU 精确注意力在线递推峰值追踪分配下降。这些是限定实验条件下的可复现结果，不是通用修复准确率或 GPU 加速结论。[实测 CI](https://github.com/Afloat16/research-to-fix/actions/runs/45355977079) · [冻结 JSON](docs/figures/v1-snapshot.json) · [正式版本说明](docs/releases/v1.0.0.md)。

- 多轮研究账本最多四轮，记录去重后的查询预算、计划绑定的结果及覆盖缺口，不自动重试。
- 可选公开元数据入口支持 GitHub、arXiv、Crossref、Hugging Face、Semantic Scholar、OpenAlex 和 DBLP；均衡调度与最多四个独立来源工作线程需显式启用。
- 配对排序提升显式实现关系，不把 URL 提及冒充实现；冲突标识、撤回/撤稿警告进入复核。默认 BM25 保持兼容。
- 实验协议锁及候选设计锁检测冻结后变更；全配对 Pareto 比较同种子实测，保留真正的取舍。

**真实访问范围：**一次明确授权的已知条目探测通过 GitHub、Crossref、OpenAlex 返回 15 条观测，命中目标论文 DOI 和代码仓库。arXiv 不可用、Semantic Scholar 限流、DBLP 响应格式无效。[探测记录](https://github.com/Afloat16/research-to-fix/actions/runs/45355435962)。这不是代表性检索准确率评测；元数据入口不读取全文，优先使用宿主真实浏览能力。

## 从哪里开始

| 我想… | 从这里开始 |
| --- | --- |
| 让 Agent 调研并修复疑难问题 | [安装 Skill](#安装) · [示例请求](#使用) |
| 复用以往修复经验 | [记录案例并检索复用](#记录案例并检索复用) |
| 比较算法和真实实验数据 | [性能与实验](#性能与实验) · [基准协议](benchmarks/README.md) |
| 了解全部命令和证据规则 | [详细使用手册](docs/USER_GUIDE.zh-CN.md) · [案例模板](skills/research-to-fix/references/case-template.md) |

## 它做什么

- **有目的地研究：** 提取问题指纹，规划均衡查询，按相关性检索 GitHub Issue/PR、Hugging Face、技术社区、原始论文与作者资料，区分可靠证据和待核实线索。
- **有判断地复用：** 召回历史案例，比较版本与机制，把候选解决方案映射到本地文件与符号；相关性不能证明兼容性。
- **可比较地修复：** 保留原症状检查和回归验收标准，记录候选方案、失败轮次与实际前后结果。
- **可审计地交付：** 检查案例声明的一致性、复核证据和测试明细的缺口，并可选用 SHA-256 清单封存指定产物。

完整方法见[来源检索指南](skills/research-to-fix/references/source-playbook.md)、[证据判定](skills/research-to-fix/references/evidence-rules.md)和[修复流程](skills/research-to-fix/references/repair-workflow.md)。

## 安装

正式版安装包：[v1.2.0 与 SHA-256 校验文件](https://github.com/Afloat16/research-to-fix/releases/tag/v1.2.0)。解压后将 `research-to-fix/` 目录放入宿主 Skill 目录；安装包只包含提交的 Skill、许可与版本，不包含实验日志或本地用户数据。

使用支持 Agent Skills 格式的宿主。核对安装工具后运行：

```bash
npx skills add Afloat16/research-to-fix --skill research-to-fix
```

也可克隆仓库，将 `skills/research-to-fix/` 完整复制到宿主的 Skill 目录。辅助工具要求 **Python 3.10+**。搜索、浏览和执行能力主要由宿主提供；可选公开元数据检索需明确授权，本项目不捆绑爬虫、登录凭据或模型 API。

## 使用

在支持的宿主 Agent 中试试：

```text
使用 $research-to-fix：我们的多 GPU 训练偶发卡死。
先复现并记录环境，调研相关 Issue 和修复 PR，比较版本与机制，
适配兼容的解决方案，再验证原始故障和回归测试。
记录证据缺口与失败的迭代轮次。
```

```text
使用 $research-to-fix：论文复现结果明显低于作者报告。
查原始论文、作者代码、模型/数据配置和复现讨论，
在相同数据切分、随机种子和资源预算下比较候选方案，
最后验证最有证据支持的改动。
```

## 面向算法研究者的研究—决策引擎

**找论文、找原始开源实现、找替代机制，再用同条件实验选方案。** 针对算法瓶颈、复现失败和性能退化，新增研究计划、可选的公开 API 元数据发现、跨来源去重排序、论文—代码关联图、证据缺口诊断以及实测多方案决策。优先使用宿主真实联网搜索；只在脱敏查询获授权后启用固定公开 API。

```text
使用 $research-to-fix 优化这个算法瓶颈。
调研相关论文、作者开源实现、Issue/PR 和失败案例。
至少比较两个不同机制的可行方案（如有）。
固定数据集、随机种子、硬件、指标和验收阈值，实际进行同条件实验。
展示 Pareto 最优方案、精度/耗时/资源取舍，实施最合适的方案，
最后运行原始故障与回归测试并保存证据。
```

| 环节 | 工具 |
| --- | --- |
| 有界多轮研究账本 | `research_session.py start / next / append / review` |
| 单轮公开问题指纹与查询规划 | `research_workflow.py plan` |
| 明确授权后检索公开元数据 | `public_discovery.py` |
| 去重、排序、证据关联与缺口发现 | `research_workflow.py triage` |
| 冻结设计与同条件实测比较 | `solution_compare.py --freeze-design` / `--comparison` |

![研究决策架构、论文开源来源检索对照和实测多方案 Pareto 结果](docs/figures/research-decision.zh-CN.svg)

*历史开发回放：32 个真实来源身份、44 条观测、16 条查询。默认短名单的 Recall@6 为 92.19%、完整论文—代码配对召回 87.5%，与 Stemmed BM25 基线相同；本样本论文+代码覆盖 100%。纯分面排序整体较弱，故作为可选策略。五次本地方差配对实测保留中心化两遍、在线递推两个非支配方案。[实测 CI](https://github.com/Afloat16/research-to-fix/actions/runs/45343672697) · [冻结实验报告](docs/figures/research-snapshot.json)。不是实时 API 的独立评测，也不代表 Agent 修复成功率。*

查看[完整用法与 JSON 格式](skills/research-to-fix/references/research-decision.md)、[论文/开源来源基准](benchmarks/README.md#algorithm-discovery-and-decision)及[真实数值方差修复实验](examples/numerical-variance/README.md)。联网与执行依赖宿主能力及授权；不能保证任何算法问题必定解决。

## 性能与实验

检索引擎采用双路径架构：单次查询使用低启动成本扫描；批量查询复用一次校验的内存倒排索引。五种可解释词项排序兼顾兼容性、技术标识符扩展、英文词形归一、精确词/词干融合及短语特征实验。

![图 2：单次扫描和批量内存快照的双路径检索架构。](docs/figures/retrieval-architecture.zh-CN.svg)

*图 2｜两条路径共享默认评分公式、确定性平分排序、案例校验与候选过滤。不持久化查询缓存；案例修改后重新构建快照。*

### 合成数据集：检索准确性对比

![图 3：固定双语合成数据集上八种方法的 MRR@5、Recall@5 零基线横向条形图。](docs/figures/synthetic-ranking.zh-CN.svg)

*图 3｜40 个故障描述、80 条正例查询和 3 条无关查询。Hybrid 在这组开发样本上 MRR@5、Recall@5、nDCG@5 均为 1.00；所有受测方法对三条无关查询均返回空结果。*

### 真实公开 Issue：检索质量与速度对比

![图 4：真实公开 Issue 数据上八种方法的 MRR@5、Recall@5 和中位查询延迟。](docs/figures/github-ranking.zh-CN.svg)

*图 4｜44 个公开 Issue 标题、18 条有标签查询。Stemmed 将旧版 MRR@5 从 50.93% 提升至 72.22%，Recall@5 从 61.11% 提升至 83.33%。SQLite Porter 的 MRR 更高（74.07%）、召回率相同；Stemmed 的实测中位检索延迟更低（26.7 vs 39.1 µs）。该小样本含未标注干扰项，不是独立盲测。*

### 实测吞吐量与内存

**27.05×** 批量案例召回加速 · **109.34×** 稀疏索引热查询加速 · **76.4%** 索引常驻分配内存下降（对应以下配对负载）。

![图 5：批量查询、热索引查询与索引内存的配对实验条形图。](docs/figures/efficiency.zh-CN.svg)

*图 5｜最近一次已记录实验：120 个合成案例 × 32 条查询；5,000 个生成文档 × 64 条稀疏查询。批量报告与 Top-10 评分完全一致。内存不含输入语料；热查询不含索引构建时间，加速比只对应此负载。*

**可复现性。** 图 3–5 的数字来自同一次已完成的 [GitHub Actions 性能实验](https://github.com/Afloat16/research-to-fix/actions/runs/45339912941)，环境为 Linux / Python 3.13.18。参阅[原始 JSON 快照](docs/figures/benchmark-snapshot.json)、[性能技术报告](docs/PERFORMANCE.md)、[数据集来源和复现命令](benchmarks/README.md)及[图表生成源码](docs/figures/README.md)。该实验对应代码运行了 166 项辅助工具测试和 6 项示例测试，七个操作系统/Python CI 组合均通过（[测试记录](https://github.com/Afloat16/research-to-fix/actions/runs/45339912917)）。

> 检索和资源开销指标不等于 Agent 修复成功率。两套排名样本均用于开发迭代，不能据此宣称全面领先。外部 BEIR 与 NASA 实测见上文；同条件 SWE-bench Agent 修复对比尚未完成。

## 记录案例并检索复用

从仓库根目录执行内置流式统计示例的实际故障/修复对比，选择一个不存在的输出目录：

```bash
python examples/streaming-metrics/record_case.py --output /tmp/r2f-case
python skills/research-to-fix/scripts/research_case.py validate /tmp/r2f-case/case.json
python skills/research-to-fix/scripts/research_case.py recall \
  --cases-dir /tmp/r2f-case --error 'single-use iterator count mean' --format markdown
```

示例保留故障版与修复版的实际命令、退出码、逐测试结果、日志和源码快照。[查看完整案例](examples/streaming-metrics/README.md)。召回仅访问显式案例目录顶层，且只考虑结构校验通过并声明为 `solved` 的记录。

## 高吞吐召回与实测排序

多条相关查询使用单独的 JSON 文件（1–128 条字符串，不要放在案例语料目录内）：

```bash
python skills/research-to-fix/scripts/research_case.py recall-batch \
  --cases-dir ./cases --queries-file ./queries.json --ranking stemmed
```

| 模式 | 适用场景 |
| --- | --- |
| `bm25`（默认） | 保持旧版精确评分与排序契约 |
| `technical` | 技术标识符变体和原症状加权 |
| `stemmed` | 英文词形变化影响相似问题匹配 |
| `hybrid` | 同时保留精确技术词与词干特征 |
| `contextual` | 尝试有序短语信号 |
| `precision_field` | 精确词、词干、短语与独立字段归一（可选） |

具体限制、评分解释及快照行为见[本地案例复用指南](skills/research-to-fix/references/case-reuse.md)。任何排序均不证明修复正确性。

## 辅助工具

标准库 CLI `skills/research-to-fix/scripts/research_case.py` 提供：

| 命令 | 用途 |
| --- | --- |
| `queries` | 离线中英文研究计划；对外发送前需人工复核 |
| `init` | 创建新的 blocked 案例模板，不覆盖已有文件 |
| `recall` / `recall-batch` | 单条或批量本地案例召回 |
| `validate` | 检查 schema v1 声明与引用一致性 |
| `review` | 复核证据、比较条件及测试细节缺口 |

[查看完整命令和参数](docs/USER_GUIDE.zh-CN.md#辅助工具)。

## 完整性复核与证据封存

```bash
python skills/research-to-fix/scripts/research_case.py review /tmp/r2f-case/case.json
python skills/research-to-fix/scripts/case_bundle.py seal --directory /tmp/r2f-case
python skills/research-to-fix/scripts/case_bundle.py verify --directory /tmp/r2f-case
```

证据工具封存 `case.json`、声明的运行产物和显式选择的文件。验证检查文件字节是否与清单一致，而不认证作者或实验真实性。需要检测相对于原清单的篡改时，应独立保存清单摘要。参见[证据包指南](skills/research-to-fix/references/evidence-bundle.md)和[安全政策](SECURITY.md)。分享前人工复核脱敏。

## 项目结构

```text
skills/research-to-fix/    Agent Skill、参考资料、离线工具与可选公开检索
examples/                 可复现修复实例
benchmarks/               标签数据集、基线算法与性能门禁
docs/figures/             可再生成矢量图与原始实测数据
docs/                     使用手册、实验方法与发布标准
tests/                    回归与行为测试
```

## 验证与贡献

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
```

对比实验请遵循[基准协议](benchmarks/README.md)。欢迎贡献真实复现、可比较的验收检查、来源链接、明确局限和经过脱敏的案例。参见[贡献指南](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md)、[安全政策](SECURITY.md)、[发布清单](docs/RELEASE_CHECKLIST.md)与[变更记录](CHANGELOG.md)。

## 许可

[MIT](LICENSE)。

## 相关开源项目

浏览 [Afloat16 项目导航](docs/PROJECTS.zh-CN.md)、[需求调研](docs/DEMAND_REVIEW.zh-CN.md)和[推广记录](docs/OUTREACH.zh-CN.md)。
