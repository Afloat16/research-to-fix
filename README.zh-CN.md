# Research to Fix

[English](README.md) | **简体中文**

**查到相似问题，适配或组合已有方案，再验证本地修复。**

Research to Fix 是一个遵循 [Agent Skills 格式](https://agentskills.io/specification)的调研与修复工作流。它让模型在陌生报错、难复现 bug、训练异常或性能退化时，先查别人是否已经解决或给出可行路线，再对照当前项目的代码、版本和运行条件实施修复。兼容的方案部件可以组合使用，并明确记录各自贡献、本地适配及整体验证。

创意与工作流设计：**[Afloat16](https://github.com/Afloat16)**。维护者：**Afloat16**。

## 从哪里开始

- 想让模型实际调研并修复项目：安装后使用 [示例请求](#使用)。
- 想了解来源与核验方法：阅读 [来源检索指南](skills/research-to-fix/references/source-playbook.md)和 [证据判定](skills/research-to-fix/references/evidence-rules.md)。
- 想先检查一个可复现的小案例：查看 [流式统计案例](examples/streaming-metrics/README.md)。
- 想记录多轮调研或交接证据：使用 [辅助工具](#辅助工具)和 [记录模板](skills/research-to-fix/references/case-template.md)。

## 它做什么

| 环节 | 产物 |
| --- | --- |
| 问题指纹 | 去敏错误、环境/版本、调用链、最小复现、成功标准 |
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

发送前逐条复核查询。输入检查会拒绝常见凭据模式、检测出的私有地址和识别到的非 HTTP(S) URI，但秘密检测只是启发式检查，不能保证所有内容均可公开。

`init` 不覆盖已有文件。`validate` 检查记录结构与已声明的引用，`--format json` 提供机器可读结果。退出码 **0** 表示结构通过，**1** 表示记录错误，**2** 表示文件或 JSON 输入错误。纯标准库辅助工具不联网、不登录服务、不上传代码，也不执行记录中的命令。通过校验不能证明记录真实、修复有效或因果判断成立。

格式仍为 **schema_version: 1**。新增的比较上下文、修复轮次和采用方案字段均可选，原单轮格式可继续使用，无须补填这些字段。校验有意收紧：遗漏回归 after 检查、completed 搜索缺少日期、criteria 类型错误等不完整或矛盾的记录现在会被拒绝。

`solved` 要求**每项已记录的 before 检查**都有 after pass，包括回归测试，并且至少有一项原症状从失败变通过。前后配对检查保持命令、标准、预期退出码及已声明的比较上下文一致。多轮记录保留历史失败并明确最终验收轮次；组合方案需要覆盖整个组合的支持实验。详细规则见 [案例模板](skills/research-to-fix/references/case-template.md)。空的 blocked 模板仍合法；本地推断无需虚构外部来源。

## 项目结构

- `skills/research-to-fix/SKILL.md`：核心指令。
- `skills/research-to-fix/references/`：来源检索、证据判定、修复流程和记录模板。
- `skills/research-to-fix/scripts/research_case.py`：检索计划与记录检查工具。
- `tests/`：辅助工具的行为验证。
- `examples/`：独立可复现的小案例与练习输入。

## 验证与贡献

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
```

欢迎提交真实问题中的改进：触发请求、环境、脱敏复现、实际调研与本地验证、哪里浪费了搜索或误判了适用性。不要上传私有代码、密钥或客户数据。新增来源应说明如何核验原始内容与访问失败；新增脚本应附实际运行结果。

独立试用的 [流式统计案例](examples/streaming-metrics/README.md)包含原始证据、失败基线、兼容修复与可复现检查。这是小型合成案例，尚不代表大型工程或科研问题上的效果。当前版本不能保证所有平台可访问、每个问题都有外部答案或每项修复一定成功；访问受限与验证缺口应进入记录。

## 许可

[MIT](LICENSE)。

## 相关开源项目

按用途浏览 [Afloat16 项目导航](https://github.com/Afloat16/research-to-fix/blob/main/docs/PROJECTS.md)，选择需求论证、调研修复、任务验收、接口诊断、通知、MCP建议、机器人排障和三维重建工具。

本轮新增六个领域工具，选题与边界见 [29线程/336评论调研](docs/DEMAND_REVIEW.md)，实际目录申请和相关问题回复见 [推广记录](docs/OUTREACH.md)。

