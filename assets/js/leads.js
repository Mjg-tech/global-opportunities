/* Leads (leads.html): items found by the daily feed harvest. Pointers only, never facts. */
(function () {
  "use strict";
  const { el, fill, icon, fmtDate, fmtDateTime, safeUrl, loadAll, initTheme, showError } = window.OI;
  const TIERS = { 1: "Official feed", 2: "Institutional feed", 3: "Aggregator" };
  const LANGS = { en: "English", fr: "French", pt: "Portuguese", es: "Spanish" };
  let data = null;
  const state = { q: "", lang: "", source: "" };

  function render() {
    const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    const rows = data.leads.filter((lead) =>
      (!state.lang || lead.language === state.lang) && (!state.source || lead.source === state.source)
      && words.every((w) => lead.title.toLowerCase().includes(w)));
    document.getElementById("count").textContent = "Showing " + rows.length + " of " + data.leads.length + " leads";
    fill(document.getElementById("list"), rows.length ? el("ul", { class: "lead-table" }, rows.map((lead) =>
      el("li", null,
        el("div", { class: "lead-main" },
          el("a", { href: safeUrl(lead.url) || "#", target: "_blank", rel: "noopener noreferrer nofollow" }, lead.title, icon("external")),
          el("p", { class: "muted small" },
            lead.source + " · " + (TIERS[lead.source_tier] || "Aggregator") + " · " + (LANGS[lead.language] || lead.language || "")
            + " · published " + (fmtDate(lead.published) || "date unknown") + " · first seen " + fmtDate(lead.first_seen)
            + ((lead.also_seen_in || []).length ? " · also listed by " + lead.also_seen_in.join(", ") : ""))),
        el("span", { class: "badge tone-serious" }, icon("alert"), "Needs verification"))))
      : el("div", { class: "empty-state" }, el("p", { text: data.leads.length ? "No lead matches these filters." : "No leads yet." }),
        el("p", { class: "muted", text: "The daily refresh adds new items from the feeds listed in data/sources.json." })));
  }

  function select(id, values, labels) {
    const node = document.getElementById(id);
    fill(node, el("option", { value: "", text: "All" }),
      values.map((value) => el("option", { value, text: (labels && labels[value]) || value })));
    return node;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    try {
      data = await loadAll();
    } catch (error) {
      showError(document.getElementById("list"), error);
      return;
    }
    const lang = select("f-lang", [...new Set(data.leads.map((l) => l.language))].sort(), LANGS);
    const source = select("f-source", [...new Set(data.leads.map((l) => l.source))].sort());
    lang.addEventListener("change", () => { state.lang = lang.value; render(); });
    source.addEventListener("change", () => { state.source = source.value; render(); });
    const search = document.getElementById("search");
    search.addEventListener("input", () => { state.q = search.value.trim(); render(); });

    const feeds = (data.meta && data.meta.feeds) || [];
    fill(document.getElementById("feeds"), feeds.length ? el("table", { class: "viz-table" },
      el("thead", null, el("tr", null, ["Feed", "Type", "Last answer", "Items read", "New leads"].map((h) => el("th", { scope: "col", text: h })))),
      el("tbody", null, feeds.map((feed) => el("tr", null,
        el("th", { scope: "row", text: feed.name }),
        el("td", { text: TIERS[feed.tier] || "Aggregator" }),
        el("td", { text: feed.status === 200 ? "OK" : "HTTP " + feed.status }),
        el("td", { text: String(feed.items) }),
        el("td", { text: String(feed.new) })))))
      : el("p", { class: "muted", text: "The feeds have not been read yet." }));
    document.getElementById("refreshed").textContent = data.meta && data.meta.last_refresh
      ? "Last automatic refresh: " + fmtDateTime(data.meta.last_refresh) + "."
      : "Automatic refresh has not run yet.";
    render();
  });
})();
