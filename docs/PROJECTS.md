# Afloat16 开源项目导航

按问题选择工具，再查看对应仓库的安装说明、验证记录和限制。这里收录 Afloat16 原创维护的公开项目；每个项目独立发布，不要求一起安装。

| 你的需求 | 推荐项目 | 主要产物 | 使用前了解 |
| --- | --- | --- | --- |
| 需求含糊、方案有争议，需要可审查方向 | [Debate Direction](https://github.com/Afloat16/debate-direction) | 两个参与方的独立论证、修订、问题台账与下一步验证 | 讨论共识不证明方案正确；原生 Skill 需要支持子任务的宿主，CLI 使用所选模型服务 |
| 本地问题难解决，想先查已有修复与可行路线 | [Research to Fix](https://github.com/Afloat16/research-to-fix) | 原始来源、适用性映射、最小修复与前后验证 | 联网与编码工具由宿主提供；工具的记录检查不证明修复效果 |
| 编码改动需要范围约束、产物治理和可追溯检查 | [AI Dev Steward / StewardCheck](https://github.com/Afloat16/ai-dev-steward) | 原始 Skill 的审阅记录，以及 StewardCheck 的 Git 基线和任务验收记录 | 本地工具和 Skill 可独立使用；验收记录不替代人工标准；MIT 仅覆盖 tools/stewardcheck 子目录 |
| OpenAI 兼容接口接上了，但 streaming/tools/usage 表现不一致 | [LLM Handshake](https://github.com/Afloat16/llm-handshake) | 有预算上限的接口探测、报告和差异比较 | 默认模型列表 GET；推理需明确启用，不是完整协议认证，也不自动认定供应商质量 |
| 长时间运行的 agent 需要你输入或审阅，想收到提醒 | [Agent Action Notifier](https://github.com/Afloat16/agent-action-notifier) | 邮件/本地桌面通知、请求跟踪、重试与待审阅回复 | 通知不等于批准；SMTP 是显式选择，导入回复不自动获得可信身份 |
| MCP 工作流需要受限的概率建议作为第二意见 | [Jev MCP](https://github.com/Afloat16/jev-mcp) | 四个只读建议工具：选项决策、路由、风险信号、yes/no gate | 非官方 TypeSafe Jev 集成；state 会发给外部服务，建议不拥有审批权；需要服务访问条件 |
| 想在本地 CPU 上检查照片、恢复稀疏几何或处理标定双目 | [ReconTrail](https://github.com/Afloat16/recontrail) | 影像质量检查、相机位姿、稀疏重建、双目可见表面和离线报告 | 重建受输入、视差和标定影响；不承诺通用稠密或封闭网格重建 |

## 从哪个开始

- **日常项目诊断**：从 Research to Fix 开始；接口兼容性症状使用 LLM Handshake 的针对性探测。
- **需求与设计讨论**：用 Debate Direction 把分歧转成可验证条件，再进入代码工作。
- **任务交付与等待输入**：用 StewardCheck 记录改动与检查；需要提醒时单独配置 Agent Action Notifier。
- **特定领域任务**：MCP 概率建议查看 Jev MCP；影像几何查看 ReconTrail。

这些是按当前代码与文档做的用途推荐。各项目的真实测试环境、发布日期、兼容性和验证缺口，以仓库中的记录和实际 CI 为准；目录提交不等于维护者已经收录，也不代表上游平台背书。

## English

Independent tools and skills maintained by [Afloat16](https://github.com/Afloat16): requirements debate, evidence-driven debugging, task-scoped Git checks, endpoint diagnostics, human-input notifications, a conservative MCP advisory integration, and local CPU photogrammetry. Choose a project by the task above, then follow its own installation and validation guide. License scope and external-service requirements remain project-specific.
