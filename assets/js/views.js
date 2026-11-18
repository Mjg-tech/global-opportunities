/* The eleven preset views. A view is a saved question over the same records, not a separate list:
   it is opened as opportunities.html?view=<id> and combines with every filter on that page.
   Nothing here changes a record. */
(function () {
  "use strict";
  const { statusOf, known, matchesTravelFilter } = window.OI;
  const DAY = 86400000;

  const isLive = (r, now) => ["OPEN", "CLOSING SOON", "ROLLING"].includes(statusOf(r, now));
  const hasCategory = (r, ...names) => (r.category || []).some((c) => names.includes(c));
  const sinceDays = (iso, now) => {
    const t = Date.parse(iso || "");
    return Number.isNaN(t) ? Infinity : (now.getTime() - t) / DAY;
  };

  const VIEWS = [
    { id: "recommended", label: "Recommended", sort: "fit",
      blurb: "Open now, not ruled out, with the official page read at least in part and a source that is not low-confidence.",
      test: (r, ctx) => isLive(r, ctx.now) && r.eligibility_for_me !== "NOT ELIGIBLE"
        && r.verification !== "NEEDS VERIFICATION" && r.source_confidence !== "LOW" },
    { id: "fully-funded", label: "Fully funded", sort: "deadline",
      blurb: "The organiser's own wording supports the label.",
      test: (r) => r.funding_type === "Fully Funded" },
    { id: "travel", label: "International travel", sort: "travel",
      blurb: "In-person programmes abroad. Open the detail to see who pays for the flight.",
      test: (r) => matchesTravelFilter(r, "international") },
    { id: "scholarships", label: "Scholarships and fellowships", sort: "deadline",
      blurb: "Degree scholarships and fellowships.",
      test: (r) => hasCategory(r, "Scholarship", "Fellowship") },
    { id: "events", label: "Conferences and events", sort: "deadline",
      blurb: "Summits, forums and international conferences.",
      test: (r) => hasCategory(r, "Conference") },
    { id: "youth", label: "Youth and leadership", sort: "deadline",
      blurb: "Leadership programmes and anything aimed at young people.",
      test: (r) => hasCategory(r, "Leadership") || /\b(youth|young|jeunes|juventud)\b/i.test(r.title || "") },
    { id: "entrepreneurship", label: "Entrepreneurship and innovation", sort: "deadline",
      blurb: "Start-up, business and technology programmes.",
      test: (r) => hasCategory(r, "Entrepreneurship", "Technology") },
    { id: "volunteering", label: "International volunteering", sort: "deadline",
      blurb: "Volunteer schemes abroad or run by international bodies.",
      test: (r) => hasCategory(r, "Volunteering") },
    { id: "future", label: "Future opportunities", sort: "deadline",
      blurb: "Not open yet: an opening is announced, or the next cycle is expected. Estimates are labelled as estimates.",
      test: (r, ctx) => statusOf(r, ctx.now) === "UPCOMING" },
    { id: "new", label: "New discoveries", sort: "discovered",
      blurb: "Added to the database in the last 30 days. Unverified feed leads are on the New leads page.",
      test: (r, ctx) => sinceDays(r.date_discovered, ctx.now) <= 30 },
    { id: "verify", label: "Needs verification", sort: "verified",
      blurb: "Not fully verified, low-confidence, or flagged by the daily check for a changed page.",
      test: (r, ctx) => r.verification !== "VERIFIED" || r.source_confidence === "LOW" || ctx.flagged.has(r.id) }
  ];

  function context(meta) {
    return { now: new Date(), flagged: new Set(((meta && meta.flags) || []).map((f) => f.id)) };
  }

  function find(id) { return VIEWS.find((v) => v.id === id) || null; }

  function counts(records, meta) {
    const ctx = context(meta);
    return VIEWS.map((v) => ({ view: v, count: records.filter((r) => v.test(r, ctx)).length }));
  }

  Object.assign(window.OI, { VIEWS, viewContext: context, findView: find, viewCounts: counts });
})();
