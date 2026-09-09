---
layout: item
title: "Study Finds LLM Agents Often Adopt Corrupted Tool Outputs Uncritically"
date: 2026-09-09 21:24:41 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.05587"
source: "arXiv cs.AI"
edition_url: "/2026/09/09/2124-summary-en.html"
edition_title: "2026-09-09 21:24 UTC"
enriched: true
---
A study evaluating fourteen large language models across three tool types—web search, delegation to a sub-agent, and code execution—deliberately corrupted tool returns and measured whether agents incorporated the corrupted content into their final answers. Mean adoption of corrupted output exceeded one third across all tool types and reached 68.0% for web search. Analysis of the models' reasoning traces showed that agents frequently detected the conflict and even internally recovered the correct answer, yet still presented only the corrupted answer to the user without any warning. The researchers tested three mitigation approaches—user prompting, tool-provider metadata, and post-training by the agent builder—and found that none of them consistently reduced overtrust across all tested models and tools. This is a laboratory evaluation using controlled corruption of tool returns rather than an observed incident in a live deployment.

rss · arXiv cs.AI · Sep 9, 04:00

## Agentic pipelines surface conflicts and degrade gracefully under bad inputs
{: .item-block .item-block-written .item-block-background}

Evaluations of tool-using agents have generally focused on whether an agent completes a task successfully, implicitly assuming that the information tools return is reliable. This assumption underlies much of the current design of agentic and multi-agent systems, which chain web search, sub-agent delegation, and code execution together with limited built-in verification of intermediate outputs.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Any organization deploying tool-augmented or multi-agent large language model systems that rely on web search results, sub-agent outputs, or code execution results without independent verification is in scope. Exposure is broadest for pipelines that pass tool output directly into a final user-facing answer without a separate validation or cross-checking step, and for deployments using any of the fourteen models tested, though the study suggests the failure mode is systemic rather than limited to specific model families. Teams should check whether their agents have any mechanism to flag conflicting or low-confidence tool results, since the study found this capability largely absent even when the correct answer was internally available to the model.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

The study tested prompting interventions, tool-provider metadata, and post-training adjustments, but found no approach that consistently reduced overtrust across all tested models and tool types, meaning no established fix currently exists. Compensating controls in the interim would need to come from external validation layers that independently check tool outputs before they reach a final answer, since the agents themselves cannot be relied upon to self-flag conflicts.

**Tags**: `#tool-use reliability`, `#LLM agents`, `#benchmark evaluation`, `#failure modes`, `#multi-agent systems`
