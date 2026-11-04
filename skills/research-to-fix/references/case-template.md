# 调研与修复记录

按问题规模选择简短 Markdown 或结构化 JSON。默认本地保存，公开前去掉私有路径、数据、账户、内部地址和研究细节。

导航：[简短模板](#简短交付模板) · [JSON 工具](#json-工具) · [字段与来源状态](#字段与来源状态) · [可比检查](#可比检查与-solved) · [多轮与组合](#多轮修复与方案组合) · [示例片段](#组合与轮次示例片段)

## 简短交付模板

```markdown
## 问题与基线

- 预期/实际：
- 环境与版本：
- 原症状检查、命令、退出码、观测：
- 约束、成功标准、预期退出码和预算：
- 比较时需固定的输入、评估条件与检查版本：

## 调研证据

| ID | 原始链接/访问时间 | 主张与条件 | 来源已解决/可行路线/线索 | 与本地差异 |
| --- | --- | --- | --- | --- |

覆盖状态：GitHub / Hugging Face / 知乎 / 小红书 / 论文 / 学者与实验室。
对未检索、无关、访问受限或工具不可用的类别分别说明原因。

## 本地分析与方案

- 相关文件、符号和调用路径：
- 支持与反对证据 ID：
- 机制假设、候选方案比较、选择理由：
- 采用组件、各自贡献、适配/舍弃部分、组合兼容性：
- 实际改动、临时 workaround 取舍与退出条件：

## 验证与状态

| 检查 | 前/后及轮次 | 实际命令 | 退出码 | 观测/阈值 | 结果 |
| --- | --- | --- | --- | --- | --- |

- 最终验收轮次与历史失败：
- 相关回归、兼容性与资源成本：
- 状态：solved / partial / blocked
- 未解决项与下一步：
```

## JSON 工具

从 skill 所在目录运行，Python 3.10+，无第三方依赖：

```bash
python scripts/research_case.py queries \
  --error 'RuntimeError: dtype mismatch' --component pytorch --version 2.5 \
  --concept 'mixed precision' --source github_issues --source huggingface_forum \
  --repo pytorch/pytorch --language en --limit 4
python scripts/research_case.py init --output /tmp/research-case.json
python scripts/research_case.py validate /tmp/research-case.json --format json
```

`queries` 只产生候选查询，不搜索、抓取、登录或上传。默认生成 26 条中英文候选，按相关性选 4–8 条发送。`--source` 和 `--language en` / `--language zh` 均可重复；`--limit` 必须为正整数，仅限制生成数量，不是实际联网预算。`--repo owner/name` 只缩小 GitHub issue/PR 的仓库范围，其他来源不变。论文、学者和实验室查询使用 `--concept` 机制词，缺机制词时须先人工改写。

输入检查拒绝常见凭据模式、检测出的私有地址及识别到的非 HTTP(S) URI。秘密检测是启发式检查，发送前仍须人工复核。`init` 不覆盖已有文件，模板初始状态为 blocked。输出目录使用项目允许的本地位置；`/tmp` 只是示例。

`validate` 默认输出文本，`--format json` 输出机器可读结果。退出码 0 表示结构通过，1 表示案例记录错误，2 表示文件读取或 JSON 输入错误。通过检查只说明声明与引用符合规则，不证明问题已解决。

## 字段与来源状态

`schema_version` 仍为 1，新增的比较上下文、轮次与方案字段均可选。原单轮格式可继续使用，无须补填新字段或升级格式版本。校验有意收紧：遗漏回归 after 检查、completed 缺少日期、criteria 类型错误等此前通过的记录现在可能被拒绝，须补齐或纠正真实记录。

| 顶层字段 | 填写内容 |
| --- | --- |
| `schema_version`, `case_id` | 格式版本与本地问题 ID |
| `problem` | 症状、组件、版本、复现命令/结果、约束；reproduction 可用 check_id 关联原症状检查 |
| `searches` | S… ID、query、language、source、status、searched_at、result_urls；未查询时填写 reason |
| `evidence` | E… ID、URL、标题、来源、author、accessed_at、revision、访问/发表/原始性状态、outcome、主张、相关性、限制、search_ids |
| `mapping` | M… ID、evidence_ids、本地路径/符号、相同/不同条件、假设、basis（external / local_code / mixed） |
| `experiments` | X… ID、mapping_ids、evidence_ids、hypothesis、change、commands、status（planned / supports / rejects / inconclusive）；可选 attempt_id |
| `solution`（可选） | single / combined 策略、components、选择理由、兼容性、取舍及未解决冲突 |
| `validation` | status、summary、limitations、runs；多轮验收用 final_attempt_id 指定最终轮 |

每条搜索、证据、映射、实验和运行记录均有在案例内唯一的 `id`，引用必须存在且不重复。`check_id` 标识同一项检查，前后运行共用它，各次运行的 `id` 仍不同。

搜索状态统一使用 planned / completed / not_relevant / access_blocked / unavailable / blocked；`searched` 作为旧的 completed 别名继续接受。planned 要求非空 query，completed 要求非空 query 和 searched_at，未命中可保留空 result_urls。not_relevant / unavailable / access_blocked / blocked 可用空 query，但必须填写非空 reason；旧的非空 query 记录仍兼容。无论状态如何，query 和 searched_at 字段仍是字符串。

证据使用 `access_status: read / snippet_only / access_blocked / unavailable`；未读或不可达来源只能标 `outcome: lead`。已读证据的 accessed_at 不能为空，未知 author/revision 可空并在 limitations 解释。`publication_status` 可为 preprint / submitted / accepted / published / discussion / not_applicable / unknown；`outcome` 可为 solved_report / viable_route / lead。无外部证据时可用 `mapping.basis: local_code` 并保留空 evidence_ids，明确说明本地推断，不补造链接。

## 可比检查与 solved

`validation.runs` 的每条记录包含 id、check_id、phase（before / after）、kind（reproduction / test / benchmark）、command、exit_code、result（fail / pass / not_run）、observed 和 evidence_ids。已执行项必须有非空命令、观测和整数退出码；not_run 的退出码为 null。

| 比较字段 | 规则 |
| --- | --- |
| `criteria` | 已执行 reproduction / benchmark 必填；其他检查可选。任何已提供的标准都须为非空字符串，验收前后保持一致。 |
| `expected_exit_code`（可选） | 整数，省略为 0；pass 的实际退出码须等于它，验收前后预期值不变。预期拒绝非法输入等场景可明确填写非零码。 |
| `comparison_context`（可选） | 非空对象，键和值均为非空字符串；solved 验收时前后任一侧提供，两侧就须有相同内容。可记录 input、data_split、seed_set、check_revision、protocol 等需要固定的条件。 |

本轮计划修改的依赖版本、配置或算法应写入实验 change，不放进不可变 comparison_context。性能检查即使退出码符合预期，未达阈值仍须标 fail；校验器不会读取指标或判断实际是否达标。

`solved` 必须同时满足：

1. 有问题描述、本地映射和支持假设的实验；使用轮次时，支持实验属于指定最终轮。
2. 至少一项原症状 reproduction / benchmark 有 before fail → after pass，单独的回归测试不能替代它。
3. **每项已记录的 before 检查**，包括原先通过、失败或未执行的回归，都有最终验收轮的 after pass。按 check_id、kind、command 配对，并保持上述比较字段一致。
4. `problem.reproduction` 若已填写 fail 命令，它必须对应同命令的 before 原症状失败记录；可选 check_id 进一步明确关联。若摘要明确填写 criteria、expected_exit_code 或 comparison_context，这些字段也须与关联的 before 记录一致。未填写旧摘要时，可由 validation.runs 提供完整事实。
5. 最终验收轮没有 fail / not_run 项；若填写 solution，还须满足下节的整体支持与冲突规则。

因此，不必删除历史失败来获得 solved；用明确轮次区分历史与最终验收。缺少验证时保留 partial 或 blocked。

## 多轮修复与方案组合

after 运行可填写非空 `attempt_id`。一旦使用轮次，所有 after 运行都须标记所属轮次；标为 solved 时必须用 `validation.final_attempt_id` 明确选择含 after 记录的最终轮，不能按数组顺序推断。最终 supports 实验也要有相同 attempt_id。历史轮次的失败保留在原记录中，仍检查字段完整性，但不作为最终验收结果；所有 before 基线与回归都要在最终轮重新通过。不填写轮次时仍按严格单轮检查，任何 after 失败或未执行都会阻止 solved。

可选的顶层 `solution` 描述本次实际采用或计划采用的方案。没有该字段时不要求补填；一旦提供，就检查以下结构：

| 字段 | 内容 |
| --- | --- |
| `strategy` | single 或 combined；single 恰有一个组件，combined 至少有两个不同本地映射。 |
| `components` | 每项包含已有且不重复的 mapping_id、非空 contribution（采用贡献）、非空 adaptation（本地适配）；无需适配时说明理由。omitted 可选，用字符串说明舍弃部分。 |
| `rationale`, `compatibility` | 非空字符串，说明选择或组合理由，以及接口、版本、数据假设等条件的兼容性。 |
| `tradeoffs` | 字符串数组，记录成本和取舍，可为空。 |
| `unresolved_conflicts`（可选） | 字符串数组，记录尚未解决的冲突；存在条目时不得标 solved。 |

来源经 `components[].mapping_id → mapping.evidence_ids` 追溯，本地推断映射也可参与组合。solved 时至少有**一个最终 supports 实验**的 mapping_ids 覆盖全部选定组件；分散在多个实验中的单独成功不能代替组合验证。不强制凑足多个候选或多个来源。

## 组合与轮次示例片段

下面是**尚未执行的结构示意**，不是成功案例，也不是可单独校验的完整 JSON。假定 M1/M2 的证据与本地映射已在完整案例中填写；为简短省略了运行的 command、criteria、exit_code、observed 等字段，实际填写须补齐。实验保持 planned，运行保持 not_run，不填造前后结果。

```json
{
  "solution": {
    "strategy": "combined",
    "components": [
      {"mapping_id": "M1", "contribution": "采用有界流式归约", "adaptation": "保留本地输入校验"},
      {"mapping_id": "M2", "contribution": "采用累加误差补偿", "adaptation": "只调整固定大小的累加状态"}
    ],
    "rationale": "需要同时满足内存上限与数值精度要求",
    "compatibility": "计划保持单遍输入和固定大小状态，实际效果待联合实验核验",
    "tradeoffs": ["每个元素增加少量计算"],
    "unresolved_conflicts": []
  },
  "experiments": [
    {"id": "X2", "attempt_id": "A2", "mapping_ids": ["M1", "M2"], "status": "planned"}
  ],
  "validation": {
    "status": "partial",
    "summary": "示例计划：尚未运行基线、组合实验与回归",
    "final_attempt_id": "A2",
    "runs": [
      {"id": "V0", "check_id": "C1", "phase": "before", "kind": "reproduction", "result": "not_run"},
      {"id": "V1", "check_id": "C1", "phase": "after", "kind": "reproduction", "attempt_id": "A1", "result": "not_run"},
      {"id": "V2", "check_id": "C1", "phase": "after", "kind": "reproduction", "attempt_id": "A2", "result": "not_run"}
    ]
  }
}
```

执行后逐次记录真实命令、退出码、观测和结果。若 A1 实际失败而 A2 最终通过，保留 A1；只有 A2 的整体支持实验、C1 原症状前后记录及所有已记录回归都满足条件，才改为 solved。固定输入或协议时，在对应 before 与最终 after 同时填写一致的 comparison_context。

`validate` 只检查声明与引用的一致性；它不访问 URL、认证账户、执行命令、阅读日志、检验代码差异或证明修复效果和因果。审核者仍需查看原始材料、代码 diff 和实际测试记录。不得通过填假字段获得 solved。
