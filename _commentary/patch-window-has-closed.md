---
published: false
title: "The patch window has closed"
date: 2026-08-30 08:30:00 +0000
theme: Reliability & Assurance
item_title: "Maintainers report exploit attempts within minutes of bug disclosure"
item_url: "https://simonwillison.net/2026/Aug/28/just-a-rumour-of-a-bug/"
item_score: "6.0"
edition_url: /2026/08/29/2323-summary-en.html
---

**What happened.** A security patch for OCaml was shared for discussion, before any disclosure. Within about ten minutes the project's website was fielding probes for percent-encoded traversal sequences. The maintainer, a Cambridge computer scientist, puts it down to automated watchers on public repositories and coding agents that turn a hint of a bug into a working attempt.

**Why this is signal.** Coordinated disclosure gives maintainers days to weeks before details become public. That window exists because an attacker was assumed to need comparable time. At ten minutes there is no window.

**What it changes.** For a delivery team, stop treating CVE assignment as the trigger. Assignment now runs three to four weeks behind, so a fixed release ships marked CVE-PENDING and your scanner reports nothing. Track upstream advisories and patched releases directly. For a board, every control that assumes time between a fix existing and an exploit existing needs re-dating, and an OT estate on a quarterly patch cycle is where that assumption is most expensive.

**The question to ask.** Which of our controls depend on that gap, and what is each one worth if the gap is zero?

**Where I would be wrong.** One maintainer, one project, one measurement, and the trigger was a rumour of a bug. The forty disclosures rclone took in a month tell you about volume. They tell you nothing about speed.
