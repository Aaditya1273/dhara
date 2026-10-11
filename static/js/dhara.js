/* DHARA interface behaviour. Progressive enhancement only: every form and link works without this file. */
(function () {
  'use strict';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function busy(form, on) {
    form.querySelectorAll('button[type=submit]').forEach(function (b) {
      b.classList.toggle('is-busy', on); b.disabled = on;
      if (on) b.setAttribute('aria-busy', 'true'); else b.removeAttribute('aria-busy');
    });
  }

  function announce(msg) {
    var live = document.getElementById('live-region');
    if (live) { live.textContent = ''; setTimeout(function () { live.textContent = msg; }, 30); }
  }

  /* 1. Prevent duplicate submissions on consequential forms. */
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches('form[data-once]') || e.defaultPrevented) return;
    if (form.dataset.sent) { e.preventDefault(); return; }
    form.dataset.sent = '1';
    busy(form, true);
    if (form.dataset.pending) announce(form.dataset.pending);
  });
  /* Landing nav: transparent over the hero, floating pill once the page scrolls. */
  var lpHeader = document.querySelector('.lp-header');
  if (lpHeader) {
    var floatNav = function () { lpHeader.classList.toggle('is-floating', window.scrollY > 8); };
    window.addEventListener('scroll', floatNav, { passive: true });
    floatNav();
  }

  // Restore buttons if the page is shown again from the back/forward cache.
  window.addEventListener('pageshow', function () {
    document.querySelectorAll('form[data-sent]').forEach(function (f) { delete f.dataset.sent; busy(f, false); });
  });

  /* 2. Mobile navigation drawer. */
  document.querySelectorAll('[data-nav-toggle]').forEach(function (btn) {
    var drawer = document.getElementById(btn.getAttribute('aria-controls'));
    if (!drawer) return;
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!open));
      drawer.hidden = open;
      if (!open) { var first = drawer.querySelector('a, button'); if (first) first.focus(); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') { btn.click(); btn.focus(); }
    });
  });

  /* 3. Local previews for chosen images (the browser's own file data; nothing is uploaded yet). */
  document.querySelectorAll('input[type=file]').forEach(function (input) {
    var box = document.createElement('div');
    box.className = 'file-previews'; box.setAttribute('aria-live', 'polite');
    input.insertAdjacentElement('afterend', box);
    input.addEventListener('change', function () {
      box.innerHTML = '';
      Array.prototype.forEach.call(input.files, function (f) {
        var fig = document.createElement('figure');
        if (/^image\/(jpeg|png)$/.test(f.type)) {
          var img = document.createElement('img');
          img.alt = 'Preview of ' + f.name; img.src = URL.createObjectURL(f);
          img.onload = function () { URL.revokeObjectURL(img.src); };
          fig.appendChild(img);
        }
        var cap = document.createElement('figcaption');
        cap.textContent = f.name + ' · ' + (f.size / 1048576).toFixed(1) + ' MB';
        fig.appendChild(cap); box.appendChild(fig);
      });
    });
  });

  /* 4. Real upload progress for multipart forms marked data-upload. The bar reflects the browser's actual
        upload events. The server's response (success page or validation errors) then replaces the page. */
  document.querySelectorAll('form[data-upload]').forEach(function (form) {
    if (!window.XMLHttpRequest || !window.FormData) return;
    form.addEventListener('submit', function (e) {
      var hasFile = Array.prototype.some.call(form.querySelectorAll('input[type=file]'), function (i) { return i.files.length; });
      if (!hasFile) return;               // nothing to measure: let the normal submit happen
      e.preventDefault();
      if (form.dataset.sent) return;
      form.dataset.sent = '1'; busy(form, true);
      var wrap = form.querySelector('.upload-progress') || document.createElement('div');
      wrap.className = 'upload-progress';
      wrap.innerHTML = '<label class="label" for="up-bar">Uploading files</label><progress id="up-bar" max="100" value="0"></progress>' +
                       '<p class="help" aria-live="polite"></p>';
      var actions = form.querySelector('.form-actions');
      if (actions) actions.insertAdjacentElement('beforebegin', wrap); else form.appendChild(wrap);
      var bar = wrap.querySelector('progress'), note = wrap.querySelector('p');
      var xhr = new XMLHttpRequest();
      xhr.open(form.method || 'POST', form.action || window.location.href);
      xhr.upload.onprogress = function (ev) {
        if (!ev.lengthComputable) return;
        var pct = Math.round(ev.loaded / ev.total * 100);
        bar.value = pct; note.textContent = pct < 100 ? pct + '% sent' : 'Upload complete. Waiting for DHARA to validate and store the files…';
      };
      xhr.onload = function () {
        // Show exactly what the server returned (redirect target or the form with errors).
        if (xhr.responseURL) history.replaceState(null, '', xhr.responseURL);
        document.open(); document.write(xhr.responseText); document.close();
      };
      xhr.onerror = function () {
        note.textContent = 'The connection failed before the server answered. Nothing was saved. Check your network and try again.';
        busy(form, false); delete form.dataset.sent;
      };
      xhr.send(new FormData(form));
    });
  });

  /* 5. Measurement form: only offer units and methods that match the chosen measurement. */
  var kind = document.querySelector('select[data-kind-select]');
  if (kind) {
    var sync = function () {
      document.querySelectorAll('select[data-kind-dependent]').forEach(function (sel) {
        sel.querySelectorAll('optgroup').forEach(function (g) { g.disabled = g.dataset.kind !== kind.value; });
        if (!sel.selectedOptions[0] || sel.selectedOptions[0].parentElement.disabled) {
          var first = sel.querySelector('optgroup:not([disabled]) option'); if (first) first.selected = true;
        }
      });
    };
    kind.addEventListener('change', sync); sync();
  }

  /* 6. Accessible tabs (landing product demonstration). */
  document.querySelectorAll('[role=tablist]').forEach(function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role=tab]'));
    function select(tab, animate) {
      tabs.forEach(function (t) {
        var on = t === tab, panel = document.getElementById(t.getAttribute('aria-controls'));
        t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
        panel.hidden = !on;
        if (on && animate && !reduceMotion) { panel.classList.remove('is-entering'); void panel.offsetWidth; panel.classList.add('is-entering'); }
      });
    }
    select(tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0] || tabs[0]);
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(t, true); });
      t.addEventListener('keydown', function (e) {
        var n = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (n) { e.preventDefault(); var next = tabs[(i + n + tabs.length) % tabs.length]; select(next, true); next.focus(); }
      });
    });
  });

  /* 7. Scroll reveals: one observer, each element revealed once. Without JS (or IO) content is simply visible. */
  var reveals = document.querySelectorAll('.reveal, .lane-row');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
    reveals.forEach(function (el) { io.observe(el); });
  } else { reveals.forEach(function (el) { el.classList.add('is-in'); }); }

  /* 8. Five-layer illustration: focus one layer, explain it. Pressing the active layer again shows all. */
  var stage = document.querySelector('[data-layer-stage]');
  if (stage) {
    var btns = document.querySelectorAll('[data-layer-btn]');
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        var key = b.dataset.layerBtn, active = stage.dataset.focus === key;
        btns.forEach(function (o) { o.setAttribute('aria-pressed', String(!active && o === b)); });
        if (active) delete stage.dataset.focus; else stage.dataset.focus = key;
        stage.querySelectorAll('.layer-explain [data-layer]').forEach(function (d) {
          d.classList.toggle('is-on', active ? d.dataset.layer === 'all' : d.dataset.layer === key);
        });
      });
    });
  }

  /* 9. Workflow story: the step nearest the middle of the viewport becomes active; the aside shows progress. */
  var steps = document.querySelectorAll('.steps .step');
  if (steps.length && 'IntersectionObserver' in window) {
    var bar = document.querySelector('[data-story-bar]'), label = document.querySelector('[data-story-label]');
    var so = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var idx = Array.prototype.indexOf.call(steps, en.target);
        steps.forEach(function (s, i) { s.classList.toggle('is-active', i <= idx); });
        if (bar) bar.style.width = ((idx + 1) / steps.length * 100) + '%';
        if (label) label.textContent = 'Step ' + (idx + 1) + ' of ' + steps.length + ': ' + en.target.dataset.step;
      });
    }, { rootMargin: '-45% 0px -45% 0px' });
    steps.forEach(function (s) { so.observe(s); });
  }

})();
