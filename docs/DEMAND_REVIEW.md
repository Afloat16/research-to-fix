# Demand research and tool selection — 2026-10-14

[English](DEMAND_REVIEW.md) | [简体中文](DEMAND_REVIEW.zh-CN.md)

This review selected six specific engineering needs across robotics, LLM tool calling, and 3D reconstruction. Deliverables were limited to diagnostics or format conversions that can be checked locally. The goal is to add evidence to existing ROS, model-service, execution-framework, and reconstruction-engine workflows, helping users clarify problems with inputs, timing, call identity, and coordinate conventions before reporting an issue, comparing versions, or connecting a downstream workflow.

The collected material covers 29 public issue threads and 336 comments, of which 332 were not marked by the platform as comments from bot accounts. At collection time, 16 threads were open and 13 were closed. This is a **purposive sample** selected for relevance to the problems, not a representative survey or a statistical ranking of demand across these fields. More comments do not mean more independent users, a more severe problem, or stronger willingness to pay; repeated follow-ups, disagreements, and troubleshooting by the same person can all increase the count. Project stars are only a dated indicator of reach, not evidence of demand, correctness, or tool quality.

All six projects are currently experimental tools. Public threads establish that a problem was raised; tool documentation states what the current implementation promises. Reproducible inputs and validation results are still needed to connect the two. The links below retain the original discussion entry points without reproducing comment bodies, and these tools are not presented as having resolved the corresponding upstream issues.

