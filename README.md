# Research to Fix

**English** | [简体中文](README.zh-CN.md)

**Find similar problems, adapt or combine prior solutions, and verify a local repair.**

Research to Fix is a research and repair workflow that follows the [Agent Skills format](https://agentskills.io/specification). For unfamiliar errors, hard-to-reproduce bugs, training instability, or performance regressions, it guides an agent to investigate whether others have solved a similar problem or found a viable approach, then check that approach against the current project's code, versions, and runtime conditions before applying a fix. Compatible parts of different solutions can be combined, with their contributions, adaptations, and joint validation recorded explicitly.

Concept and workflow design: **[Afloat16](https://github.com/Afloat16)**. Maintainer: **Afloat16**.

## Where to start

- To research and repair a project: install the skill, then use the [example requests](#usage).
- To understand source selection and verification: read the [source playbook](skills/research-to-fix/references/source-playbook.md) and [evidence rules](skills/research-to-fix/references/evidence-rules.md).
- To inspect a small reproducible case first: see the [streaming metrics example](examples/streaming-metrics/README.md).
- To reuse a previous repair: [record a case and recall related cases](#record-and-reuse-a-case) from a directory you choose.
- To record multiple research rounds or hand off evidence: use the [helper tools](#helper-tools) and [case template](skills/research-to-fix/references/case-template.md).

## What it does

| Stage | Output |
| --- | --- |
| Problem fingerprint | Redacted error, environment and versions, call path, minimal reproduction, and success criteria |
| Local case reuse | Related recorded solutions, matching terms, version facts, source references, and limitations to recheck |
| Research across sources | Verifiable evidence from GitHub, Hugging Face, Zhihu, Xiaohongshu, original papers, researchers, and labs |
| Applicability analysis | Source conditions mapped to local files and symbols, candidate approaches, compatible components, tradeoffs, and falsifiable hypotheses |
| Repair and experiments | Small code changes, before/after checks of the original symptom, relevant regressions, costs, and limitations |
| Reviewable delivery | Original links, actual commands, exit codes, observations, and a solved / partial / blocked status |

Choose sources by relevance. When full coverage is requested, search each category and explain any unavailable sources. Zhihu and Xiaohongshu can help uncover experience and terminology; technical conclusions still require original materials or local experiments. Famous authors, conference labels, stars, and likes do not replace evidence.

## Installation

Use a host that supports `SKILL.md`. The host provides search and browsing tools; this project does not bundle a search service, login credentials, or a crawler. The helper script requires Python 3.10+.

Install in a supported host after checking the installation tool you use:

```bash
npx skills add Afloat16/research-to-fix --skill research-to-fix
```

Alternatively, clone the repository and copy the complete `skills/research-to-fix` directory into your host's skills directory. Automatic triggering, Python execution, and UI metadata support depend on the host's configuration.

## Usage

```text
Use $research-to-fix: this project occasionally hangs during multi-GPU training.
First reproduce it and record the versions, then research similar issues and
fix PRs online. Adapt or combine compatible solutions, explain the differences
from the current call path, and validate the complete repair.
```

```text
Use $research-to-fix: our reproduction of a paper performs far below its
reported results. Research the authors' code, Hugging Face configuration,
the published paper, and community reproductions. Identify viable approaches
and compare them with the same data splits, seeds, and resource budget.
```

```text
Use $research-to-fix: cover GitHub, Hugging Face, Zhihu, Xiaohongshu,
relevant leading journals and conferences, researchers, and labs.
Record any sources you cannot access truthfully.
```

## Record and reuse a case

From the repository root, generate a case from actual local test runs, check it, then recall it for a related problem:

```bash
python examples/streaming-metrics/record_case.py \
  --output /tmp/research-to-fix-example

python skills/research-to-fix/scripts/research_case.py validate \
  /tmp/research-to-fix-example/case.json --format json

python skills/research-to-fix/scripts/research_case.py recall \
  --cases-dir /tmp/research-to-fix-example \
  --error 'single-use iterator count mean' --limit 3 --format markdown
```

Choose a **new output directory**; `/tmp/research-to-fix-example` is an example location. The separate `record_case.py` example runs the documented broken implementation and the current fixed implementation in an isolated temporary directory, using the same tests and command. It writes `case.json` and the actual logs and per-test outcomes under `runs/`. This example executes its fixed local tests; the main helper never executes commands from a case file.

For your own cases, point `recall` at their directory. It reads only that directory's top-level JSON files and considers only structurally valid records declaring `solved`. The case directory itself and its JSON entries cannot be symbolic links; ancestors in the explicitly supplied path resolve normally. It returns bounded summaries and matching reasons rather than complete command logs. Ranking uses local BM25 keyword matching, including Chinese character pairs; it requires no network, model, embedding service, or additional package. No matching terms means no result, and weak matches are not added merely to fill the limit.

| Recall option | Effect |
| --- | --- |
| `--cases-dir DIR`, `--error TEXT` | Explicit case directory and a local problem description for keyword matching. |
| `--component TEXT` | Optional trimmed, case-insensitive exact component filter. |
| `--version TEXT` | Report a literal `same` / `different` / `unknown` comparison; it does not change ranking or establish compatibility. |
| `--limit N` | Return at most N candidates; default 5, maximum 20. |
| `--format json` / `--format markdown` | Machine-readable output or a readable candidate list. |

Recall results are leads for a new repair. Recheck the current code, conditions, original evidence, and tests before adapting a prior solution. A relevance score is not proof of correctness, and a recorded `solved` status is not independently authenticated. Recall does not automatically redact local content; review excerpts before sharing them. See [case reuse](skills/research-to-fix/references/case-reuse.md) for resource limits, selection rules, and the upstream implementations that informed this design.

## Helper tools

```bash
python skills/research-to-fix/scripts/research_case.py queries \
  --error 'RuntimeError: dtype mismatch' --component pytorch \
  --version 2.5 --concept 'mixed precision' \
  --source github_issues --source huggingface_forum \
  --repo pytorch/pytorch --language en --limit 4

python skills/research-to-fix/scripts/research_case.py init \
  --output /tmp/research-case.json

python skills/research-to-fix/scripts/research_case.py validate \
  /tmp/research-case.json --format json
```

`queries` generates an offline plan. With no source or language filters or limit, it keeps the default 26 English and Chinese candidates; select 4–8 by relevance before searching. Searches for papers, researchers, and labs use mechanism keywords.

| Query option | Effect |
| --- | --- |
| `--source` | Select source categories; repeat to include several. |
| `--language en` / `--language zh` | Select query languages; repeat to include both. |
| `--limit N` | Cap the number of generated candidates with a positive integer. This does not set or execute an online search budget. |
| `--repo owner/name` | Scope GitHub issue and pull-request candidates to one repository; other sources remain unchanged. |

Review every query before sending it. Input checks reject common credential patterns, detected private addresses, and recognized non-HTTP(S) URI forms, but secret detection is heuristic and cannot guarantee safe disclosure.

`init` does not overwrite existing files. `validate` checks record structure and declared references; `--format json` provides machine-readable results. Its exit codes are **0** for a structurally valid record, **1** for record errors, and **2** for file or JSON input errors. The standard-library helper does not access the network, authenticate to services, upload code, or execute recorded commands. Passing validation establishes neither the truth of the record nor a repair's effectiveness or cause.

Schema version remains **1**. Comparison context, repair attempt, adopted solution, and per-test result fields are optional, and the existing single-attempt format remains usable without them. Stricter checks intentionally reject incomplete or inconsistent records, including missing regression after checks, completed searches without dates, and malformed criteria.

A solved record needs an after pass for **every recorded before check**, including regressions, plus at least one failure-to-pass comparison for the original symptom. Matching checks keep their command, criteria, expected exit code, and any declared comparison context consistent. Multiple attempts retain historical failures and explicitly identify the final attempt; a combined solution needs a supporting experiment that covers the whole combination. The [case template](skills/research-to-fix/references/case-template.md) describes these rules and optional fields. An empty blocked template remains valid, and local inference needs no invented external sources.

For test suites, record optional `test_results` with stable test IDs and outcomes. A pass cannot contain zero passing tests, failures, errors, or unexecuted tests. When details are supplied for a before/after comparison, final results must retain every baseline test ID and pass every test that previously passed, failed, or errored; previously skipped tests may remain skipped. Legacy records without these details remain supported, but the validator cannot detect deleted or skipped tests inside their suite from an aggregate exit code alone.

## Project structure

- `skills/research-to-fix/SKILL.md`: core instructions.
- `skills/research-to-fix/references/`: source selection, case reuse, evidence rules, repair workflow, and case template.
- `skills/research-to-fix/scripts/research_case.py`: query planning, local case recall, and record validation.
- `tests/`: behavior checks for the helper tool.
- `examples/`: small independently reproducible cases and practice inputs.

## Validation and contributions

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
```

CI runs these checks on Python 3.10 and 3.13, then records, validates, and retrieves the streaming example. Successful jobs retain the case, source snapshots, raw test logs, per-test reports, and retrieval result as `repair-case-python-<version>` artifacts for 7 days. These are reviewable results for this small example, not a general repair-success benchmark.

Contributions based on real problems are welcome. Include the triggering request, environment, redacted reproduction, actual research and local validation, and where the workflow wasted searches or misjudged applicability. Do not upload private code, secrets, or customer data. New sources should explain how to verify original content and record access failures; new scripts should include actual execution results.

The independently tried [streaming metrics case](examples/streaming-metrics/README.md) includes original evidence, a failing baseline, a compatible fix, and reproducible checks. It is a small synthetic case and does not establish effectiveness on large engineering or research problems. The current version cannot guarantee access to every platform, an external answer for every problem, or success for every repair. Record access restrictions and validation gaps.

## License

[MIT](LICENSE).

## Related projects

Browse the [Afloat16 project guide](https://github.com/Afloat16/research-to-fix/blob/main/docs/PROJECTS.md) by task: requirements debate, research and repair, task checks, endpoint diagnostics, notifications, MCP advice, robotics troubleshooting, and 3D reconstruction.

Six domain-specific tools were added in this round. See the [review of 29 threads and 336 comments](docs/DEMAND_REVIEW.md) for their selection and boundaries, and the [outreach record](docs/OUTREACH.md) for actual directory submissions and replies to relevant issues.

