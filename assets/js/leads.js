/* Leads (leads.html): items found by the daily feed harvest. Pointers only, never facts.
   Every lead carries a score and flags written by scripts/leadfilter.py. A flag is a reason to check
   the organiser's page, never a verdict: a title alone does not establish that anyone is ineligible. */
(function () {
  "use strict";
  const { el, fill, icon, fmtDate, fmtDateTime, safeUrl, loadAll, initTheme, showError } = window.OI;
  const TIERS = { 1: "Official feed", 2: "Institutional feed", 3: "Aggregator" };
  const LANGS = { en: "English", fr: "French", pt: "Portuguese", es: "Spanish" };
  const PAGE = 100;
  const STATUS_LABEL = { NEW: "Needs verification" };
  let data = null;
  const state = { q: "", lang: "", source: "", status: "", flags: "", sort: "score", shown: PAGE };

  function titleCase(text) {
    return text.toLowerCase().replace(/(^|[ -])([a-z])/g, (m, a, b) => a + b.toUpperCase());
  }

  /* Plain-language reading of a flag such as "audience:nationality:for Nigerian". */
  function explain(flag) {
    const [kind, sub, ...rest] = flag.split(":");
    const detail = (sub === undefined ? "" : [sub, ...rest].join(":"));
    if (kind === "audience" && sub === "nationality") return "The title names a nationality (“" + rest.join(":") + "”). Check the organiser’s country list before ruling it out.";
    if (kind === "audience" && sub === "country") return "The title names a country (“" + rest.join(":") + "”). It may be the venue, not a restriction.";
    if (kind === "audience" && sub === "level-only") return "The title names only one study level (“" + rest.join(":") + "”). Check whether a bachelor’s holder can apply.";
    if (kind === "check" && sub === "gender-term") return "The title mentions “" + rest.join(":") + "”. The applicant profile records no gender, so this must be read on the organiser’s page.";
    if (kind === "risk") return "The title mentions a fee. Check for application or participation fees first.";
    if (kind === "recurring") return "A similar title was seen in an earlier cycle: possibly a new edition of a known programme.";
    return detail || flag;
  }

  function sorted(rows) {
    const copy = rows.slice();
    if (state.sort === "new") {
      copy.sort((a, b) => (b.first_seen || "").localeCompare(a.first_seen || "") || (b.score || 0) - (a.score || 0));
    } else {
      copy.sort((a, b) => (b.score || 0) - (a.score || 0) || (b.first_seen || "").localeCompare(a.first_seen || ""));
    }
    return copy;
  }

  function leadRow(lead) {
    const flags = lead.flags || [];
    const score = typeof lead.score === "number" ? lead.score : null;
    return el("li", null,
      el("div", { class: "lead-main" },
        el("a", { href: safeUrl(lead.url) || "#", target: "_blank", rel: "noopener noreferrer nofollow" }, lead.title, icon("external")),
        el("p", { class: "muted small" },
          lead.source + " · " + (TIERS[lead.source_tier] || "Aggregator") + " · " + (LANGS[lead.language] || lead.language || "")
          + " · published " + (fmtDate(lead.published) || "date unknown") + " · first seen " + fmtDate(lead.first_seen)
          + ((lead.also_seen_in || []).length ? " · also listed by " + lead.also_seen_in.join(", ") : "")),
        flags.length ? el("div", { class: "lead-flags muted small" }, flags.map((f) => el("p", { text: explain(f) }))) : null),
      el("div", { class: "lead-badges" },
        score === null ? null : el("span", { class: "badge quiet", title: "Priority score from 0 to 100, used only to order this list. It says nothing about eligibility or legitimacy." }, "Score " + score),
        el("span", { class: "badge tone-serious" }, icon("alert"), STATUS_LABEL[lead.status] || titleCase(lead.status || "NEW"))));
  }

  function render() {
    const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    const rows = sorted(data.leads.filter((lead) =>
      (!state.lang || lead.language === state.lang) && (!state.source || lead.source === state.source)
      && (!state.status || (lead.status || "NEW") === state.status)
      && (!state.flags || (state.flags === "flagged") === Boolean((lead.flags || []).some((f) => f.startsWith("audience:"))))
      && words.every((w) => lead.title.toLowerCase().includes(w))));
    const visible = rows.slice(0, state.shown);
    document.getElementById("count").textContent = "Showing " + visible.length + " of " + rows.length
      + " matching leads (" + data.leads.length + " active in total)";
    const more = rows.length > visible.length
      ? el("div", { class: "more-row" }, el("button", {
        type: "button", class: "btn small",
        onclick: () => { state.shown += PAGE; render(); },
      }, "Show " + Math.min(PAGE, rows.length - visible.length) + " more"))
      : null;
    fill(document.getElementById("list"), rows.length
      ? [el("ul", { class: "lead-table" }, visible.map(leadRow)), more]
      : el("div", { class: "empty-state" }, el("p", { text: data.leads.length ? "No lead matches these filters." : "No leads yet." }),
        el("p", { class: "muted", text: "The daily refresh adds new items from the feeds listed in data/sources.json." })));
  }

  function select(id, values, labels) {
    const node = document.getElementById(id);
    fill(node, el("option", { value: "", text: "All" }),
      values.map((value) => el("option", { value, text: (labels && labels[value]) || value })));
    return node;
  }

  function bind(node, key) {
    node.addEventListener("change", () => { state[key] = node.value; state.shown = PAGE; render(); });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    try {
      data = await loadAll();
    } catch (error) {
      showError(document.getElementById("list"), error);
      return;
    }
    bind(select("f-lang", [...new Set(data.leads.map((l) => l.language))].sort(), LANGS), "lang");
    bind(select("f-source", [...new Set(data.leads.map((l) => l.source))].sort()), "source");
    const statuses = [...new Set(data.leads.map((l) => l.status || "NEW"))].sort();
    bind(select("f-status", statuses, STATUS_LABEL), "status");
    document.getElementById("field-status").hidden = statuses.length < 2;
    const flags = document.getElementById("f-flags");
    fill(flags, el("option", { value: "", text: "All" }),
      el("option", { value: "flagged", text: "With a flag" }), el("option", { value: "clean", text: "Without a flag" }));
    bind(flags, "flags");
    const sort = document.getElementById("f-sort");
    fill(sort, el("option", { value: "score", text: "Best score" }), el("option", { value: "new", text: "Newest first" }));
    bind(sort, "sort");
    const search = document.getElementById("search");
    search.addEventListener("input", () => { state.q = search.value.trim(); state.shown = PAGE; render(); });

    const feeds = (data.meta && data.meta.feeds) || [];
    const info = data.meta && data.meta.leads;
    document.getElementById("lead-summary").textContent = info
      ? info.archived_total + " older leads are archived, never deleted. " + info.audit_entries
        + " titles the filters set aside are logged with their reason (data/lead-audit.json)."
      : "";
    fill(document.getElementById("feeds"), feeds.length ? el("div", { class: "table-scroll", tabindex: "0", role: "region", "aria-label": "Feeds watched" },
      el("table", { class: "viz-table" },
        el("thead", null, el("tr", null, ["Feed", "Type", "Last answer", "Items read", "New leads", "Alert"].map((h) => el("th", { scope: "col", text: h })))),
        el("tbody", null, feeds.map((feed) => el("tr", null,
          el("th", { scope: "row", text: feed.name }),
          el("td", { text: TIERS[feed.tier] || "Aggregator" }),
          el("td", { text: feed.status === 200 ? "OK" : "HTTP " + feed.status }),
          el("td", { text: String(feed.items) }),
          el("td", { text: String(feed.new) }),
          el("td", { text: feed.alert || "" }))))))
      : el("p", { class: "muted", text: "The feeds have not been read yet." }));
    document.getElementById("refreshed").textContent = data.meta && data.meta.last_refresh
      ? "Last automatic refresh: " + fmtDateTime(data.meta.last_refresh) + "."
      : "Automatic refresh has not run yet.";
    render();
  });
})();
