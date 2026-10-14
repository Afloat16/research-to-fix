# Afloat16 Project Guide

[English](PROJECTS.md) · [简体中文](PROJECTS.zh-CN.md)

Independent public tools and skills maintained by [Afloat16](https://github.com/Afloat16). Choose by the problem you are solving, then follow the project's installation guide, examples and validation notes.

## Geometry and reconstruction

| Project | What it helps you do | Scope |
|---|---|---|
| [ReconTrail](https://github.com/Afloat16/recontrail) | Inspect photo quality, recover sparse geometry and camera poses, reconstruct calibrated stereo, and share offline interactive reports. | CPU/local workflow; results depend on input, parallax and calibration. No general dense or watertight-mesh guarantee. |
| [COLMAP Model Audit](https://github.com/Afloat16/colmap-model-audit) | Check reciprocal tracks, view connectivity and exact-name overlap candidates in legacy COLMAP text models. | No newer rig/frame validation; reprojection supports PINHOLE/SIMPLE_PINHOLE. Name overlap does not guarantee alignment or database compatibility. |
| [Pose Convention Bridge](https://github.com/Afloat16/pose-convention-bridge) | Convert explicit w2c/c2w, OpenCV/OpenGL and COLMAP/TUM/JSON pose conventions; export Nerfstudio cameras. | Does not infer extrinsics, intrinsics or scale. Apply the same world mapping to scene geometry separately. |

## Robotics diagnostics

| Project | What it helps you do | Scope |
|---|---|---|
| [Bag Timeline Audit](https://github.com/Afloat16/bag-timeline-audit) | Inspect ROS 2 SQLite/MCAP or JSONL timestamps for gaps, regressions, duplicates and declared same-clock topic offsets. | A gap is not proof of loss; does not infer split-bag ordering or decode SQLite payload headers. |
| [TF Route Audit](https://github.com/Afloat16/tf-route-audit) | Inspect exported TF or native URDF topology, required frames, conflicts and observed time windows. | Does not simulate live tf2 cache/interpolation or discover publisher authority; movable URDF joints provide no temporal evidence. |

## Model interfaces and tool execution

| Project | What it helps you do | Scope |
|---|---|---|
| [LLM Handshake](https://github.com/Afloat16/llm-handshake) | Preview and run bounded OpenAI-compatible Chat Completions endpoint probes; compare reports after changes. | Defaults to a model-list GET; inference must be enabled. Not full protocol certification or a model-quality benchmark. |
| [SSE Toolcall Audit](https://github.com/Afloat16/sse-toolcall-audit) | Audit saved Chat Completions/Responses SSE tool-call assembly and compare semantic calls with saved non-stream responses. | Offline; does not repair generation. Different stochastic completions do not automatically imply a regression. |
| [Tooltrace Audit](https://github.com/Afloat16/tooltrace-audit) | Inspect execution attempts or conversations for duplicates, overlaps, missing results and identity conflicts; optionally record argument digests. | Caller supplies stable IDs and meaningful clocks. Does not implement idempotency, cancellation or scheduler fixes. |
| [Jev MCP](https://github.com/Afloat16/jev-mcp) | Ask four read-only advisory tools for bounded decisions, routing, risk signals and yes/no gates. | Unofficial TypeSafe Jev integration; requires service access. State is sent to the external API; advice has no approval authority. |

## Research and engineering workflow

| Project | What it helps you do | Scope |
|---|---|---|
| [Research to Fix](https://github.com/Afloat16/research-to-fix) | Find prior fixes and viable approaches, map evidence to local code, apply a small repair and compare the original symptom before/after. | Search and coding tools come from the host; record validation does not prove a repair worked. |
| [Debate Direction](https://github.com/Afloat16/debate-direction) | Turn ambiguous requirements into independent proposals, challenges, revisions, an issue ledger and testable next steps. | Consensus is not proof. Native skill needs a host with child tasks; the CLI uses the selected model service. |
| [AI Dev Steward / StewardCheck](https://github.com/Afloat16/ai-dev-steward) | Track task-scoped Git changes, explicit checks and review evidence; use the complementary artifact/review skill when appropriate. | CLI and skill are independent. Evidence does not replace human acceptance criteria; MIT applies only to tools/stewardcheck. |
| [Agent Action Notifier](https://github.com/Afloat16/agent-action-notifier) | Receive email/local desktop notifications, track waiting requests and retry failed sends. | Notifications are not approvals; SMTP is opt-in and imported replies do not establish trusted identity. |

## Suggested starting points

- **Unfamiliar bug:** Research to Fix; add LLM Handshake for endpoint integration symptoms.
- **Ambiguous design:** Debate Direction, then validate the selected assumptions in code.
- **Robot data:** Bag Timeline Audit for timing; TF Route Audit for exported frame graphs.
- **Model tool calls:** SSE Toolcall Audit for saved responses; Tooltrace Audit for actual attempt records.
- **3D workflow:** ReconTrail for reconstruction, COLMAP Model Audit for text-model preflight, Pose Convention Bridge after establishing the camera conventions.

## Evidence and community work

The six newer domain utilities were selected from [29 public issue threads and 336 comments](DEMAND_REVIEW.md), a purposive sample rather than a field-wide urgency ranking. They are experimental MIT projects with **67 local tests and 36 passing OS/Python CI combinations** at the recorded release. See the linked runs and limitations in the report.

[Outreach and directory submissions](OUTREACH.md) record actual PRs and issue replies. A submitted recommendation is not a listing, adoption claim or upstream endorsement.

For selected merged upstream contributions, visit [Afloat16's profile](https://github.com/Afloat16).

