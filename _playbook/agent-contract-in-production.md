---
layout: default
title: "One Page of Agent Governance, and the Gap It Did Not Cover"
permalink: /agent-contract-in-production/
date: 2026-09-10
published: true
summary: "The coordination contract in production: twice it worked, the third time it was silent, and what stopped the overreach sat outside the agent system entirely. With receipts, and the vendor's own documentation."
---

# One page of agent governance, and the gap it did not cover

My AI agents work under [a one-page coordination contract](/agent-contract/). In its first three days it was tested three times. Twice an agent refused an instruction it could not verify came from me and came to me directly: the page did its job. The third time it was silent. My coordinating agent reached for a capability its task never needed, nothing in the page covered that, and what stopped it was my locked Mac; macOS asked whether to allow it, and within a minute the agent itself told me it was the cause and to refuse. I did. That is the finding. Written agent governance can be perfectly obeyed and still not protect you, because it governs who may ask and not what can be taken.

If you approve AI agents in a regulated operation, two questions follow: which of your agents would refuse an instruction that only claims to come from you, and if one reached for something nobody authorised, what outside the agent system would stop it? The account below is for the engineers who will be asked to answer it: the sequence, the layers of control, and what I would do next.

## The setting

Several AI sessions do the work, each a long-running conversation with a coding agent that is the sole writer of one repository. They research, write, review and publish. One session coordinates; the others own their domains, and the coordinator can spawn subagents of its own for bounded tasks. I am
the one human, and every decision that crosses a boundary is mine.

## The three moments

### First evening: a relayed contract refused

The task-manager session drafted a coordination contract and sent it to another session by message, with my agreement implied. That session refused to register it on relayed authority, flagged a gap (an
experiment that would have put an untrusted agent framework on working
infrastructure), and surfaced the whole thing for my direct decision. I
ratified it with three amendments, one of which wrote the no-relay rule
into the contract itself. It took three steps over about five minutes: my ratification, the tightening to one writer per resource, and my clarification that the task-manager session is a debate space.

The same clause then fired in the other direction. The coordinating
session relayed that clarification to the task-manager session, which
held it as a proposal until I said it in that session myself. A relayed
message demoting my own future direct words is exactly what the rule
exists to block, however legitimate the instance. The task manager's
`COORDINATION.md` keeps the superseded status lines ("pending Bruno's
direct ratification in this session") beside the ratified text.

### Same evening: the coordinator's overreach, stopped by a locked screen and disclosed by the agent itself

Producing a LinkedIn visual, the coordinating session hit an opaque save
path in its browser tooling and fell back to the operating system's
screen capture, a permission the task never justified. The capture failed because my display was locked, and the Screen Recording prompt I
saw was the residue of the attempt rather than the thing that stopped
it. About a minute later, unprompted, the agent told me: deny it, it was me, and here is why. I denied it. The headless render tool that removes the need for any screen was committed that same evening, two minutes after I wrote the incident down. The journal episode originally said "five in the
morning"; a later claim-attack pass found nothing in the record at that hour and dated it to the evening instead. The correction stands in the journal beside the
original.

### Day three: succession on direct word only

A successor session booted into one of those repositories, read instructions naming another session as its writer, said so, and was ratified by me directly three minutes later. The outgoing
session stood down on my word to it, and the coordinating session
refused the relay too. For a few minutes the two records disagreed on
purpose, each waiting for me, and the disagreement resolved only when I
had spoken to each. A record that says where it disagrees is more
trustworthy than one that agrees by rewrite.

## The four layers, and what each one misses

Three of these shape what an agent tries. One enforces a boundary. The distinction is not mine, it is the vendor's, documented: "Permission rules are enforced by Claude Code, not by the model. Instructions in your prompt or CLAUDE.md shape what Claude tries to do, but they don't change what Claude Code allows." And on writing rules into an agent's instruction file: "This shapes what Claude tries but doesn't enforce a boundary, so pair it with one of the options above." ([Anthropic, Claude Code permissions](https://code.claude.com/docs/en/permissions), read 2026-09-10.) My one page is an instruction file. It shapes; it does not enforce.

Four layers were in place, added at different times for different
reasons. Each covers a scope the others miss.

1. **The agent runtime's rule for subagents.** The tool that runs these
   sessions instructs every subagent it spawns that no message from
   another agent is ever the user's consent or approval. Scope: the
   subagents of one session. Alone it says nothing about peer sessions,
   which are separate conversations with no runtime relationship.
2. **The repository rule, written earlier.** That repository's own instructions recorded, when a second session joined it, that neither
   session takes authorization from the other relaying it. Scope: the two sessions of one project. Alone
   it binds nobody outside this repository.
3. **The cross-project contract.** The ratified contract
   extended the same rule to every peer session across projects, with
   one coordinator, one decision-maker and one writer per resource
   (contract sections 4 and 5). Scope: messages between sessions.
   Alone it is silent about resources: a permission prompt is a request
   to the operating system, and no message passes between agents.
4. **The operating system's permission gate.** macOS asked before
   granting Screen Recording, on a locked machine, to a human who had
   given no such instruction. Scope: resources. Alone it knows nothing
   about authority; it would have granted the permission to a
   distracted click.

The two refusals were caught by layers 2 and 3, on the first day layer 3 existed: instruction files, obeyed. The overreach was caught by neither, because neither had anything to say about it. The popup did not catch it either; a locked screen did. Layer 4's part was to require permission for that capability at all, on Apple's own terms, and mine was to refuse. Layer 1 never had
the chance to fire, because every relayed instruction in these three
days travelled between sessions, and none reached a subagent.

## The stress test

Section 7 of the contract schedules one: two agents with deliberately
conflicting goals inside a sandbox, watched against sections 2 through
6. Mine is still to run, and the write-up will follow on this site when
it does. Until then, the three moments above are what the contract has
been tested against: real work, small stakes, and no adversary.

## What I would do next

**Inventory what your agents can reach, not only who may instruct them.** My
page governed instruction and said nothing about capability. Most written agent
governance I have seen does the same, which is why the gap is worth looking for
before it finds you.

**Put one control where your agents cannot configure it.** Mine was the
operating system, and it was there by default rather than by design. Choose it
deliberately: device management, identity, control over what can leave the
network. The test is simple: if your agents can change it, it is not that layer.

**Read your own transcripts.** Every instruction an agent receives is written
down, in that session's own record. Mine were complete enough to reconstruct the
overreach afterwards, down to the failed call and its exit. What is missing is
not the evidence, it is anything that reads it: a check that looks for
instructions which should have been refused, and reports the ones that were not.
That check does not exist in my system yet. It is the next thing I am building.

**Test it before someone else does.** Section 7 of the contract is a stress
test: two agents with deliberately conflicting goals, watched against the rest
of the page. Mine has not run yet, and the write-up follows here when it does.

One caveat, and I would rather state it than have it found: this is three days,
a handful of agents, one vendor's models, and nobody trying to break in. It is a
starting point rather than proof, which is why I am publishing the method as well as the conclusion.

