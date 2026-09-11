---
layout: item
title: "Standard Chat-Model Evaluations Miss Multi-Step Agentic Risks"
date: 2026-09-11 21:33:34 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.09647"
source: "arXiv cs.AI"
edition_url: "/2026/09/11/2133-summary-en.html"
edition_title: "2026-09-11 21:33 UTC"
enriched: true
---
A research paper proposes a black-box red-teaming framework for agentic AI systems, built on a seven-domain risk taxonomy and an automated method \(SAGE-RT\) that generates 120 adversarial scenarios per domain, with results reviewed via human-validated LLM judges. The framework was tested against agents built on two multi-agent architectures, CrewAI and AutoGen, using four different base language models, requiring only basic system descriptions rather than privileged access. Measured results include an average governance risk of 56.25%, a privacy risk of 65% in multi-agent configurations, and agent behavior vulnerabilities reaching 85%. This is a laboratory study introducing and validating a new evaluation methodology rather than a disclosed exploit against a named production deployment, and no vendor disclosure process is described.

rss · arXiv cs.AI · Sep 11, 04:00

## Assumption that chat-model safety evaluations transfer to autonomous agents
{: .item-block .item-block-written .item-block-background}

Organizations deploying agentic systems have generally relied on evaluation methods built for single-turn chat interactions, trusting that safety benchmarks developed for conversational models would carry over to systems that call tools, hold real permissions, and act across multiple steps. This assumption has been convenient because multi-turn, architecture-aware red teaming is harder to automate and standardize than single-prompt testing.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Teams operating multi-agent systems built with frameworks such as CrewAI or AutoGen, or similar orchestration layers where agents call tools and pass tasks between each other, are the most directly relevant audience, since the measured failure rates specifically concern multi-agent configurations. Organizations should check whether their current evaluation and red-teaming practices go beyond single-turn chat prompts to cover multi-step, tool-using, cross-agent interactions, and whether governance, privacy, and behavioral risks have been assessed for the specific base models and orchestration patterns in production. Exposure is architectural rather than tied to a specific vendor flaw: any deployment granting agents real permissions and autonomy without multi-step adversarial testing fits the scope of this study.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

The paper's contribution is itself a proposed mitigation: adopting a taxonomy-driven, automated red-teaming process that tests multi-agent, multi-step behavior rather than relying solely on single-turn evaluations, with human-validated judging as a compensating check on automated results. No patch applies since this is an evaluation methodology rather than a vulnerability in a specific product; organizations should treat this as a prompt to expand their own testing coverage to agentic and multi-agent scenarios.

**Tags**: `#agentic AI`, `#red teaming`, `#multi-agent systems`, `#AI risk evaluation`, `#security benchmarking`
