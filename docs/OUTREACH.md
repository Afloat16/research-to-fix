# 推广与收录申请记录 — 2026-10-14

推广先检查贡献规则、重复提交和工具适用性。资源目录使用 PR；问题讨论先提供针对当前症状的建议，再说明工具链接与边界。作者与维护者均为 Afloat16，不声称上游背书、采用率或人工审查已完成。Stars 是采集时传播范围快照。

## 本轮新增目录申请

5份PR，覆盖4个目录。均已由GitHub API确认作者为Afloat16、状态open、未合并，改动仅新增README条目，没有删除目录既有内容。

| 实际提交 | Stars快照 | 推荐资源 | 当前状态 |
|---|---:|---|---|
| [punkpeye/awesome-mcp-servers #16394](https://github.com/punkpeye/awesome-mcp-servers/pull/16394) | 96,314 | jev-mcp | open，待维护者审查 |
| [kiloreux/awesome-robotics #119](https://github.com/kiloreux/awesome-robotics/pull/119) | 7,236 | bag-timeline-audit | open，待维护者审查 |
| [kiloreux/awesome-robotics #120](https://github.com/kiloreux/awesome-robotics/pull/120) | 7,236 | tf-route-audit | open，待维护者审查 |
| [Hannibal046/Awesome-LLM #849](https://github.com/Hannibal046/Awesome-LLM/pull/849) | 27,446 | sse-toolcall-audit、tooltrace-audit、llm-handshake | open，待维护者审查 |
| [MrNeRF/awesome-3D-gaussian-splatting #447](https://github.com/MrNeRF/awesome-3D-gaussian-splatting/pull/447) | 8,946 | colmap-model-audit、pose-convention-bridge | open，待维护者审查 |

Punkpeye目录的自动检查要求Glama链接。已核对[Jev MCP既有公开页面](https://glama.ai/mcp/servers/Afloat16/jev-mcp)及[四工具schema](https://glama.ai/mcp/servers/Afloat16/jev-mcp/schema)，并补上该页面的官方动态score徽章。Schema上的TDQS评分日期为2026-09-28；它不是本轮新建记录、实际调用成功或平台背书。后续是否满足全部目录检查由维护者核验。

## 本轮需求匹配评论

5条评论，均已在开放、未锁定的相关问题下发布，并由GitHub API确认。发布前没有相同Afloat16推荐。原调研样本的336条评论快照不含本轮推广评论；线程后续可能继续增长。

| 实际评论 | 项目Stars快照 | 推荐资源 | 方式 |
|---|---:|---|---|
| [colmap/colmap #1703](https://github.com/colmap/colmap/issues/1703#issuecomment-6164675576) | 12,940 | colmap-model-audit | 已发布，提供具体排查方法并披露维护关系 |
| [ros2/rosbag2 #1845](https://github.com/ros2/rosbag2/issues/1845#issuecomment-6164698180) | 4,439 | bag-timeline-audit | 已发布，提供具体排查方法并披露维护关系 |
| [vllm-project/vllm #44676](https://github.com/vllm-project/vllm/issues/44676#issuecomment-6164726054) | 93,747 | sse-toolcall-audit | 已发布，提供具体排查方法并披露维护关系 |
| [langchain-ai/langgraph #7417](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-6164775238) | 43,238 | tooltrace-audit | 已发布，提供具体排查方法并披露维护关系 |
| [nerfstudio-project/nerfstudio #3690](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-6164799946) | 12,066 | pose-convention-bridge | 已发布，提供具体排查方法并披露维护关系 |

- COLMAP：解释共同注册图像按名称匹配、单边前缀可能破坏对应；模型审计只提供传统文本track及候选重叠检查。
- rosbag2：将实时publish/receive计数与离线记录时间证据区分；不把间隙称为丢帧证明。
- vLLM：支持保存低/高推理预算实验的SSE证据；不声称修复ThinkingBudgetStateHolder。
- LangGraph：稳定逻辑调用ID、唯一attempt及实际执行前后事件；审计不提供幂等或恰好一次执行。
- Nerfstudio：区分右乘相机基变换、左乘世界变换与真实外参，并指出示例JPG输入和PNG输出路径需核对。

## 先前已发布推荐

以下此前已提交，本轮没有重复提交。目录申请与自动草稿仍不是正式收录。

| 推荐资源 | 真实链接 |
|---|---|
| Research to Fix | [open-agent-craft #28](https://github.com/open-agent-craft/awesome-agent-skills/issues/28) |
| Debate Direction | [open-agent-craft #29](https://github.com/open-agent-craft/awesome-agent-skills/issues/29) |
| StewardCheck（仅MIT子工具） | [open-agent-craft #30](https://github.com/open-agent-craft/awesome-agent-skills/issues/30) |
| Agent Action Notifier | [open-agent-craft #31](https://github.com/open-agent-craft/awesome-agent-skills/issues/31) |
| LLM Handshake | [open-agent-craft #32](https://github.com/open-agent-craft/awesome-agent-skills/issues/32) |
| Jev MCP | [TensorBlock #3663](https://github.com/TensorBlock/awesome-mcp-servers/issues/3663)，自动生成[草稿PR #3664](https://github.com/TensorBlock/awesome-mcp-servers/pull/3664) |
| ReconTrail | [awesome-photogrammetry #17](https://github.com/awesome-photogrammetry/awesome-photogrammetry/issues/17) |

## 未计入已完成推广的渠道

- Appcypher MCP目录：fork表单两次返回“was submitted too quickly”，一次普通刷新仍未创建成功，停止该入口；没有PR。
- Heilcheng Agent Skill Index：fork表单同样返回“was submitted too quickly”。此外，按贡献指南对完整、固定提交的网站源码实际运行npm构建，Node24和Node22均因当前环境缺/proc/self/stat而报ENOENT / uv_resident_set_memory，未记为通过；没有PR。
- Composio技能目录要求实际Claude环境验证，当前没有该环境，未声称已测试。
- 机器人库目录有项目年龄、stars及独立采用门槛；新项目尚不满足，未提交或勾选人工审查确认。
- 总Awesome目录当前暂停PR；其他窄范围agent目录与本次CLI不匹配，未强行推荐。

没有批量发相同广告、私信、伪造评论、交换star或绕过站点限制。收录和反馈需要外部维护者决定。

参见[项目导航](PROJECTS.md)和[需求调研](DEMAND_REVIEW.md)。

