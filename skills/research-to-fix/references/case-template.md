# 调研与修复记录

按问题规模选择简短 Markdown 或结构化 JSON。默认本地保存，公开前去掉私有路径、数据、账户、内部地址和研究细节。

## 简短交付模板

```markdown
## 问题与基线
- 预期/实际：
- 环境与版本：
- 原症状检查、命令、退出码、观测：
- 约束、成功标准和预算：

## 调研证据
| ID | 原始链接/访问时间 | 主张与条件 | 来源已解决/可行路线/线索 | 与本地差异 |
| --- | --- | --- | --- | --- |

覆盖状态：GitHub / Hugging Face / 知乎 / 小红书 / 论文 / 学者与实验室。
对未检索、无关、访问受限或工具不可用的类别分别说明原因。

## 本地分析与方案
- 相关文件、符号和调用路径：
- 支持与反对证据 ID：
- 机制假设、候选方案比较、选择理由：
- 实际改动、临时 workaround 取舍与退出条件：

## 验证与状态
| 检查 | 前/后 | 实际命令 | 退出码 | 观测/阈值 | 结果 |
| --- | --- | --- | --- | --- | --- |
- 相关回归、兼容性与资源成本：
- 状态：solved / partial / blocked
- 未解决项与下一步：
```

## JSON 工具

从 skill 所在目录运行，Python 3.10+，无第三方依赖：

```bash
python scripts/research_case.py queries --error 'RuntimeError: dtype mismatch' --component pytorch --version 2.5 --concept 'mixed precision' --source github_issues --source huggingface_forum
python scripts/research_case.py init --output /tmp/research-case.json
python scripts/research_case.py validate /tmp/research-case.json
```

`queries` 只产生候选查询，不搜索、抓取或上传。省略 `--source` 时列出完整来源，按相关性选 4–8 条发送；`--source` 可重复。论文、学者和实验室查询使用 `--concept` 机制词，缺机制词时须先人工改写。明显凭据和私有 URL 会拒绝，但不能保证自动识别全部敏感内容。`init` 不覆盖已有文件。模板初始状态为 blocked，结构检查通过不代表问题已解决。输出目录应使用项目允许的本地位置；`/tmp` 只是示例。

| 顶层字段 | 填写内容 |
| --- | --- |
| `schema_version`, `case_id` | 格式版本与本地问题 ID |
| `problem` | 症状、组件、版本、复现命令/结果、约束 |
| `searches` | S… ID、查询、语言、来源、状态、日期、结果 URL |
| `evidence` | E… ID、URL、标题、来源、author、accessed_at、revision、访问/发表/原始性状态、outcome、主张、相关性、限制、search_ids |
| `mapping` | M… ID、evidence_ids、本地路径/符号、相同/不同条件、假设、basis（external / local_code / mixed） |
| `experiments` | X… ID、mapping_ids、evidence_ids、假设、改动、命令、状态 |
| `validation` | 当前状态、总结、限制、runs（check_id、前/后、类型、命令、退出码、结果、观测；reproduction / benchmark 已执行项均补 criteria） |

证据使用 `access_status: read / snippet_only / access_blocked / unavailable`；未读或不可达来源只能标 `outcome: lead`。已读证据的访问日期不能为空，未知作者/revision 可空并在 limitations 解释。`publication_status` 可为 preprint / submitted / accepted / published / discussion / not_applicable / unknown；`outcome` 可为 solved_report / viable_route / lead。搜索状态使用 planned / completed / not_relevant / access_blocked / unavailable；blocked 用于一般阻碍。

从模板复制字段，数组条目的精确约束以脚本为准。引用不存在的 ID、重复 ID、缺少已执行命令/退出码/观测、无可比前后检查而标 solved，均被拒绝。solved 要求每个原问题失败检查有同 check_id、类型、命令和标准的 after pass，并且不存在记录中的修复后失败/未执行项。性能检查可退出码为 0 但未达阈值，须如实标 fail。

没有外部证据也可用 `mapping.basis: local_code`，允许对应 evidence_ids 为空；必须仍有本地映射、支持实验及完整原症状前后记录。明确写“本地推断”，不补造外部链接。

`validate` 只检查声明与引用的一致性；它不访问 URL、执行命令、阅读日志、检验差异或证明修复效果。审核者仍需查看原始材料、代码 diff 和实际测试记录。不得通过填假字段获得 solved。
