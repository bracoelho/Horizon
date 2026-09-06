---
layout: default
title: Method
permalink: /method/
description: How items are found, scored, compared and written up, and what has to be true for one to publish.
---

<div class="radar-intro" markdown="1">

**Several hundred items arrive each day. A handful are published.** This page explains what happens in between, so you can judge whether the selection deserves your attention.

</div>

<h2 class="section-label">The pipeline</h2>

<div class="pipeline" markdown="1">

`read` → `deduplicate` → `sift on title and summary` → `score what survives` → `rank the survivors against each other` → `argue the case for the strongest` → `research` → `publish what clears the floor`

</div>

<h2 class="section-label">Where it reads</h2>

<ul class="doc-links">
  <li><strong>Research</strong>: arXiv computer science feeds covering AI, language, learning and software engineering.</li>
  <li><strong>First-party</strong>: announcements from the major model developers and tooling vendors.</li>
  <li><strong>Sector</strong>: energy and utilities trade press, standards bodies, and a keyword search across news for AI and infrastructure.</li>
  <li><strong>Practitioners</strong>: Hacker News, selected engineering writing, release notes for widely used tools, and trending repositories.</li>
</ul>

<h2 class="section-label">The five themes</h2>

<p class="method-note">Each item is routed to one theme, and each theme carries its own question and its own rubric. The question is what a reader of that theme has to decide.</p>

<ul class="sub-facts">
  <li><span class="k">Critical Infrastructure</span><span class="v">Energy, utilities, water, transport and industrial operations, plus the demands AI places on them. Asks what an operator would do differently.</span></li>
  <li><span class="k">Reliability &amp; Assurance</span><span class="v">Whether these systems can be trusted to run: drift, agent and workflow failure, evaluation integrity, security, and the regimes that govern them. Asks who is exposed and what to check.</span></li>
  <li><span class="k">Business &amp; Markets</span><span class="v">Deals, pricing, supply and regulation with commercial consequence. Asks what changes commercially, and for whom.</span></li>
  <li><span class="k">Practice</span><span class="v">What an engineering team could act on this quarter. Asks what a team would do differently.</span></li>
  <li><span class="k">Horizon</span><span class="v">Research whose consequence is real and unproven. Asks what would have to be true for it to matter.</span></li>
</ul>

<h2 class="section-label">How an item earns its place</h2>

<p class="method-note">A first pass reads every item's title and summary and drops what has no bearing on the radar's subject. What survives is scored 0 to 10 for significance against its theme's rubric. The scored items are then ranked against each other, so what publishes depends on the strength of that day's field. The strongest few are taken one at a time and argued individually, each on the single question of whether a reader would act on it, and most are refused at that stage. A significance floor applies last, so nothing reaches the page on rank alone.</p>

<p class="method-note">A rigorous negative result scores above a marginal positive one. Popularity is not evidence of importance, and a confident headline is not evidence of anything. Research is the largest category by volume and the smallest by decisions changed: on a normal weekday, arXiv alone supplies more than five hundred items.</p>

<p class="method-note">Most editions carry very few items and some carry none, which is a judgement and not a fault.</p>

<p class="method-note">What survives is researched further, with background and consequence added, then published. Each edition carries a health report showing what was read, what cleared, and whether anything failed, so an empty edition can be told apart from a broken one.</p>

<h2 class="section-label">The point</h2>

<p class="method-note">Reading everything is cheap now. Judgement is the scarce part, so the effort goes there: choosing what earns attention, and saying why. The commentary is where that judgement gets argued in public.</p>

<p class="method-note">Built on <a href="https://github.com/Thysrael/Horizon">Horizon</a>, an open source pipeline, with Claude doing the scoring and background research. The sources, the themes, the scoring rubrics and the selection stage built on top are my own. <a href="{{ '/subscribe/' | relative_url }}">Follow the radar</a>.</p>
