---
layout: default
title: Home
---
{%- comment -%}
The edition page. One set of markup for every screen: the same items in the
same order with the same colophon, arranged as the briefing on a phone (the
lead item opens as a block) and as the shelves on a wide screen (the owner,
2026-09-14). The radar's order: the shelf holding the lead comes first, then
the shelves in the order _config.yml gives them; on each shelf, the newest
edition first and each edition in its published rank.
{%- endcomment -%}
{%- assign en_posts = site.posts | where: "lang", "en" -%}
{%- assign edition = en_posts.first -%}
{%- assign en_items = site.items | where: "lang", "en" | sort: "relative_path" -%}
{%- assign groups = en_items | group_by: "edition_url" | reverse -%}
{%- assign tonight = en_items | where: "edition_url", edition.url -%}
{%- comment -%} Only an item from this edition leads. On a night with nothing published no item is promoted, and the sentence under the date leads instead (the outside reviews, 2026-09-14). {%- endcomment -%}
{%- assign lead = tonight.first -%}
{%- assign lead_shelf = lead.shelf | default: lead.theme -%}
{%- assign shelves = site.shelves | default: site.themes -%}

{% if edition %}
<div class="edition" data-edition data-labels="soon ev">
  <header class="edition-head">
    <p class="kicker">Latest edition <span aria-hidden="true">·</span> <a href="#editions-h">Past editions</a></p>
    <h1 class="edition-h"><a href="{{ edition.url | relative_url }}">{{ edition.date | date: "%-d %B %Y" }}</a></h1>
    {% if tonight.size == 0 %}
    <p class="edition-lead">Nothing was published in this edition: none of the {{ edition.analyzed | default: 0 }} items read met the bar. Each shelf shows its latest items, with their dates.</p>
    {% endif %}
    {% include colophon.html edition=edition tonight=tonight shelves=shelves %}
  </header>

  {%- if tonight.size > 1 %}
  {% include in-edition.html items=tonight %}
  {%- endif %}

  <div class="shelves">
    {%- for s in shelves -%}{%- if s.id == lead_shelf %}
    {% include shelf.html shelf=s groups=groups lead=lead edition=edition %}
    {%- endif -%}{%- endfor -%}
    {%- for s in shelves -%}{%- unless s.id == lead_shelf %}
    {% include shelf.html shelf=s groups=groups lead=lead edition=edition %}
    {%- endunless -%}{%- endfor %}
  </div>
  <p class="shelves-empty" hidden>Every shelf is hidden. Open Adjust to show one.</p>
</div>
{% else %}
<p class="take-empty">No editions published yet.</p>
{% endif %}

<section class="home-block" id="commentary" aria-labelledby="commentary-h">
  <h2 class="home-block-h" id="commentary-h">Commentary</h2>
  {%- assign takes = site.commentary | where_exp: "c", "c.title" | sort: "date" | reverse %}
  {% if takes.size > 0 %}
  <ul class="takes">
    {%- for take in takes limit:3 %}
    <li class="take">
      <a class="take-title" href="{{ take.url | relative_url }}">{{ take.title }}</a>
      <span class="take-meta">{{ take.date | date: "%-d %b %Y" }}{% if take.theme %} · {{ take.theme }}{% endif %}{% if take.related.size > 0 %}{% assign on_n = take.related.size %}{% if take.item_url %}{% assign on_n = on_n | plus: 1 %}{% endif %}{% if on_n > 1 %} · on {{ on_n }} stories{% endif %}{% endif %}</span>
    </li>
    {%- endfor %}
  </ul>
  {% else %}
  <p class="take-empty">Nothing written yet.</p>
  {% endif %}
</section>

<section class="home-block" aria-labelledby="editions-h">
  <details class="editions">
    <summary><h2 class="home-block-h" id="editions-h" tabindex="-1">Past editions</h2></summary>
    <ul class="edition-list">
      {%- for post in en_posts limit:30 %}
      {%- assign pn = post.items | default: 0 %}
      <li><a href="{{ post.url | relative_url }}"><span class="ed-date">{{ post.date | date: "%-d %b %Y, %H:%M" }} UTC</span><span class="ed-pub">{% if pn > 0 %}{{ pn }} published{% else %}none published{% endif %}</span><span class="ed-read">{{ post.analyzed | default: 0 }} read</span></a></li>
      {%- endfor %}
    </ul>
  </details>
</section>

<section class="home-block about" aria-labelledby="about-h">
  <h2 class="home-block-h" id="about-h">About the radar</h2>
  <p class="about-lede"><strong>Early warning on AI, for the people who have to decide what to do about it.</strong> Each day this reads several hundred items from research feeds, vendor announcements, developer communities and trending repositories, then publishes the few that would change a decision.</p>
  <p class="about-by">Curated by <strong>Bruno Coelho</strong>, technology leadership across Europe, Asia-Pacific and the Middle East, from strategy through execution. An item earns its place here when it would change an architecture, an investment case, or a risk position.</p>
  <ul class="doc-links">
    <li><a href="{{ '/method/' | relative_url }}">Method</a>: where it reads, and how the strongest items are chosen.</li>
    <li><a href="{{ '/playbook/' | relative_url }}">Firsthand Playbook</a>: what I have run on my own systems, written up to copy.</li>
    <li><a href="{{ '/subscribe/' | relative_url }}">Subscribe</a>: RSS or LinkedIn, with nothing to sign up for.</li>
  </ul>
</section>
