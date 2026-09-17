---
layout: item
title: "New Benchmark Finds Agents Save ERP Records Correctly in as Few as 3% of Runs"
date: 2026-09-17 21:53:34 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 7.0
link: "https://arxiv.org/abs/2609.17885"
source: "arXiv cs.AI"
edition_url: "/2026/09/17/2153-summary-en.html"
edition_title: "2026-09-17 21:53 UTC"
enriched: true
---
Researchers introduce ERPBench, a benchmark that evaluates screenshot-only computer-use agents on a live, reproducible Enterprise Resource Planning \(ERP\) system by checking task outcomes against ground-truth values in the underlying database, rather than relying on screen-based success signals. The benchmark also ships a production-grade harness that gates agent actions behind human approval for safe deployment, though ERPBench itself runs agents autonomously for evaluation. Across six closed- and open-source agents, the study finds that strong performance on general graphical user interface \(GUI\) benchmarks does not transfer to enterprise reliability: some agents successfully reach the correct form and save a record in up to 85% of runs, but write the actually correct value in as few as 3% of those runs. The paper also catalogs failure modes specific to enterprise workflows, such as dense interfaces and coordinated multi-step interactions where an ERP system needs several linked actions to record one business event.

rss · arXiv cs.AI · Sep 17, 04:00

## Existing enterprise agent benchmarks rely on proxies rather than real systems
{: .item-block .item-block-written .item-block-background}

Computer-use agents that act via screenshots and simulated clicks are increasingly evaluated on general desktop and web tasks, but ERP systems that run finance, procurement, inventory, and customer operations have largely been tested only on proprietary platforms or simplified approximations. Because ERP errors alter persistent business records rather than producing visible on-screen failures, a benchmark that only checks whether an agent appears to finish a task can miss silent data corruption entirely.

## What a team would do differently
{: .item-block .item-block-fixed .item-block-what-this-changes}

Teams building or evaluating agents for ERP-style automation \(finance, procurement, inventory, customer records\) should not treat 'form saved' or 'task marked complete' signals as evidence of correctness; ERPBench's methodology shows these can diverge sharply from what actually lands in the database. Anyone considering autonomous agent deployment against systems of record should adopt state-grounded evaluation, checking outcomes against ground-truth database values, and should default to human-approval gating for write actions until agents demonstrate high database-verified correctness, not just high save rates. This is most relevant for organizations piloting agent-driven back-office automation where undetected wrong values carry regulatory or financial risk.

## Caveats
{: .item-block .item-block-fixed .item-block-caveats}

The results come from one benchmark built on a specific live ERP system with six evaluated agents; correctness rates \(as low as 3%\) and save rates \(up to 85%\) may not generalize across all ERP platforms, task types, or future agent versions. This is a newly introduced benchmark rather than an evaluation of an already-deployed production system, so it establishes a measurement method and a current snapshot rather than a definitive ceiling on agent capability.

**Tags**: `#computer-use agents`, `#enterprise software`, `#benchmark evaluation`, `#agent reliability`, `#ERP systems`
