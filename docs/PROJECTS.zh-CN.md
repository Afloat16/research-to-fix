# Afloat16 开源项目导航

[English](PROJECTS.md) · [简体中文](PROJECTS.zh-CN.md)

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


| 检查ROS 2录包时间异常、重复和跨topic偏差 | [Bag Timeline Audit](https://github.com/Afloat16/bag-timeline-audit) | SQLite/MCAP/JSONL的离线时间诊断 | 间隙不能证明丢包；跨topic必须明确同一时钟；不推断分段包顺序 |
| 检查TF/URDF坐标链、缺失frame和时间覆盖 | [TF Route Audit](https://github.com/Afloat16/tf-route-audit) | 拓扑与已观察时间范围报告 | 不模拟实时tf2缓存、插值或publisher authority |
| 流式工具调用参数丢失、缺名或组装异常 | [SSE Toolcall Audit](https://github.com/Afloat16/sse-toolcall-audit) | 保存的Chat Completions/Responses SSE诊断与非流式对比 | 不访问服务器或修复生成；跨次随机输出差异不自动算回归 |
| 排查长工具重复执行、缺少结果与重试重叠 | [Tooltrace Audit](https://github.com/Afloat16/tooltrace-audit) | 执行事件与对话配对审计、可选参数摘要记录 | 调用方提供稳定ID/时钟；不实现幂等、取消或调度修复 |
| 检查COLMAP模型合并前的track和图像重叠 | [COLMAP Model Audit](https://github.com/Afloat16/colmap-model-audit) | 传统文本模型一致性、连通性与同名候选 | 不验证新版rig/frame；重投影仅支持两种pinhole；名称重叠不保证可合并 |
| 接入相机轨迹时混淆w2c/c2w、OpenCV/OpenGL与尺度 | [Pose Convention Bridge](https://github.com/Afloat16/pose-convention-bridge) | 显式刚性位姿转换、COLMAP/TUM/JSON与Nerfstudio导出 | 不猜外参、内参或尺度；点云需另用同一世界变换 |

## 从哪个开始

- **日常项目诊断**：从 Research to Fix 开始；接口兼容性症状使用 LLM Handshake 的针对性探测。
- **需求与设计讨论**：用 Debate Direction 把分歧转成可验证条件，再进入代码工作。
- **任务交付与等待输入**：用 StewardCheck 记录改动与检查；需要提醒时单独配置 Agent Action Notifier。
- **机器人排障**：录包时序用 Bag Timeline Audit，导出坐标链用 TF Route Audit。
- **大模型集成**：接口探测用 LLM Handshake，保存的流式响应用 SSE Toolcall Audit，真实工具尝试记录用 Tooltrace Audit。
- **影像几何**：重建用 ReconTrail，传统 COLMAP 模型预检用 COLMAP Model Audit，明确位姿约定后使用 Pose Convention Bridge。
- **MCP 概率建议**：查看 Jev MCP 的服务条件和权限边界。

这些是按当前代码与文档做的用途推荐。各项目的真实测试环境、发布日期、兼容性和验证缺口，以仓库中的记录和实际 CI 为准；目录提交不等于维护者已经收录，也不代表上游平台背书。

## 调研与推广记录

六个新工具的选题来自 [29个线程、336条评论的调研](DEMAND_REVIEW.zh-CN.md)。采样不是全领域需求统计排名；六项目为MIT实验性工具，合计67项测试，最新六仓库的36个OS/Python CI组合通过。另见 [实际推广记录](OUTREACH.zh-CN.md)，收录申请仍需由目录维护者审查。


