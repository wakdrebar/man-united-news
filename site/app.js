"use strict";
const STALE_HOURS = 3; // warn if the automation has not refreshed for this long
const $ = (id) => document.getElementById(id);
let articles = [], stories = [], activeSource = "All", lastSeen = null, section = "news";

// Which tab each article kind belongs to, and the badge shown on non-news cards.
const SECTION = { news: "news", live: "live", poll: "live", video: "media", gallery: "media" };
const TABS = [["news", "News"], ["story", "Whole story"], ["live", "Live & Polls"], ["media", "Media"]];
const BADGE = { live: "LIVE", poll: "POLL", video: "VIDEO", gallery: "PHOTOS" };
const sectionOf = (a) => SECTION[a.kind || "news"] || "news";

// Time ranges are cumulative: "This week" includes today. "All time" = everything stored (30 days).
const RANGES = [["today", "Today"], ["week", "This week"], ["2weeks", "Last 2 weeks"], ["all", "All time"]];
let range = "week";

function inRange(a, key) {
  if (key === "all") return true;
  if (key === "today") { const d = new Date(); d.setHours(0, 0, 0, 0); return new Date(a.published) >= d; }
  const days = key === "week" ? 7 : 14;
  return Date.now() - new Date(a.published) <= days * 86400000;
}

try {
  section = localStorage.getItem("section") || "news";
  range = localStorage.getItem("range") || "week";
} catch (e) {}

try { lastSeen = localStorage.getItem("lastSeen"); } catch (e) {}

function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}

// ---- Whole story: AI-written comparison of how different sources covered one event ----
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}

function block(title, node) {
  const d = document.createElement("details");
  d.append(el("summary", title), node);
  return d;
}

function renderStory(s) {
  const li = document.createElement("li");
  const card = el("article", null, "story");
  card.append(el("h2", s.headline));
  const depth = Object.values(s.read_depth || {});
  const full = depth.filter((d) => d === "full").length;
  card.append(el("div", `${(s.sources || []).join(", ")} · updated ${ago(s.analysed || s.last)}` +
    (depth.length ? ` · full text read for ${full} of ${depth.length}` : ""), "info"));
  card.append(el("p", s.whole_story, "whole"));

  if ((s.agree || []).length) {
    const ul = el("ul"); s.agree.forEach((t) => ul.append(el("li", t)));
    card.append(block("Where they agree", ul));
  }
  if ((s.differ || []).length) {
    const box = el("div");
    s.differ.forEach((d) => {
      box.append(el("p", d.point, "pt"));
      const ul = el("ul");
      (d.views || []).forEach((v) => { const li2 = el("li"); li2.append(el("b", v.source + ": "), v.says); ul.append(li2); });
      box.append(ul);
    });
    card.append(block("Where they differ", box));
  }
  if ((s.lean || []).length) {
    const ul = el("ul");
    s.lean.forEach((l) => { const li2 = el("li"); li2.append(el("b", l.source + ": "), l.note); ul.append(li2); });
    card.append(block("How each source framed it", ul));
  }
  const links = el("ul");
  (s.articles || []).forEach((a) => {
    const href = safeUrl(a.url); if (!href) return;
    const li2 = el("li"), link = el("a", `${a.source}: ${a.title}`);
    link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer";
    li2.append(link); links.append(li2);
  });
  card.append(block("Read the originals", links));
  if (s.caveat) card.append(el("p", "Note: " + s.caveat, "caveat"));
  card.append(el("p", "Written by AI from the linked articles. It can make mistakes, so check the originals for anything important.", "ai"));
  li.append(card);
  return li;
}

function renderStories() {
  $("filters").hidden = true; $("ranges").hidden = true;
  $("empty").textContent = "No comparisons yet. They appear here once several sources cover the same big story.";
  $("empty").hidden = stories.length > 0;
  $("list").replaceChildren(...stories.map(renderStory));
}

