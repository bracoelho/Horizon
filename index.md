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

The reader's page rules govern what it says (the owner, 2026-09-14, OS N-222;
in full in OS specs/RADAR-PAGE-BRIEF.md): a reader's page states what is
there, with its date, and how the machine ran stays in the run record.
Rule 1, "Updated" is the newest edition's run time. Rule 2, the lead order,
below. Rule 3, no sentence about an absence. Rule 4, no machine numbers: an
edition's and a shelf's article counts stay, items read do not. Rule 8, an
edition with zero articles is neither listed nor shown as the latest edition,
and stays reachable at its address.
{%- endcomment -%}
{%- assign en_posts = site.posts | where: "lang", "en" -%}
{%- assign newest = en_posts.first -%}
{%- assign with_items = en_posts | where_exp: "p", "p.items > 0" -%}
{%- assign edition = with_items.first -%}
{%- assign en_items = site.items | where: "lang", "en" | sort: "relative_path" -%}
{%- assign groups = en_items | group_by: "edition_url" | reverse -%}
{%- assign tonight = en_items | where: "edition_url", edition.url -%}
{%- assign takes = site.commentary | where_exp: "c", "c.title" | sort: "date" | reverse -%}
{%- assign shelves = site.shelves | default: site.themes -%}

{%- comment -%}
Rule 2, the lead until stage 2, in order: the newest edition's top item if
that edition has an article; else the newest commentary if it is at most
lead_commentary_days old; else the newest article if it is at most
lead_article_days old, shown with its date; else no lead. The two limits live
in _data/reader_rules.yml and count back from the build. In stage 2 the story
lead the owner picked (S1 and T1) replaces the first step.
{%- endcomment -%}
{%- assign now_s = site.time | date: "%s" | plus: 0 -%}
{%- assign lead = nil -%}
{%- assign lead_take = nil -%}
{%- assign lead_dated = false -%}
{%- if newest.items > 0 -%}
  {%- assign lead = tonight.first -%}
{%- else -%}
  {%- assign take_days = site.data.reader_rules.lead_commentary_days | default: 7 -%}
  {%- assign item_days = site.data.reader_rules.lead_article_days | default: 7 -%}
  {%- assign newest_take = takes.first -%}
  {%- if newest_take -%}
    {%- assign take_s = newest_take.date | date: "%s" | plus: 0 -%}
    {%- assign take_age = now_s | minus: take_s -%}
    {%- assign take_max = take_days | times: 86400 -%}
    {%- if take_age <= take_max -%}{%- assign lead_take = newest_take -%}{%- endif -%}
  {%- endif -%}
  {%- unless lead_take -%}
    {%- assign cand = groups.first.items.first -%}
    {%- if cand -%}
      {%- assign item_s = cand.date | date: "%s" | plus: 0 -%}
      {%- assign item_age = now_s | minus: item_s -%}
      {%- assign item_max = item_days | times: 86400 -%}
      {%- if item_age <= item_max -%}{%- assign lead = cand -%}{%- assign lead_dated = true -%}{%- endif -%}
    {%- endif -%}
  {%- endunless -%}
{%- endif -%}
{%- assign lead_shelf = lead.shelf | default: lead.theme -%}

