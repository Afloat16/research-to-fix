# 需求调研与工具选择 — 2026-10-14

[English](DEMAND_REVIEW.md) | [简体中文](DEMAND_REVIEW.zh-CN.md)

本次选择了机器人、大模型工具调用和三维重建三个方向的六项具体工程需求，并将交付范围限定为可在本地复核的诊断或格式转换。目标是为 ROS、模型服务、执行框架和重建引擎的既有工作流补充证据，帮助使用者在提交问题、比较版本或接入下游流程前，先把输入、时间、调用身份和坐标约定中的问题说清楚。

调研采集范围为 29 个公开 issue 线程、336 条评论，其中 332 条未由平台标为机器人账号评论；采集时有 16 个 open、13 个 closed 线程。这是按问题相关性选择的**目的性样本**，不是代表性调查，也不是全领域需求的统计排名。评论多不等于独立用户多、问题更严重或付费需求更强；同一人的多次跟进、争论和排障过程都可能增加计数。项目 stars 只能作为带日期的传播范围线索，不能证明需求、正确性或工具质量。

六个项目目前都定位为实验性工具。公开线程说明问题曾被提出，工具文档说明当前实现承诺；二者之间仍需要可复现输入和验证结果建立联系。以下链接保留原始讨论入口，不复制评论正文，不将这些工具描述为已解决对应上游 issue。

