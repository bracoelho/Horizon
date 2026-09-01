---
layout: default
title: "The Firsthand Playbook"
permalink: /playbook/
description: "Operational artifacts from Bruno Coelho's own AI systems, from experiment to framework."
---

<div class="radar-intro" markdown="1">

**From experiment to framework: everything here ran on my own systems before it was written down.** Run first, written after.

</div>

<h2 class="section-label">Entries</h2>

{% assign entries = site.playbook | sort: "date" | reverse %}
{% if entries.size > 0 %}
<ul class="playbook-list">
  {% for entry in entries %}
    <li class="playbook-entry">
      <a href="{{ entry.url | relative_url }}">
        <span class="playbook-entry-title">{{ entry.title }}</span>
        {% if entry.summary %}<span class="playbook-entry-summary">{{ entry.summary }}</span>{% endif %}
        {% if entry.date %}<span class="playbook-entry-date">{{ entry.date | date: "%d %b %Y" }}</span>{% endif %}
      </a>
    </li>
  {% endfor %}
</ul>
{% else %}
<p class="take-empty">Nothing here yet.</p>
{% endif %}
