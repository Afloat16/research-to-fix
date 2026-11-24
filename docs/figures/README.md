# Project figures / 项目图表

These local SVGs are original vector figures for the English and Chinese landing pages. They use no external fonts, images, scripts, or chart services. The two architecture diagrams are conceptual descriptions of the workflow and current helper architecture; the three quantitative charts are generated from the actual printed reports of [GitHub Actions run 45339912941](https://github.com/Afloat16/research-to-fix/actions/runs/45339912941), job 138260812812, commit `672145cb26aadc9d7ac43e23a3f0e96ec8abbe0f`.

- `benchmark-snapshot.json`: frozen, source-linked JSON reports (unchanged measurements) used for all quantitative figures. See [performance evidence](../PERFORMANCE.md) and [benchmark protocol](../../benchmarks/README.md).
- `render.cjs`: deterministic Node.js development-only SVG generator; it is not a runtime dependency of the skill or Python helpers.
- `workflow*.svg` and `retrieval-architecture*.svg`: system flow and retrieval architecture.
- `synthetic-ranking*.svg`, `github-ranking*.svg`, `efficiency*.svg`: zero-origin bar charts with units, direct labels, and workload/provenance notes. The displayed percentages and times are rounded only for readability.

Regenerate from the repository root with `node docs/figures/render.cjs`. Check committed figures with `node docs/figures/render.cjs --check`. To publish new measured values, first retain the exact CI job reports, update the snapshot and source metadata, rerender, and update the surrounding README text and performance report. Do not replace data with desired or projected results. The development fixtures are not independent held-out evaluations, and none of the charts measures agent repair success.

中文：SVG 为本项目原创矢量图；两张架构图是工作流与检索实现示意，三张实验图均由上述 CI 真实报告生成。中英文共享同一冻结数据，避免数字漂移。Node.js 仅用于维护图表，不是 Skill 运行时依赖。

## Research-decision figure

`research-decision*.svg` visualizes the workflow plus measured discovery replay and numerical variance comparison from [CI run 45343672697](https://github.com/Afloat16/research-to-fix/actions/runs/45343672697), job 138272992882, commit `8d5d2aee6631cb165216069d51792ad8df7aafbb`. Both languages use [research-snapshot.json](research-snapshot.json) and `render-research.cjs`. Regenerate with `node docs/figures/render-research.cjs`; CI uses `--check`. The snapshot is the actual printed report; the diagram distinguishes development ranking from local measured repairs.

## v1.0.0 release figure

`release-v1*.svg` uses the frozen printed reports in [v1-snapshot.json](v1-snapshot.json) from [offline CI run 45355977079](https://github.com/Afloat16/research-to-fix/actions/runs/45355977079) (job 138313769739, commit `618413f03a715cfb5573bc0f655d92d931d9db95`). A separate earlier authorized [known-item probe](https://github.com/Afloat16/research-to-fix/actions/runs/45355435962) is retained in the JSON, not mixed into offline latency. Regenerate/check using `node docs/figures/render-v1.cjs [--check]`. The two curated algorithm corpora, mock transport, and tiny exact-attention example do not establish general agent repair success or GPU performance.

## External holdout figure

`independent-holdout*.svg` is rendered from `independent-snapshot.json`: actual holdout run 45359141496 (job 138324408563) and parity run 45360121033 (job 138327753247). `node docs/figures/render-independent.cjs --check` verifies deterministic SVGs. Three selected methods are visualized, all six are preserved in the JSON and full report. Pointwise bootstrap intervals are unadjusted; not agent repair scores.

## Specialized competitor figure

`competitor-diagnostic*.svg` derives from `competitor-snapshot.json`, the actual completed [CI run 45361899401](https://github.com/Afloat16/research-to-fix/actions/runs/45361899401), job 138333776080. Run `node docs/figures/render-competitor.cjs --check` to verify both localized figures. nDCG bars and prepared-token scoring times have separate axes and scopes. Full build times and limitations are preserved in the JSON and [report](../../benchmarks/COMPETITOR_RESULTS.md).
