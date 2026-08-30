---
published: false
title: "Ten minutes"
date: 2026-08-30 08:30:00 +0000
theme: Reliability & Assurance
item_title: "Maintainers report exploit attempts within minutes of bug disclosure"
item_url: "https://simonwillison.net/2026/Aug/28/just-a-rumour-of-a-bug/"
item_score: "6.0"
edition_url: /2026/08/29/2323-summary-en.html
---
**What happened.** Ten minutes passed between a bug being mentioned and the first probe arriving. A security patch for OCaml was shared for discussion, before any disclosure, and the project's website began fielding percent-encoded traversal attempts. The maintainer, a Cambridge computer scientist, puts it down to automated watchers on public repositories and coding agents that turn a hint of a bug into a working attempt.

**Why it matters.** Coordinated disclosure has no window left. It gives maintainers days to weeks because an attacker was assumed to need comparable time to notice an issue and build against it. At ten minutes that assumption is gone.

**What to do.** CVE assignment has stopped being a usable trigger. It runs three to four weeks behind, so a fixed release ships marked CVE-PENDING and your scanner reports nothing; track upstream advisories and patched releases directly. For a board, the question is which of our controls depend on the gap between a fix existing and an exploit existing, and what each one is worth if that gap is zero. An OT estate on a quarterly patch cycle is where that answer costs most.

**Where I would be wrong.** The error is cheap in one direction and costly in the other. If I have overread one maintainer's measurement, you have re-dated a few controls and stopped trusting CVE timing that was never worth trusting. If I have it right and you wait for more evidence, a quarterly patch cycle spends that quarter defending a window that closed before it opened.
