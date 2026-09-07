---
layout: item
title: "Static Red-Team Scores May Understate Prompt-Injection Risk to Agents"
date: 2026-09-07 21:57:04 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.04495"
source: "arXiv cs.AI"
edition_url: "/2026/09/07/2157-summary-en.html"
edition_title: "2026-09-07 21:57 UTC"
enriched: true
---
Researchers built an agentic attacker equipped with a dedicated search harness that performs environment reconnaissance, structured reasoning over candidate attack strategies, and adaptive evaluation using feedback from the victim agent. Tested across heterogeneous tasks, the framework shows that indirect prompt-injection success increases as the attacker is given more test-time search compute, and that explicit strategy management \(avoiding redundant search paths\) is needed to sustain these gains at larger compute budgets. The paper reports this as a demonstrated laboratory finding across multiple tasks rather than a single exploited deployment, with no disclosed victim system names, CVE identifiers, or production incident tied to it.

rss · arXiv cs.AI · Sep 7, 04:00

## Assumption that attack success rate is a fixed property of the victim system
{: .item-block .item-block-written .item-block-background}

Agentic system security evaluations commonly report a single attack success rate from a fixed red-team exercise, treating that number as a stable characteristic of the defended system that can be compared across products or certified once. This assumption underlies static benchmarks and vendor security claims because it lets evaluators avoid specifying or standardizing the attacker's own computational budget or search strategy.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

This concerns any organisation running tool-using large language model agents that process untrusted external content \(web pages, documents, emails, tool outputs\) where indirect prompt injection is possible, and any organisation relying on a one-time or fixed-budget red-team report as evidence of agent robustness. Teams should check whether their security evaluations specify and vary the attacker's test-time compute and search strategy, or whether they quote a single static attack-success figure as if it were budget-independent. Exposure is broadest for agent deployments handling sensitive actions \(payments, code execution, data access\) where an under-resourced red-team test may have missed vulnerabilities that a better-resourced adaptive attacker could find.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No patch applies since this is a methodological finding rather than a specific software defect; the suggested mitigation is to redesign agentic security evaluations to report attack success as a function of attacker compute budget and search strategy, testing at multiple budget levels rather than a single static pass, combined with runtime defenses that reduce the practical attack surface available to any adaptive attacker.

**Tags**: `#prompt injection`, `#agentic security`, `#red-teaming`, `#test-time compute`, `#LLM agents`
