---
layout: item
title: "Clinical LLM Agents Issue Different Orders on Identical Reruns"
date: 2026-09-15 22:24:00 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.13582"
source: "arXiv cs.CL"
edition_url: "/2026/09/15/2224-summary-en.html"
edition_title: "2026-09-15 22:24 UTC"
enriched: true
---
A study reran identical clinical agent tasks from MedAgentBench 1000 times across 50 tasks spanning five write-capable task families, using two open-weight large language models below ten billion parameters at four-bit quantization and two temperature settings. Under the 8B model at temperature 0.7, all 43 ordering groups produced a different set of orders across five identical reruns, 26 groups only issued the order on some runs, and 28 recorded a different coded value, dose, or analyte. In 22 of those 43 cases the benchmark reported the same failing verdict despite materially different underlying behavior, a pattern that also held for all 10 divergent groups of the 4B model at temperature 0.7. One order was rejected by the record server but the agent was informed it had succeeded. The authors explicitly state the finding demonstrates that such divergence exists and can go undetected by scoring, not that these specific rates generalize beyond this lab setup.

rss · arXiv cs.CL · Sep 15, 04:00

## Single-attempt benchmark scoring is treated as evidence of reliable agent behavior
{: .item-block .item-block-written .item-block-background}

Clinical agent benchmarks such as MedAgentBench typically score one run per task, and this pass/fail verdict is commonly used as a proxy for whether an agent behaves consistently and safely when placing orders, requesting medications, or making referrals. That practice assumes that identical inputs will yield materially identical actions, or that scoring alone would catch it if they did not.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Exposure is narrow as demonstrated: the reported rates apply specifically to two open-weight models under 10 billion parameters at 4-bit quantization, tested only on MedAgentBench's 50 write-capable tasks. Organizations relying on single-run clinical agent benchmark scores as assurance of reliability, or deploying small quantized open-weight models as clinical agents, should check whether their evaluation pipeline reruns identical inputs and inspects action-level outputs \(orders, doses, endpoints\) rather than trusting the pass/fail verdict alone, and whether environment feedback to the agent is verified against actual system state.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

The authors propose repeated-run evaluation, explicit action-level stability reporting, and execution-faithful environment feedback \(so agents are not told a rejected order succeeded\) as compensating controls; no fix to the underlying models is presented, and these recommendations have not yet been validated at scale or across larger, non-quantized models.

**Tags**: `#clinical AI agents`, `#LLM reliability`, `#benchmark validity`, `#multi-agent/action-level evaluation`, `#healthcare AI safety`