{% if edition %}
<div class="edition" data-edition data-labels="soon ev">
  <header class="edition-head">
    <p class="kicker">Latest edition <span aria-hidden="true">·</span> <a href="#editions-h">Past editions</a></p>
    <h1 class="edition-h"><a href="{{ edition.url | relative_url }}">{{ edition.date | date: "%-d %B %Y" }}</a></h1>
    {% include colophon.html edition=edition updated=newest tonight=tonight shelves=shelves %}
  </header>

  {%- if lead_take %}
  {%- assign on_n = lead_take.related.size | default: 0 -%}
  {%- if lead_take.item_url -%}{%- assign on_n = on_n | plus: 1 -%}{%- endif -%}
  {%- comment -%}
  The excerpt opens on what happened (the owner, 2026-09-15, "What happened"):
  a paragraph naming who should read the piece is skipped. Past 48 words it
  ends at the last full sentence, or with an ellipsis when that would leave
  fewer than 20 words.
  {%- endcomment -%}
  {%- assign summary = "" -%}
  {%- assign paras = lead_take.content | split: "</p>" -%}
  {%- for p in paras -%}
    {%- assign t = p | strip_html | strip -%}
    {%- assign head = t | slice: 0, 20 | downcase -%}
    {%- if t != "" and head != "who should read this" -%}{%- assign summary = t -%}{%- break -%}{%- endif -%}
  {%- endfor -%}
  {%- assign summary_words = summary | split: " " -%}
  {%- if summary_words.size > 48 -%}
    {%- assign cut_text = summary | truncatewords: 48, "" | strip -%}
    {%- assign parts = cut_text | split: ". " -%}
    {%- assign whole = "" -%}
    {%- for part in parts -%}{%- unless forloop.last -%}{%- assign whole = whole | append: part | append: ". " -%}{%- endunless -%}{%- endfor -%}
    {%- assign whole = whole | strip -%}
    {%- assign whole_words = whole | split: " " -%}
    {%- if whole_words.size >= 20 -%}
      {%- assign summary = whole -%}
    {%- else -%}
      {%- assign summary = cut_text -%}
      {%- assign tail = summary | slice: -1 -%}
      {%- if tail == "." or tail == "," or tail == ";" or tail == ":" %}{% assign cut = summary.size | minus: 1 %}{% assign summary = summary | slice: 0, cut %}{% endif -%}
      {%- assign summary = summary | append: "…" -%}
    {%- endif -%}
  {%- endif %}
  <section class="lead-take" aria-labelledby="lead-take-h">
    <p class="row-kicker">Commentary <span aria-hidden="true">·</span> <time datetime="{{ lead_take.date | date_to_xmlschema }}">{{ lead_take.date | date: "%-d %B" }}</time></p>
    <h2 class="lead-take-title" id="lead-take-h"><a href="{{ lead_take.url | relative_url }}">{{ lead_take.title }}</a></h2>
    <p class="row-meta">Bruno Coelho{% if on_n > 1 %} <span aria-hidden="true">·</span> on {{ on_n }} stories{% endif %}</p>
    {%- if summary != "" %}
    <p class="lead-take-text">{{ summary }}</p>
    {%- endif %}
  </section>
  {%- endif %}

  {%- if tonight.size > 1 %}
  {% include in-edition.html items=tonight %}
  {%- endif %}

  <div class="shelves">
    {%- for s in shelves -%}{%- if s.id == lead_shelf %}
    {% include shelf.html shelf=s groups=groups lead=lead dated=lead_dated edition=edition %}
    {%- endif -%}{%- endfor -%}
    {%- for s in shelves -%}{%- unless s.id == lead_shelf %}
    {% include shelf.html shelf=s groups=groups lead=lead dated=lead_dated edition=edition %}
    {%- endunless -%}{%- endfor %}
  </div>
  <p class="shelves-empty" hidden>Every shelf is hidden. Open Adjust to show one.</p>
</div>
{% endif %}

{% if takes.size > 0 %}
<section class="home-block" id="commentary" aria-labelledby="commentary-h">
  <h2 class="home-block-h" id="commentary-h">Commentary</h2>
  <ul class="takes">
    {%- for take in takes limit:3 %}
    <li class="take">
      <a class="take-title" href="{{ take.url | relative_url }}">{{ take.title }}</a>
      <span class="take-meta">{{ take.date | date: "%-d %b %Y" }}{% if take.theme %} · {{ take.theme }}{% endif %}{% if take.related.size > 0 %}{% assign on_n = take.related.size %}{% if take.item_url %}{% assign on_n = on_n | plus: 1 %}{% endif %}{% if on_n > 1 %} · on {{ on_n }} stories{% endif %}{% endif %}</span>
    </li>
    {%- endfor %}
  </ul>
  {%- if takes.size > 3 %}
  <p class="more-link"><a href="{{ '/commentary/' | relative_url }}">All {{ takes.size }} commentaries</a></p>
  {%- endif %}
</section>
{% endif %}

{% if with_items.size > 0 %}
<section class="home-block" aria-labelledby="editions-h">
  <details class="editions">
    <summary><h2 class="home-block-h" id="editions-h" tabindex="-1">Past editions</h2></summary>
    <ul class="edition-list">
      {%- for post in with_items limit:30 %}
      <li><a href="{{ post.url | relative_url }}"><span class="ed-date">{{ post.date | date: "%-d %b %Y, %H:%M" }} UTC</span><span class="ed-pub">{{ post.items }} article{% if post.items != 1 %}s{% endif %}</span></a></li>
      {%- endfor %}
    </ul>
  </details>
</section>
{% endif %}

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
