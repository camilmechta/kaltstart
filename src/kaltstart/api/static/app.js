// Kaltstart: the few things a page cannot do without a script.
// Every feature works without it, except copying to the clipboard.
(function () {
  "use strict";

  // Theme: the system setting, or the student's choice kept in this browser.
  var root = document.documentElement;
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* storage blocked: follow the system */ }

  function current() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-theme-toggle]");
    if (toggle) {
      var next = current() === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) { /* ignore */ }
      return;
    }

    // Copy buttons: data-copy="<id of the element holding the text>".
    var button = event.target.closest("[data-copy]");
    if (!button) return;
    var source = document.getElementById(button.getAttribute("data-copy"));
    if (!source || !navigator.clipboard) return;
    navigator.clipboard.writeText(source.innerText).then(function () {
      var label = button.getAttribute("data-label") || button.textContent;
      button.setAttribute("data-label", label);
      button.innerHTML = '<svg class="copied-check" width="14" height="14" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" ' +
        'aria-hidden="true"><path d="M4 12l5 5L20 6"/></svg>Copied';
      setTimeout(function () { button.textContent = label; }, 2000);
      // Copying the body tells the server the mail moved to "copied".
      var notify = button.getAttribute("data-copied-form");
      if (notify) {
        var form = document.getElementById(notify);
        if (form) fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin" });
      }
    });
  });

  // Sign-in and sign-up: one click is enough. A second click would send the
  // form again after the first one changed its token.
  document.addEventListener("submit", function (event) {
    var form = event.target.closest("form[data-submit-once]");
    if (!form) return;
    if (form.getAttribute("data-sent")) { event.preventDefault(); return; }
    form.setAttribute("data-sent", "1");
    var button = form.querySelector('button[type="submit"]');
    if (button) {
      button.setAttribute("aria-disabled", "true");
      button.setAttribute("data-label", button.textContent);
      button.textContent = button.textContent.indexOf("Create") === 0 ? "Creating your account…" : "Signing in…";
    }
  });
  // Back to a page the browser kept: the form can be sent again.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-sent]").forEach(function (form) {
      form.removeAttribute("data-sent");
      var button = form.querySelector('button[type="submit"][data-label]');
      if (button) { button.textContent = button.getAttribute("data-label"); button.removeAttribute("aria-disabled"); }
    });
  });

  // Live word counters: <textarea data-max-words="60"> and <span data-counter-for="id">.
  function count(field) {
    var words = field.value.trim() ? field.value.trim().split(/\s+/).length : 0;
    var max = parseInt(field.getAttribute("data-max-words"), 10);
    var counter = document.querySelector('[data-counter-for="' + field.id + '"]');
    if (!counter) return;
    counter.textContent = words + " / " + max + " words";
    counter.classList.toggle("near", words >= max * 0.9 && words <= max);
    counter.classList.toggle("over", words > max);
  }
  document.addEventListener("input", function (event) {
    if (event.target.matches("[data-max-words]")) count(event.target);
  });
  // Parts shown only when a field is chosen: data-show-when="lang_de" (a
  // ticked checkbox) or data-show-when="request=part_time" (a chosen radio).
  function sync() {
    document.querySelectorAll("[data-show-when]").forEach(function (el) {
      var rule = el.getAttribute("data-show-when").split("=");
      var selector = 'input[name="' + rule[0] + '"]' + (rule[1] ? '[value="' + rule[1] + '"]' : "");
      var input = document.querySelector(selector);
      if (input) el.hidden = !input.checked;
    });
  }
  // Filters: a choice applies at once; typed text lights the button up until
  // it is applied (Enter or the button). Without the script, the button applies all.
  document.addEventListener("change", function (event) {
    var form = event.target.closest("form[data-auto-submit]");
    if (form && event.target.matches("select, input[type=checkbox]")) {
      form.classList.add("is-applying");
      form.requestSubmit();
    }
  });
  document.addEventListener("input", function (event) {
    var form = event.target.closest("form[data-auto-submit]");
    if (form && event.target.matches("input[type=search]")) {
      form.classList.toggle("is-dirty", event.target.value !== event.target.defaultValue);
    }
  });
  document.addEventListener("change", function (event) {
    if (!event.target.matches("input[type=checkbox], input[type=radio]")) return;
    sync();
    // A short press on the card or chip that was just chosen.
    var card = event.target.closest(".chip-toggle, .role-card, .option-card");
    if (card && event.target.checked) {
      card.classList.remove("pop");
      void card.offsetWidth;
      card.classList.add("pop");
    }
  });
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-max-words]").forEach(count);
    sync();
    // The landing example plays once, when it comes into view.
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Cards of the landing page reveal once, when they come into view.
    if (!reduce && "IntersectionObserver" in window) {
      document.querySelectorAll("[data-reveal]").forEach(function (el) {
        el.classList.add("will-reveal");
        var seen = new IntersectionObserver(function (entries) {
          if (!entries[0].isIntersecting) return;
          el.classList.add("revealed");
          seen.disconnect();
        }, { threshold: 0.2 });
        seen.observe(el);
      });
    }
    if (!reduce && "IntersectionObserver" in window) {
      document.querySelectorAll("[data-play]").forEach(function (el) {
        el.classList.add("will-play");
        var seen = new IntersectionObserver(function (entries) {
          if (!entries[0].isIntersecting) return;
          el.classList.add("playing");
          seen.disconnect();
        }, { threshold: 0.25 });
        seen.observe(el);
      });
    }
  });
})();