| 方向 | 工具 | 本次交付范围 |
|---|---|---|
| 机器人 | [bag-timeline-audit](https://github.com/Afloat16/bag-timeline-audit) | 只读检查 ROS 2 SQLite、MCAP 或 JSONL 中的时间倒退、重复时间、间隙及同一时钟下的跨 topic 配对。 |
| 机器人 | [tf-route-audit](https://github.com/Afloat16/tf-route-audit) | 检查导出的 TF 记录或原生 URDF 中的拓扑、必需 frame、冲突及已观察动态时间范围。 |
| 大模型 | [sse-toolcall-audit](https://github.com/Afloat16/sse-toolcall-audit) | 检查保存的 Chat Completions / Responses SSE 工具调用组装、完成状态与参数语义；可对比保存的非流式响应。 |
| 大模型 | [tooltrace-audit](https://github.com/Afloat16/tooltrace-audit) | 检查显式执行事件或对话记录中的重复尝试、重试重叠、缺失结果及调用身份冲突。 |
| 三维重建 | [colmap-model-audit](https://github.com/Afloat16/colmap-model-audit) | 只读检查 COLMAP 传统文本稀疏模型的字段、双向 track、一致性、视图连通性及同名图像重叠。 |
| 三维重建 | [pose-convention-bridge](https://github.com/Afloat16/pose-convention-bridge) | 在用户明确声明方向、相机轴和世界变换后，转换刚性相机位姿及相关文件格式。 |

## 选择方法与证据解释

选择综合考虑症状在不同线程中的复现、近期跟进、对数据或工作流的影响、离线复核的可行性，以及是否能避免重复实现已有运行时。没有根据评论数或 stars 给出加权分数，也没有将六项需求按“最迫切”排序。每个方向选两项，是本次实现范围的安排，不代表三个方向的需求规模相同。

- **原始入口可回溯。** [thread-index.json](thread-index.json) 保留线程 URL、采集时状态、更新日期、评论数和评论链接。该索引的 29 个线程和 336 个评论链接可用于核对审阅范围，不包含评论正文。
- **状态不能代替结果。** open 线程可能已有 workaround；closed 可能是修复、重复、版本变化或其他关闭原因。closed 线程在这里提供历史症状和回归线索，不作为当前仍有故障的证据。
- **更新日期不能代替紧迫性。** 最近的回复有助于找到仍在讨论的条件，但也可能只是补充信息。不同版本、模型、硬件、数据和配置中的相似表现，不能直接归为同一根因。
- **报告区分三层结论。** 线程中的症状、对工具机会的判断、当前实现能力分别描述。纯结构或时间检查通过，不等于传感器无丢帧、执行恰好一次、协议完全兼容或重建精度合格。
- **替代方案先保留。** 如果官方工具已经能完成实际任务，应优先使用它。本次比较用于说明小工具在哪个输入和环节能补充诊断，并非证明不存在其他同类工具。

## 六项需求为何进入实现范围

| 工具 | 来源中的需求线索 | 选择理由与仍待验证的部分 |
|---|---|---|
| bag-timeline-audit | rosbag2 #1845 涉及录制中帧缺失的排障；#2173 和 #2023 提供同时间戳排序及仿真时钟差异的历史线索。 | 先把“记录中存在间隙”“时间倒退”“使用不同时间基准”分开，便于提供可复核的报错材料。当前只能检查看到的记录，无法确认缺失发生在传感器、传输、录制还是回放阶段；真实分段包及复杂压缩录制仍不在承诺内。 |
| tf-route-audit | geometry2 #749、#798 与 rosbag2 #2094 分别涉及路径、authority 和旧时间数据问题。 | 拓扑错误与时间覆盖不足可以先离线隔离，不要求安装或运行整套 ROS。聚合导出中的多父节点是待复核现象；时间范围内有边不证明连续可查询，更不能从导出记录恢复 live authority 或 tf2 缓存行为。 |
| sse-toolcall-audit | vLLM #31501、#45449、#39426、#44676 涉及流式参数、函数名、Responses 组装及推理标记干扰。 | 将已保存的服务输出变成可重复检查的样本，便于比较 parser 或客户端变更。只能定位客户端收到的可见结果，不能单凭 capture 判定模型、parser 或网络哪一层有错；两个随机生成结果不同也不自动构成回归。 |
| tooltrace-audit | LangGraph #7417 提出长调用重执行；#8204 涉及调用终止条件；#8102 讨论执行前策略挂钩。 | 调用身份、attempt 与结果配对是检查重试及执行记录的共同前提。离线审计不能实现讨论中的策略拦截、调度修复或幂等保护；仍需调用方提供稳定 ID、适用时钟与完整事件，区分合法重试和重复副作用。 |
| colmap-model-audit | COLMAP #1703 涉及模型合并；#4557、#4376 提供版本和多相机 rig 场景中的问题线索。 | 在合并或进入下游前先验证传统文本模型的引用、track 和重叠候选，能减少格式层面的不确定性。该实现不检验新 rig/frame 文件，不处理多相机几何优化，也不能通过结构通过或名称重叠证明 COLMAP/GLOMAP 的精度问题已解决。 |
| pose-convention-bridge | Nerfstudio #2182、#3101、#3690、#3484 涉及 ORB-SLAM、RTAB-Map、COLMAP 和 dataparser 位姿接入。 | 显式表示 w2c/c2w、相机轴、四元数顺序和世界映射，有利于复核可逆转换。它不猜测数据来源的外参、世界朝向或尺度；正确的矩阵转换仍需真实图像对应、内参及场景点采用同一世界映射。 |

## 采集线程索引

| 线程 | 采集时状态 | 评论数 | 最后更新 |
|---|---|---:|---|
| [ros2/rosbag2 #1845](https://github.com/ros2/rosbag2/issues/1845) | open | 19 | 2026-10-03 |
| [ros2/rosbag2 #2173](https://github.com/ros2/rosbag2/issues/2173) | closed | 0 | 2025-09-22 |
| [ros2/rosbag2 #2023](https://github.com/ros2/rosbag2/issues/2023) | closed | 5 | 2025-05-29 |
| [ros2/rosbag2 #2094](https://github.com/ros2/rosbag2/issues/2094) | closed | 3 | 2026-05-10 |
| [ros2/rosbag2 #1482](https://github.com/ros2/rosbag2/issues/1482) | closed | 4 | 2024-08-09 |
| [ros2/geometry2 #749](https://github.com/ros2/geometry2/issues/749) | open | 10 | 2025-01-30 |
| [ros2/geometry2 #798](https://github.com/ros2/geometry2/issues/798) | open | 6 | 2025-09-12 |
| [vllm-project/vllm #31501](https://github.com/vllm-project/vllm/issues/31501) | closed | 10 | 2026-06-13 |
| [vllm-project/vllm #40195](https://github.com/vllm-project/vllm/issues/40195) | closed | 0 | 2026-06-19 |
| [vllm-project/vllm #45449](https://github.com/vllm-project/vllm/issues/45449) | closed | 2 | 2026-06-17 |
| [vllm-project/vllm #16340](https://github.com/vllm-project/vllm/issues/16340) | closed | 1 | 2025-05-12 |
| [vllm-project/vllm #39584](https://github.com/vllm-project/vllm/issues/39584) | closed | 6 | 2026-06-19 |
| [vllm-project/vllm #39426](https://github.com/vllm-project/vllm/issues/39426) | closed | 8 | 2026-08-10 |
| [langchain-ai/langgraph #7417](https://github.com/langchain-ai/langgraph/issues/7417) | open | 84 | 2026-10-05 |
| [langchain-ai/langgraph #8204](https://github.com/langchain-ai/langgraph/issues/8204) | open | 16 | 2026-09-09 |
| [langchain-ai/langgraph #8102](https://github.com/langchain-ai/langgraph/issues/8102) | open | 49 | 2026-10-05 |
| [colmap/colmap #1703](https://github.com/colmap/colmap/issues/1703) | open | 18 | 2026-02-27 |
| [colmap/colmap #4376](https://github.com/colmap/colmap/issues/4376) | open | 16 | 2026-08-11 |
| [colmap/colmap #4557](https://github.com/colmap/colmap/issues/4557) | open | 10 | 2026-08-21 |
| [colmap/colmap #1376](https://github.com/colmap/colmap/issues/1376) | open | 22 | 2023-11-30 |
| [nerfstudio-project/nerfstudio #3101](https://github.com/nerfstudio-project/nerfstudio/issues/3101) | closed | 1 | 2024-05-24 |
| [nerfstudio-project/nerfstudio #3484](https://github.com/nerfstudio-project/nerfstudio/issues/3484) | open | 5 | 2024-10-23 |
| [nerfstudio-project/nerfstudio #2182](https://github.com/nerfstudio-project/nerfstudio/issues/2182) | closed | 3 | 2023-07-13 |
| [nerfstudio-project/nerfstudio #3117](https://github.com/nerfstudio-project/nerfstudio/issues/3117) | open | 13 | 2025-10-10 |
| [vllm-project/vllm #44676](https://github.com/vllm-project/vllm/issues/44676) | open | 2 | 2026-08-31 |
| [vllm-project/vllm #41967](https://github.com/vllm-project/vllm/issues/41967) | closed | 9 | 2026-06-15 |
| [vllm-project/vllm #51914](https://github.com/vllm-project/vllm/issues/51914) | open | 7 | 2026-08-31 |
| [nerfstudio-project/nerfstudio #3690](https://github.com/nerfstudio-project/nerfstudio/issues/3690) | open | 2 | 2026-05-10 |
| [nerfstudio-project/nerfstudio #2718](https://github.com/nerfstudio-project/nerfstudio/issues/2718) | open | 5 | 2025-05-02 |

## 可回溯的需求证据

以下为选择时保留的线程及评论入口，标题沿用上游原文以便检索。链接的作用是支持复核，不代表评论作者认可这些项目；未在本报告复制评论正文。状态和日期均为采集快照。

### bag-timeline-audit

- [ros2/rosbag2 #1845](https://github.com/ros2/rosbag2/issues/1845): [humble] How to avoid frames dropped without buffsize and chunksize options?; 采集时状态：open。
  - [评论 2026-03-31](https://github.com/ros2/rosbag2/issues/1845#issuecomment-4161656893) 保留为复核链接；完整讨论见上游。
  - [评论 2026-10-03](https://github.com/ros2/rosbag2/issues/1845#issuecomment-5966319094) 保留为复核链接；完整讨论见上游。
- [ros2/rosbag2 #2173](https://github.com/ros2/rosbag2/issues/2173): Player does not preserve the order of messages with the same timestamp; 采集时状态：closed。
- [ros2/rosbag2 #2023](https://github.com/ros2/rosbag2/issues/2023): Send timestamp and receive timestamp are in different time systems for simulation; 采集时状态：closed。
  - [评论 2025-05-28](https://github.com/ros2/rosbag2/issues/2023#issuecomment-2917857175) 保留为复核链接；完整讨论见上游。
  - [评论 2025-05-29](https://github.com/ros2/rosbag2/issues/2023#issuecomment-2919787678) 保留为复核链接；完整讨论见上游。
### tf-route-audit

- [ros2/geometry2 #749](https://github.com/ros2/geometry2/issues/749): Unexpected output of _chainAsVector(); 采集时状态：open。
  - [评论 2025-01-16](https://github.com/ros2/geometry2/issues/749#issuecomment-2596914706) 保留为复核链接；完整讨论见上游。
  - [评论 2025-01-17](https://github.com/ros2/geometry2/issues/749#issuecomment-2597688808) 保留为复核链接；完整讨论见上游。
- [ros2/geometry2 #798](https://github.com/ros2/geometry2/issues/798): No authority available; 采集时状态：open。
  - [评论 2025-08-27](https://github.com/ros2/geometry2/issues/798#issuecomment-3229958334) 保留为复核链接；完整讨论见上游。
  - [评论 2025-08-28](https://github.com/ros2/geometry2/issues/798#issuecomment-3233753625) 保留为复核链接；完整讨论见上游。
- [ros2/rosbag2 #2094](https://github.com/ros2/rosbag2/issues/2094): rosbag2 playback causes TF_OLD_DATA and "trajectory ends in the past" errors; 采集时状态：closed。
  - [评论 2025-07-25](https://github.com/ros2/rosbag2/issues/2094#issuecomment-3116965066) 保留为复核链接；完整讨论见上游。
  - [评论 2025-07-25](https://github.com/ros2/rosbag2/issues/2094#issuecomment-3119438729) 保留为复核链接；完整讨论见上游。
### sse-toolcall-audit

- [vllm-project/vllm #44676](https://github.com/vllm-project/vllm/issues/44676): [Bug]: thinking_token_budget forces reasoning_end tokens into the middle of tool-call arguments — ThinkingBudgetStateHolder doesn't treat <tool_call> as implicit reasoning end (Qwen3.5+); 采集时状态：open。
  - [评论 2026-06-05](https://github.com/vllm-project/vllm/issues/44676#issuecomment-4634274051) 保留为复核链接；完整讨论见上游。
  - [评论 2026-08-16](https://github.com/vllm-project/vllm/issues/44676#issuecomment-5309241359) 保留为复核链接；完整讨论见上游。
- [vllm-project/vllm #31501](https://github.com/vllm-project/vllm/issues/31501): [Bug]: --stream-interval > 1 causes tool call arguments to be empty/lost; 采集时状态：closed。
  - [评论 2026-01-21](https://github.com/vllm-project/vllm/issues/31501#issuecomment-3780055111) 保留为复核链接；完整讨论见上游。
  - [评论 2026-02-10](https://github.com/vllm-project/vllm/issues/31501#issuecomment-3880039798) 保留为复核链接；完整讨论见上游。
- [vllm-project/vllm #45449](https://github.com/vllm-project/vllm/issues/45449): [Bug]: Gemma4 Tool Parser: Intermittently Missing `function.name` in Streaming Mode; 采集时状态：closed。
  - [评论 2026-06-12](https://github.com/vllm-project/vllm/issues/45449#issuecomment-4696618298) 保留为复核链接；完整讨论见上游。
  - [评论 2026-06-17](https://github.com/vllm-project/vllm/issues/45449#issuecomment-4732167620) 保留为复核链接；完整讨论见上游。
- [vllm-project/vllm #39426](https://github.com/vllm-project/vllm/issues/39426): [Bug]:  /v1/responses: Protocol drift and malformed tool aggregation breaking official OpenAI SDK compatibility; 采集时状态：closed。
  - [评论 2026-04-12](https://github.com/vllm-project/vllm/issues/39426#issuecomment-4230422847) 保留为复核链接；完整讨论见上游。
  - [评论 2026-04-12](https://github.com/vllm-project/vllm/issues/39426#issuecomment-4230426964) 保留为复核链接；完整讨论见上游。
### tooltrace-audit

- [langchain-ai/langgraph #7417](https://github.com/langchain-ai/langgraph/issues/7417): Long tool calls (~180s+) silently re-executed from checkpoint on LangGraph Cloud; 采集时状态：open。
  - [评论 2026-09-24](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-5820446727) 保留为复核链接；完整讨论见上游。
  - [评论 2026-10-04](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-5984099191) 保留为复核链接；完整讨论见上游。
- [langchain-ai/langgraph #8204](https://github.com/langchain-ai/langgraph/issues/8204): create_react_agent aborts return_direct=True tools with "need more steps" when remaining_steps == 1; 采集时状态：open。
  - [评论 2026-08-24](https://github.com/langchain-ai/langgraph/issues/8204#issuecomment-5391663130) 保留为复核链接；完整讨论见上游。
  - [评论 2026-09-09](https://github.com/langchain-ai/langgraph/issues/8204#issuecomment-5600364019) 保留为复核链接；完整讨论见上游。
- [langchain-ai/langgraph #8102](https://github.com/langchain-ai/langgraph/issues/8102): RFC: Pre-execution tool call interception hooks for policy enforcement; 采集时状态：open。
  - [评论 2026-09-22](https://github.com/langchain-ai/langgraph/issues/8102#issuecomment-5775006368) 保留为复核链接；完整讨论见上游。
  - [评论 2026-09-23](https://github.com/langchain-ai/langgraph/issues/8102#issuecomment-5787601045) 保留为复核链接；完整讨论见上游。
### colmap-model-audit

- [colmap/colmap #1703](https://github.com/colmap/colmap/issues/1703): How to merge models?; 采集时状态：open。
  - [评论 2024-10-24](https://github.com/colmap/colmap/issues/1703#issuecomment-2434417021) 保留为复核链接；完整讨论见上游。
  - [评论 2026-02-27](https://github.com/colmap/colmap/issues/1703#issuecomment-3974883064) 保留为复核链接；完整讨论见上游。
- [colmap/colmap #4557](https://github.com/colmap/colmap/issues/4557): Multiple Bug found in Colmap 3.13.0 and Colmap 4.1.0; 采集时状态：open。
  - [评论 2026-08-19](https://github.com/colmap/colmap/issues/4557#issuecomment-5337482793) 保留为复核链接；完整讨论见上游。
  - [评论 2026-08-21](https://github.com/colmap/colmap/issues/4557#issuecomment-5372485130) 保留为复核链接；完整讨论见上游。
- [colmap/colmap #4376](https://github.com/colmap/colmap/issues/4376): GLOMAP on ETH3D terrains multi-camera rig: significantly worse ground-truth rotation accuracy than COLMAP despite similar sparse reconstruction quality; 采集时状态：open。
  - [评论 2026-05-10](https://github.com/colmap/colmap/issues/4376#issuecomment-4416631516) 保留为复核链接；完整讨论见上游。
  - [评论 2026-08-11](https://github.com/colmap/colmap/issues/4376#issuecomment-5255367058) 保留为复核链接；完整讨论见上游。
### pose-convention-bridge

- [nerfstudio-project/nerfstudio #2182](https://github.com/nerfstudio-project/nerfstudio/issues/2182): Can I convert the camera pose obtained from ORB-SLAM into a coordinate system format under colmap for use in nerfstudio?; 采集时状态：closed。
  - [评论 2023-07-13](https://github.com/nerfstudio-project/nerfstudio/issues/2182#issuecomment-1634273832) 保留为复核链接；完整讨论见上游。
  - [评论 2023-07-13](https://github.com/nerfstudio-project/nerfstudio/issues/2182#issuecomment-1634310400) 保留为复核链接；完整讨论见上游。
- [nerfstudio-project/nerfstudio #3101](https://github.com/nerfstudio-project/nerfstudio/issues/3101): Problem using ORB-SLAM2 results instead of COLMAP for the data processing step; 采集时状态：closed。
  - [评论 2024-05-24](https://github.com/nerfstudio-project/nerfstudio/issues/3101#issuecomment-2130324279) 保留为复核链接；完整讨论见上游。
- [nerfstudio-project/nerfstudio #3690](https://github.com/nerfstudio-project/nerfstudio/issues/3690): Convert RTAB-Map poses to Nerfstudio format; 采集时状态：open。
  - [评论 2025-11-28](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-3588690311) 保留为复核链接；完整讨论见上游。
  - [评论 2026-05-10](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-4414345578) 保留为复核链接；完整讨论见上游。
- [nerfstudio-project/nerfstudio #3484](https://github.com/nerfstudio-project/nerfstudio/issues/3484): What is the coordinate convention for the saved dataparser_transforms.json ?; 采集时状态：open。
  - [评论 2024-10-23](https://github.com/nerfstudio-project/nerfstudio/issues/3484#issuecomment-2432588341) 保留为复核链接；完整讨论见上游。
  - [评论 2024-10-23](https://github.com/nerfstudio-project/nerfstudio/issues/3484#issuecomment-2432625958) 保留为复核链接；完整讨论见上游。

## 现有工具、竞争关系与能力边界

以下是与本次具体工作流直接相关的替代方案，不是完整竞品清单。新项目的价值应由输入适配、复核成本和报告是否有用来验证，不能仅凭列出几条上游 issue 就声称现有工具有空缺。

| 本次工具 | 已有工具能做什么 | 本次补充及不能替代的部分 |
|---|---|---|
| bag-timeline-audit | `ros2 bag info/play` 用于包信息和回放；[Foxglove](https://docs.foxglove.dev/docs/visualization/connecting/local-data) 已支持 ROS 2 `.db3`、`.mcap` 及同格式多文件数据源。 | 补充单原生文件或 JSONL 的有界、机器可读时间检查，不解码 payload、不回放、不改包。不能证明传输丢失，也不支持自动推断分段顺序、压缩 SQLite 或 ROS 1 bag。跨 topic 配对需用户确认时钟相同；nearest-sample 配对不等于传感器同步质量认证。 |
| tf-route-audit | [tf2 CLI 工具](https://github.com/ros2/geometry2/blob/rolling/tf2_ros/doc/cli_tools.rst) 已提供 frame 图、时间统计、链路及 broadcaster 等 live 诊断。 | 补充无需 ROS 的显式导出记录和原生 URDF 检查。不实现 tf2 缓存、插值、变换组合或 live authority 发现；不解析 xacro。动态观察范围包含某时刻不保证该时刻可查询，URDF 可动关节也没有运行时位姿时间证据。 |
| sse-toolcall-audit | vLLM 的 parser 属于服务端实现；[LLM Handshake](https://github.com/Afloat16/llm-handshake) 用于显式授权的实时 Chat Completions 探测，不测试 Responses。 | 本工具离线读取已保存的 Chat Completions / Responses 原始 SSE；组装调用并检查完成标记、严格对象参数及语义对比。它不是全部协议字段的 conformance 检验，不执行工具、不联网、不修复 vLLM，也不能把两次随机生成不一致判作确定故障。 |
| tooltrace-audit | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 以 checkpoint 支持恢复；[LangSmith](https://docs.langchain.com/langsmith/observability) 提供追踪和可观测性。[恢复过程中的副作用](https://docs.langchain.com/oss/python/langgraph/interrupts) 仍需适当的幂等设计，tracing 本身不保证恰好一次执行。 | 本工具检查文档化事件契约，另有显式启用的 Recorder；不声称直接导入原生 LangGraph/LangSmith 归档。执行模式依赖稳定身份及同 run 可比时钟；对话模式只能检查调用／结果顺序。重复参数签名是复核候选，不证明执行重复或死循环；不拦截、取消、去重工具，也不修复 checkpoint 调度。 |
| colmap-model-audit | [COLMAP CLI](https://colmap.github.io/cli.html) 已有 `model_converter`、`model_analyzer`；[PyCOLMAP](https://colmap.github.io/pycolmap/pycolmap.html) 已有内部一致性检查与共同注册图像查询。[官方模型格式](https://colmap.github.io/format.html) 还包含 rigs/frames。 | 差异是标准库实现、传统 text triples、明确检查项和有界 JSON 报告，不宣称一致性或重叠检查是新能力。二进制需先经官方转换；仅 PINHOLE / SIMPLE_PINHOLE 计算残差，未知／新相机模型明确未验证。共同名称只说明合并候选，不证明几何配准、数据库兼容或 rig 标定；不重建、合并、过滤或修复上游。 |
| pose-convention-bridge | [Nerfstudio 坐标规范](https://docs.nerf.studio/quickstart/data_conventions.html) 与其[数据解析器](https://docs.nerf.studio/_modules/nerfstudio/data/dataparsers/base_dataparser.html) 已定义训练输入、解析器变换及逆映射。 | 补充显式、可验证的刚性方向／相机轴转换，以及已声明的世界映射；不是完整 parser 或标定流程。`--dataparser-transform` 使用声明的正向映射，不自动反向还原或组合 `applied_transform`。不推断上轴、居中、尺度或 RTAB-Map 外参；内参／畸变仅透传，不校准或去畸变，场景点／网格需单独应用同一世界映射。 |

## 如何判断这些交付是否有用

当前文档将工具定位为实验性实现，示例和测试使用合成输入。配置了跨平台 CI 不等于已经在真实机器人包、完整服务端、生产执行框架或大型重建场景中验证；实际 CI 结果应以对应 Actions 记录为准。结构检查通过也不能替代业务验收。

下一步验证应选择有明确预期的、获授权的本地样本：时间审计区分记录间隙与时钟混用；TF 检查区分路径缺失与时间证据不足；SSE 检查包含并行调用、缺字段和截断；执行 trace 同时覆盖合法重试和重复 attempt；COLMAP 检查用独立构造的损坏引用及有效模型作对照；位姿转换用已知相机中心、方向和非单位世界尺度检查往返与映射顺序。只有这些验证结果，才能支持相应能力是否成立；不能从讨论数量推出采用率、诊断收益或性能提升。

输入文件和导出报告仍可能包含图像名、topic/frame 名、调用 ID、时间与哈希等敏感元数据。工具本地运行、报告省略部分内容并不等于匿名化；分享前需由数据所有者审查，未经许可不上传真实捕获、用户附件、私有数据或凭据。

## 本次发布验证

六项目均以Afloat16维护、MIT许可公开，包含双语README、需求证据、合成示例、安装说明和边界。最新版本合计67项本地测试；每个仓库的Ubuntu/Windows/macOS × Python3.10/3.13矩阵六项均通过，总36项远程CI组合。测试通过只支持被检查的行为，不代表上游issue已解决、所有协议已认证或真实机器人/生产服务已验证。

| 工具 | 本地测试 | 最新远程CI | 发布提交 |
|---|---:|---|---|
| [bag-timeline-audit](https://github.com/Afloat16/bag-timeline-audit) | 12 | [6/6通过](https://github.com/Afloat16/bag-timeline-audit/actions/runs/38538482805) | `4d0fe9d` |
| [tf-route-audit](https://github.com/Afloat16/tf-route-audit) | 10 | [6/6通过](https://github.com/Afloat16/tf-route-audit/actions/runs/38538489120) | `dc9bc2b` |
| [sse-toolcall-audit](https://github.com/Afloat16/sse-toolcall-audit) | 13 | [6/6通过](https://github.com/Afloat16/sse-toolcall-audit/actions/runs/38538497052) | `aa59b9a` |
| [tooltrace-audit](https://github.com/Afloat16/tooltrace-audit) | 12 | [6/6通过](https://github.com/Afloat16/tooltrace-audit/actions/runs/38538502277) | `0b83b73` |
| [colmap-model-audit](https://github.com/Afloat16/colmap-model-audit) | 10 | [6/6通过](https://github.com/Afloat16/colmap-model-audit/actions/runs/38538509179) | `614adef` |
| [pose-convention-bridge](https://github.com/Afloat16/pose-convention-bridge) | 10 | [6/6通过](https://github.com/Afloat16/pose-convention-bridge/actions/runs/38538514786) | `fe89aab` |

另外以ReconTrail合成输出做互操作检查：8张注册图像、2500个稀疏点，COLMAP模型审计无错误/警告，并转换出8个位姿。这不是实际场景重建精度声明。TF新增纯声明、无joint的10001-frame URDF回归：修复前失败，初始化限额修复后通过。

[项目导航](PROJECTS.zh-CN.md)给出按任务选择的入口；[推广记录](OUTREACH.zh-CN.md)保留真正已提交的PR/评论以及尚未成功的渠道。

