// Small shared helpers used by every view.

// Contract rule: escape all user-supplied text before putting it in the page.
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const today = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
export const stars = (n) => "★".repeat(Math.round(n)) + "☆".repeat(5 - Math.round(n));
export const kmToMi = (km) => Math.round(km * 0.621371 * 10) / 10;
export const miToKm = (mi) => mi * 1.609344;

export const GOALS = [
  ["muscle_gain", "Muscle gain"], ["strength", "Strength"], ["fat_loss", "Fat loss"],
  ["endurance", "Endurance"], ["general_fitness", "General fitness"]
];
export const MUSCLES = ["chest", "back", "legs", "shoulders", "arms", "core"];
export const goalLabel = (v) => (GOALS.find(([k]) => k === v) || [v, v])[1];
export const options = (pairs, selected) => pairs.map(([v, t]) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(t)}</option>`).join("");

// Banner helpers: pass the banner element (<div class="banner hidden">).
export function showMessage(el, text, type = "error") { el.textContent = text; el.className = "banner " + type; }
export function clearMessage(el) { el.className = "banner hidden"; el.textContent = ""; }
export const bannerHtml = '<div class="banner hidden" id="msg" role="status"></div>';

// Wrap an async click/submit handler so a failure shows in the banner.
export function guard(msgEl, fn) {
  return async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    clearMessage(msgEl);
    try { await fn(e); } catch (err) { showMessage(msgEl, err.message || "Something went wrong"); }
  };
}