function render() {
  $("tabs").replaceChildren(...TABS.map(([key, label]) => {
    const b = document.createElement("button");
    b.type = "button";
    const count = key === "story" ? stories.length : articles.filter((a) => sectionOf(a) === key).length;
    b.textContent = `${label} (${count})`;
    b.setAttribute("aria-pressed", key === section);
    b.onclick = () => {
      section = key; activeSource = "All"; render();
      try { localStorage.setItem("section", key); } catch (e) {}
    };
    return b;
  }));
  if (section === "story") return renderStories();
  $("filters").hidden = false; $("ranges").hidden = false;
  $("empty").textContent = "Nothing in this range. Try a wider one.";
  const inSection = articles.filter((a) => sectionOf(a) === section);
  if (activeSource !== "All" && !inSection.some((a) => a.source === activeSource)) activeSource = "All";
  const sources = ["All", ...new Set(inSection.map((a) => a.source))];
  $("filters").replaceChildren(...sources.map((s) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = s;
    b.setAttribute("aria-pressed", s === activeSource);
    b.onclick = () => { activeSource = s; render(); };
    return b;
  }));
  $("ranges").replaceChildren(...RANGES.map(([key, label]) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "range";
    const n = document.createElement("span"); n.textContent = inSection.filter((a) => inRange(a, key)).length;
    b.append(label + " ", n);
    b.setAttribute("aria-pressed", key === range);
    b.onclick = () => {
      range = key; render();
      try { localStorage.setItem("range", key); } catch (e) {}
    };
    return b;
  }));
  const shown = inSection.filter((a) => inRange(a, range) && (activeSource === "All" || a.source === activeSource));
  $("empty").hidden = shown.length > 0;
  $("list").replaceChildren(...shown.map((a) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.className = "card" + (lastSeen && a.published > lastSeen ? " new" : "");
    link.href = a.url; link.target = "_blank"; link.rel = "noopener noreferrer";
    if (a.image) {
      const img = document.createElement("img");
      img.src = a.image; img.alt = ""; img.loading = "lazy";
      img.onerror = () => img.remove();
      link.append(img);
    }
    const box = document.createElement("div");
    const h = document.createElement("h2"); h.textContent = a.title;
    const info = document.createElement("div"); info.className = "info";
    const src = document.createElement("b"); src.textContent = a.source;
    info.append(src, " · " + ago(a.published));
    if (BADGE[a.kind]) {
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = BADGE[a.kind];
      info.append(" ", tag);
    }
    box.append(h, info);
    if (a.summary) {
      const p = document.createElement("p"); p.className = "sum"; p.textContent = a.summary;
      box.append(p);
    }
    link.append(box); li.append(link);
    return li;
  }));
}

async function load(manual) {
  const btn = $("refresh");
  btn.disabled = true;
  try {
    const res = await fetch("data/news.json?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    articles = data.articles;
    try { // optional file; absent until the first analysis is written
      const sr = await fetch("data/stories.json?t=" + Date.now(), { cache: "no-store" });
      stories = sr.ok ? (await sr.json()).stories || [] : [];
      stories.sort((a, b) => String(b.last).localeCompare(String(a.last)));
    } catch (e) { stories = []; }
    const hrs = (Date.now() - new Date(data.updated)) / 3600000;
    $("meta").textContent = `${articles.length} articles · updated ${ago(data.updated)}`;
    $("warn").hidden = hrs < STALE_HOURS;
    $("warn").textContent = `Source data is ${Math.floor(hrs)}h old; the automatic update may be failing.`;
    render();
    try { localStorage.setItem("lastSeen", data.articles[0]?.published || ""); } catch (e) {}
  } catch (err) {
    $("meta").textContent = articles.length
      ? "Offline or fetch failed; showing last loaded news."
      : "Could not load news: " + err.message;
    if (manual) $("warn").hidden = true;
  } finally {
    btn.disabled = false;
  }
}

$("refresh").onclick = () => load(true);
document.addEventListener("visibilitychange", () => { if (!document.hidden) load(false); });
setInterval(() => load(false), 10 * 60 * 1000);
load(false);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
