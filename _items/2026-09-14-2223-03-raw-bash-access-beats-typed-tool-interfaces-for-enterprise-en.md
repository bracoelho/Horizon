---
layout: item
title: "Raw Bash Access Beats Typed Tool Interfaces for Enterprise Agents"
date: 2026-09-14 22:23:08 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 8.0
link: "https://arxiv.org/abs/2609.11999"
source: "arXiv cs.SE"
edition_url: "/2026/09/14/2223-summary-en.html"
edition_title: "2026-09-14 22:23 UTC"
enriched: true
---
A controlled study compares five tool interfaces for enterprise digital worker agents: typed tools, typed tools plus bash, bash alone, bash with persistent agent-synthesized tools, and programmatic tool calling \(running programs restricted to a typed tool catalog\). Testing on TheAgentCompany and APEX-Agents benchmarks with Opus-4.8 and GPT-5.5, bash alone outperformed typed tools by 21.8-24.5 percentage points on TheAgentCompany and 4.8-7.4 percentage points on APEX-Agents, while using 19-72% fewer total tokens. Adding typed tools or persistent tool synthesis on top of bash produced no detectable pooled score gain. Programmatic tool calling used fewer tokens than direct typed calls with broadly similar task performance, but generally underperformed bash alone on both quality and cost efficiency.

rss · arXiv cs.SE · Sep 14, 04:00

## Background
{: .item-block .item-block-written .item-block-background}

Agent frameworks typically give large language models access to tools either through a fixed catalog of typed function calls or through open-ended shell \(bash\) access, and enterprise deployments often favor typed catalogs for auditability and compliance even though coding agents have shown shell access to be effective. TheAgentCompany and APEX-Agents are benchmarks built to simulate realistic enterprise digital-worker tasks, such as cross-application coordination and professional analysis in domains like banking, consulting, and law, with performance scored against expert-authored task criteria rather than simple pass/fail checks. This study tests which tool-access pattern performs best on those enterprise-style tasks rather than on coding benchmarks alone.

## What a team would do differently
{: .item-block .item-block-fixed .item-block-what-this-changes}

Teams building enterprise agents that move between applications, coordinate with coworkers, or perform analysis tasks can default to giving agents raw shell access instead of building and maintaining typed tool catalogs, when arbitrary code execution can be safely isolated \(for example in a sandboxed container\). Where security or compliance policies mandate a fixed, auditable action set, programmatic tool calling is the better fallback over direct typed tool calls, since it retains the catalog restriction while cutting token usage. This reframes typed tool interfaces as a compliance-driven choice rather than a performance-driven one, shifting engineering effort away from building exhaustive tool schemas toward securing bash execution environments.

## Caveats
{: .item-block .item-block-fixed .item-block-caveats}

The model names \(Opus-4.8, GPT-5.5\) and benchmark identifiers appear to be non-standard or possibly fabricated version labels, which raises questions about reproducibility and dating of the study; readers should verify these against the actual arXiv paper before citing specific figures. Results are measured only on two benchmarks \(TheAgentCompany and APEX-Agents\) and depend on the isolation of arbitrary execution being feasible, which may not hold in all enterprise environments with strict sandboxing or audit requirements.

<details><summary>References</summary>
<ul>
<li><a href="https://www.emergentmind.com/papers/2601.14242">APEX-Agents: Benchmark for Professional AI Tasks</a></li>
<li><a href="https://www.mercor.com/apex/apex-agents-leaderboard/">AI Agent Benchmarks &amp; Leaderboards: APEX-Agents | Mercor</a></li>
<li><a href="https://www.emergentmind.com/topics/theagentcompany-benchmark">TheAgentCompany Benchmark: Evaluating LLM Agents</a></li>

</ul>
</details>

**Tags**: `#agent architecture`, `#tool use`, `#LLM benchmarking`, `#enterprise AI agents`, `#cost efficiency`
