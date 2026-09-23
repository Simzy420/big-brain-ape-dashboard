(function () {
  "use strict";

  var DATA_URL = "portfolio-data.json?v=1";
  var STORAGE_KEY = "bba-portfolio-cc-stars";
  var STATUS_ORDER = [
    "live", "active", "enabled", "active_repo", "minimal", "private_source",
    "dormant", "empty", "locked", "archived", "legacy", "abandoned",
    "not_connected", "not_found", "unknown"
  ];

  var state = {
    q: "",
    category: "all",
    status: "all",
    platform: "all",
    starredOnly: false,
    filtersOpen: window.matchMedia("(min-width: 840px)").matches,
    sheetOpen: false
  };

  var data = null;
  var stars = loadStars();

  function ensureVersionParam() {
    try {
      var url = new URL(window.location.href);
      if (!url.searchParams.get("v")) {
        url.searchParams.set("v", "1");
        history.replaceState(null, "", url.pathname + "?" + url.searchParams.toString() + url.hash);
      }
    } catch (e) {}
  }

  function loadStars() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw.filter(function (id) { return typeof id === "string"; });
    } catch (e) {
      return [];
    }
  }

  function saveStars() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stars));
    } catch (e) {}
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function statusLabel(status) {
    var map = {
      live: "Live",
      private_source: "Private source",
      active_repo: "Active repo",
      minimal: "Minimal",
      dormant: "Dormant",
      empty: "Empty",
      archived: "Archived",
      legacy: "Legacy",
      abandoned: "Abandoned",
      not_connected: "Not connected",
      not_found: "Not found",
      unknown: "URL unknown",
      locked: "No landing",
      enabled: "Enabled",
      active: "Active"
    };
    return map[status] || status;
  }

  function typeLabel(t) {
    if (!t) return "";
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  function isStarred(id) {
    return stars.indexOf(id) !== -1;
  }

  function toggleStar(id) {
    var i = stars.indexOf(id);
    if (i === -1) stars.push(id);
    else stars.splice(i, 1);
    saveStars();
    render();
  }

  function filtersActive() {
    return state.q || state.category !== "all" || state.status !== "all" || state.platform !== "all" || state.starredOnly;
  }

  function matches(item) {
    if (state.starredOnly && !isStarred(item.id)) return false;
    if (state.category !== "all" && item.category !== state.category) return false;
    if (state.status !== "all" && item.status !== state.status) return false;
    if (state.platform !== "all" && (item.platforms || []).indexOf(state.platform) === -1) return false;
    if (!state.q) return true;
    var blob = [
      item.name, item.type, item.status, item.category, item.category_label,
      item.note, item.version_note, item.live_url_note, (item.platforms || []).join(" ")
    ].join(" ").toLowerCase();
    (item.live_links || []).concat(item.other_links || []).forEach(function (link) {
      blob += " " + (link.label || "") + " " + (link.url || "");
    });
    if (item.repo_url) blob += " " + item.repo_url;
    return blob.indexOf(state.q) !== -1;
  }

  function visibleItems() {
    return data.items.filter(matches);
  }

  function chip(label, value, group, current, title) {
    var on = current === value ? " on" : "";
    var t = title ? ' title="' + escapeHtml(title) + '"' : "";
    return '<button type="button" class="chip' + on + '" data-group="' + group + '" data-value="' + escapeHtml(value) + '"' + t + '>' + escapeHtml(label) + "</button>";
  }

  function renderFilters() {
    var legend = (data.meta && data.meta.category_legend) || {};
    var cat = chip("All", "all", "category", state.category);
    ["A", "B", "C", "D"].forEach(function (key) {
      cat += chip(key, key, "category", state.category, legend[key] || "");
    });
    cat += chip("Starred", "starred", "category", state.starredOnly ? "starred" : "", "Only cards selected for Command Center");

    var statuses = [];
    var seenS = {};
    data.items.forEach(function (item) {
      if (item.status && !seenS[item.status]) {
        seenS[item.status] = true;
        statuses.push(item.status);
      }
    });
    statuses.sort(function (a, b) {
      var ia = STATUS_ORDER.indexOf(a);
      var ib = STATUS_ORDER.indexOf(b);
      if (ia === -1) ia = 99;
      if (ib === -1) ib = 99;
      if (ia !== ib) return ia - ib;
      return a.localeCompare(b);
    });
    var st = chip("All", "all", "status", state.status);
    statuses.forEach(function (s) { st += chip(statusLabel(s), s, "status", state.status); });

    var platforms = [];
    var seenP = {};
    data.items.forEach(function (item) {
      (item.platforms || []).forEach(function (p) {
        if (!seenP[p]) { seenP[p] = true; platforms.push(p); }
      });
    });
    platforms.sort();
    var pl = chip("All", "all", "platform", state.platform);
    platforms.forEach(function (p) { pl += chip(p, p, "platform", state.platform); });

    document.getElementById("filters").innerHTML =
      '<div class="frow"><div class="flabel">Category</div><div class="chips">' + cat + "</div></div>" +
      '<div class="frow"><div class="flabel">Status</div><div class="chips">' + st + "</div></div>" +
      '<div class="frow"><div class="flabel">Platform</div><div class="chips">' + pl + "</div></div>";
  }

  function linkButtons(links, primary) {
    var html = "";
    (links || []).forEach(function (link, idx) {
      if (!link || !link.url) return;
      var cls = primary && idx === 0 ? "btn pri" : "btn";
      html += '<a class="' + cls + '" href="' + escapeHtml(link.url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(link.label || "Open") + "</a>";
    });
    return html;
  }

  function renderCard(item) {
    var starred = isStarred(item.id);
    var pills = '<span class="pill ' + escapeHtml(item.status || "") + '">' + escapeHtml(statusLabel(item.status)) + "</span>";
    if (item.type) pills += '<span class="pill">' + escapeHtml(typeLabel(item.type)) + "</span>";
    if (item.category) {
      var title = item.category_label ? ' title="' + escapeHtml(item.category_label) + '"' : "";
      pills += '<span class="pill cat"' + title + ">Cat " + escapeHtml(item.category) + "</span>";
    }
    if (item.version_role === "older") pills += '<span class="pill older">Older version</span>';
    if (item.version_role === "current") pills += '<span class="pill current">Current</span>';
    if (item.visibility === "private") pills += '<span class="pill lock">Private repo</span>';

    var platforms = (item.platforms || []).map(function (p) {
      return '<span class="platform">' + escapeHtml(p) + "</span>";
    }).join("");

    var live = item.live_links || [];
    var unknown = "";
    if (!live.length) {
      unknown = '<p class="unknown">' + escapeHtml(item.live_url_note || "Live URL unknown.") + "</p>";
    }

    var links = linkButtons(live, true);
    if (item.repo_url) {
      links += '<a class="btn" href="' + escapeHtml(item.repo_url) + '" target="_blank" rel="noopener noreferrer">Repo</a>';
    }
    links += linkButtons(item.other_links || [], false);

    var vnote = item.version_note ? '<p class="vnote">' + escapeHtml(item.version_note) + "</p>" : "";
    var updated = item.updated ? '<p class="updated">Updated ' + escapeHtml(item.updated) + "</p>" : "";

    return '<article class="card' + (starred ? " starred" : "") + '" id="item-' + escapeHtml(item.id) + '">' +
      '<div class="card-top">' +
        '<label class="star">' +
          '<input type="checkbox" data-star="' + escapeHtml(item.id) + '"' + (starred ? " checked" : "") + ">" +
          '<span class="star-ui" aria-hidden="true">' + (starred ? "★" : "☆") + "</span>" +
          '<span class="sr">Select ' + escapeHtml(item.name) + " for Command Center</span>" +
        "</label>" +
        '<div><h3>' + escapeHtml(item.name) + '</h3><div class="pills">' + pills + "</div></div>" +
      "</div>" +
      (item.note ? '<p class="note">' + escapeHtml(item.note) + "</p>" : "") +
      vnote +
      (platforms ? '<div class="platforms">' + platforms + "</div>" : "") +
      unknown +
      (links ? '<div class="links">' + links + "</div>" : "") +
      updated +
    "</article>";
  }

  function renderCatalog() {
    var items = visibleItems();
    var notes = (data.meta && data.meta.section_notes) || {};
    var html = "";
    var shownSections = {};

    (data.meta.sections || []).forEach(function (sec) {
      var group = items.filter(function (item) { return item.section === sec.id; });
      shownSections[sec.id] = group.length;
      if (!group.length) return;
      html += '<section class="section" id="' + escapeHtml(sec.id) + '">';
      html += '<div class="sec-head"><h2>' + escapeHtml(sec.title) + '</h2><span class="sec-count">' + group.length + "</span></div>";
      if (sec.blurb) html += '<p class="blurb">' + escapeHtml(sec.blurb) + "</p>";
      if (notes[sec.id]) html += '<p class="sec-note">' + escapeHtml(notes[sec.id]) + "</p>";
      html += '<div class="grid">';
      group.forEach(function (item) { html += renderCard(item); });
      html += "</div></section>";
    });

    if (!html) {
      html = '<div class="empty"><p>Nothing matches.</p><button type="button" class="linkish" id="clearFilters">Clear search and filters</button></div>';
    }

    document.getElementById("catalog").innerHTML = html;
    document.getElementById("countLine").innerHTML =
      "<span>Showing " + items.length + " of " + data.items.length + "</span>" +
      (filtersActive() ? '<button type="button" class="linkish" id="clearFilters2">Clear</button>' : "<span></span>");

    var jumps = "";
    (data.meta.sections || []).forEach(function (sec) {
      var dim = shownSections[sec.id] ? "" : " dim";
      jumps += '<a class="' + dim + '" href="#' + escapeHtml(sec.id) + '">' + escapeHtml(sec.short || sec.title) + "</a>";
    });
    document.getElementById("jumps").innerHTML = jumps;
  }

  function chosenItems() {
    var byId = {};
    data.items.forEach(function (item) { byId[item.id] = item; });
    var next = stars.filter(function (id) { return byId[id]; });
    if (next.length !== stars.length) {
      stars = next;
      saveStars();
    }
    return stars.map(function (id) { return byId[id]; });
  }

  function selectionText(chosen) {
    var lines = ["Selected for Command Center", ""];
    if (!chosen.length) {
      lines.push("Nothing selected.");
      return lines.join("\n");
    }
    chosen.forEach(function (item, i) {
      var url = (item.live_links && item.live_links[0] && item.live_links[0].url) || item.repo_url || "Live URL unknown";
      lines.push((i + 1) + ". " + item.name + " — " + url);
    });
    return lines.join("\n");
  }

  function renderSheet() {
    var chosen = chosenItems();
    document.getElementById("sheetCount").textContent = chosen.length + " selected";
    var body = document.getElementById("sheetBody");
    body.hidden = !state.sheetOpen;
    document.getElementById("sheetToggle").setAttribute("aria-expanded", state.sheetOpen ? "true" : "false");

    if (!chosen.length) {
      document.getElementById("sheetList").innerHTML = '<li class="sheet-empty">Nothing starred yet. Tap the star on a card to keep it for the Command Center.</li>';
    } else {
      document.getElementById("sheetList").innerHTML = chosen.map(function (item) {
        var url = (item.live_links && item.live_links[0] && item.live_links[0].url) || "";
        var sub = url || item.live_url_note || "Live URL unknown.";
        var name = url
          ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(item.name) + "</a>"
          : "<strong>" + escapeHtml(item.name) + "</strong>";
        return '<li class="sheet-item"><div>' + name + "<p>" + escapeHtml(sub) + '</p></div>' +
          '<button type="button" class="mini" data-remove="' + escapeHtml(item.id) + '">Remove</button></li>';
      }).join("");
    }
    document.getElementById("copyMsg").textContent = "";
  }

  function render() {
    renderFilters();
    renderCatalog();
    renderSheet();
    document.getElementById("filterToggle").setAttribute("aria-expanded", state.filtersOpen ? "true" : "false");
    document.getElementById("filters").hidden = !state.filtersOpen;
    document.getElementById("filterToggle").textContent = state.filtersOpen ? "Hide" : "Filters";
  }

  function clearFilters() {
    state.q = "";
    state.category = "all";
    state.status = "all";
    state.platform = "all";
    state.starredOnly = false;
    document.getElementById("q").value = "";
    render();
  }

  function onClick(e) {
    var chipBtn = e.target.closest(".chip");
    if (chipBtn) {
      var group = chipBtn.getAttribute("data-group");
      var value = chipBtn.getAttribute("data-value");
      if (group === "category" && value === "starred") {
        state.starredOnly = !state.starredOnly;
      } else if (group === "category") {
        state.category = value;
      } else if (group === "status") {
        state.status = value;
      } else if (group === "platform") {
        state.platform = value;
      }
      render();
      return;
    }
    if (e.target.id === "clearFilters" || e.target.id === "clearFilters2") {
      clearFilters();
      return;
    }
    var remove = e.target.closest("[data-remove]");
    if (remove) {
      toggleStar(remove.getAttribute("data-remove"));
    }
  }

  function onChange(e) {
    var input = e.target.closest("[data-star]");
    if (!input) return;
    toggleStar(input.getAttribute("data-star"));
  }

  function copySelection() {
    var text = selectionText(chosenItems());
    var msg = document.getElementById("copyMsg");
    function ok() { msg.textContent = "Copied."; }
    function fail() {
      msg.textContent = "Copy failed — select the list and copy it manually.";
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok, fail);
    } else {
      fail();
    }
  }

  function boot(payload) {
    data = payload;
    if (!data || !Array.isArray(data.items)) throw new Error("bad catalog");
    var asOf = data.meta && data.meta.as_of ? data.meta.as_of : "";
    if (asOf) document.getElementById("asOf").textContent = "Inventory " + asOf + ".";
    render();
    if (location.hash) {
      var target = document.querySelector(location.hash);
      if (target) target.scrollIntoView();
    }
  }

  ensureVersionParam();
  document.getElementById("q").addEventListener("input", function (e) {
    state.q = e.target.value.trim().toLowerCase();
    if (!data) return;
    renderCatalog();
    renderSheet();
  });
  document.getElementById("filterToggle").addEventListener("click", function () {
    state.filtersOpen = !state.filtersOpen;
    if (!data) {
      document.getElementById("filters").hidden = !state.filtersOpen;
      document.getElementById("filterToggle").setAttribute("aria-expanded", state.filtersOpen ? "true" : "false");
      document.getElementById("filterToggle").textContent = state.filtersOpen ? "Hide" : "Filters";
      return;
    }
    render();
  });
  document.getElementById("sheetToggle").addEventListener("click", function () {
    state.sheetOpen = !state.sheetOpen;
    renderSheet();
  });
  document.getElementById("copyBtn").addEventListener("click", copySelection);
  document.getElementById("clearBtn").addEventListener("click", function () {
    stars = [];
    saveStars();
    render();
  });
  document.body.addEventListener("click", onClick);
  document.body.addEventListener("change", onChange);

  fetch(DATA_URL, { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(boot)
    .catch(function () {
      document.getElementById("catalog").innerHTML =
        '<div class="empty"><p>Could not load portfolio-data.json. On GitHub Pages, open portfolio.html?v=1 from this same folder.</p></div>';
    });
})();
