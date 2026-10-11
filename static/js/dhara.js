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
      form.querySelector('.form-actions').insertAdjacentElement('beforebegin', wrap);
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
    function select(tab) {
      tabs.forEach(function (t) {
        var on = t === tab; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
      });
    }
    select(tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0] || tabs[0]);
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(t); });
      t.addEventListener('keydown', function (e) {
        var n = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (n) { e.preventDefault(); var next = tabs[(i + n + tabs.length) % tabs.length]; select(next); next.focus(); }
      });
    });
  });

  /* 7. Pause decorative hero motion when it is off-screen (saves battery; no effect under reduced motion). */
  var hero = document.querySelector('.contours');
  if (hero && !reduceMotion && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { hero.style.animationPlayState = en.isIntersecting ? 'running' : 'paused';
        hero.querySelectorAll('g').forEach(function (g) { g.style.animationPlayState = en.isIntersecting ? 'running' : 'paused'; }); });
    }).observe(hero);
  }
})();
