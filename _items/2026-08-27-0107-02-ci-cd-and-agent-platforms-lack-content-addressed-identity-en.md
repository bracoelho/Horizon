---
layout: item
title: "CI/CD and Agent Platforms Lack Content-Addressed Identity Records"
date: 2026-08-27 01:07:58 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 5.0
link: "https://arxiv.org/abs/2608.23610"
source: "arXiv cs.SE"
edition_url: "/2026/08/27/0107-summary-en.html"
edition_title: "2026-08-27 01:07 UTC"
enriched: true
---
A documentation survey examined 47 delivery platforms \(20 CI/CD, 27 model-serving or agent-serving\) against a fixed three-label protocol, with every page graded twice, the second pass blind, and every consulted page pinned by content hash and date. Across 188 double-graded cells, no platform&\#x27;s default record produced a content-addressed identity binding the full behavioral tuple: model version, instructions, tool definitions, retrieval configuration, and runtime configuration. Sixteen of the 27 agent platforms default instead to immutable nominal versioning, meaning version integers sit behind mutable pointers, a pattern the researchers note the software artifact supply chain has already found insufficient. A second instrument, applied to a frozen set of 30 public repositories graded twice from a hashed archive, found that seven of 15 repositories adopting attestation tooling publish source-only releases, so the binding their workflows claim cannot actually be checked; where it could be checked, five of seven adopters did realize the binding end to end.&lt;/p&gt;

rss · arXiv cs.SE · Aug 26, 04:00

**「The assumption at stake」** Organizations deploying AI systems, and agentic systems in particular, rely on pipeline records to substantiate the claim that the system evaluated is the system running in production and that supporting evidence justified the transition. This assumption underwrites audit trails, compliance attestations, and internal sign-off processes, and it presumes that default platform tooling captures enough identity information to make that claim checkable after the fact.

**「Who should check their setup」** Any organization using CI/CD pipelines or agent-serving platforms to promote AI systems into production, and relying on those platforms&\#x27; default records for audit or compliance purposes, falls within scope; the survey covered 47 named platforms across both categories, though the abstract available here does not list them individually. Teams should check whether their deployment records capture a content-addressed binding of model version, instructions, tool definitions, retrieval configuration, and runtime configuration together, rather than versioning only one of these elements or relying on mutable pointers behind a version integer. Teams that have adopted attestation tooling specifically should verify that their releases are not source-only, since the study found this is where declared bindings become unverifiable in practice.

**「What reduces the risk」** No platform-level fix is reported as available; the finding describes a structural gap in default tooling across the surveyed platforms rather than a patchable defect. Organizations that need justifiable records now would need to build content-addressed identity binding of the full behavioral tuple on top of existing platforms themselves, and ensure attestation-adopting workflows publish artifacts that make the declared binding independently checkable rather than source-only.

**Tags**: `#AI governance`, `#provenance`, `#agentic systems`, `#supply chain`, `#auditability`
