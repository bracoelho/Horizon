---
layout: item
title: "New Benchmark Shows NL2SQL Accuracy Drops Sharply on Enterprise Schemas"
date: 2026-08-27 01:07:58 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2608.23569"
source: "arXiv cs.AI"
edition_url: "/2026/08/27/0107-summary-en.html"
edition_title: "2026-08-27 01:07 UTC"
enriched: true
---
A new paper introduces ESQ-Bench, an Oracle-first NL2SQL benchmark built across three enterprise schema complexity tiers, using six populated schemas \(465 tables, 164,682 rows\) replicated on Oracle, PostgreSQL, MySQL, and SQL Server, with 550 gold-validated question-query pairs. With schema-linked prompting, GPT-4o&\#x27;s execution-match accuracy fell from 79.8% at the simplest tier to 60.3% and 57.2% at higher tiers \(measured June 2026\), while exact-match accuracy stayed below 7% across all tiers. Among queries that executed successfully, silent semantic divergence, meaning the query ran without error but returned the wrong result, reached 73% to 99% at higher tiers. Claude Sonnet 4.6 outperformed GPT-4o schema-linked at every tier \(87.4%, 74.9%, 68.7%\), and a local Llama 3.2 model reached only 13.3% overall, indicating a substantial gap between closed API models and open-weight models on enterprise-scale Oracle schemas.

rss · arXiv cs.AI · Aug 26, 04:00

**「Background」** NL2SQL systems are commonly evaluated against academic benchmarks like Spider and BIRD, where leading models report execution accuracy above 89%. Those benchmarks use simplified schemas and open-source SQL dialects, and organizations deploying NL2SQL for enterprise data access have generally relied on such scores as a proxy for real-world reliability without independent validation on production-scale, dialect-specific schemas.

**「Exposure」** This concerns organizations using LLM-based natural language to SQL translation for querying production or enterprise-scale databases, particularly Oracle, SQL Server, or other dialects that differ from the simplified schemas used in Spider or BIRD. Teams should check what schema complexity and dialect their NL2SQL system was actually validated against, whether reported accuracy figures came from academic benchmarks rather than representative enterprise schemas, and whether any process checks query results for semantic correctness rather than just successful execution. Exposure is highest where NL2SQL output feeds directly into reporting or decision-making without a human reviewing the returned data, since a query can execute cleanly and still return a wrong answer.

**「Mitigation」** There is no fix for the underlying models; this is a measurement finding rather than a patchable defect. The paper&\#x27;s authors have released the benchmark, schemas, and evaluation harness publicly, which allows teams to test their own NL2SQL pipelines against enterprise-scale, dialect-varied schemas rather than relying solely on academic benchmark scores, and to add result-level semantic checks rather than trusting successful execution alone.

**Tags**: `#NL2SQL`, `#benchmark validity`, `#enterprise databases`, `#silent failure`, `#LLM evaluation`
