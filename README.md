# Research to Fix

**English** | [简体中文](README.zh-CN.md)

**Find similar problems, verify prior solutions, and turn them into a testable local repair.**

Research to Fix is a research and repair workflow that follows the [Agent Skills format](https://agentskills.io/specification). For unfamiliar errors, hard-to-reproduce bugs, training instability, or performance regressions, it guides an agent to investigate whether others have solved a similar problem or found a viable approach, then check that approach against the current project's code, versions, and runtime conditions before applying a fix.

Concept and workflow design: **[Afloat16](https://github.com/Afloat16)**. Maintainer: **Afloat16**.

## Where to start

- To research and repair a project: install the skill, then use the [example requests](#usage).
- To understand source selection and verification: read the [source playbook](skills/research-to-fix/references/source-playbook.md) and [evidence rules](skills/research-to-fix/references/evidence-rules.md).
- To inspect a small reproducible case first: see the [streaming metrics example](examples/streaming-metrics/README.md).
- To record multiple research rounds or hand off evidence: use the [helper tools](#helper-tools) and [case template](skills/research-to-fix/references/case-template.md).

## What it does

| Stage | Output |
| --- | --- |
| Problem fingerprint | Redacted error, environment and versions, call path, minimal reproduction, and success criteria |
| Research across sources | Verifiable evidence from GitHub, Hugging Face, Zhihu, Xiaohongshu, original papers, researchers, and labs |
| Applicability analysis | Source conditions mapped to local files and symbols, differences, candidate approaches, and falsifiable hypotheses |
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
fix PRs online. Verify the differences from the current call path before
changing the code and validating the repair.
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

## Helper tools

```bash
python skills/research-to-fix/scripts/research_case.py queries \
  --error 'RuntimeError: dtype mismatch' --component pytorch \
  --version 2.5 --concept 'mixed precision' \
  --source github_issues --source huggingface_forum

python skills/research-to-fix/scripts/research_case.py init \
  --output /tmp/research-case.json

python skills/research-to-fix/scripts/research_case.py validate \
  /tmp/research-case.json
```

Review the search plan before sending any queries; the detector cannot identify every secret. Omitting `--source` lists all candidates: select 4–8 by relevance. Searches for papers, researchers, and labs use mechanism keywords.

`init` does not overwrite existing files. `validate` checks record structure and evidence references. The standard-library Python helper does not access the network, upload code, execute tests, or independently prove that a repair worked. An empty template with a blocked status is structurally valid. A solved record requires before/after entries with matching commands and success criteria for every failed check of the original symptom. Local inference can be recorded explicitly without inventing external sources.

## Project structure

- `skills/research-to-fix/SKILL.md`: core instructions.
- `skills/research-to-fix/references/`: source selection, evidence rules, repair workflow, and case template.
- `skills/research-to-fix/scripts/research_case.py`: query planning and record validation.
- `tests/`: behavior checks for the helper tool.
- `examples/`: small independently reproducible cases and practice inputs.

## Validation and contributions

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
```

Contributions based on real problems are welcome. Include the triggering request, environment, redacted reproduction, actual research and local validation, and where the workflow wasted searches or misjudged applicability. Do not upload private code, secrets, or customer data. New sources should explain how to verify original content and record access failures; new scripts should include actual execution results.

The independently tried [streaming metrics case](examples/streaming-metrics/README.md) includes original evidence, a failing baseline, a compatible fix, and reproducible checks. It is a small synthetic case and does not establish effectiveness on large engineering or research problems. The current version cannot guarantee access to every platform, an external answer for every problem, or success for every repair. Record access restrictions and validation gaps.

## License

[MIT](LICENSE).

## Related projects

Browse the [Afloat16 project guide](https://github.com/Afloat16/research-to-fix/blob/main/docs/PROJECTS.md) by task: requirements debate, research and repair, task checks, endpoint diagnostics, notifications, MCP advice, robotics troubleshooting, and 3D reconstruction.

Six domain-specific tools were added in this round. See the [review of 29 threads and 336 comments](docs/DEMAND_REVIEW.md) for their selection and boundaries, and the [outreach record](docs/OUTREACH.md) for actual directory submissions and replies to relevant issues.

