"use strict";
const STALE_HOURS = 3; // warn if the automation has not refreshed for this long
const $ = (id) => document.getElementById(id);
let articles = [], activeSource = "All", lastSeen = null;

try { lastSeen = localStorage.getItem("lastSeen"); } catch (e) {}

function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}

function render() {
  const sources = ["All", ...new Set(articles.map((a) => a.source))];
  $("filters").replaceChildren(...sources.map((s) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = s;
    b.setAttribute("aria-pressed", s === activeSource);
    b.onclick = () => { activeSource = s; render(); };
    return b;
  }));
  const shown = articles.filter((a) => activeSource === "All" || a.source === activeSource);
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
