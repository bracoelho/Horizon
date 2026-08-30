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
