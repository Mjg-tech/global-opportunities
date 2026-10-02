/* Explorer (opportunities.html): search, filters, sorting, cards. Filter state lives in
   the query string so any view can be bookmarked or linked from the dashboard. */
(function () {
  "use strict";
  const { el, fill, icon, statusOf, daysLeft, card, openDetail, loadAll, initTheme, showError, known,
    FUNDING_RANK, STATUS_ORDER, ELIG_ORDER, ELIG_META, VERIF_META, ratingValue, relevanceScore,
    matchesFundingFilter, matchesDeadlineFilter, matchesTravelFilter } = window.OI;

  const CATEGORIES = ["Scholarship", "Fellowship", "Conference", "Travel", "Exchange", "Internship", "Research",
    "Entrepreneurship", "Leadership", "Training", "Volunteering", "Cultural", "Technology", "Other"];
  const LEVELS = ["Bachelor's", "Master's", "PhD", "Graduate", "Professional", "Open to all"];

  const FILTERS = [
    { key: "category", label: "Category", options: () => CATEGORIES.map((c) => [c, c]),
      test: (r, v) => (r.category || []).includes(v) },
    { key: "funding", label: "Funding", options: () => [["fully", "Fully funded"], ["substantially", "Substantially funded"],
      ["partially", "Partially funded"], ["travel", "Travel funded"], ["self", "Self funded"], ["unknown", "Unknown"]],
      test: (r, v) => matchesFundingFilter(r, v) },
    { key: "eligibility", label: "Eligibility", options: () => ELIG_ORDER.map((k) => [k, ELIG_META[k].label]),
      test: (r, v) => r.eligibility_for_me === v },
    { key: "deadline", label: "Deadline", options: () => [["open", "Open now"], ["closing", "Closing soon"],
      ["month", "This month"], ["quarter", "Next 3 months"], ["later", "Later"], ["upcoming", "Upcoming"],
      ["rolling", "Rolling"], ["unknown", "Unknown"], ["passed", "Deadline passed"]],
      test: (r, v) => matchesDeadlineFilter(r, v) },
    { key: "travel", label: "Travel", options: () => [["international", "International travel"], ["domestic", "Domestic travel"],
      ["remote", "Remote"], ["hybrid", "Hybrid"], ["inperson", "In-person"]],
      test: (r, v) => matchesTravelFilter(r, v) },
    { key: "level", label: "Education level", options: () => LEVELS.map((l) => [l, l]),
      test: (r, v) => (r.education_levels || []).includes(v) },
    { key: "continent", label: "Continent", options: (all) => distinct(all, "continent"), test: (r, v) => r.continent === v },
    { key: "region", label: "Region", options: (all) => distinct(all, "region"), test: (r, v) => r.region === v },
    { key: "country", label: "Country", options: (all) => distinct(all, "country"), test: (r, v) => r.country === v },
    { key: "verification", label: "Verification", options: () => Object.keys(VERIF_META).map((k) => [k, VERIF_META[k].label]),
      test: (r, v) => r.verification === v }
  ];

  const SORTS = {
    deadline: ["Deadline (soonest first)", (a, b) => byDeadline(a, b)],
    discovered: ["Recently discovered", (a, b) => (b.date_discovered || "").localeCompare(a.date_discovered || "") || byDeadline(a, b)],
    verified: ["Recently verified", (a, b) => (b.last_verified || "").localeCompare(a.last_verified || "") || byDeadline(a, b)],
    funding: ["Funding level", (a, b) => (FUNDING_RANK[b.funding_type] || 0) - (FUNDING_RANK[a.funding_type] || 0) || byDeadline(a, b)],
    travel: ["Travel value", (a, b) => ratingValue(b, "travel") - ratingValue(a, "travel") || byDeadline(a, b)],
    fit: ["Profile relevance", (a, b) => ratingValue(b, "profile_fit") - ratingValue(a, "profile_fit") || relevanceScore(b) - relevanceScore(a)],
    academic: ["Academic relevance", (a, b) => ratingValue(b, "academic") - ratingValue(a, "academic") || byDeadline(a, b)],
    career: ["Career relevance", (a, b) => ratingValue(b, "career") - ratingValue(a, "career") || byDeadline(a, b)],
    country: ["Country (A to Z)", (a, b) => (a.country || "").localeCompare(b.country || "") || a.title.localeCompare(b.title)],
    category: ["Category (A to Z)", (a, b) => ((a.category || [])[0] || "").localeCompare((b.category || [])[0] || "") || a.title.localeCompare(b.title)]
  };

  let data = null;
  let state = {};

  function distinct(records, field) {
    return [...new Set(records.map((r) => r[field]).filter(known))].sort().map((v) => [v, v]);
  }

  function byDeadline(a, b) {
    const sa = STATUS_ORDER.indexOf(statusOf(a)), sb = STATUS_ORDER.indexOf(statusOf(b));
    const liveA = sa <= 1, liveB = sb <= 1;                 // closing soon and open first, by date
    if (liveA !== liveB) return liveA ? -1 : 1;
    const da = daysLeft(a), db = daysLeft(b);
    if (liveA && da !== null && db !== null && da !== db) return da - db;
    if (liveA && (da === null) !== (db === null)) return da === null ? 1 : -1;
    if (sa !== sb) return sa - sb;
    if (da !== null && db !== null && da !== db) return da - db;
    return a.title.localeCompare(b.title);
  }

  function readState() {
    const params = new URLSearchParams(location.search);
    state = { q: params.get("q") || "", sort: SORTS[params.get("sort")] ? params.get("sort") : "deadline",
      archive: params.get("archive") === "1", fundingtype: params.get("fundingtype") || "" };
    for (const filter of FILTERS) state[filter.key] = params.get(filter.key) || "";
  }

  function writeState() {
    const params = new URLSearchParams();
    if (state.q) params.set("q", state.q);
    if (state.sort !== "deadline") params.set("sort", state.sort);
    if (state.archive) params.set("archive", "1");
    if (state.fundingtype) params.set("fundingtype", state.fundingtype);
    for (const filter of FILTERS) if (state[filter.key]) params.set(filter.key, state[filter.key]);
    const query = params.toString();
    history.replaceState(null, "", location.pathname + (query ? "?" + query : "") + location.hash);
  }

  function searchable(rec) {
    return [rec.title, rec.organization, rec.overview, rec.country, rec.city, rec.region,
      (rec.category || []).join(" "), (rec.subcategory || []).join(" "), (rec.eligibility || []).join(" "),
      rec.funding_type, rec.eligibility_reason].join(" ").toLowerCase();
  }

  function apply() {
    const pool = state.archive ? data.records.concat(data.archive) : data.records;
    const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    let rows = pool.filter((rec) => {
      if (words.length) {
        const text = searchable(rec);
        if (!words.every((w) => text.includes(w))) return false;
      }
      if (state.fundingtype && rec.funding_type !== state.fundingtype) return false;
      return FILTERS.every((f) => !state[f.key] || f.test(rec, state[f.key]));
    });
    rows = rows.slice().sort(SORTS[state.sort][1]);
    return { rows, pool };
  }

  function render() {
    const { rows, pool } = apply();
    const flags = (data.meta && data.meta.flags) || [];
    const open = (id) => openDetail(pool.find((r) => r.id === id) || data.archive.find((r) => r.id === id), flags);

    document.getElementById("count").textContent =
      "Showing " + rows.length + " of " + pool.length + (state.archive ? " (archive included)" : "")
      + (data.archive.length && !state.archive ? " · " + data.archive.length + " archived hidden" : "");

    const active = FILTERS.filter((f) => state[f.key]).map((f) => {
      const option = f.options(pool).find(([value]) => value === state[f.key]);
      return [f.key, f.label + ": " + (option ? option[1] : state[f.key])];
    });
    if (state.fundingtype) active.push(["fundingtype", "Funding: " + state.fundingtype]);
    if (state.q) active.push(["q", "Search: " + state.q]);
    fill(document.getElementById("active"), 
      active.map(([key, label]) => el("button", {
        type: "button", class: "chip removable", "aria-label": "Remove filter " + label,
        onclick: () => { state[key] = ""; syncControls(); writeState(); render(); }
      }, label, icon("close"))),
      active.length ? el("button", { type: "button", class: "btn ghost small", text: "Reset all",
        onclick: () => { FILTERS.forEach((f) => { state[f.key] = ""; }); state.q = ""; state.fundingtype = ""; syncControls(); writeState(); render(); } }) : null);

    const grid = document.getElementById("grid");
    fill(grid, rows.length ? rows.map((rec) => card(rec, open))
      : [el("div", { class: "empty-state" }, el("p", { text: "No opportunity matches these filters." }),
        el("p", { class: "muted", text: "Low-relevance entries are never hidden: remove a filter to see them." }))]);
  }

  function syncControls() {
    document.getElementById("search").value = state.q;
    document.getElementById("sort").value = state.sort;
    document.getElementById("archive").checked = state.archive;
    for (const filter of FILTERS) {
      const select = document.getElementById("f-" + filter.key);
      if (select) select.value = state[filter.key];
    }
  }

  function buildControls() {
    const all = data.records.concat(data.archive);
    const row = document.getElementById("filters");
    fill(row, FILTERS.map((filter) => {
      const select = el("select", { id: "f-" + filter.key },
        el("option", { value: "", text: "All" }),
        filter.options(all).map(([value, label]) => el("option", { value, text: label })));
      select.addEventListener("change", () => { state[filter.key] = select.value; writeState(); render(); });
      return el("label", { class: "field" }, el("span", { text: filter.label }), select);
    }));

    const sort = document.getElementById("sort");
    fill(sort, Object.entries(SORTS).map(([key, [label]]) => el("option", { value: key, text: label })));
    sort.addEventListener("change", () => { state.sort = sort.value; writeState(); render(); });

    const search = document.getElementById("search");
    let timer = null;
    search.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = search.value.trim(); writeState(); render(); }, 120);
    });

    const archive = document.getElementById("archive");
    archive.addEventListener("change", () => { state.archive = archive.checked; writeState(); render(); });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    try {
      data = await loadAll();
    } catch (error) {
      showError(document.getElementById("grid"), error);
      return;
    }
    readState();
    buildControls();
    syncControls();
    if (window.innerWidth < 700) document.getElementById("filter-box").removeAttribute("open");
    render();
    const match = location.hash.match(/^#o=(.+)$/);
    if (match) {
      const id = decodeURIComponent(match[1]);
      const rec = data.records.concat(data.archive).find((r) => r.id === id);
      if (rec) openDetail(rec, (data.meta && data.meta.flags) || []);
    }
  });
})();
