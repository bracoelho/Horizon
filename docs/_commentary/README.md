---
published: false
---
# Writing a commentary

1. Copy `template.md`, rename it after the subject. The filename becomes the
   URL, so `grid-interconnection.md` publishes at `/commentary/grid-interconnection/`.
2. Fill the front matter. `item_url` and `item_title` link back to what prompted
   it; `edition_url` links to the edition it appeared in.
3. Write to the four-beat shape below. Aim for 200-300 words: short enough to
   write in a taxi, long enough to say something.
4. Set `published: true`.
5. Commit. GitHub's web editor does all of this from a phone.

## The four beats

1. **What happened.** The finding.
2. **Why it matters.** The belief this overturns. The judgement beat, and what
   stops the piece being a better summary.
3. **What to do.** The team's action, then the director's question.
4. **Where I would be wrong.** Priced both ways, see below.

The shape exists because two audiences read this: the engineer wants to know
what changes on Monday, the director wants to know what to ask on Thursday.
Writing both is the whole point, and plenty of people can do one.

**Beat three carries both, and must contain a question a director could repeat
verbatim in a meeting.** It was two beats until 2026-08-30, "what it changes"
and "the question to ask", and they said the same thing twice: once as an
instruction, once as a question. The first published piece cut one of them
without saying why, which was the right instinct on the wrong beat. The
question is the memorable half and survives inside the action.

Keep the voice first-person and specific. The radar already produces neutral
summaries; if a piece reads like a better summary, it has failed.

## The shape of a beat

Every beat that carries evidence leads with its conclusion in one sentence,
then gives the evidence for it. Both early drafts opened with setup and buried
the finding: "a study ran 15,840 choices" before "73% of them flipped", "a
patch was shared for discussion" before "within about ten minutes".

**The test.** If your first sentence could swap places with the second and
lose nothing, it is a fact and belongs below. "Coordinated disclosure gives
maintainers days to weeks" is a fact. "Coordinated disclosure has no window
left" is a claim.

Read only the bold labels and the sentence after each. That should be the
whole argument, with no evidence in it. If it is not, a beat is missing its
conclusion, and that is invisible until you try this.

Beats that are a single move stay as they are. The question is already one
sentence and already the conclusion, so a summary above it is padding.

## "Where I would be wrong" prices the error, it does not hedge

The beat exists to show the piece came from someone who has thought about
being wrong. Four things it could do, and only one of them is worth the space:

- Name the experiment that would settle it. Honest.
- Argue the other side yourself. Senior, and it hands the reader your
  counter-argument, so it needs a strong piece to survive.
- **Price the error in both directions. Chosen, 2026-08-30.**
- Say what you are not claiming. Modest, and closer to scope than to doubt.

The reader is paid to decide under uncertainty, and pricing the error is the
only version that tells them what to do while you are still unsure. Listing
the limits of the evidence is the failure mode: it drains the four beats above
it and reads as an apology for having written.

## Voice

Write as someone accountable for the decision, not as a commentator on the
industry. That means: claims you would defend in a boardroom, evidence you have
actually seen, and consequences named in terms of cost, risk, dependency or
capability rather than in terms of the technology.

Avoid the two failure modes. The first is analyst voice - confident, general,
unfalsifiable. The second is enthusiast voice - excited about capability with
no account of what it costs to run, assure or maintain. The credibility comes
from having lived both the strategy and the delivery, so let that show.

Understatement carries further than superlatives with this audience.

## The doctrine (owner, 2026-09-01)

Define the audience segment before writing a word. Then raise that
segment's governance level, calmly: no "act by tomorrow" alarm, no
change-the-world sweep. The reader governs things; the piece hands them
one notch more governance over one real risk. A "Who should read this:" line near
the top (the owner's chosen wording, 2026-09-01) names the segment and
the horizon, so the reader knows in five seconds whether the piece is
for them.
