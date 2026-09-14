---
layout: item
title: "LLM-Judge Satisfaction Scores Fail to Predict Task-Oriented Agent Success"
date: 2026-09-14 22:23:08 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 7.0
link: "https://arxiv.org/abs/2609.12191"
source: "arXiv cs.CL"
edition_url: "/2026/09/14/2223-summary-en.html"
edition_title: "2026-09-14 22:23 UTC"
enriched: true
---
A study introduces GAUGE, a reusable offline protocol testing whether the common practice of scoring persona-driven LLM user-simulator conversations with an LLM-as-a-judge produces rankings that match grounded, verifiable task success. Across 25 agents from six providers on the tau2-bench and SimulatorArena benchmarks, the authors find that conversations a blind panel rated 'satisfied' are decorrelated from actual task success, with 57.5% of satisfied conversations failing the customer's task, a pattern that held across five rater populations, both benchmarks, and every subjective dimension measured. The ranking produced by the judge gate is robust when comparing agents with a wide capability gap, but decision-disagreement jumps from under 1% on wide-reward pairs to 31% on close, near-equal pairs. The paper's diagnosis is that the gate is human-validated but mis-anchored, and it proposes a calibrate-then-trust cadence using a zero-cost, judge-free 'completion bit' as a tripwire for truncation regressions.

rss · arXiv cs.CL · Sep 14, 04:00

## Teams treat LLM-judge satisfaction scores as a stand-in for task success
{: .item-block .item-block-written .item-block-background}

Many organisations building task-oriented agents \(customer service bots, booking assistants, etc.\) use a low-cost offline gate: an LLM-simulated user converses with a candidate agent, another LLM judges the transcript for satisfaction or quality, and the higher-scoring agent gets promoted to production. This is attractive because it avoids expensive human evaluation or live A/B testing, but it assumes that a judge's subjective satisfaction rating tracks whether the agent actually completed the user's task correctly.

## What a team would do differently
{: .item-block .item-block-fixed .item-block-what-this-changes}

Teams using LLM-as-a-judge satisfaction or quality scores as a promotion gate for task-oriented agents should not trust that gate when comparing near-equal candidates, since disagreement reaches 31% in that regime, and should not treat high satisfaction ratings as evidence of task success at all, given the 57.5% failure rate among 'satisfied' conversations. The paper's proposed fix is concrete and cheap to adopt: add a judge-free, verifiable completion signal \(a binary task-completion check\) as a tripwire alongside the judge score, reserving the judge for coarse capability differences rather than fine-grained ranking decisions. This applies specifically to offline, simulated-user evaluation pipelines for task-oriented or tool-using agents; it does not address live production monitoring or judge use in open-ended chat quality assessment.

## Caveats
{: .item-block .item-block-fixed .item-block-caveats}

The results are measured on two specific benchmarks \(tau2-bench and SimulatorArena\) with 25 agents from six providers using persona-driven LLM user simulators; it is not established whether the satisfaction-success gap or the ranking-resolution collapse generalizes to other agent domains, real \(non-simulated\) users, or judges built on different model families or prompting schemes.

**Tags**: `#LLM-as-judge`, `#agent evaluation`, `#benchmark validity`, `#task-oriented agents`, `#evaluation methodology`
