/* AI Radar: the reader's choices on the edition page, kept in this browser
   only. No tracking and no requests. Every page is complete without it. */
(function () {
  "use strict";

  var KEY = "radar.choices.v1";
  var DEPTHS = [1, 3, 5];
  var ORDERS = ["radar", "soon", "ev", "ind"];
  var RANK = { soon: ["now", "dated", "eventually"], ev: ["confirmed", "reported", "unconfirmed"] };

  function all(root, sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }
  function words(s) { return s ? s.split(/\s+/).filter(Boolean) : []; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function toggle(list, v) { var k = list.indexOf(v); if (k > -1) list.splice(k, 1); else list.push(v); }
  function load() { try { return JSON.parse(window.localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function save(c) { try { window.localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) { /* storage blocked: choices last this visit */ } }

  /* Shelf colours are the reader's choice, and the choice holds on every page
     (the owner, 2026-09-14). Set as soon as the script runs, before the page
     is read. Without the script the colours stay on. */
  function hues(on) { document.documentElement.setAttribute("data-hues", on ? "on" : "off"); }
  hues(load().hues !== false);

  /* No score on any public page. Edition pages written by the pipeline still
     print a star and "N/10" beside each headline; this removes the text until
     the pipeline stops writing it. */
  function dropScores() {
    var find = /\s*⭐️?\s*\d+(?:\.\d+)?\/10/;
    var strip = /\s*⭐️?\s*\d+(?:\.\d+)?\/10/g;
    all(document, ".main-content h2, .main-content h3, .main-content li").forEach(function (el) {
      var walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), node, hits = [];
      while ((node = walk.nextNode())) if (find.test(node.nodeValue)) hits.push(node);
      hits.forEach(function (t) { t.nodeValue = t.nodeValue.replace(strip, ""); });
    });
  }

  /* The item body's "rss · The Verge - AI · Sep 11, 16:09" line, and an edition's tag line. */
  function markLines() {
    all(document, ".main-content p").forEach(function (p) {
      var text = p.textContent.trim();
      if (/^(Tags|标签)\s*:/.test(text)) p.classList.add("tag-line");
      else if (/^(rss|reddit|github|hackernews|hn|telegram)\s*·/i.test(text)) p.classList.add("source-line");
    });
  }

  /* One date line on an item page. The pipeline's "rss · The Verge - AI ·
     Sep 11, 16:09" becomes "Published 11 Sep, 16:09" beside the surfaced date,
     and the line goes. Without the script both stay. */
  function itemDates() {
    var attr = document.querySelector(".item-attr");
    var line = document.querySelector(".item-body .source-line");
    if (!attr || !line) return;
    var m = line.textContent.trim().match(/·\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{1,2}:\d{2})$/);
    if (!m) return;
    var surfaced = all(attr, "span").filter(function (s) { return /^Surfaced/.test(s.textContent.trim()); })[0];
    if (!surfaced) return;
    var pub = document.createElement("span");
    pub.textContent = "Published " + m[2] + " " + m[1] + ", " + m[3];
    var sep = document.createElement("span");
    sep.setAttribute("aria-hidden", "true");
    sep.textContent = "·";
    attr.insertBefore(pub, surfaced);
    attr.insertBefore(sep, surfaced);
    line.remove();
  }

  function edition(root) {
    var box = root.querySelector(".shelves");
    var fold = document.getElementById("fold");
    var adjust = root.querySelector(".adjust");
    if (!box || !fold || !adjust) return;
    var sections = all(box, ".shelf");
    var rows = all(box, ".row");
    rows.forEach(function (r, k) { r.setAttribute("data-k", String(k)); });

    var has = {
      ev: rows.some(function (r) { return r.hasAttribute("data-ev"); }),
      soon: rows.some(function (r) { return r.hasAttribute("data-soon"); }),
      ind: rows.some(function (r) { return r.hasAttribute("data-ind"); })
    };
    has.labels = has.ev || has.soon;
    has.order = has.labels || has.ind;
    all(root, "[data-needs]").forEach(function (el) { el.hidden = !has[el.getAttribute("data-needs")]; });

    var present = sections.map(function (s) { return s.getAttribute("data-shelf"); });
    all(fold, '[data-act="shelf"]').forEach(function (b) { if (present.indexOf(b.getAttribute("data-v")) < 0) b.remove(); });

    function members(v) {
      var b = fold.querySelector('[data-act="ind"][data-v="' + v + '"]');
      return b && b.hasAttribute("data-members") ? words(b.getAttribute("data-members")) : [v];
    }
    function isBundle(v) { var b = fold.querySelector('[data-act="ind"][data-v="' + v + '"]'); return !!(b && b.hasAttribute("data-members")); }
    function nameOf(v) { var b = fold.querySelector('[data-act="ind"][data-v="' + v + '"]'); return b ? b.getAttribute("data-name") : v; }
    all(fold, '[data-act="ind"]').forEach(function (b) {
      var ms = members(b.getAttribute("data-v"));
      var n = rows.filter(function (r) { return words(r.getAttribute("data-ind")).some(function (x) { return ms.indexOf(x) > -1; }); }).length;
      var out = b.querySelector(".n");
      if (out) out.textContent = String(n);
      b.classList.toggle("zero", n === 0);
    });

    var d = load();
    var C = {
      hidden: Array.isArray(d.hidden) ? d.hidden : [],
      depth: DEPTHS.indexOf(d.depth) > -1 ? d.depth : 3,
      order: ORDERS.indexOf(d.order) > -1 ? d.order : "radar",
      ind: Array.isArray(d.ind) ? d.ind : [],
      labels: Array.isArray(d.labels) ? d.labels : ["soon", "ev"],
      now: d.now === true,
      hues: d.hues !== false
    };

    function marks(r) {
      var mine = words(r.getAttribute("data-ind")), out = [];
      C.ind.forEach(function (v) { members(v).forEach(function (m) { if (mine.indexOf(m) > -1 && out.indexOf(m) < 0) out.push(m); }); });
      return out;
    }
    function available(order) {
      if (order === "radar") return true;
      if (order === "ind") return has.ind && C.ind.length > 0;
      return !!has[order];
    }
    function out(name, html) { var dd = root.querySelector('[data-out="' + name + '"]'); if (dd) dd.innerHTML = html; }

    function apply() {
      if (!available(C.order)) C.order = "radar";
      box.classList.add("is-live");
      var visible = 0;
      sections.forEach(function (s) {
        s.hidden = C.hidden.indexOf(s.getAttribute("data-shelf")) > -1;
        if (!s.hidden) visible++;
        var list = s.querySelector(".rows");
        var key = C.order === "radar" ? null
          : C.order === "ind" ? function (r) { return marks(r).length ? 0 : 1; }
          : function (r) { var x = RANK[C.order].indexOf(r.getAttribute("data-" + C.order)); return x < 0 ? 9 : x; };
        var rs = all(list, ".row").sort(function (a, b) {
          return (key ? key(a) - key(b) : 0) || (+a.getAttribute("data-k") - +b.getAttribute("data-k"));
        });
        var shown = 0;
        rs.forEach(function (r) {
          list.appendChild(r);
          var m = has.ind ? marks(r) : [];
          var mk = r.querySelector(".row-mark");
          r.classList.toggle("is-marked", m.length > 0);
          if (mk) { mk.hidden = m.length === 0; mk.textContent = m.map(nameOf).join(" · "); }
          var pass = !C.now || r.getAttribute("data-soon") === "now";
          r.hidden = !(pass && shown < C.depth);
          if (pass) shown++;
        });
        var empty = s.querySelector(".shelf-empty");
        if (empty) empty.hidden = shown > 0;
      });
      var none = root.querySelector(".shelves-empty");
      if (none) none.hidden = visible > 0;
      root.setAttribute("data-labels", C.labels.join(" "));
      hues(C.hues);

      out("shelves", visible === sections.length ? "All " + sections.length + " shelves" : visible + " of " + sections.length + " shelves");
      out("depth", C.depth === 1 ? "1 each" : C.depth + " each");
      out("hues", C.hues ? "" : ', <b>no shelf colours</b><button class="reset" type="button" data-act="hues" data-v="on">Reset</button>');
      if (C.order === "radar") out("order", "the radar's order");
      else {
        var ob = fold.querySelector('[data-act="order"][data-v="' + C.order + '"]');
        out("order", "<b>" + esc(ob.textContent.trim().toLowerCase()) + '</b><button class="reset" type="button" data-act="order" data-v="radar">Reset</button>');
      }
      var mn = !C.ind.length ? "none" : C.ind.length === 1 ? nameOf(C.ind[0]) : C.ind.length + " industries";
      out("marked", C.ind.length ? "<b>" + esc(mn) + "</b>" + (C.now ? " · now only" : "") : "none" + (C.now ? " · now only" : ""));

      all(fold, "[data-act]").forEach(function (b) {
        var act = b.getAttribute("data-act"), v = b.getAttribute("data-v"), on = null;
        if (act === "shelf") on = C.hidden.indexOf(v) < 0;
        else if (act === "depth") on = C.depth === +v;
        else if (act === "hues") on = (v === "on") === C.hues;
        else if (act === "order") { on = C.order === v; b.disabled = !available(v); }
        else if (act === "ind") on = C.ind.indexOf(v) > -1;
        else if (act === "label") on = C.labels.indexOf(v) > -1;
        else if (act === "now") on = C.now;
        if (on !== null) b.setAttribute("aria-pressed", String(on));
      });
      save(C);
    }

    function setOpen(open) {
      fold.hidden = !open;
      adjust.setAttribute("aria-expanded", String(open));
    }

    root.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b || !root.contains(b)) return;
      var act = b.getAttribute("data-act"), v = b.getAttribute("data-v");
      if (act === "toggle") { setOpen(fold.hidden); return; }
      if (act === "close") { setOpen(false); adjust.focus(); return; }
      if (act === "shelf") toggle(C.hidden, v);
      else if (act === "depth") C.depth = +v;
      else if (act === "hues") C.hues = v === "on";
      else if (act === "order") { if (available(v)) C.order = v; }
      else if (act === "ind") {
        if (isBundle(v)) C.ind = C.ind.indexOf(v) > -1 ? [] : [v];
        else { C.ind = C.ind.filter(function (x) { return !isBundle(x); }); toggle(C.ind, v); }
      }
      else if (act === "label") toggle(C.labels, v);
      else if (act === "now") C.now = !C.now;
      else return;
      apply();
    });
    root.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !fold.hidden) { setOpen(false); adjust.focus(); }
    });

    adjust.hidden = false;
    apply();
  }

  document.addEventListener("DOMContentLoaded", function () {
    dropScores();
    markLines();
    itemDates();
    var root = document.querySelector("[data-edition]");
    if (root) edition(root);
  });
})();
