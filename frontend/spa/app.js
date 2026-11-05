// App shell: hash router + header. Every page of the site lives in index.html.
import { api, getToken, getUser, setUser, clearSession } from "./api.js";
import { esc } from "./ui.js";
import { login, register } from "./views/auth.js";
import { gyms } from "./views/gyms.js";
import { gym } from "./views/gym.js";
import { workouts } from "./views/workouts.js";
import { plans } from "./views/plans.js";
import { calories } from "./views/calories.js";
import { community } from "./views/community.js";

const routes = [
  { re: /^#\/login$/, view: login, pub: true },
  { re: /^#\/register$/, view: register, pub: true },
  { re: /^#\/gyms$/, view: gyms, nav: "gyms" },
  { re: /^#\/gyms\/([^/]+)$/, view: gym, nav: "gyms", params: (m) => ({ id: decodeURIComponent(m[1]) }) },
  { re: /^#\/workouts$/, view: workouts, nav: "workouts" },
  { re: /^#\/plans$/, view: plans, nav: "plans" },
  { re: /^#\/calories$/, view: calories, nav: "calories" },
  { re: /^#\/community$/, view: community, nav: "community" }
];

const header = document.getElementById("site-header");
const main = document.getElementById("app");

function initials(user) {
  const name = (user?.username || user?.email || "").trim();
  if (!name) return "";
  const words = name.split(/[^A-Za-z0-9]+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
}

function paintHeader(activeNav) {
  const authed = !!getToken();
  header.classList.toggle("hidden", !authed);
  if (!authed) return;
  document.getElementById("initials").textContent = initials(getUser());
  header.querySelectorAll(".main-nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === activeNav));
}

async function render() {
  const hash = location.hash || "#/";
  let route, match;
  for (const r of routes) { match = hash.match(r.re); if (match) { route = r; break; } }

  // Guards: signed-out users go to login; signed-in users skip the auth pages.
  if (!route) { location.hash = getToken() ? "#/gyms" : "#/login"; return; }
  if (!route.pub && !getToken()) { location.hash = "#/login"; return; }
  if (route.pub && getToken()) { location.hash = "#/gyms"; return; }

  paintHeader(route.nav);
  const root = document.createElement("div"); // a fresh node per navigation, so a slow old page can't draw over the new one
  main.replaceChildren(root);
  window.scrollTo(0, 0);
  try {
    await route.view(root, route.params ? route.params(match) : {});
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="banner error">${esc(err.message || "Something went wrong")}</div></div>`;
  }
  document.title = (route.nav ? route.nav[0].toUpperCase() + route.nav.slice(1) : "Log in") + " – Pump Check";
}

document.getElementById("logout").addEventListener("click", async () => {
  try { await api.logout(); } catch { /* the session is cleared either way */ }
  clearSession();
  location.hash = "#/login";
});

window.addEventListener("hashchange", render);

// Pages that need the full user (e.g. a reload with only a token saved) fetch it once.
(async () => {
  if (getToken() && !getUser()) { try { setUser(await api.me()); } catch { /* handled by request() on 401 */ } }
  render();
})();
