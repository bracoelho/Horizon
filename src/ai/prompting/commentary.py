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
        "angles": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
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

Return exactly three, ordered best first. Rank on whether acting on the claim
would change a decision, then on whether it reaches his sector, which is
critical infrastructure and regulated industry, then on how far it goes beyond
what the article already says.

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

Three angles, ordered best first, as JSON matching the schema."""


DRAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "beats"],
    "properties": {
        "title": {"type": "string"},
        "beats": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
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

No em dashes. Never write "not X but Y", "X, not Y", "rather than" or "instead
of" as a rhetorical turn. No three-part lists written for rhythm. Do not use:
crucial, pivotal, leverage, robust, landscape, unlock, delve, seamless,
elevate, empower, harness, streamline, holistic. Numbers beat adjectives.
Understatement carries further than superlatives with this audience."""


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
