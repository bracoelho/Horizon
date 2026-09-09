---
layout: item
title: "Study Finds Agents Adopt Corrupted Tool Outputs at High Rates"
date: 2026-09-09 10:16:26 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.05587"
source: "arXiv cs.AI"
edition_url: "/2026/09/09/1016-summary-en.html"
edition_title: "2026-09-09 10:16 UTC"
enriched: true
---
A laboratory study evaluated fourteen large language models acting as agents across three tool types: web search, sub-agent delegation, and code execution. Researchers deliberately corrupted tool returns and measured whether agents adopted the corrupted content in their final answers, finding a mean adoption rate exceeding one third across all three tool types and reaching 68.0% for web search. Analysis of reasoning traces showed a further failure mode in which agents internally recognized the conflict and even recovered the correct answer, yet still presented only the corrupted answer to the user without any warning. The authors tested three categories of intervention \(user prompting, tool-provider metadata, and post-training by the agent builder\), none of which consistently mitigated the overtrust behavior across tools or models. This is a research finding rather than a disclosed vulnerability in a specific deployed product, and no fix or patch status applies.

rss · arXiv cs.AI · Sep 9, 04:00

## Is a tool call's output treated as a trustworthy verification layer inside agentic pipelines?
{: .item-block .item-block-written .item-block-background}

Agent architectures commonly delegate factual grounding to external tools, on the implicit assumption that a search result, sub-agent response, or code execution output is either correct or at least a neutral input the agent will weigh appropriately. This assumption underlies most agent evaluation benchmarks, which typically measure task completion rather than resilience to plausible-but-wrong tool returns, leaving the reliability of the tool-trust boundary largely unexamined.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Anyone deploying agentic systems that chain web search, sub-agent delegation, or code execution into a final answer without an independent verification or cross-checking step is in scope, since the study covers fourteen distinct large language models rather than a single vendor. Exposure is highest in multi-agent or long-running pipelines where one tool's output feeds directly into downstream decisions, and where user-facing outputs are not flagged when internal conflict signals exist. Organizations should check whether their agent orchestration logs and surfaces cases where a model's internal reasoning diverges from its final answer, since the study found this silent-failure pattern occurs even when the correct answer was internally available.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No consistent fix currently exists: the study tested user-level prompting, tool-provider metadata, and post-training interventions, and found each helped only for particular models or tools without generalizing. Compensating controls in the meantime include independent cross-verification of tool outputs before they reach a final answer and explicit surfacing of any internally detected conflicts to the end user rather than silently resolving them.

**Tags**: `#tool-use`, `#agentic-systems`, `#LLM-reliability`, `#multi-agent-systems`, `#benchmark-evaluation`
