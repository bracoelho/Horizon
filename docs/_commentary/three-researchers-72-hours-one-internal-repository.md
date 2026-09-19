---
published: false
title: "Three researchers, 72 hours, one internal repository"
date: 2026-09-19 21:22:37 +0000
theme: Reliability & Assurance
item_title: "Researchers used Claude to compromise OpenAI employee accounts"
item_url: "https://www.theverge.com/ai-artificial-intelligence/997444/openai-hack-claude-heif-heist"
item_score: "7.0"
edition_url: /2026/09/19/2101-summary-en.html
---
<!-- VOICE CHECK. Read this, then delete this whole block.

  negative to positive: ', not'
  negative to positive: 'instead of'

"rather than" and "instead of" are only banned in their
rhetorical use, so a plain comparison here is fine and this note
is wrong about it. ", not" and "not just" are the flourish
itself, and the title is where they do the most damage.
-->

**What happened.** Three independent security researchers used Anthropic's Claude Opus models to break into OpenAI employee accounts and reach OpenAI's internal code repository in under 72 hours, according to a Wall Street Journal report cited by The Verge. The researchers reportedly chained several steps, credential access, session use, and lateral movement toward the internal repository, into a single fast run. No detail in the reporting suggests a lone unpatched flaw. It reads as ordinary technique executed at a pace no human attacker sustains.'

**Why it matters.** Detection thresholds at most operators assume an attacker who moves in days, pausing to research and pivot, giving defenders time to notice unusual logins and rotate credentials before real damage. That assumption is what got tested here, and it failed: three people took under 72 hours to go from outside access to an internal repository. Think of a hospital that reports a strong on-time average across all patients. The average hides its emergency room, where a few-minute delay is the whole event. Security operations centers report similarly strong averages: time to detect, time to respond. Those averages hide the emergency case, the chained attack that completes before the average has time to matter.

**What to do.** This is a question to assess, not an emergency to escalate tonight. The team should treat account and session defenses as though an AI-paced attacker is inside the timeline already, and adjust what they monitor and how fast they act on it. Rebuild detection thresholds around minutes rather than days, by setting alerts to fire on sequences of account, session, and repository events that complete within hours, not on any single event alone. Shorten credential and session lifetimes so a stolen token expires before a multi-step attack can chain through it, which means shorter session windows and forced re-authentication at key repository boundaries. Run a timed internal test, giving a small team the same tools and access an outside attacker would have, and measure how long a full chain actually takes inside the organization's own systems. The question to raise with the board: if an attacker moved through our systems as fast as these researchers moved through OpenAI's, would anyone here notice before they reached what mattered?

**Where I would be wrong.** Acting on this and being wrong costs real operating friction: shorter sessions and tighter thresholds slow down engineers, generate more alerts, and require more staff time to review, all against a threat that may not materialize the same way twice. Waiting and being wrong costs an internal repository or worse, discovered only after the fact, in the emergency room case the average never flagged. The three researchers here did not need a new kind of vulnerability. They needed hours instead of days. That is the part of the emergency room that averages hide, and it is the part worth pricing now.
