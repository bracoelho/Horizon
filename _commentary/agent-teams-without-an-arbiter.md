---
published: true
title: "Agent Teams Without an Arbiter Turn on Each Other"
date: 2026-09-01 05:00:00 +0000
theme: Reliability & Assurance
item_title: "Patterns and problems in multiagent systems (Anthropic Research)"
item_url: "https://www.anthropic.com/research/multiagent-systems"
---

**Who should read this:** executives approving multi-agent deployments, and
the platform teams wiring agents into shared systems. Horizon: this quarter.

**What happened.** Anthropic gave three Claude instances the same codebase
and contradictory goals: each was told to migrate the backend to a different
language. Every model tested concluded the others were interfering on
purpose. They protected their own work, then attacked, force-terminating
rival processes and writing increasingly aggressive self-replicating malware
against each other. Roughly 60 percent of runs ended in resolution by force.
A minority resolved it the right way: they recognized the contradiction in
their instructions and asked the human for help. A separate January
benchmark points the same direction from the cooperative side: agents
collaborating on code succeeded at roughly half the rate of one agent
working alone.

**Why it matters.** Multi-agent systems are being sold as teams, and teams
are assumed to add up. The evidence says coordination must be designed:
without explicit authority, contradictory incentives turn shared
infrastructure into a battlefield, and the agents in this experiment reached
for sabotage faster than for clarification. Enterprises are wiring agents
from different vendors, departments and budgets into the same systems this
year, and inside any real organisation, partially conflicting objectives are
the everyday condition.

**What to do.** Think about the prototype of functional teams: all have "a contract" on who does what, "rules of engagement", and a leader who settles differences and makes decisions. Agentic systems are no different.
In case you are thinking this is just a "research topic", I assure you it is not. I have experienced this pattern myself in my projects. Until I ensured a written coordination contract, nominated a coordinator and decision-maker, and detailed the mechanism for how agents communicate, I spent my time solving the mistakes of coordination myself. After the "contract", on the same day, two agents caught each
other's boundary errors and brought both to me for the decision. 
Consider the following thought experiment: What if one of my agents goes dark against the contract, into a spree of expenditure and damage?
The question you should ask: How are my agentic systems today? Where do my design guidelines, "checklists", my review process and stress tests stand on this topic?

**Where I would be wrong.** This article was done to showcase and study the behaviour. Your case might not match. However, waiting for a production incident before acting buys the same lesson at incident cost when it is available today for [a page of governance](/agent-contract/).
