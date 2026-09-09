---
layout: item
title: "Some Quantized Models in Official Registries Silently Fail All Tasks"
date: 2026-09-09 10:16:26 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2609.05881"
source: "arXiv cs.SE"
edition_url: "/2026/09/09/1016-summary-en.html"
edition_title: "2026-09-09 10:16 UTC"
enriched: true
---
A study evaluated 327 quantized code-capable model artifacts in GGUF format: 305 from the official Ollama library across 15 model lines at every quantization level at or under 8 gigabytes, plus 22 from the most-downloaded community repositories on HuggingFace. Each artifact ran a 15-task smoke test, and suspects then went through a full 164-task evaluation, a second inference backend, and comparison against an independent distributor's conversion of the same model and quantization level. Five artifacts in the official Ollama library were found to be silently defective, a batch of four Qwen2.5-Coder-3B conversions and one phi3.5-mini conversion, solving zero of 164 tasks and zero of the smoke suite on both backends tested, while independent conversions of the same models worked correctly; this represents 1.6% of official artifacts, or 2 of 29 model-and-size conversion groups. The authors also identified two older community conversions that degrade badly on one backend \(CUDA\) while passing on another \(Metal\), a distinct backend-dependent failure mode. The authors released the audit dataset, the quantcheck acceptance-testing tool, and disclosure reports for every confirmed defect.

rss · arXiv cs.SE · Sep 9, 04:00

## Does distribution through a major model registry imply the artifact was functionally tested?
{: .item-block .item-block-written .item-block-background}

Developers running large language models locally increasingly pull pre-quantized artifacts from public registries such as Ollama and HuggingFace, trusting that popularity, official status, or download counts serve as a proxy for correctness. Unlike package registries for software, which often run acceptance gates before publication, model registries currently perform no functional testing of quantized conversions before they reach users, leaving silent conversion defects undetected by any existing control.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Anyone running local inference with quantized GGUF artifacts pulled from Ollama's official library or from popular HuggingFace community repositories is potentially exposed, particularly users of the specific affected conversions: Qwen2.5-Coder-3B \(four quantization variants\) and phi3.5-mini. Organizations should check which exact model, size, and quantization level they have deployed, since the defect rate found was small and concentrated in specific model-and-size groups rather than widespread; teams using unaffected models or quantization levels are not implicated by this finding. Teams relying solely on CUDA or solely on Metal backends for community conversions should also check for backend-dependent degradation, a failure mode distinct from outright defective files.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

The authors disclosed the confirmed defects and released an open-source acceptance-testing tool, quantcheck, along with the audit dataset, enabling teams to functionally verify quantized artifacts before deployment rather than trusting registry distribution alone; running such acceptance tests across backends and against independent conversions is the compensating control until registries adopt functional testing gates themselves.

**Tags**: `#model supply chain`, `#quantization`, `#LLM registries`, `#artifact integrity`, `#evaluation methodology`
