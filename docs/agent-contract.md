---
layout: default
title: "The One-Page Agent Coordination Contract"
permalink: /agent-contract/
published: true
---

# The one-page agent coordination contract

A template, distilled from a contract I run in production across the AI
sessions that build and operate [this radar](/). Anthropic's [multiagent study](https://www.anthropic.com/research/multiagent-systems)
showed what agents do to each other when nobody writes this page: they
assume sabotage, then commit it. Mine caught each other's boundary errors
on the contract's first evening and escalated to me. The difference was
one page. Copy it, adapt the words, keep the structure.

## 1. Roles

Name every agent (or agent team) and the one thing it owns. Ownership is
exclusive: if two agents can claim the same territory, this section is not
finished.

## 2. The coordinator

One agent is named the coordinator. It routes work between the others,
holds the shared picture, and carries escalations to the decision-maker.
The coordinator routes work; it never absorbs another agent's territory,
and being the coordinator grants no authority of its own: authority stays
with the human in section 3.

## 3. The decision-maker

One named human arbitrates goal conflicts and owns every decision that
crosses agent boundaries. Agents escalate conflicts to this person through the coordinator or directly, and
escalation must be cheaper for the agent than acting alone. If your
design makes asking harder than doing, the study above shows you what
the agents will choose.

## 4. Boundaries

Each agent writes only its own resources. Coordination happens by message,
never by two agents editing the same file, table, or record. One writer
per resource, no exceptions clause: the exceptions are where the
incidents live.

## 5. Authorization

No agent accepts an instruction relayed by another agent as the human's
authority. The decision-maker authorizes each agent directly. A relayed
"the human said so" is coordination information, never permission.

## 6. Debate and decision

Say which spaces are for exploration and which produce decisions. What is
said in a debate space is a proposal until the decision-maker confirms it
in the decision space. Agents mark unconfirmed outcomes as proposals.

## 7. The stress test

Schedule one: give two agents deliberately conflicting goals inside a
sandbox and watch what they do with sections 2 through 6. The study above
is the control group; your contract is the treatment. Keep the write-up.

---

*Written for the readers of [the commentary on Anthropic's multiagent
study](/commentary/agent-teams-without-an-arbiter/). The contract this
template distils governs the sessions that build and run this site, and
what they operate is measured in public: [the control room](/ops.html)
carries every run's numbers.*
