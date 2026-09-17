---
layout: item
title: "Pareto Atlas Maps Which LLM Inference Optimizations Actually Win"
date: 2026-09-17 21:53:34 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 8.0
link: "https://arxiv.org/abs/2609.17863"
source: "arXiv cs.AI"
edition_url: "/2026/09/17/2153-summary-en.html"
edition_title: "2026-09-17 21:53 UTC"
enriched: true
---
Researchers built a calibrated Pareto atlas covering cost, quality, and latency for large language model \(LLM\) inference, measuring 54 configurations of Qwen2.5-7B-Instruct on vLLM 0.12 across L4, A100, and H100 GPUs, then used those anchor points to calibrate a simulator with cross-campaign drift below 1.5 percent. On a calibrated 36-configuration grid, 18 reached the Pareto frontier, and combined optimization methods reached it more often than single methods \(9 of 15 combinations versus 9 of 21 single methods\). A separate quality evaluation on 200 GSM8K math questions found FP8 \(8-bit floating point\) weights retained 99.4 percent of baseline accuracy at 0.61-0.65x baseline latency across all three GPUs and appeared in three of four regime winners, while AWQ 4-bit quantization cut per-token latency to 0.34x baseline on L4 but lost 5.9 percent accuracy, narrowly missing a 95 percent quality floor. Most strikingly, a naive FP8 key-value \(KV\) cache maintained normal throughput but answered zero of 200 questions correctly, and n-gram speculative decoding measured 0.90-0.98x baseline with no real benefit on this stack. H100 won for tight latency constraints while A100 won for throughput and cost, reaching $0.106 per million tokens.

rss · arXiv cs.AI · Sep 17, 04:00

## Do published inference speedups transfer across models and hardware?
{: .item-block .item-block-written .item-block-background}

LLM inference optimization papers typically report speedups on different models, GPUs, prompts, and quality metrics, which makes it hard to know which techniques compose well or which ones dominate under a given deployment constraint like a latency budget or a cost target. Because exhaustively testing every combination of quantization method, batch size, and GPU is impractical, this work builds anchor measurements and calibrates a simulator to extrapolate across the full configuration space.

## What a team would do differently
{: .item-block .item-block-fixed .item-block-what-this-changes}

Teams running Qwen2.5-7B-class models on vLLM can use FP8 weight quantization as a near-default choice, since it kept 99.4 percent of baseline accuracy while cutting latency to roughly 0.61-0.65x across L4, A100, and H100, and it appeared in most regime-winning configurations. Teams should treat FP8 KV cache as unsafe without dedicated accuracy testing, since it preserved normal throughput numbers while producing zero correct answers on GSM8K, meaning throughput dashboards alone would not have caught the failure. GPU selection can now be constraint-driven rather than default-to-largest: pick H100 when latency is the binding constraint and A100 when the target is throughput per dollar \(measured here at $0.106 per million tokens\). Teams considering n-gram speculative decoding on a similar stack should not expect a latency win, since it measured 0.90-0.98x baseline with no real benefit in this setup.

## Caveats
{: .item-block .item-block-fixed .item-block-caveats}

All measurements are scoped to one model \(Qwen2.5-7B-Instruct\), one serving stack \(vLLM 0.12\), and three specific GPUs \(L4, A100, H100\), so absolute numbers and winner rankings may not transfer to other model sizes, architectures, or serving frameworks. Sparse attention was evaluated only in simulation, not measured directly, and the quality evaluation used a single benchmark \(200 GSM8K questions, five-shot\), so accuracy conclusions are specific to that task type and may not generalize to other domains like open-ended generation or code.

**Tags**: `#LLM inference optimization`, `#quantization`, `#benchmarking`, `#GPU cost-performance`, `#vLLM`
