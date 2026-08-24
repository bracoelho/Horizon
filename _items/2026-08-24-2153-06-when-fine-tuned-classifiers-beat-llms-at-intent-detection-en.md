---
layout: item
title: "When Fine-Tuned Classifiers Beat LLMs at Intent Detection, and When They Don't"
date: 2026-08-24 21:53:55 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 7.0
link: "https://arxiv.org/abs/2608.20371"
source: "arXiv cs.CL"
edition_url: "/2026/08/24/2153-summary-en.html"
edition_title: "2026-08-24 21:53 UTC"
enriched: true
---
The paper compares a fine-tuned RoBERTa classifier, a TF-IDF plus logistic regression baseline, sentence-embedding kNN, and zero-shot Claude Haiku on intent detection, using the ATIS and CLINC150 benchmarks with bootstrap 95% confidence intervals and paired significance tests. On the narrow ATIS schema, fine-tuned RoBERTa beats zero-shot Claude by 11.8 points \(95.9 vs. 84.1, p&lt;0.001\) while being three orders of magnitude cheaper and faster. On the broad 150-intent CLINC150 schema the two are statistically tied \(89.1 vs. 88.5, p=0.24\), meaning the LLM matches a fully supervised model with no training data. The LLM pulls ahead in three specific regimes: out-of-scope detection \(85.6 vs. 58.1 recall\), robustness to ASR noise in a TTS-to-noise-to-Whisper pipeline \(92.5 vs. 80.0 at 0 dB\), and dynamic per-deployment schemas, where the trained classifier scores 0% on a new app&\#x27;s intents while the schema-prompted LLM serves both apps at roughly 94% with no retraining.

rss · arXiv cs.CL · Aug 24, 04:00

**「Context」** Intent detection, classifying a user utterance into one of a fixed set of intents, is a core component of conversational systems and has traditionally been handled by fine-tuned classifiers like RoBERTa. The rise of capable zero-shot LLMs has led many teams to consider replacing these classifiers outright, but head-to-head evidence with statistical rigor has been limited, and most comparisons rely on a single benchmark or lack significance testing.

**「Practical implications」** Teams building intent detection for production conversational systems get a concrete decision rule instead of a blanket recommendation: keep or train a fine-tuned classifier when the intent schema is narrow and stable and cost or latency matters, since it wins clearly there and runs far cheaper. Reach for a zero-shot LLM when the deployment needs to handle out-of-scope utterances gracefully, operate over noisy ASR transcripts, or serve multiple apps with different intent schemas without retraining, since the classifier&\#x27;s accuracy collapses to 0% on an unseen schema while the LLM transfers with a prompt change. For broad, many-intent schemas the choice can hinge on operational factors like retraining overhead rather than raw accuracy, since the two approaches tie statistically.

**「Limits」** Results are measured on two specific benchmarks, ATIS and CLINC150, with one LLM \(Claude Haiku\) in zero-shot mode, so findings may not generalize to other LLMs, few-shot prompting, or intent schemas with different structure or label noise than these datasets.

**Tags**: `#intent detection`, `#LLM vs fine-tuning`, `#NLU benchmarks`, `#production ML evaluation`, `#out-of-scope detection`
