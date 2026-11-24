# Project figures / 项目图表

These local SVGs are original vector figures for the English and Chinese landing pages. They use no external fonts, images, scripts, or chart services. The two architecture diagrams are conceptual descriptions of the workflow and current helper architecture; the three quantitative charts are generated from the actual printed reports of [GitHub Actions run 45339912941](https://github.com/Afloat16/research-to-fix/actions/runs/45339912941), job 138260812812, commit `672145cb26aadc9d7ac43e23a3f0e96ec8abbe0f`.

- `benchmark-snapshot.json`: frozen, source-linked JSON reports (unchanged measurements) used for all quantitative figures. See [performance evidence](../PERFORMANCE.md) and [benchmark protocol](../../benchmarks/README.md).
- `render.cjs`: deterministic Node.js development-only SVG generator; it is not a runtime dependency of the skill or Python helpers.
- `workflow*.svg` and `retrieval-architecture*.svg`: system flow and retrieval architecture.
- `synthetic-ranking*.svg`, `github-ranking*.svg`, `efficiency*.svg`: zero-origin bar charts with units, direct labels, and workload/provenance notes. The displayed percentages and times are rounded only for readability.

Regenerate from the repository root with `node docs/figures/render.cjs`. Check committed figures with `node docs/figures/render.cjs --check`. To publish new measured values, first retain the exact CI job reports, update the snapshot and source metadata, rerender, and update the surrounding README text and performance report. Do not replace data with desired or projected results. The development fixtures are not independent held-out evaluations, and none of the charts measures agent repair success.

中文：SVG 为本项目原创矢量图；两张架构图是工作流与检索实现示意，三张实验图均由上述 CI 真实报告生成。中英文共享同一冻结数据，避免数字漂移。Node.js 仅用于维护图表，不是 Skill 运行时依赖。
