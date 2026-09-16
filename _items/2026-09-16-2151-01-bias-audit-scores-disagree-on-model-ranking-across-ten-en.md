---
layout: item
title: "Bias Audit Scores Disagree on Model Ranking Across Ten Instruments"
date: 2026-09-16 21:51:14 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 8.0
link: "https://arxiv.org/abs/2609.15995"
source: "arXiv cs.CL"
edition_url: "/2026/09/16/2151-summary-en.html"
edition_title: "2026-09-16 21:51 UTC"
enriched: true
---
A study ran ten extrinsic bias audit instruments over a shared panel of ten frontier language models through a single pooled inference gateway, testing occupational gender bias and then replicating on age and socioeconomic status. Eight of the ten tools detected bias with confidence intervals clear of zero, but cross-tool agreement on how the ten models ranked against each other was indistinguishable from chance \(Kendall's coefficient of concordance W=0.07, p=0.83\). A positive control using six deliberately weaker models showed that within-tool reliability recovers when the panel spans real capability differences, but cross-tool ranking agreement never recovers, indicating the tools measure different underlying constructs rather than the same construct with more noise. The direction of detected bias also split by audit format: forced-choice tools mostly over-corrected toward women and working-class candidates, while free-generation and default coreference tools stayed stereotype-congruent. Raw responses, code, and the full analysis pipeline are published openly alongside the paper.

rss · arXiv cs.CL · Sep 16, 04:00

## Regulators and organisations assume bias audit scores are comparable across tools
{: .item-block .item-block-written .item-block-background}

Emerging AI regulation increasingly mandates bias audits for high-risk systems, and audit scores are starting to be used to rank or certify models for procurement and compliance purposes. This practice rests on the unstated assumption that different audit instruments measure the same underlying construct well enough that their scores can be compared or ranked against one another.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

Organisations that rely on a single bias audit tool to certify a model as fair, to compare vendors during procurement, or to satisfy a regulatory bias-audit requirement are in scope, since the study found no instrument-independent ranking signal across the ten frontier models and ten audit tools tested. Compliance teams should check whether their audit process uses only one instrument or format \(forced-choice, free generation, or coreference\), since the paper shows these formats can disagree even on the direction of bias, not just its magnitude. The finding applies specifically to extrinsic bias audits used for cross-model comparison; it does not claim that individual audits fail to detect bias within their own framework.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

No fix is proposed or implied by the study since the disagreement appears to stem from different tools measuring different constructs rather than from a correctable defect in any one instrument; the authors' compensating recommendation is to avoid using any single audit score as evidence of comparative fairness or safety and to treat detection and ranking as separate claims requiring separate validation.

**Tags**: `#bias audits`, `#AI regulation`, `#model evaluation`, `#benchmark validity`, `#fairness testing`
