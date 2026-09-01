---
published: false
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

**What to do.** Think about the protype of functional teams, all have "a contract" on who does what, "rules of engagement", and a leader to escalate and differences and make decisions. Agentic system are no different.
In case you are thinking this is just a "research topic", I assure you it is not. I've experienced myself this pattern at my projects. I observed that until ensuring a written the coordination contract, nominated a coordinator and decision-maker including details a mechanism of how agents communicate, spent time solving the mistakes of coordination myself. After the "contract" on the same day two agents them caught each
other's boundary errors and brought both to me for the decision. The
question you should ask: How are my agentic systems today ? Do my design guidelines, "checklists" and review process stand on this topic? 

**Where I would be wrong.**. This article is done to showcase and study the behaviour. However, consider the thought experience: What if one of my agents goes into dark mode against the contract and goes into a spree of expenditure and damage, specially the ones you have hosted in your own datacenter? I think it is worth to schedule a stress test in any case.
