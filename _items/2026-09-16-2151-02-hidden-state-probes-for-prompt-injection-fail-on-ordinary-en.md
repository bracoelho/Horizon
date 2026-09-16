---
layout: item
title: "Hidden-State Probes for Prompt Injection Fail on Ordinary Typos"
date: 2026-09-16 21:51:14 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.15994"
source: "arXiv cs.CL"
edition_url: "/2026/09/16/2151-summary-en.html"
edition_title: "2026-09-16 21:51 UTC"
enriched: true
---
Researchers show that hidden-state probes used to detect malicious prompts are sharply degraded by ordinary typos, even though the underlying language model's behavior and interpretation of intent remain essentially unchanged. A single typo rotates the probe's readout vector by 43-56 degrees at the perturbed token, an effect that decays below 15% within roughly ten downstream tokens; stacking about three common typos in one message cuts a single-position probe's true-positive rate at a 1% false-positive threshold by 12.0 percentage points, a gap that simple recalibration cannot fix. The geometry of this rotation-and-decay effect was replicated across Llama-3.1-8B, Qwen3-8B, and Gemma-4-E4B, though the full probe evaluation was conducted only on Llama-3.1-8B. The authors propose a key-value-cache fork mitigation -- appending a short fixed suffix so the probe reads tokens downstream of the perturbation -- which closes 95% of the gap, substantially outperforming perturbation-augmented training. This is laboratory research on open models; no disclosure process applies since it targets a general technique rather than a specific deployed product.

rss · arXiv cs.CL · Sep 16, 04:00

## Hidden-state probes are assumed robust to benign text variation
{: .item-block .item-block-written .item-block-background}

Hidden-state \(activation-based\) probes are a lightweight interpretability technique used to flag prompt injection or malicious intent by reading a model's internal representations rather than only its output text. They are attractive because they can run cheaply alongside inference and, in principle, catch manipulative inputs that evade output-only filters, so some teams treat them as a promising layer of defense-in-depth for guardrails.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

This affects organizations that have built or are evaluating hidden-state/activation probes as a prompt-injection or malicious-intent detection layer, particularly single-position probes reading a fixed token location. Teams should check whether their monitoring stack relies on this probe architecture, which base model family it uses, and whether inputs are normalized or spell-corrected before probing. Exposure is narrow today: this class of probe is not yet a dominant, widely-deployed industry control, and the measured results come from three specific open model families \(Llama-3.1-8B, Qwen3-8B, Gemma-4-E4B\) rather than a broad survey of production systems.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

The authors demonstrate a key-value-cache fork -- appending a short fixed suffix so the probe reads tokens past the perturbation point -- that closes 95% of the accuracy gap for single-position probes, far outperforming perturbation-augmented training; multi-position aggregation also helps for localized typos but only partially attenuates more distributed perturbations. Code is publicly available, but teams using hidden-state probes should treat this as an open research mitigation requiring their own validation before relying on it in production.

**Tags**: `#prompt-injection-detection`, `#LLM-probes`, `#robustness`, `#guardrail-evaluation`, `#interpretability`
