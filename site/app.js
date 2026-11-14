"use strict";
const STALE_HOURS = 3; // warn if the automation has not refreshed for this long
const $ = (id) => document.getElementById(id);
let articles = [], activeSource = "All", lastSeen = null, section = "news";

// Which tab each article kind belongs to, and the badge shown on non-news cards.
const SECTION = { news: "news", live: "live", poll: "live", video: "media", gallery: "media" };
const TABS = [["news", "News"], ["live", "Live & Polls"], ["media", "Media"]];
const BADGE = { live: "LIVE", poll: "POLL", video: "VIDEO", gallery: "PHOTOS" };
const sectionOf = (a) => SECTION[a.kind || "news"] || "news";

// Time ranges are cumulative: "This week" includes today. "Whole story" = everything stored (30 days).
const RANGES = [["today", "Today"], ["week", "This week"], ["2weeks", "Last 2 weeks"], ["all", "Whole story"]];
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

function render() {
  $("tabs").replaceChildren(...TABS.map(([key, label]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = `${label} (${articles.filter((a) => sectionOf(a) === key).length})`;
    b.setAttribute("aria-pressed", key === section);
    b.onclick = () => {
      section = key; activeSource = "All"; render();
      try { localStorage.setItem("section", key); } catch (e) {}
    };
    return b;
  }));
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
