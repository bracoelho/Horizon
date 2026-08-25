---
layout: item
title: "IBM Granite 4.2: Dense Reasoning LLMs at 3B, 8B, and 30B"
date: 2026-08-25 21:56:22 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 7.0
link: "https://huggingface.co/blog/ibm-granite/granite-4-2"
source: "Hugging Face Blog"
edition_url: "/2026/08/25/2156-summary-en.html"
edition_title: "2026-08-25 21:56 UTC"
enriched: true
---
IBM released Granite 4.2, a family of dense decoder-only reasoning LLMs in three sizes \(3B, 8B, 30B\), each pre-trained from scratch on roughly 15 trillion tokens using a five-phase pipeline that extends context to 512K tokens \(models are documented with a 131,072-token sequence length\). All three share the same architecture \(GQA with 40 heads and 8 KV heads on the 3B, RoPE with theta = 10,000,000, SwiGLU MLP, RMSNorm, untied embeddings, bfloat16\) and follow the same recipe: pre-training, supervised fine-tuning on chain-of-thought and agentic-trajectory data, then a multi-stage RL pipeline. The 8B and 30B models additionally go through an agentic RL stage that trains them to call tools, edit and run code, drive a terminal, and search the web inside sandboxed environments; the 30B model gets an extra SFT phase upsampling agentic coding and SWE data. Every model supports a thinking/non-thinking switch, a low-effort reasoning mode for easy questions, and native OpenAI-format tool calling, and is served through vLLM or SGLang. All models are released under Apache 2.0. SFT used about 7.2 million samples \(roughly 100B tokens, ~65B trainable\), with GPT-OSS-120B and Gemma 4 used as LLM judges for quality filtering.

rss · Hugging Face Blog · Aug 25, 15:14

**「Context」** Granite is IBM&\#x27;s family of open-weight language models; earlier releases focused on instruction-following rather than explicit reasoning. Granite 4.2 is described as the first Granite generation built specifically for reasoning, building on the pre-training and long-context recipe from the prior Granite 4.1 release.

**「Practical implications」** Teams needing a self-hosted, Apache 2.0-licensed model with native tool calling, a controllable thinking/non-thinking switch, and 512K context now have a dense option across three sizes \(3B, 8B, 30B\) that plugs directly into vLLM or SGLang with OpenAI-compatible function calling. This is most relevant for agentic workloads \(code editing, terminal use, web search, SWE tasks\) where the 8B and 30B variants were specifically RL-trained in sandboxed tool-use environments, and for deployments where licensing flexibility and long-context handling matter more than squeezing out maximum benchmark scores. Because no comparative benchmarks against similarly sized open models are given here, this does not yet establish whether Granite 4.2 outperforms alternatives in the same size class; it only establishes that a new, permissively licensed, tool-trained option exists to evaluate against existing choices.

**「Caveats」** The source is IBM&\#x27;s own technical blog post and contains no independent benchmark results or head-to-head comparisons against other open models, so performance claims cannot be verified from this content alone. Training details \(15T tokens, five-phase pretraining, RL pipeline\) describe IBM&\#x27;s process but give no accuracy, latency, or cost figures that would let a team size expected gains before testing the models directly.

**Tags**: `#open-weight-models`, `#LLM-release`, `#reasoning-models`, `#agentic-RL`, `#tool-calling`