| Field | Tool | Scope of this delivery |
|---|---|---|
| Robotics | [bag-timeline-audit](https://github.com/Afloat16/bag-timeline-audit) | Read-only checks for backward time jumps, duplicate timestamps, gaps, and cross-topic pairing on a shared clock in ROS 2 SQLite, MCAP, or JSONL records. |
| Robotics | [tf-route-audit](https://github.com/Afloat16/tf-route-audit) | Checks topology, required frames, conflicts, and observed dynamic time ranges in exported TF records or native URDF. |
| LLM workflows | [sse-toolcall-audit](https://github.com/Afloat16/sse-toolcall-audit) | Checks tool-call assembly, completion state, and argument semantics in saved Chat Completions / Responses SSE; can compare a saved non-streaming response. |
| LLM workflows | [tooltrace-audit](https://github.com/Afloat16/tooltrace-audit) | Checks repeated attempts, overlapping retries, missing results, and call-identity conflicts in explicit execution events or conversation records. |
| 3D reconstruction | [colmap-model-audit](https://github.com/Afloat16/colmap-model-audit) | Read-only checks of fields, bidirectional tracks, consistency, view connectivity, and same-name image overlap in traditional COLMAP text sparse models. |
| 3D reconstruction | [pose-convention-bridge](https://github.com/Afloat16/pose-convention-bridge) | Converts rigid camera poses and related file formats after the user explicitly declares pose direction, camera axes, and the world transform. |

## Selection method and interpretation of evidence

Selection considered recurrence of symptoms across threads, recent follow-ups, effects on data or workflows, the feasibility of offline review, and whether an existing runtime could be reused rather than reimplemented. No weighted score was assigned from comment counts or stars, and the six needs were not ranked as “most urgent.” Selecting two needs per field was an implementation-scope decision, not a claim that demand is equal across the three fields.

- **Original sources remain traceable.** [thread-index.json](thread-index.json) retains thread URLs, status at collection, update dates, comment counts, and comment links. Its 29 threads and 336 comment links allow the review scope to be checked; it contains no comment bodies.
- **Status is not an outcome.** An open thread may already have a workaround. A closed thread may reflect a fix, a duplicate, a version change, or another reason for closure. Closed threads supply historical symptoms and regression leads here, not evidence of a fault that still exists.
- **An update date is not urgency.** Recent replies can help identify conditions still being discussed, but may only add information. Similar behavior across different versions, models, hardware, data, and configurations cannot automatically be assigned the same root cause.
- **The report separates three levels of conclusion.** Symptoms reported in threads, judgments about tool opportunities, and current implementation capabilities are described separately. Passing structural or timing checks does not establish that sensors dropped no frames, execution occurred exactly once, a protocol is fully compatible, or reconstruction accuracy is acceptable.
- **Existing alternatives remain the first option.** If an official tool already performs the actual task, use it first. This comparison explains where a small tool can add diagnostics for a particular input or workflow step; it does not establish that no comparable tools exist.

## Why these six needs entered the implementation scope

| Tool | Demand signals in the sources | Selection rationale and what remains unverified |
|---|---|---|
| bag-timeline-audit | rosbag2 #1845 concerns troubleshooting missing frames during recording; #2173 and #2023 provide historical leads about ordering at identical timestamps and simulation-clock differences. | Separating gaps in recorded data, backward time jumps, and different time bases helps users provide reviewable issue evidence. The tool can inspect only the records it sees; it cannot determine whether a missing record originated at the sensor, transport, recording, or playback stage. Real split bags and complex compressed recordings remain outside the promised scope. |
| tf-route-audit | geometry2 #749, #798, and rosbag2 #2094 concern paths, authority, and old-time data, respectively. | Topology errors and insufficient time coverage can first be isolated offline without installing or running the full ROS stack. Multiple parents in an aggregated export are a finding to review. An edge observed within a time range does not establish continuous queryability, and exported records cannot recover live authority or tf2 cache behavior. |
| sse-toolcall-audit | vLLM #31501, #45449, #39426, and #44676 concern streamed arguments, function names, Responses assembly, and interference from reasoning markers. | Saved service output becomes a repeatably checkable sample for comparing parser or client changes. A capture shows only the visible result received by the client; it cannot by itself assign fault to the model, parser, or network. Differences between two stochastic generations do not automatically establish a regression. |
| tooltrace-audit | LangGraph #7417 raises re-execution of long calls; #8204 concerns call-termination conditions; #8102 discusses pre-execution policy hooks. | Call identity, attempts, and result pairing are shared prerequisites for checking retries and execution records. Offline auditing does not implement the policy interception, scheduling fixes, or idempotency protection discussed in those threads. Callers still need stable IDs, applicable clocks, and complete events to distinguish legitimate retries from duplicate side effects. |
| colmap-model-audit | COLMAP #1703 concerns model merging; #4557 and #4376 provide leads involving versions and multi-camera rigs. | Checking references, tracks, and overlap candidates in traditional text models before merging or downstream use reduces format-level uncertainty. This implementation does not check new rig/frame files or perform multi-camera geometric optimization. Passing structural checks or finding name overlap does not establish that COLMAP/GLOMAP accuracy problems have been resolved. |
| pose-convention-bridge | Nerfstudio #2182, #3101, #3690, and #3484 concern pose integration from ORB-SLAM, RTAB-Map, COLMAP, and dataparser output. | Explicit w2c/c2w direction, camera axes, quaternion order, and world mapping make reversible conversions easier to review. The tool does not infer source extrinsics, world orientation, or scale. Correct matrix conversion still requires actual image correspondence, intrinsics, and scene points to use the same world mapping. |

## Collected thread index

| Thread | Status at collection | Comments | Last updated |
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

## Traceable demand evidence

The following thread and comment entry points were retained during selection. Upstream titles are preserved to make them searchable. Links support review and do not imply that comment authors endorse these projects; no comment bodies are reproduced in this report. Statuses and dates are collection snapshots.

### bag-timeline-audit

- [ros2/rosbag2 #1845](https://github.com/ros2/rosbag2/issues/1845): [humble] How to avoid frames dropped without buffsize and chunksize options?; status at collection: open.
  - [Comment 2026-03-31](https://github.com/ros2/rosbag2/issues/1845#issuecomment-4161656893) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-10-03](https://github.com/ros2/rosbag2/issues/1845#issuecomment-5966319094) retained for review; see the upstream thread for the full discussion.
- [ros2/rosbag2 #2173](https://github.com/ros2/rosbag2/issues/2173): Player does not preserve the order of messages with the same timestamp; status at collection: closed.
- [ros2/rosbag2 #2023](https://github.com/ros2/rosbag2/issues/2023): Send timestamp and receive timestamp are in different time systems for simulation; status at collection: closed.
  - [Comment 2025-05-28](https://github.com/ros2/rosbag2/issues/2023#issuecomment-2917857175) retained for review; see the upstream thread for the full discussion.
  - [Comment 2025-05-29](https://github.com/ros2/rosbag2/issues/2023#issuecomment-2919787678) retained for review; see the upstream thread for the full discussion.

### tf-route-audit

- [ros2/geometry2 #749](https://github.com/ros2/geometry2/issues/749): Unexpected output of _chainAsVector(); status at collection: open.
  - [Comment 2025-01-16](https://github.com/ros2/geometry2/issues/749#issuecomment-2596914706) retained for review; see the upstream thread for the full discussion.
  - [Comment 2025-01-17](https://github.com/ros2/geometry2/issues/749#issuecomment-2597688808) retained for review; see the upstream thread for the full discussion.
- [ros2/geometry2 #798](https://github.com/ros2/geometry2/issues/798): No authority available; status at collection: open.
  - [Comment 2025-08-27](https://github.com/ros2/geometry2/issues/798#issuecomment-3229958334) retained for review; see the upstream thread for the full discussion.
  - [Comment 2025-08-28](https://github.com/ros2/geometry2/issues/798#issuecomment-3233753625) retained for review; see the upstream thread for the full discussion.
- [ros2/rosbag2 #2094](https://github.com/ros2/rosbag2/issues/2094): rosbag2 playback causes TF_OLD_DATA and "trajectory ends in the past" errors; status at collection: closed.
  - [Comment 2025-07-25](https://github.com/ros2/rosbag2/issues/2094#issuecomment-3116965066) retained for review; see the upstream thread for the full discussion.
  - [Comment 2025-07-25](https://github.com/ros2/rosbag2/issues/2094#issuecomment-3119438729) retained for review; see the upstream thread for the full discussion.

### sse-toolcall-audit

- [vllm-project/vllm #44676](https://github.com/vllm-project/vllm/issues/44676): [Bug]: thinking_token_budget forces reasoning_end tokens into the middle of tool-call arguments — ThinkingBudgetStateHolder doesn't treat `<tool_call>` as implicit reasoning end (Qwen3.5+); status at collection: open.
  - [Comment 2026-06-05](https://github.com/vllm-project/vllm/issues/44676#issuecomment-4634274051) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-08-16](https://github.com/vllm-project/vllm/issues/44676#issuecomment-5309241359) retained for review; see the upstream thread for the full discussion.
- [vllm-project/vllm #31501](https://github.com/vllm-project/vllm/issues/31501): [Bug]: --stream-interval > 1 causes tool call arguments to be empty/lost; status at collection: closed.
  - [Comment 2026-01-21](https://github.com/vllm-project/vllm/issues/31501#issuecomment-3780055111) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-02-10](https://github.com/vllm-project/vllm/issues/31501#issuecomment-3880039798) retained for review; see the upstream thread for the full discussion.
- [vllm-project/vllm #45449](https://github.com/vllm-project/vllm/issues/45449): [Bug]: Gemma4 Tool Parser: Intermittently Missing `function.name` in Streaming Mode; status at collection: closed.
  - [Comment 2026-06-12](https://github.com/vllm-project/vllm/issues/45449#issuecomment-4696618298) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-06-17](https://github.com/vllm-project/vllm/issues/45449#issuecomment-4732167620) retained for review; see the upstream thread for the full discussion.
- [vllm-project/vllm #39426](https://github.com/vllm-project/vllm/issues/39426): [Bug]:  /v1/responses: Protocol drift and malformed tool aggregation breaking official OpenAI SDK compatibility; status at collection: closed.
  - [Comment 2026-04-12](https://github.com/vllm-project/vllm/issues/39426#issuecomment-4230422847) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-04-12](https://github.com/vllm-project/vllm/issues/39426#issuecomment-4230426964) retained for review; see the upstream thread for the full discussion.

### tooltrace-audit

- [langchain-ai/langgraph #7417](https://github.com/langchain-ai/langgraph/issues/7417): Long tool calls (~180s+) silently re-executed from checkpoint on LangGraph Cloud; status at collection: open.
  - [Comment 2026-09-24](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-5820446727) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-10-04](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-5984099191) retained for review; see the upstream thread for the full discussion.
- [langchain-ai/langgraph #8204](https://github.com/langchain-ai/langgraph/issues/8204): create_react_agent aborts return_direct=True tools with "need more steps" when remaining_steps == 1; status at collection: open.
  - [Comment 2026-08-24](https://github.com/langchain-ai/langgraph/issues/8204#issuecomment-5391663130) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-09-09](https://github.com/langchain-ai/langgraph/issues/8204#issuecomment-5600364019) retained for review; see the upstream thread for the full discussion.
- [langchain-ai/langgraph #8102](https://github.com/langchain-ai/langgraph/issues/8102): RFC: Pre-execution tool call interception hooks for policy enforcement; status at collection: open.
  - [Comment 2026-09-22](https://github.com/langchain-ai/langgraph/issues/8102#issuecomment-5775006368) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-09-23](https://github.com/langchain-ai/langgraph/issues/8102#issuecomment-5787601045) retained for review; see the upstream thread for the full discussion.

### colmap-model-audit

- [colmap/colmap #1703](https://github.com/colmap/colmap/issues/1703): How to merge models?; status at collection: open.
  - [Comment 2024-10-24](https://github.com/colmap/colmap/issues/1703#issuecomment-2434417021) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-02-27](https://github.com/colmap/colmap/issues/1703#issuecomment-3974883064) retained for review; see the upstream thread for the full discussion.
- [colmap/colmap #4557](https://github.com/colmap/colmap/issues/4557): Multiple Bug found in Colmap 3.13.0 and Colmap 4.1.0; status at collection: open.
  - [Comment 2026-08-19](https://github.com/colmap/colmap/issues/4557#issuecomment-5337482793) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-08-21](https://github.com/colmap/colmap/issues/4557#issuecomment-5372485130) retained for review; see the upstream thread for the full discussion.
- [colmap/colmap #4376](https://github.com/colmap/colmap/issues/4376): GLOMAP on ETH3D terrains multi-camera rig: significantly worse ground-truth rotation accuracy than COLMAP despite similar sparse reconstruction quality; status at collection: open.
  - [Comment 2026-05-10](https://github.com/colmap/colmap/issues/4376#issuecomment-4416631516) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-08-11](https://github.com/colmap/colmap/issues/4376#issuecomment-5255367058) retained for review; see the upstream thread for the full discussion.

### pose-convention-bridge

- [nerfstudio-project/nerfstudio #2182](https://github.com/nerfstudio-project/nerfstudio/issues/2182): Can I convert the camera pose obtained from ORB-SLAM into a coordinate system format under colmap for use in nerfstudio?; status at collection: closed.
  - [Comment 2023-07-13](https://github.com/nerfstudio-project/nerfstudio/issues/2182#issuecomment-1634273832) retained for review; see the upstream thread for the full discussion.
  - [Comment 2023-07-13](https://github.com/nerfstudio-project/nerfstudio/issues/2182#issuecomment-1634310400) retained for review; see the upstream thread for the full discussion.
- [nerfstudio-project/nerfstudio #3101](https://github.com/nerfstudio-project/nerfstudio/issues/3101): Problem using ORB-SLAM2 results instead of COLMAP for the data processing step; status at collection: closed.
  - [Comment 2024-05-24](https://github.com/nerfstudio-project/nerfstudio/issues/3101#issuecomment-2130324279) retained for review; see the upstream thread for the full discussion.
- [nerfstudio-project/nerfstudio #3690](https://github.com/nerfstudio-project/nerfstudio/issues/3690): Convert RTAB-Map poses to Nerfstudio format; status at collection: open.
  - [Comment 2025-11-28](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-3588690311) retained for review; see the upstream thread for the full discussion.
  - [Comment 2026-05-10](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-4414345578) retained for review; see the upstream thread for the full discussion.
- [nerfstudio-project/nerfstudio #3484](https://github.com/nerfstudio-project/nerfstudio/issues/3484): What is the coordinate convention for the saved dataparser_transforms.json ?; status at collection: open.
  - [Comment 2024-10-23](https://github.com/nerfstudio-project/nerfstudio/issues/3484#issuecomment-2432588341) retained for review; see the upstream thread for the full discussion.
  - [Comment 2024-10-23](https://github.com/nerfstudio-project/nerfstudio/issues/3484#issuecomment-2432625958) retained for review; see the upstream thread for the full discussion.

## Existing tools, competition, and capability boundaries

These alternatives relate directly to the specific workflows reviewed here; this is not a complete competitive landscape. The value of a new project should be established through input compatibility, review effort, and useful reports. Listing a few upstream issues is not enough to claim a gap in existing tooling.

| Tool in this delivery | What existing tools provide | What this tool adds and cannot replace |
|---|---|---|
| bag-timeline-audit | `ros2 bag info/play` provides bag information and playback; [Foxglove](https://docs.foxglove.dev/docs/visualization/connecting/local-data) already supports ROS 2 `.db3`, `.mcap`, and multi-file sources of the same format. | Adds bounded, machine-readable timing checks for a single native file or JSONL without decoding payloads, replaying, or modifying bags. It cannot prove transport loss and does not automatically infer split-file ordering or support compressed SQLite or ROS 1 bags. Cross-topic pairing requires the user to confirm a shared clock; nearest-sample pairing is not certification of sensor synchronization quality. |
| tf-route-audit | [tf2 CLI tools](https://github.com/ros2/geometry2/blob/rolling/tf2_ros/doc/cli_tools.rst) already provide live diagnostics for frame graphs, timing statistics, chains, and broadcasters. | Adds checks of explicit exported records and native URDF without ROS. It does not implement tf2 caching, interpolation, transform composition, or live authority discovery, and it does not parse xacro. An observed dynamic range containing a timestamp does not guarantee queryability at that timestamp; movable URDF joints provide no evidence of runtime pose timing. |
| sse-toolcall-audit | vLLM parsers are server-side implementations; [LLM Handshake](https://github.com/Afloat16/llm-handshake) performs explicitly authorized live Chat Completions probes and does not test Responses. | Reads saved raw Chat Completions / Responses SSE offline, assembles calls, and checks completion markers, strict object arguments, and semantic comparisons. It is not a conformance test for every protocol field. It executes no tools, makes no network requests, does not fix vLLM, and cannot classify differences between two stochastic generations as a definite fault. |
| tooltrace-audit | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) supports resumption through checkpoints; [LangSmith](https://docs.langchain.com/langsmith/observability) provides tracing and observability. [Side effects during resumption](https://docs.langchain.com/oss/python/langgraph/interrupts) still require appropriate idempotency design; tracing alone does not guarantee exactly-once execution. | Checks a documented event contract and also provides an explicitly enabled Recorder; it does not claim direct import of native LangGraph/LangSmith archives. Execution mode requires stable identity and comparable clocks within the same run; conversation mode can check only call/result ordering. Repeated argument signatures are review candidates, not proof of duplicate execution or an infinite loop. It does not intercept, cancel, or deduplicate tools, or fix checkpoint scheduling. |
| colmap-model-audit | The [COLMAP CLI](https://colmap.github.io/cli.html) already provides `model_converter` and `model_analyzer`; [PyCOLMAP](https://colmap.github.io/pycolmap/pycolmap.html) already checks internal consistency and finds commonly registered images. The [official model format](https://colmap.github.io/format.html) also includes rigs/frames. | The differences are a standard-library implementation, traditional text triples, explicit checks, and bounded JSON reports; consistency and overlap checks are not claimed as new capabilities. Binary models require official conversion first. Residuals are computed only for PINHOLE / SIMPLE_PINHOLE; unknown or new camera models are explicitly unverified. Shared names identify merge candidates, not geometric registration, database compatibility, or rig calibration. The tool does not reconstruct, merge, filter, or repair upstream software. |
| pose-convention-bridge | [Nerfstudio coordinate conventions](https://docs.nerf.studio/quickstart/data_conventions.html) and its [dataparser](https://docs.nerf.studio/_modules/nerfstudio/data/dataparsers/base_dataparser.html) already define training inputs, parser transforms, and inverse mappings. | Adds explicit, verifiable rigid pose-direction and camera-axis conversions, plus a declared world mapping; it is not a complete parser or calibration workflow. `--dataparser-transform` uses the declared forward mapping and does not automatically invert it or compose `applied_transform`. It does not infer the up axis, centering, scale, or RTAB-Map extrinsics. Intrinsics/distortion are passed through, not calibrated or undistorted; scene points/meshes must separately receive the same world mapping. |

## How to judge whether these deliverables are useful

Current documentation positions the tools as experimental implementations, with synthetic inputs used in examples and tests. Configuring cross-platform CI is not equivalent to validation on real robot bags, complete server stacks, production execution frameworks, or large reconstruction scenes. Actual CI outcomes must come from the corresponding Actions records. Passing structural checks is also no substitute for acceptance of the actual workflow.

Next validation should use authorized local samples with explicit expectations: timing audits should distinguish record gaps from mixed clocks; TF checks should distinguish missing paths from insufficient temporal evidence; SSE checks should include parallel calls, missing fields, and truncation; execution traces should cover both legitimate retries and repeated attempts; COLMAP checks should compare independently constructed broken references with valid models; pose conversions should use known camera centers, directions, and non-unit world scales to check round trips and mapping order. Only these validation results can support the corresponding capability claims. Discussion counts cannot establish adoption, diagnostic benefit, or performance gains.

Input files and exported reports can still contain sensitive metadata such as image names, topic/frame names, call IDs, times, and hashes. Local execution or omission of some report content does not imply anonymization. Data owners must review material before sharing; do not upload real captures, user attachments, private data, or credentials without permission.

## Validation for this release

All six projects are publicly maintained by Afloat16 under the MIT license and include bilingual READMEs, demand evidence, synthetic examples, installation instructions, and boundaries. The latest versions total 67 local tests. Each repository passed all six combinations of Ubuntu/Windows/macOS × Python 3.10/3.13, for a total of 36 remote CI combinations. Passing tests supports only the behavior checked; it does not mean upstream issues are resolved, all protocols are certified, or real robotics/production services have been validated.

| Tool | Local tests | Latest remote CI | Release commit |
|---|---:|---|---|
| [bag-timeline-audit](https://github.com/Afloat16/bag-timeline-audit) | 12 | [6/6 passed](https://github.com/Afloat16/bag-timeline-audit/actions/runs/38538482805) | `4d0fe9d` |
| [tf-route-audit](https://github.com/Afloat16/tf-route-audit) | 10 | [6/6 passed](https://github.com/Afloat16/tf-route-audit/actions/runs/38538489120) | `dc9bc2b` |
| [sse-toolcall-audit](https://github.com/Afloat16/sse-toolcall-audit) | 13 | [6/6 passed](https://github.com/Afloat16/sse-toolcall-audit/actions/runs/38538497052) | `aa59b9a` |
| [tooltrace-audit](https://github.com/Afloat16/tooltrace-audit) | 12 | [6/6 passed](https://github.com/Afloat16/tooltrace-audit/actions/runs/38538502277) | `0b83b73` |
| [colmap-model-audit](https://github.com/Afloat16/colmap-model-audit) | 10 | [6/6 passed](https://github.com/Afloat16/colmap-model-audit/actions/runs/38538509179) | `614adef` |
| [pose-convention-bridge](https://github.com/Afloat16/pose-convention-bridge) | 10 | [6/6 passed](https://github.com/Afloat16/pose-convention-bridge/actions/runs/38538514786) | `fe89aab` |

An additional interoperability check used synthetic ReconTrail output: 8 registered images and 2,500 sparse points, no errors/warnings in the COLMAP model audit, and 8 converted poses. This is not a claim about reconstruction accuracy on real scenes. A new TF regression uses a purely declarative, joint-free URDF with 10,001 frames: it failed before the fix and passed after correcting the initialization limit.

The [project guide](PROJECTS.md) provides task-based entry points; the [outreach record](OUTREACH.md) retains PRs/comments actually submitted and channels that have not succeeded.
