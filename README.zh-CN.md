# Research to Fix

[English](README.md) | **简体中文**

**查到相似问题，适配或组合已有方案，再验证本地修复。**

Research to Fix 是一个遵循 [Agent Skills 格式](https://agentskills.io/specification)的调研与修复工作流。它让模型在陌生报错、难复现 bug、训练异常或性能退化时，先查别人是否已经解决或给出可行路线，再对照当前项目的代码、版本和运行条件实施修复。兼容的方案部件可以组合使用，并明确记录各自贡献、本地适配及整体验证。

创意与工作流设计：**[Afloat16](https://github.com/Afloat16)**。维护者：**Afloat16**。

## 从哪里开始

- 想让模型实际调研并修复项目：安装后使用 [示例请求](#使用)。
- 想了解来源与核验方法：阅读 [来源检索指南](skills/research-to-fix/references/source-playbook.md)和 [证据判定](skills/research-to-fix/references/evidence-rules.md)。
- 想先检查一个可复现的小案例：查看 [流式统计案例](examples/streaming-metrics/README.md)。
- 想复用已有修复经验：先 [记录案例并检索复用](#记录案例并检索复用)，目录由你明确指定。
- 想记录多轮调研或交接证据：使用 [辅助工具](#辅助工具)和 [记录模板](skills/research-to-fix/references/case-template.md)。

## 它做什么

| 环节 | 产物 |
| --- | --- |
| 问题指纹 | 去敏错误、环境/版本、调用链、最小复现、成功标准 |
| 本地案例复用 | 相关已有方案、命中词、版本事实、来源引用及需要重新核验的限制 |
| 跨来源调研 | GitHub、Hugging Face、知乎、小红书、正式论文、学者与实验室的可核验证据 |
| 适用性分析 | 来源条件与本地文件/符号的映射、候选方案、兼容部件、取舍及可证伪假设 |
| 修复与实验 | 小范围代码改动、原症状前后对比、相关回归、成本与限制 |
| 可复核交付 | 原始链接、实际命令、退出码、观测和 solved / partial / blocked 状态 |

不同平台按相关性选择；请求完整覆盖时逐类检索并说明不可用项。知乎与小红书帮助发现经验线索，技术判断继续追溯原始资料或本地实验。知名作者、顶会标签、stars 与点赞不会替代证据。

## 安装

需要支持 `SKILL.md` 的宿主。联网由宿主提供搜索/浏览工具，本项目不捆绑搜索服务、登录凭据或爬虫。辅助脚本只需 Python 3.10+。

安装到支持的宿主（执行前核对你使用的安装工具）：

```bash
npx skills add Afloat16/research-to-fix --skill research-to-fix
```

也可克隆仓库后，将 `skills/research-to-fix` 整个目录复制到宿主的 skills 目录。宿主是否支持自动触发、Python 或 UI 元数据，取决于其自身配置。

## 使用

```text
使用 $research-to-fix：这个项目在多卡训练时偶尔卡住。
请先复现并记录版本，联网查同类问题与修复 PR，
适配或组合兼容方案，解释与当前调用链的差异，再验证完整修复。
```

```text
使用 $research-to-fix：论文复现的结果明显低于报告值。
调研作者代码、Hugging Face 配置、正式论文与社区复现，
列出可行路线，以相同数据切分、种子和预算做对比实验。
```

```text
使用 $research-to-fix：完整覆盖 GitHub、Hugging Face、知乎、
小红书、相关顶刊顶会、学者与实验室。无法访问的来源请如实记录。
```

## 记录案例并检索复用

从仓库根目录运行，先用实际本地测试生成案例，再校验并查询相关案例：

```bash
python examples/streaming-metrics/record_case.py \
  --output /tmp/research-to-fix-example

python skills/research-to-fix/scripts/research_case.py validate \
  /tmp/research-to-fix-example/case.json --format json

python skills/research-to-fix/scripts/research_case.py recall \
  --cases-dir /tmp/research-to-fix-example \
  --error 'single-use iterator count mean' --limit 3 --format markdown
```

选择一个**尚不存在的输出目录**；`/tmp/research-to-fix-example` 只是示例位置。独立的 `record_case.py` 示例会在隔离的临时目录中，以相同测试和命令运行已记录的错误实现与当前修复实现，生成 `case.json`，并将实际日志及逐测试结果保存在 `runs/` 下。这个示例执行固定的本地测试；主辅助工具不执行案例文件中的命令。

使用自己的案例时，将 `recall` 指向对应目录。它只读取该目录顶层的 JSON 文件，仅纳入结构校验通过且声明为 `solved` 的记录。案例目录本身及其 JSON 条目不得为符号链接；显式路径的祖先目录按系统规则正常解析。输出有界摘要与命中理由，不输出整段命令日志。排序使用本地 BM25 关键词匹配，并支持中文相邻字二元组，无需联网、模型、嵌入服务或第三方依赖。没有命中词时返回空结果，也不为凑满数量而加入弱相关案例。

| 召回选项 | 作用 |
| --- | --- |
| `--cases-dir DIR`、`--error TEXT` | 明确指定案例目录及仅供本地词项匹配的问题描述。 |
| `--component TEXT` | 可选组件筛选；去除首尾空白、忽略大小写后精确匹配。 |
| `--version TEXT` | 仅报告字面比较结果 same / different / unknown，不改变排名，也不证明版本兼容。 |
| `--limit N` | 最多返回 N 个候选，默认 5、最大 20。 |
| `--format json` / `--format markdown` | 机器可读输出或便于阅读的候选列表。 |

召回结果是新一轮修复的线索。采用旧方案前，仍需核对当前代码、条件、原始证据与测试。相关性分数不证明方案正确，记录中的 `solved` 也未经独立认证。recall 不自动脱敏，对外分享摘要前须复核内容。资源上限、选择规则与参考项目见 [本地案例复用](skills/research-to-fix/references/case-reuse.md)。

## 高吞吐召回与实测排序

同一案例库需要检索多个问题时，`recall-batch` 一次读取与校验显式目录，复用紧凑内存倒排索引。查询文件为 1–128 条非空字符串组成的 JSON 数组，最多 2 MiB；所有查询共享组件、版本筛选及返回数量上限。不回显整个原始查询列表。

```bash
python skills/research-to-fix/scripts/research_case.py recall-batch \
  --cases-dir ./cases --queries-file ./queries.json --ranking stemmed
```

| 排序模式 | 适用情况 |
| --- | --- |
| `bm25`（默认） | 与旧版评分和排序保持兼容。 |
| `technical` | camelCase/snake_case 标识符扩展、原症状加权。 |
| `stemmed` | 技术词加英文词形归一，适合英文问题描述的候选模式。 |
| `hybrid` | 精确词和词干双通道，适合技术标识符和混合语言。 |
| `contextual` | 词干加有序短语弱加权，实验模式。 |

单次召回保留低启动成本扫描路径；批量索引只保存在内存中，案例改变后应重新构建。排序不联网、不依赖模型或第三方包；扩展词、词干和短语可能产生误匹配，分数不能代表兼容性或修复成功率。详见[基准评测](benchmarks/README.md)、[实测性能记录](docs/PERFORMANCE.md)及[案例复用指南](skills/research-to-fix/references/case-reuse.md)。

## 辅助工具

```bash
python skills/research-to-fix/scripts/research_case.py queries \
  --error 'RuntimeError: dtype mismatch' --component pytorch \
  --version 2.5 --concept 'mixed precision' \
  --source github_issues --source huggingface_forum \
  --repo pytorch/pytorch --language en --limit 4

python skills/research-to-fix/scripts/research_case.py init \
  --output /tmp/research-case.json

python skills/research-to-fix/scripts/research_case.py validate \
  /tmp/research-case.json --format json
```

`queries` 生成离线检索计划。不指定来源、语言筛选或数量上限时，默认仍生成 26 条中英文候选；联网前按相关性选 4–8 条。论文、学者和实验室检索使用机制词。

| 查询选项 | 作用 |
| --- | --- |
| `--source` | 筛选来源类别；可重复以选择多个来源。 |
| `--language en` / `--language zh` | 筛选查询语言；可重复以保留两种语言。 |
| `--limit N` | 用正整数限制生成的候选数，不设置或执行实际联网预算。 |
| `--repo owner/name` | 仅将 GitHub issue 和 PR 候选限定到指定仓库，其他来源不变。 |
| `--strategy balanced` | 交错错误匹配与机制检索阶段，优先覆盖各选定来源再补第二语言。默认 `source_order` 保持原顺序；这不是相关性排名。 |

发送前逐条复核查询。输入检查会拒绝常见凭据模式、检测出的私有地址和识别到的非 HTTP(S) URI，但秘密检测只是启发式检查，不能保证所有内容均可公开。

`init` 不覆盖已有文件。`validate` 检查记录结构与已声明的引用，`--format json` 提供机器可读结果。退出码 **0** 表示结构通过，**1** 表示记录错误，**2** 表示文件或 JSON 输入错误。纯标准库辅助工具不联网、不登录服务、不上传代码，也不执行记录中的命令。通过校验不能证明记录真实、修复有效或因果判断成立。

格式仍为 **schema_version: 1**。比较上下文、修复轮次、采用方案和逐测试结果字段均可选，原单轮格式可继续使用，无须补填这些字段。校验有意收紧：遗漏回归 after 检查、completed 搜索缺少日期、criteria 类型错误等不完整或矛盾的记录现在会被拒绝。

`solved` 要求**每项已记录的 before 检查**都有 after pass，包括回归测试，并且至少有一项原症状从失败变通过。前后配对检查保持命令、标准、预期退出码及已声明的比较上下文一致。多轮记录保留历史失败并明确最终验收轮次；组合方案需要覆盖整个组合的支持实验。详细规则见 [案例模板](skills/research-to-fix/references/case-template.md)。空的 blocked 模板仍合法；本地推断无需虚构外部来源。

测试套件可用 `test_results` 记录稳定的测试 ID 与结果。pass 记录不能零通过，也不能包含失败、错误或未执行项。前后比较提供明细时，最终结果必须保留全部基线测试 ID；原先通过、失败或错误的测试都须最终通过，原本已跳过的测试可继续跳过。不提供明细的旧记录仍兼容，但校验器无法仅凭套件的总退出码识别内部删测或跳过。

## 完整性复核与证据封存

案例记录后，检查声明的完整度，并按需在本地封存证据包：

```bash
python skills/research-to-fix/scripts/research_case.py review /tmp/research-to-fix-example/case.json
python skills/research-to-fix/scripts/case_bundle.py seal --directory /tmp/research-to-fix-example \
  --artifact runs/before/metrics.py --artifact runs/after/metrics.py
python skills/research-to-fix/scripts/case_bundle.py verify --directory /tmp/research-to-fix-example
```

- `review` 统计基线与最终检查覆盖、比较上下文、逐测试明细、已声明的产物、改变的验收标准、缺失或未通过的基线测试与外部证据缺口。提示项用于复核，不是成功率评分；结构合法但不完整的案例仍返回 0。
- `seal` 排他创建 `manifest.json`，记录 `case.json`、运行记录 `artifacts` 字段所引用文件与额外显式 `--artifact` 文件的 SHA-256 和字节长度。需要保留的源码快照须明确选择，不自动扫描目录。
- `verify` 检查记录结构和文件字节是否匹配清单。可用 `--expected-manifest-sha256` 输入独立保存的摘要以检测清单本身被替换。不重跑测试、不认证作者、不证明所声明观测真实发生。

全部命令离线、无第三方依赖。`validate` 与 `review` 接收最多 4 MiB 的普通 UTF-8 JSON 文件，不接收符号链接或特殊文件。证据包使用可移植相对路径和有限读取（128 个成员、单产物 16 MiB、总量 64 MiB）。请控制工作目录；检查不是防御并发恶意替换文件系统的沙箱。共享前仍需脱敏。参阅[证据包指南](skills/research-to-fix/references/evidence-bundle.md)与[安全政策](SECURITY.md)。

## 项目结构

- `skills/research-to-fix/SKILL.md`：核心指令。
- `skills/research-to-fix/references/`：来源检索、案例复用、证据判定、修复流程和记录模板。
- `skills/research-to-fix/scripts/research_case.py`：检索计划、本地案例召回、记录检查与完整度复核工具。
- `skills/research-to-fix/scripts/case_bundle.py`：离线证据封存与完整性校验。
- `tests/`：辅助工具的行为验证。
- `examples/`：独立可复现的小案例与练习输入。

## 验证与贡献

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
```

CI 在 Linux 上覆盖 Python 3.10–3.14，并在 Windows、macOS 上覆盖 Python 3.13。Linux 任务记录、校验、复核、召回、封存及验证流式示例，成功时将案例、源码快照、原始日志、逐测试报告、摘要清单、复核及检索结果保存为 `repair-case-python-<版本>` 产物，保留 7 天。这些是可复查的小案例结果，不代表通用修复成功率。

欢迎提交真实问题中的改进，参阅[贡献指南](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md)、[发布清单](docs/RELEASE_CHECKLIST.md)和[变更记录](CHANGELOG.md)：触发请求、环境、脱敏复现、实际调研与本地验证、哪里浪费了搜索或误判了适用性。不要上传私有代码、密钥或客户数据。新增来源应说明如何核验原始内容与访问失败；新增脚本应附实际运行结果。

独立试用的 [流式统计案例](examples/streaming-metrics/README.md)包含原始证据、失败基线、兼容修复与可复现检查。这是小型合成案例，尚不代表大型工程或科研问题上的效果。当前版本不能保证所有平台可访问、每个问题都有外部答案或每项修复一定成功；访问受限与验证缺口应进入记录。

## 许可

[MIT](LICENSE)。

## 相关开源项目

按用途浏览 [Afloat16 项目导航](https://github.com/Afloat16/research-to-fix/blob/main/docs/PROJECTS.md)，选择需求论证、调研修复、任务验收、接口诊断、通知、MCP建议、机器人排障和三维重建工具。

本轮新增六个领域工具，选题与边界见 [29线程/336评论调研](docs/DEMAND_REVIEW.md)，实际目录申请和相关问题回复见 [推广记录](docs/OUTREACH.md)。

