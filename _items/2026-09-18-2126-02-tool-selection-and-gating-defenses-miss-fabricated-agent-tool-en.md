---
layout: item
title: "Tool-Selection and Gating Defenses Miss Fabricated Agent Tool Calls"
date: 2026-09-18 21:26:07 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.19425"
source: "arXiv cs.AI"
edition_url: "/2026/09/18/2126-summary-en.html"
edition_title: "2026-09-18 21:26 UTC"
enriched: true
---
A benchmark study evaluated ten hosted large language models across two invocation surfaces and measured 322 genuine tool hallucinations, with fabricated-tool calls concentrated on the unconstrained raw-JSON surface \(34 cases\) versus a more structured surface \(3 cases\); the paper reports that model scale did not reduce the problem, with a 675-billion-parameter model matching the failure rate of a 7-8 billion-parameter model. Extending the test to live Model Context Protocol \(MCP\) deployments where multiple servers are merged into one namespace, the authors measured 154 additional hallucinations, including from frontier models that had been clean on single-registry setups, attributed to naming collisions and shadowing introduced by namespace merging. The authors argue this is a structural blind spot: existing tool-selection and gating defenses presuppose a call refers to a real tool, so they cannot reject calls that reference tools or arguments that were never declared. As a reference baseline, they propose a training-free closed-world resolver checking registry membership and argument signatures, and release a versioned benchmark \(Hallucinated-Tools Benchmark\) for comparison. This is a single arXiv preprint, not yet peer-reviewed, and the proposed resolver is presented as a measurement baseline rather than a deployed fix.

rss · arXiv cs.AI · Sep 18, 04:00

## Why tool-selection and gating controls were assumed sufficient
{: .item-block .item-block-written .item-block-background}

Organisations deploying tool-augmented large language model agents typically rely on tool-selection mechanisms and gating layers to constrain what an agent can do, trusting that these controls limit an agent to a known, real set of tools and permitted arguments. The Model Context Protocol \(MCP\), an open standard for connecting AI applications to external data sources, tools, and workflows, has become a common way to expose multiple tool servers to a single agent \(tool-1-1, tool-1-2\). Both selection and gating approaches implicitly assume every emitted tool call refers to something real in the registry, which is the assumption this paper's measurements target.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Organizations running tool-augmented or agentic large language model systems that rely on tool-selection or gating layers as their primary safeguard against invalid tool use are in scope, particularly those exposing tools through unconstrained raw-JSON interfaces rather than structured schemas. Deployments using the Model Context Protocol with multiple servers merged into a single namespace face additional exposure, since the study found frontier models that behaved correctly on single-registry setups still produced fabricated calls once namespaces were merged. Teams should check whether their monitoring distinguishes fabricated tool references from policy violations on real tools, and whether namespace merging in their MCP configuration could introduce naming collisions or shadowing between servers.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No production-ready fix is described; the authors offer a training-free closed-world resolver \(registry membership plus signature checking\) as a reference baseline that must run before any causal gating step, and note one irreducible residue where borrowed arguments remain schema-indistinguishable from valid calls. Organizations can compensate in the interim by validating tool calls against a closed registry prior to gating, avoiding unconstrained raw-JSON tool interfaces where feasible, and auditing MCP namespace merges for collisions before deployment.

<details><summary>References</summary>
<ul>
<li><a href="https://modelcontextprotocol.io/">What is the Model Context Protocol ( MCP )? - Model Context Protocol</a></li>
<li><a href="https://github.com/modelcontextprotocol">Model Context Protocol · GitHub</a></li>

</ul>
</details>

**Tags**: `#tool-hallucination`, `#LLM agents`, `#MCP`, `#benchmark`, `#AI security`
