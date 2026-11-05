import { api, setToken, setUser } from "../api.js";
import { $, bannerHtml, showMessage, guard } from "../ui.js";

const logo = '<a class="logo" href="#/login"><img src="assets/logo-wordmark.png" alt="Pump Check"></a>';

async function finish(res, msg) {
  if (res.confirmation_required) { // backend: confirm the email first, then log in
    showMessage(msg, res.message || "Check your email to confirm your account, then log in.", "ok");
    return;
  }
  setToken(res.access_token);
  setUser(res.user);
  location.hash = "#/gyms";
}

export function login(root) {
  root.innerHTML = `
    <div class="auth-wrap"><div class="auth-card">
      ${logo}
      <form class="card" id="form" novalidate>
        <h2>Log in</h2>
        ${bannerHtml}
        <div class="field"><label for="email">Email</label><input id="email" type="email" autocomplete="email"></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="current-password"></div>
        <button class="full" type="submit">Log in</button>
        <p class="hint" style="text-align:center">No account? <a href="#/register">Sign up</a></p>
      </form>
    </div></div>`;
  const msg = $("#msg", root);
  $("#form", root).addEventListener("submit", guard(msg, async () => {
    const email = $("#email", root).value.trim(), password = $("#password", root).value;
    if (!email || !password) return showMessage(msg, "Enter your email and password");
    await finish(await api.login(email, password), msg); // on failure the typed values stay in the form
  }));
}

export function register(root) {
  root.innerHTML = `
    <div class="auth-wrap"><div class="auth-card">
      ${logo}
      <form class="card" id="form" novalidate>
        <h2>Create account</h2>
        ${bannerHtml}
        <div class="field"><label for="username">Username</label><input id="username" autocomplete="username"></div>
        <div class="field"><label for="email">Email</label><input id="email" type="email" autocomplete="email"></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="new-password"><p class="hint">At least 8 characters.</p></div>
        <button class="full" type="submit">Sign up</button>
        <p class="hint" style="text-align:center">Already have an account? <a href="#/login">Log in</a></p>
      </form>
    </div></div>`;
  const msg = $("#msg", root);
  $("#form", root).addEventListener("submit", guard(msg, async () => {
    const username = $("#username", root).value.trim(), email = $("#email", root).value.trim(), password = $("#password", root).value;
    if (!username || !email) return showMessage(msg, "Fill in all fields");
    if (password.length < 8) return showMessage(msg, "Password too weak");
    await finish(await api.register(email, password, username), msg);
  }));
}
