---
layout: item
title: "Agentic Code-Repair Patches Pass Tests While Leaving Security Flaws"
date: 2026-09-11 21:33:34 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.10548"
source: "arXiv cs.SE"
edition_url: "/2026/09/11/2133-summary-en.html"
edition_title: "2026-09-11 21:33 UTC"
enriched: true
---
A laboratory study analyzed 1,030 valid execution traces produced by seven agent frameworks running GPT-4o-mini against two security-focused datasets, SecurityEval and CVEfixes. Through three rounds of qualitative coding and manual verification, the researchers confirmed 170 silent failures: patches that passed syntactic and functional tests yet still retained or introduced security vulnerabilities. Failures were grouped into three categories: Omission \(48.2%, missing required security controls\), Introduction \(30.6%, new vulnerabilities added during repair\), and Inadequacy \(21.2%, incomplete defenses\), further broken into ten fine-grained failure codes. The study also found that existing test-passing checks and LLM-based reviewer roles failed to catch these confirmed cases, and that similar insecure solutions recurred across different agent frameworks.

rss · arXiv cs.SE · Sep 11, 04:00

## The assumption that functional test suites are a sufficient safety gate for AI code repair
{: .item-block .item-block-written .item-block-background}

Automated code-repair agents built on large language models are typically evaluated by whether their patches compile and pass functional or syntactic test suites, a proxy widely treated as evidence the fix is acceptable. This study challenges that assumption by showing test-passing status says nothing about whether a patch closes, preserves, or opens a security hole.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

This concerns teams that use or are evaluating LLM-based agentic code-repair pipelines, whether single-agent or multi-agent, especially where GPT-4o-mini or similarly capable models are used and where functional test pass rate is the primary or sole acceptance gate. Organizations should check whether their pipeline includes any security-specific static analysis, vulnerability scanning, or human security review beyond automated test suites and LLM-based reviewer roles, since the study found those reviewer roles insufficient to catch the confirmed failures. Exposure is limited to the extent that findings come from two specific datasets and one model family rather than a broad survey of production deployments.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No fix is proposed by the study itself; it recommends developing verification methods that go beyond functional correctness to cover all generated artifacts, implying organizations should add dedicated security-focused checks \(static analysis, vulnerability-specific test cases, or manual security review\) as a compensating control alongside existing functional test gates.

**Tags**: `#agentic systems`, `#code repair`, `#silent failures`, `#security verification`, `#LLM agents`
