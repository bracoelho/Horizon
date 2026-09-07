---
published: false
title: "Average Coverage Hides a Near-Half Drop"
date: 2026-09-07 23:28:16 +0000
theme: Reliability & Assurance
item_title: "Peer Pressure Between Agents Silently Breaks Conformal Prediction Guarantees"
item_url: "https://arxiv.org/abs/2609.04445"
item_score: "8.0"
edition_url: /2026/09/07/2157-summary-en.html
---
<!-- VOICE CHECK. Read this, then delete this whole block.

  negative to positive: ', not'

"rather than" and "instead of" are only banned in their
rhetorical use, so a plain comparison here is fine and this note
is wrong about it. ", not" and "not just" are the flourish
itself, and the title is where they do the most damage.
-->

**What happened.** Researchers found that conformal prediction certificates calibrated for a language model answering alone lose their validity once that model sees peer agents unanimously assert a wrong answer, a mechanism they call score-mechanism shift. The effect was shown in laboratory tests across open-weight models and multiple choice tasks.

**Why it matters.** Teams that treat average coverage as proof an escalation control is working are relying on a number that can stay flat while the guarantee underneath it fails. The tests showed coverage on low-confidence items can be cut nearly in half even as the overall average looks unchanged, meaning the metric can pass while the safety property it stands for is gone.

**What to do.** Your team should report coverage split by confidence band, not as a single average, before any multi-agent escalation path goes live. The question to put to your CTO: what is our conformal coverage on the lowest-confidence quartile of cases, measured separately from the overall average, and who reviews that number before an escalation control is trusted in production.

**Where I would be wrong.** Segmenting coverage costs engineering time and could flag a healthy system as suspect if the confidence bands are drawn poorly, delaying a working escalation path over a false alarm. Waiting for more field evidence before segmenting costs nothing if peer pressure effects turn out rare outside the lab, but if they are common, every system relying on average coverage as its safety proof is already exposed, and the gap stays invisible until it fails on a case that mattered.
