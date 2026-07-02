async function run() {
  const params = new URLSearchParams(window.location.search);
  const status = document.getElementById("callback-status");
  const errEl = document.getElementById("callback-error");
  const back = document.getElementById("callback-back");

  const error = params.get("error");
  const code = params.get("code");
  const state = params.get("state");

  if (error) {
    status.textContent = "Authorization cancelled.";
    errEl.textContent = "You declined access on Discord.";
    errEl.classList.remove("hidden");
    back.classList.remove("hidden");
    return;
  }

  if (!code) {
    status.textContent = "Missing authorization code.";
    back.classList.remove("hidden");
    return;
  }

  try {
    status.textContent = "Finishing login…";
    await completeDiscordOAuth(code, state);
    window.location.replace("/dashboard/");
  } catch (e) {
    status.textContent = "Login failed.";
    errEl.textContent = e.message || "Could not complete Discord login.";
    errEl.classList.remove("hidden");
    back.classList.remove("hidden");
  }
}

run();
