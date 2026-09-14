(function () {
  'use strict';

  /**
   * Remove the "⭐️ N/10" text the edition renderer still writes beside each
   * headline. No score is shown to readers (BACKLOG #36, option c). A stopgap:
   * the renderer keeps writing it until the notifier is decoupled (N-212), and
   * the redesign's theme replaces this file.
   */
  function stripScores() {
    var scoreRe = /\s*⭐️?\s*\d+(?:\.\d+)?\/10/g;
    var targets = document.querySelectorAll('.main-content h2, .main-content h3, .main-content li');
    targets.forEach(function (el) {
      if (!scoreRe.test(el.innerHTML)) return;
      scoreRe.lastIndex = 0;
      el.innerHTML = el.innerHTML.replace(scoreRe, '');
    });
  }

  /** Add semantic classes to tag lines, source lines, and background paragraphs */
  function markSemanticElements() {
    var paragraphs = document.querySelectorAll('.main-content p');
    paragraphs.forEach(function (p) {
      var text = p.textContent.trim();

      // Tag line: starts with Tags or 标签 (bold prefix rendered by Markdown)
      if (/^(Tags|标签)\s*:/.test(text)) {
        p.classList.add('tag-line');
        return;
      }

      // Source line: pattern like "source · site · date"
      if (/^(rss|reddit|github|hackernews|hn|telegram)\s*·/i.test(text)) {
        p.classList.add('source-line');
        return;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    stripScores();
    markSemanticElements();
  });
})();
