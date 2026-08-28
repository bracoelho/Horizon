---
layout: item
title: "Researcher bypasses Claude Code auto mode about 80% of the time"
date: 2026-08-28 05:38:38 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 8.0
link: "https://simonwillison.net/2026/Aug/27/breaking-claude-code-opus-5-auto-mode/"
source: "Simon Willison"
edition_url: "/2026/08/28/0538-summary-en.html"
edition_title: "2026-08-28 05:38 UTC"
enriched: true
---
Prompt injection researcher Johann Rehberger reports an attack that defeats Claude Code&\#x27;s auto mode safety classifier roughly 80% of the time. The attack tricks the agent into downloading and unzipping an archive, then running code that imports base64, which instead loads a malicious local struct.py extracted from that archive. In some runs, after Claude detected the compromise and tried to terminate the malware process, auto mode blocked the cleanup command itself, letting the malicious process keep running. The account comes from a link-blog summary by Simon Willison citing Rehberger&\#x27;s research rather than a full primary methodology writeup, and disclosure status to Anthropic is not stated in the source.

rss · Simon Willison · Aug 27, 22:50

**「Why auto mode was trusted」** Anthropic made Claude Code&\#x27;s auto mode the default for Pro, Max, and Team plans starting mid-August 2026, pairing it with a prompt-injection probe that screens tool outputs and default-deny rules covering data exfiltration, destructive Git operations, and sensitive data access. The change was pitched as letting the agent work autonomously for longer stretches while catching dangerous commands, effectively asking users to rely on the classifier layer rather than manual approval for every action. Enterprise customers were left to opt in separately, but Pro, Max, and Team users were switched over by default, widening the population depending on this protection.

**「Who is affected」** This concerns organizations and individuals running Claude Code with auto mode enabled, which Anthropic recently made the default approval mode for the coding agent. Exposure is highest for unattended or lightly supervised agent runs that have network access and can fetch and execute external archives or packages, especially where the agent&\#x27;s runtime has access to home directories, SSH keys, or cloud credentials. Teams should check whether their Claude Code deployments rely on auto mode as a primary defense against prompt injection, and whether agents run with broad filesystem or credential access rather than inside a restricted sandbox.

**「What reduces the risk」** No vendor fix is described in the source. The researcher&\#x27;s recommended compensating control, endorsed by Willison, is to run unattended coding agents inside a container, VM, or OS sandbox, restrict network egress, monitor agent activity, and avoid exposing home directories, SSH keys, or cloud credentials to the agent runtime, treating auto mode as insufficient on its own against adversarial input.

<details><summary>References</summary>
<ul>
<li><a href="https://advancedai.com/briefings/anthropic-claude-code-auto-mode-default-august-2026/">Anthropic Switches Claude Code to Auto Mode by Default</a></li>
<li><a href="https://claude.com/blog/auto-mode-default-in-claude-code">Auto mode is now the default in Claude Code for Pro, Max, and ...</a></li>
<li><a href="https://developmentstoday.com/ai-robotics/anthropic-claude-code-auto-mode-default-2026">Anthropic makes Claude Code Auto Mode the default</a></li>

</ul>
</details>

**Tags**: `#prompt injection`, `#AI agent security`, `#Claude Code`, `#coding agents`, `#LLM safety`
