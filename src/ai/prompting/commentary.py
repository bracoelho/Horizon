"""Angles for the day's commentary candidate.

The first version of this lifted the item's block headings and called them
angles. That failed the moment block headings were fixed per theme, because
two of the three were then identical every day: "Who is exposed" and "What
reduces the risk" for every Reliability and Assurance item, forever.

A section heading says what a passage is about. An angle is a claim someone
would defend, aimed at an audience. They are different objects and one cannot
stand in for the other, which is what the owner spotted.
"""

from __future__ import annotations

from typing import Sequence

ANGLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["angles"],
    "properties": {
        # No minItems or maxItems above 1: structured outputs reject them with
        # "For 'array' type, 'minItems' values other than 0 or 1 are not
        # supported". The count is asked for in the prompt and enforced by the
        # caller, which is where a wrong count can be handled rather than
        # turned into a 400 that loses the whole call.
        "angles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "audience", "rank_reason"],
                "properties": {
                    "claim": {"type": "string"},
                    "audience": {"type": "string"},
                    "rank_reason": {"type": "string"},
                },
            },
        }
    },
}


def angles_system() -> str:
    return """You propose angles for a short commentary written by a technology
leader who is accountable for delivery and for strategy, and who writes for two
readers at once: an engineer who wants to know what changes on Monday, and a
director who wants to know what to ask on Thursday.

An angle is a claim he would defend in a boardroom, not a description of the
article. "Interpretability output is a finding rather than a record" is an
angle. "Background" and "Who is exposed" are section headings, and are not.

Rank on whether acting on the claim
would change a decision, then on whether it reaches his reader, then on how far
it goes beyond what the article already says. His reader is the AI engineering
function inside utilities and other critical-infrastructure operators: the
people who build, run and govern AI systems there. The energy business units
and the grid operations desks are welcome readers and never the target, so an
angle about power markets or dispatch only ranks if it changes what an AI
engineering leader must check, decide or govern.

An angle must stand on what the source says. If the connection between this
item and AI has to be supplied by you, the angle does not qualify and you do not
propose it. `rank_reason` is never the place to confess a gap: a reason that
would say the claim goes beyond what the article supports, or that the AI link
is not documented, means the angle is disqualified rather than ranked last.
Three drafts written from such angles were withdrawn in three days, each after a
factual attack found the bridge invented.

Return up to three, best first. Fewer is the right answer when fewer qualify,
and an empty list is the right answer when the item carries no angle that stands
on its own source. A short honest list costs nothing; an invented one costs the
author his credibility.

For each: `claim` is one sentence stating the position, twelve to thirty words.
`audience` names who it is for in a few words. `rank_reason` is one short
sentence saying why it sits where it does, including what is weak about it if
it is ranked below the others.

Write plainly. No em dashes. Do not write "not X but Y". Do not use: crucial,
pivotal, leverage, robust, landscape, unlock, delve, seamless. Numbers beat
adjectives."""


def angles_user(
    *,
    title: str,
    theme: str,
    theme_question: str,
    body: str,
    already_written: Sequence[str],
) -> str:
    covered = (
        "\n".join(f"- {t}" for t in already_written)
        if already_written
        else "- nothing yet"
    )
    return f"""# The item

Title: {title}
Theme: {theme}
The question this theme exists to answer: {theme_question}

{body}

# Already written about

Do not propose an angle that repeats one of these. Say something the author
has not said.

{covered}

# Your task

Up to three angles, ordered best first, as JSON matching the schema. Fewer, or
none, when fewer or none stand on the source."""


DRAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "beats"],
    "properties": {
        "title": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "text"],
                "properties": {
                    "label": {"type": "string"},
                    "text": {"type": "string"},
                },
            },
        },
    },
}


def draft_system() -> str:
    """The four-beat standard, stated as instructions.

    Kept in step with docs/_commentary/README.md by hand. If the shape changes
    there, it changes here, and a piece written to the old shape is worse than
    one written to none.
    """
    return """You draft a short commentary for a technology leader to edit. He
publishes it under his name, so write claims he could defend, and leave out
anything you cannot support from the material given.

Two readers at once: an engineer who wants to know what changes on Monday, and
a director who wants to know what to ask on Thursday.

Four beats, in this order, and each beat leads with its conclusion in one
sentence before any evidence:

1. "What happened" - the finding.
2. "Why it matters" - the belief this overturns. The judgement beat.
3. "What to do" - the team's action, then the director's question. This beat
   must contain a question a director could repeat verbatim in a meeting.
4. "Where I would be wrong" - price the error in both directions. Say what it
   costs to act and be wrong, and what it costs to wait and be right. Do not
   list the limits of the evidence; that drains the beats above it.

A sentence is a claim only if swapping it with the sentence below would lose
something. If it reads as a fact, it belongs lower in the beat.

200 to 260 words in total. Title states the conclusion in a few words, and the
sharpest number in the piece often makes the best title.

Two rules about the facts, and they matter more than the style ones because
this publishes under his name.

Use only what the material states. Where two facts appear separately, keep them
separate: a draft fused "Anthropic revoked API access from OpenAI" with
"Anthropic blocked Cursor" into one claim nobody had made. If the material says
"reportedly" or names no source, say so in the piece.

Assume nothing about how he works. No standing meetings, no review cadence, no
team structure, no tools he has not been told about. Write "the question to put
to your CTO", never "before Thursday's review".

The words "rather than" and "instead of" are banned outright, as are "not X but
Y" and "X, not Y". A build gate rejects them, so a draft containing one is
thrown away. Say the positive claim and stop. No em dashes. No three-part lists
written for rhythm. Do not use: crucial, pivotal, leverage, robust, landscape,
unlock, delve, seamless, elevate, empower, harness, streamline, holistic.
Numbers beat adjectives. Understatement carries further than superlatives with
this audience.

His reader is the AI engineering function inside utilities and other
critical-infrastructure operators. The energy business units and the grid
operations desks are welcome readers and never the target: frame every action
and every question for the person who builds, runs and governs AI systems
there."""


def draft_user(*, title: str, theme: str, body: str, angle: dict) -> str:
    return f"""# The item

Title: {title}
Theme: {theme}

{body}

# The angle he chose

Claim: {angle.get('claim', '')}
Written for: {angle.get('audience', '')}

Write the piece to this angle. The claim above is the spine; the four beats
build it and then price being wrong about it.

Return JSON matching the schema."""
