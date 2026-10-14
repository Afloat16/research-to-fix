# Outreach and directory-submission record — 2026-10-14

[English](OUTREACH.md) | [简体中文](OUTREACH.zh-CN.md)

Outreach starts by checking contribution rules, duplicate submissions, and tool applicability. Resource directories receive PRs; issue discussions first receive advice specific to the current symptom, followed by a tool link and its boundaries. Afloat16 is both author and maintainer. No upstream endorsement, adoption rate, or completed human review is claimed. Star counts are reach snapshots at collection time.

## New directory submissions in this round

Five PRs cover four directories. The GitHub API confirmed all five were authored by Afloat16, are open, and have not been merged. Changes only add README entries; no existing directory content was removed.

| Actual submission | Star snapshot | Recommended resources | Current status |
|---|---:|---|---|
| [punkpeye/awesome-mcp-servers #16394](https://github.com/punkpeye/awesome-mcp-servers/pull/16394) | 96,314 | jev-mcp | open; awaiting maintainer review |
| [kiloreux/awesome-robotics #119](https://github.com/kiloreux/awesome-robotics/pull/119) | 7,236 | bag-timeline-audit | open; awaiting maintainer review |
| [kiloreux/awesome-robotics #120](https://github.com/kiloreux/awesome-robotics/pull/120) | 7,236 | tf-route-audit | open; awaiting maintainer review |
| [Hannibal046/Awesome-LLM #849](https://github.com/Hannibal046/Awesome-LLM/pull/849) | 27,446 | sse-toolcall-audit, tooltrace-audit, llm-handshake | open; awaiting maintainer review |
| [MrNeRF/awesome-3D-gaussian-splatting #447](https://github.com/MrNeRF/awesome-3D-gaussian-splatting/pull/447) | 8,946 | colmap-model-audit, pose-convention-bridge | open; awaiting maintainer review |

The Punkpeye directory's automated checks require a Glama link. The [existing public Jev MCP page](https://glama.ai/mcp/servers/Afloat16/jev-mcp) and its [four-tool schema](https://glama.ai/mcp/servers/Afloat16/jev-mcp/schema) were checked, and the page's official dynamic score badge was added. The schema's TDQS score is dated 2026-09-28; it is not a record newly created in this round, evidence of a successful real invocation, or platform endorsement. Maintainers will determine whether all directory checks are satisfied.

## Demand-matched comments in this round

Five comments were published on relevant, open, unlocked issues and confirmed through the GitHub API. There was no identical Afloat16 recommendation before publication. The original research snapshot of 336 comments excludes this round's outreach comments; threads may continue to grow afterward.

| Actual comment | Project star snapshot | Recommended resource | Approach |
|---|---:|---|---|
| [colmap/colmap #1703](https://github.com/colmap/colmap/issues/1703#issuecomment-6164675576) | 12,940 | colmap-model-audit | Published with specific troubleshooting steps and disclosure of the maintenance relationship |
| [ros2/rosbag2 #1845](https://github.com/ros2/rosbag2/issues/1845#issuecomment-6164698180) | 4,439 | bag-timeline-audit | Published with specific troubleshooting steps and disclosure of the maintenance relationship |
| [vllm-project/vllm #44676](https://github.com/vllm-project/vllm/issues/44676#issuecomment-6164726054) | 93,747 | sse-toolcall-audit | Published with specific troubleshooting steps and disclosure of the maintenance relationship |
| [langchain-ai/langgraph #7417](https://github.com/langchain-ai/langgraph/issues/7417#issuecomment-6164775238) | 43,238 | tooltrace-audit | Published with specific troubleshooting steps and disclosure of the maintenance relationship |
| [nerfstudio-project/nerfstudio #3690](https://github.com/nerfstudio-project/nerfstudio/issues/3690#issuecomment-6164799946) | 12,066 | pose-convention-bridge | Published with specific troubleshooting steps and disclosure of the maintenance relationship |

- COLMAP: explains that commonly registered images are matched by name and that a prefix on only one side can break correspondence; model auditing provides only traditional text-track checks and candidate-overlap checks.
- rosbag2: distinguishes live publish/receive counts from offline recorded-time evidence; gaps are not described as proof of dropped frames.
- vLLM: supports saving SSE evidence from low/high reasoning-budget experiments; does not claim to fix ThinkingBudgetStateHolder.
- LangGraph: recommends stable logical call IDs, unique attempts, and events before/after actual execution; auditing supplies neither idempotency nor exactly-once execution.
- Nerfstudio: distinguishes right-multiplied camera-basis changes, left-multiplied world transforms, and actual extrinsics, and points out that the example's JPG input and PNG output paths need checking.

## Previously published recommendations

These were submitted earlier and were not resubmitted in this round. Directory applications and automatically generated drafts still do not constitute accepted listings.

| Recommended resource | Actual link |
|---|---|
| Research to Fix | [open-agent-craft #28](https://github.com/open-agent-craft/awesome-agent-skills/issues/28) |
| Debate Direction | [open-agent-craft #29](https://github.com/open-agent-craft/awesome-agent-skills/issues/29) |
| StewardCheck (MIT subtool only) | [open-agent-craft #30](https://github.com/open-agent-craft/awesome-agent-skills/issues/30) |
| Agent Action Notifier | [open-agent-craft #31](https://github.com/open-agent-craft/awesome-agent-skills/issues/31) |
| LLM Handshake | [open-agent-craft #32](https://github.com/open-agent-craft/awesome-agent-skills/issues/32) |
| Jev MCP | [TensorBlock #3663](https://github.com/TensorBlock/awesome-mcp-servers/issues/3663), with an automatically generated [draft PR #3664](https://github.com/TensorBlock/awesome-mcp-servers/pull/3664) |
| ReconTrail | [awesome-photogrammetry #17](https://github.com/awesome-photogrammetry/awesome-photogrammetry/issues/17) |

## Channels not counted as completed outreach

- Appcypher MCP directory: the fork form returned “was submitted too quickly” twice. One normal refresh still did not create the fork, so this route was stopped; there is no PR.
- Heilcheng Agent Skill Index: the fork form also returned “was submitted too quickly.” In addition, an npm build was actually run on the complete website source pinned to a fixed commit, as required by the contribution guide. Both Node 24 and Node 22 failed with ENOENT / uv_resident_set_memory because the current environment lacks /proc/self/stat. The build was not recorded as passing; there is no PR.
- The Composio skill directory requires validation in an actual Claude environment. That environment is unavailable, and no testing claim was made.
- The robotics-library directory has project-age, star, and independent-adoption thresholds. The new projects do not yet meet them; no submission was made and no human-review confirmation was checked.
- The general Awesome directory currently pauses PRs. Other narrowly scoped agent directories do not fit these CLIs, and no recommendation was forced into them.

No identical advertisements were sent in bulk, no direct messages were sent, and no comments were fabricated, stars exchanged, or site restrictions bypassed. Listing decisions and feedback belong to external maintainers.

See the [project guide](PROJECTS.md) and [demand research](DEMAND_REVIEW.md).
