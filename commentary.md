---
layout: default
title: Commentary
permalink: /commentary/
description: Every commentary published on the AI Radar, newest first, with the stories each one is written about.
---

{%- comment -%}
The commentary index, radar N-554 (the commentary is reachable only forward).
The home page carries three pieces and nothing linked past them, so a piece
fell out of reach the moment a fourth was written.

Ordering and the story count are the home page's, so the two surfaces cannot
drift: `site.commentary` already excludes unpublished pieces, `c.title` drops
the README and the template, and a piece counts its related rows plus its own
lead story. The lede is deliberately absent: a sentence about what the
commentary IS would be an editorial claim, and those are not written here.
{%- endcomment -%}
{%- assign takes = site.commentary | where_exp: "c", "c.title" | sort: "date" | reverse -%}

<div class="page-head" markdown="1">

# Commentary

</div>

{% if takes.size > 0 %}
<ul class="takes takes-index">
  {%- for take in takes %}
  <li class="take">
    <a class="take-title" href="{{ take.url | relative_url }}">{{ take.title }}</a>
    <span class="take-meta">{{ take.date | date: "%-d %b %Y" }}{% if take.theme %} <span aria-hidden="true">·</span> {{ take.theme }}{% endif %}{% if take.related.size > 0 %}{% assign on_n = take.related.size %}{% if take.item_url %}{% assign on_n = on_n | plus: 1 %}{% endif %}{% if on_n > 1 %} <span aria-hidden="true">·</span> on {{ on_n }} stories{% endif %}{% endif %}</span>
    {%- if take.item_title %}
    <span class="take-on">on <a href="{{ take.item_url }}">{{ take.item_title }}</a></span>
    {%- endif %}
  </li>
  {%- endfor %}
</ul>
{% endif %}

<p class="page-back"><a href="{{ '/' | relative_url }}">Back to the radar</a></p>
