---
layout: item
title: "Large-Language-Model Document Auditors Fabricate Findings at Scale"
date: 2026-09-10 21:24:46 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.09696"
source: "arXiv cs.CL"
edition_url: "/2026/09/10/2124-summary-en.html"
edition_title: "2026-09-10 21:24 UTC"
enriched: true
---
A study evaluated Google Gemini 3.0 Pro's ability to detect planted contaminants in a constructed corpus of 150 academic papers from supply chain management and medical research, with 450 known contaminants \(typographical corruption, semantic reversal, absurd out-of-context insertion\) injected across the set. Testing a 180-contaminant answer-key subset across 60 documents under three prompting regimes, recovery held at 50% for single documents and 60% for small batches, then collapsed to 2.8% for large batches. Critically, the failure at scale did not manifest as the model reporting incomplete processing; instead it produced confident, fabricated findings, including invented contaminants such as "telepathic squirrel" and "quantum-powered toaster" that mimic the planted material's style but appear in no source document. Detection also varied by contamination type, with absurd insertions recovered at 75% in completed evaluations versus 50% for semantic reversals and typographical corruptions, meaning the most realistic error types were also the most often missed. This is a single-model, single-study result on a purpose-built contamination corpus; the paper's disclosure status and peer-review state are not specified in the available material.

rss · arXiv cs.CL · Sep 10, 04:00

## The assumption that large language models can substitute for human quality-assurance review at scale
{: .item-block .item-block-written .item-block-background}

Organisations increasingly propose using large language models as automated auditors to check large volumes of documents for errors, inconsistencies, or planted contamination, on the assumption that model competence demonstrated on small samples generalises to batch processing. This trust rests on the idea that degradation under increased load would be graceful and visible, for example through explicit abstention or reduced confidence, rather than silent and deceptive.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

This affects organisations that use, or plan to use, large language models to audit, review, or perform quality assurance on document batches at scale, particularly where the auditing model is Gemini 3.0 Pro or a similarly deployed general-purpose model rather than a purpose-built verification pipeline. Exposure is highest where document batches are large, where a human is not independently cross-checking every flagged finding against source text, and where the audit workflow lacks bounded batch sizes or mechanical verification steps. Because the study covers one model on one constructed corpus spanning two academic domains, organisations should treat this as a demonstrated failure mode to test for in their own pipelines rather than a confirmed property of all large language models or all document types.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No model fix is described; the authors instead outline a harness for safer use: bounded batch sizes rather than large-batch processing, direct content injection into the review context, and mechanical verification of every reported finding against the original source text before it is trusted.

**Tags**: `#LLM evaluation`, `#hallucination`, `#document auditing`, `#batch-size scaling`, `#AI reliability`
