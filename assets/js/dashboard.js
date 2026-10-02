/* Dashboard (index.html). One scope control above everything; every tile, list and
   chart below re-renders against the same slice so the numbers always agree. */
(function () {
  "use strict";
  const { el, fill, icon, statusOf, daysLeft, timeLeftLabel, fmtDate, fmtDateTime, deadlineSummary, badge,
    STATUS_META, ELIG_META, ELIG_ORDER, openDetail, loadAll, initTheme, showError, known, safeUrl } = window.OI;

  const SCOPES = {
    all: { label: "Everything tracked", test: () => true },
    open: { label: "Not ruled out", test: (r) => r.eligibility_for_me !== "NOT ELIGIBLE" },
    likely: { label: "Likely eligible only", test: (r) => r.eligibility_for_me === "LIKELY ELIGIBLE" }
  };
  let state = { scope: "all" };
  let data = null;
  let tooltip = null;

  function isLive(rec) {
    const status = statusOf(rec);
    return status === "OPEN" || status === "CLOSING SOON" || status === "ROLLING";
  }

  function tile(label, value, href, hint) {
    return el("a", { class: "tile", href },
      el("span", { class: "tile-label", text: label }),
      el("span", { class: "tile-value", text: String(value) }),
      hint ? el("span", { class: "tile-hint", text: hint }) : null);
  }

  /* ------------------------------------------------------------ bar chart with table twin */
  function showTip(event, title, value) {
    if (!tooltip) {
      tooltip = el("div", { class: "viz-tip", role: "status" });
      document.body.appendChild(tooltip);
    }
    fill(tooltip, el("strong", { text: value }), el("span", { text: title }));
    tooltip.hidden = false;
    const box = event.currentTarget.getBoundingClientRect();
    const x = event.clientX || box.left + box.width / 2;
    const y = event.clientY || box.top;
    tooltip.style.left = Math.min(window.innerWidth - tooltip.offsetWidth - 12, Math.max(12, x + 12)) + "px";
    tooltip.style.top = Math.max(12, y - tooltip.offsetHeight - 10) + window.scrollY + "px";
  }
  function hideTip() { if (tooltip) tooltip.hidden = true; }

  function barChart(title, subtitle, rows, hrefFor) {
    const total = rows.reduce((sum, row) => sum + row.value, 0);
    const max = Math.max(1, ...rows.map((row) => row.value));
    const bars = el("div", { class: "bars" }, rows.map((row) => {
      const share = total ? Math.round((row.value / total) * 100) : 0;
      const tip = (event) => showTip(event, row.label, row.value + " (" + share + "% of entries)");
      return el("a", {
        class: "bar-row", href: hrefFor(row.key),
        onpointermove: tip, onpointerleave: hideTip, onfocus: tip, onblur: hideTip
      },
        el("span", { class: "bar-label", text: row.label }),
        el("span", { class: "bar-track" }, el("span", { class: "bar", style: "width:" + (row.value / max) * 100 + "%" })),
        el("span", { class: "bar-value", text: String(row.value) }));
    }));
    const table = el("table", { class: "viz-table", hidden: true },
      el("thead", null, el("tr", null, el("th", { scope: "col", text: title }), el("th", { scope: "col", text: "Count" }))),
      el("tbody", null, rows.map((row) => el("tr", null, el("th", { scope: "row", text: row.label }), el("td", { text: String(row.value) })))));
    const toggle = el("button", { type: "button", class: "btn ghost small", "aria-pressed": "false" }, icon("table"), "Table");
    toggle.addEventListener("click", () => {
      const showTable = table.hidden;
      table.hidden = !showTable;
      bars.hidden = showTable;
      toggle.setAttribute("aria-pressed", String(showTable));
      fill(toggle, icon(showTable ? "bars" : "table"), showTable ? "Chart" : "Table");
    });
    return el("figure", { class: "panel viz" },
      el("figcaption", null,
        el("div", null, el("h3", { text: title }), el("p", { class: "muted small", text: subtitle })), toggle),
      rows.length ? bars : el("p", { class: "muted", text: "Nothing in this scope." }), table);
  }

  function countBy(records, picker) {
    const counts = new Map();
    for (const rec of records) {
      for (const key of [].concat(picker(rec) || [])) {
        if (!known(key)) continue;
        counts.set(key, (counts.get(key) || 0) + 1);
      }
    }
    return [...counts.entries()].map(([key, value]) => ({ key, label: key, value }))
      .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
  }

  /* ------------------------------------------------------------ render */
  function render() {
    const now = new Date();
    const flags = (data.meta && data.meta.flags) || [];
    const scope = SCOPES[state.scope];
    const records = data.records.filter(scope.test);
    const open = (id) => openDetail(data.records.find((r) => r.id === id), flags);

    const live = records.filter(isLive);
    const closing = records.filter((r) => statusOf(r, now) === "CLOSING SOON");
    const upcoming = records.filter((r) => statusOf(r, now) === "UPCOMING");
    const q = (params) => "opportunities.html?" + new URLSearchParams(
      Object.assign(state.scope === "likely" ? { eligibility: "LIKELY ELIGIBLE" } : {}, params)).toString();

    // hero + tiles
    fill(document.getElementById("hero"), 
      el("div", { class: "hero-figure" },
        el("span", { class: "hero-value", text: String(live.length) }),
        el("span", { class: "hero-label" }, "open to act on now",
          el("span", { class: "muted", text: " out of " + records.length + " tracked in this scope" }))),
      el("p", { class: "muted small" },
        "Last research cycle: " + (fmtDate(data.updated) || "not recorded") + ". ",
        data.meta && data.meta.last_refresh ? "Last automatic refresh: " + fmtDateTime(data.meta.last_refresh) + "." : "Automatic refresh has not run yet."));

    fill(document.getElementById("tiles"), 
      tile("Tracked", records.length, q({}), data.archive.length + " in archive"),
      tile("Open now", live.length, q({ deadline: "open" })),
      tile("Closing soon", closing.length, q({ deadline: "closing" }), "within 14 days"),
      tile("Upcoming", upcoming.length, q({ deadline: "upcoming" })),
      tile("Fully funded", records.filter((r) => r.funding_type === "Fully Funded").length, q({ funding: "fully" })),
      tile("Travel funded", records.filter((r) => r.travel_funded).length, q({ funding: "travel" }), "flight covered or part-covered"),
      tile("Likely eligible", records.filter((r) => r.eligibility_for_me === "LIKELY ELIGIBLE").length, q({ eligibility: "LIKELY ELIGIBLE" })));

    // action queue
    const queue = live.filter((r) => r.eligibility_for_me !== "NOT ELIGIBLE" && r.source_confidence !== "LOW").sort((a, b) => {
      const da = daysLeft(a, now), db = daysLeft(b, now);
      if ((da === null) !== (db === null)) return da === null ? 1 : -1;
      if (da !== null && da !== db) return da - db;
      return ELIG_ORDER.indexOf(a.eligibility_for_me) - ELIG_ORDER.indexOf(b.eligibility_for_me);
    });
    fill(document.getElementById("queue"), 
      queue.length ? el("ol", { class: "queue" }, queue.map((rec) => {
        const apply = safeUrl(rec.official_application_url) || safeUrl(rec.official_information_url);
        return el("li", null,
          el("div", { class: "queue-main" },
            el("button", { type: "button", class: "linklike queue-title", onclick: () => open(rec.id), text: rec.title }),
            el("p", { class: "queue-meta" },
              el("span", { class: "queue-deadline" }, icon("calendar"), deadlineSummary(rec),
                timeLeftLabel(rec, now) ? el("span", { class: "left", text: timeLeftLabel(rec, now) }) : null),
              badge(ELIG_META[rec.eligibility_for_me]),
              el("span", { class: "muted", text: rec.funding_type })),
            known(rec.action) ? el("p", { class: "queue-action", text: rec.action }) : null),
          el("div", { class: "queue-buttons" },
            el("button", { type: "button", class: "btn small", onclick: () => open(rec.id), text: "Details" }),
            apply ? el("a", { class: "btn small primary", href: apply, target: "_blank", rel: "noopener noreferrer" }, "Apply", icon("external")) : null));
      })) : el("p", { class: "muted", text: "Nothing open in this scope right now." }));

    // deadline monitor
    const buckets = [[1, "24 hours"], [3, "3 days"], [7, "7 days"], [14, "14 days"], [30, "30 days"]];
    let floor = -Infinity;
    fill(document.getElementById("monitor"), el("ul", { class: "monitor" }, buckets.map(([limit, label]) => {
      const lower = floor;
      floor = limit;
      const hits = records.filter((r) => {
        const left = daysLeft(r, now);
        return left !== null && left >= 0 && left <= limit && left > lower && statusOf(r, now) !== "UPCOMING";
      });
      return el("li", { class: hits.length ? "" : "empty" },
        el("span", { class: "monitor-label", text: "Within " + label }),
        el("span", { class: "monitor-count", text: String(hits.length) }),
        hits.length ? el("ul", null, hits.map((r) => el("li", null,
          el("button", { type: "button", class: "linklike", onclick: () => open(r.id), text: r.title }),
          el("span", { class: "muted small", text: " " + fmtDate(r.application_deadline) })))) : null);
    })));

    // leads preview
    const leads = data.leads.slice(0, 6);
    fill(document.getElementById("leads"), 
      leads.length ? el("ul", { class: "lead-list" }, leads.map((lead) => el("li", null,
        el("a", { href: safeUrl(lead.url) || "#", target: "_blank", rel: "noopener noreferrer nofollow", text: lead.title }),
        el("span", { class: "muted small", text: lead.source + " · " + (fmtDate(lead.published) || fmtDate(lead.first_seen)) }))))
        : el("p", { class: "muted", text: "No new leads yet. The daily refresh fills this list from the feeds in data/sources.json." }),
      el("p", null, el("a", { class: "more", href: "leads.html" }, "All " + data.leads.length + " unverified leads", icon("arrow"))));

    // flags and low-confidence warnings
    const flagBox = document.getElementById("flags");
    const risky = records.filter((r) => r.source_confidence === "LOW");
    fill(flagBox, risky.length ? el("div", { class: "notice tone-critical" }, icon("alert"),
      el("div", null, el("strong", { text: risky.length + (risky.length === 1 ? " low-confidence listing" : " low-confidence listings") + " kept as a warning, not as a recommendation" }),
        el("ul", { class: "plain-list" }, risky.map((r) => el("li", null,
          el("button", { type: "button", class: "linklike", onclick: () => open(r.id), text: r.title }),
          el("span", { class: "muted small", text: " " + ((r.potential_issues || [])[0] || "") })))))) : null,
    flags.length ? el("div", { class: "notice tone-serious" }, icon("alert"),
      el("div", null, el("strong", { text: flags.length + (flags.length === 1 ? " record needs" : " records need") + " re-verification" }),
        el("ul", { class: "plain-list" }, flags.map((f) => {
          const rec = data.records.find((r) => r.id === f.id);
          return el("li", null,
            rec ? el("button", { type: "button", class: "linklike", onclick: () => open(f.id), text: rec.title }) : f.id,
            el("span", { class: "muted small", text: " " + f.detail }));
        })))) : null);

    // charts
    fill(document.getElementById("charts"), 
      barChart("By category", "A programme can sit in several categories.", countBy(records, (r) => r.category),
        (key) => q({ category: key })),
      barChart("By destination", "Country or region where the programme takes place.", countBy(records, (r) => r.country).slice(0, 10),
        (key) => q({ country: key })),
      barChart("By funding", "How the official source describes what is paid.", countBy(records, (r) => r.funding_type),
        (key) => q({ fundingtype: key })),
      barChart("By eligibility", "Assessed against the anonymous profile.",
        ELIG_ORDER.map((key) => ({ key, label: ELIG_META[key].label, value: records.filter((r) => r.eligibility_for_me === key).length }))
          .filter((row) => row.value > 0),
        (key) => "opportunities.html?" + new URLSearchParams({ eligibility: key }).toString()));

    // profile the eligibility labels are measured against
    const profile = data.profile || {};
    fill(document.getElementById("profile"), 
      [["Nationality", profile.nationality], ["Residence", profile.country_of_residence], ["Age", profile.age_band],
        ["Degree", profile.highest_degree], ["Experience", profile.work_experience],
        ["Languages", (profile.languages || []).join(", ")]]
        .filter((row) => known(row[1])).map(([label, value]) => el("li", null, el("strong", { text: label }), value)));

    // footer: feed health
    const feeds = (data.meta && data.meta.feeds) || [];
    const ok = feeds.filter((f) => f.status === 200).length;
    document.getElementById("health").textContent = feeds.length
      ? ok + " of " + feeds.length + " discovery feeds answered on the last automatic run."
      : "The discovery feeds have not been read yet.";
  }

  function initScope() {
    const box = document.getElementById("scope");
    fill(box, el("span", { class: "filter-label", id: "scope-label", text: "Scope" }),
      el("div", { class: "segmented", role: "group", "aria-labelledby": "scope-label" },
        Object.entries(SCOPES).map(([key, scope]) => el("button", {
          type: "button", "aria-pressed": String(state.scope === key), "data-scope": key, text: scope.label,
          onclick: () => {
            state.scope = key;
            box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.scope === key)));
            render();
          }
        }))));
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    try {
      data = await loadAll();
    } catch (error) {
      showError(document.getElementById("hero"), error);
      return;
    }
    initScope();
    render();
    const match = location.hash.match(/^#o=(.+)$/);
    if (match) {
      const id = decodeURIComponent(match[1]);
      const rec = data.records.concat(data.archive).find((r) => r.id === id);
      if (rec) openDetail(rec, (data.meta && data.meta.flags) || []);
    }
  });
})();
