---
layout: item
title: "Exact-Match RLVR Verifiers Show Strong Language-Dependent Bias"
date: 2026-08-24 21:53:55 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 7.0
link: "https://arxiv.org/abs/2608.20362"
source: "arXiv cs.CL"
edition_url: "/2026/08/24/2153-summary-en.html"
edition_title: "2026-08-24 21:53 UTC"
enriched: true
---
Researchers audited the exact-match verifier commonly used as a reward function in reinforcement learning with verifiable rewards \(RLVR\) and found its false-negative rate varies sharply by language rather than staying neutral as assumed. On MGSM rollouts with k=8, Qwen3-8B saw a false-negative rate of 0.642 for Japanese answers versus 0.122 for English and 0.073 for Chinese, with similar language-dependent gaps observed on Qwen3-4B and Llama-3.1-8B-Instruct. The authors trace the effect to the final-answer interface rather than underlying reasoning ability, and identify a related cross-lingual selection bottleneck on MGSM250 and a 483-problem MATH-500 set, where a target-local aggregation rule without trusted labels closes 55-78% of the selection gap. A controlled training audit further shows that a rule-based GRPO training run raises trusted accuracy while the underlying reward-error metric remains high, indicating the bias persists through training rather than resolving itself. This is a measured, reproducible laboratory finding with a released audit protocol, not a report of exploitation in a deployed system.

rss · arXiv cs.CL · Aug 24, 04:00

**「The assumption being tested」** RLVR treats an automated answer verifier as a language-neutral reward signal, checking whether a model&\#x27;s final answer matches a known correct answer regardless of the language or script used to reach it. This assumption underlies post-training pipelines for reasoning models across many languages, and has generally been trusted because exact-match verification looks like a simple, mechanical check rather than something susceptible to linguistic variation.

**「Who should check their pipeline」** This affects teams performing RLVR-style post-training or fine-tuning on multilingual reasoning tasks, particularly with model families such as Qwen3 or Llama-3.1 evaluated in the study, where reward is computed via exact-match verification against final answers. Organizations should check whether their verifier logic accounts for format and script variation across target languages, and whether benchmark or training accuracy claims for non-English languages have been validated against a language-conditioned reward-error audit rather than assumed to be comparable across languages. Exposure is narrow in the sense that it applies specifically to exact-match verification schemes and non-English \(especially non-Latin-script\) evaluation settings; teams training or evaluating only in English are not directly implicated by these measurements.

**「What reduces the risk」** The authors provide a reusable audit protocol, including a verifier-robustness suite and language-conditioned reward-error metrics, that teams can apply before optimizing against a multilingual RLVR reward signal. No universal fix to the exact-match verifier itself is presented; the compensating approach demonstrated is auditing by language and by answer interface, plus a target-local aggregation rule that partially closes the cross-lingual selection gap without requiring trusted labels.

**Tags**: `#RLVR`, `#multilingual NLP`, `#reward hacking`, `#LLM training`, `#benchmark validity`
