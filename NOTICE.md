# Notice and attribution

NEWS-Radar is built on a fork of [Thysrael/Horizon](https://github.com/Thysrael/Horizon),
released under the MIT License. Upstream's copyright notice is retained unmodified in
`LICENSE` and travels with every file derived from it, as MIT requires.

Every count below was measured on 2026-09-17 by comparing this repository against
`upstream/main` file by file, and it can be re-run: a path present here and absent upstream
is original, a path present in both is derived, and the patch figures are `git diff --numstat
upstream/main..origin/main` on the derived files. Line counts are of the files as they stand
here.

## Derived from Horizon

- `src/`, the pipeline engine: scrapers, orchestration, the AI client, enrichment, the
  summariser, storage and the MCP server. **63 files and 13,965 lines** derive from upstream
  and are the larger part of the code by volume.
- Those 63 files carry **1,598 added and 102 removed lines** of local work across **13 of
  them**, which is more than a set of compatibility fixes: `src/orchestrator.py` alone carries
  902 added lines, and `src/ai/client.py` 292. The original model-compatibility fixes and the
  publishing bug fix are inside that figure rather than the whole of it.
- `docs/` layouts and configuration as inherited at fork time. Every inherited layout has
  since been replaced (see Original work).
- `profiles/tech-news`, `profiles/tech-blog`, `profiles/finance-news` and
  `profiles/ai-creator`, upstream's example profiles, retained because upstream tests depend
  on them. They route nothing in production.

## Original work

**The stages that decide what publishes have no upstream ancestor.** `src/selection/` does not
exist in Horizon at all: 0 files at `upstream/main` against 9 here.

- `src/selection/`, the selection stage: the sift that judges every fetched item
  (`gate.py`), the setwise tournament that ranks the survivors (`setwise.py`, `rank.py`), the
  defender that argues each shortlisted item (`defend.py`), the stage order and the lead-source
  rule (`pipeline.py`), the prompts and enforced schemas (`prompts.py`), the recorded contract
  (`contract.py`), and the adapter into the engine. **9 files, 1,502 lines.**
- `src/ai/synthesis.py`, `src/ai/enrichment_native.py`, `src/ai/prompting/commentary.py`,
  `src/scrapers/retry.py` and `src/seen.py`. **5 files, 759 lines**, none of them upstream.
- Together the original code under `src/` is **14 files and 2,261 lines**, about 14 percent of
  that tree.
- `scripts/check_run_health.py`, run health checking: log parsing, funnel reporting, GitHub
  annotations, the digest footer and failure severity.
- `scripts/notify_telegram.py`, notification delivery.
- `scripts/check_voice.py` and `scripts/check_claims.py`, the writing and claim gates;
  `scripts/draft_commentary.py` and `scripts/notify_drafted.py`, the commentary chain;
  `scripts/record_metrics.py`, `scripts/preflight.py`, `scripts/replay.py`,
  `scripts/replay_rank.py` and `scripts/build_backfill_feed.py`.
- 14 test files, including those covering the selection stage, the setwise ranker, the
  novelty store, run health and the voice gate.
- `profiles/critical-infrastructure`, `profiles/reliability-assurance`,
  `profiles/business-markets`, `profiles/practice` and `profiles/horizon-research`, the
  five-theme editorial taxonomy and its scoring rubrics.
- `.github/workflows/`, scheduling, health gating, notification and self-test.
- `docs/`, the published site: its theme, layouts and includes, the item, commentary and
  playbook collections, the method page, and `STYLE.md`. The layouts inherited at fork time
  were replaced in full.
- `data/config.github.json`, source selection, thresholds, routing and cadence.

## Licence

Upstream code remains under the MIT License, reproduced in `LICENSE`. Original work in
this repository is the work of its author. Any redistribution of the derived portions
must retain upstream's copyright and permission notice.
