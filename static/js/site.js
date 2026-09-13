const toggle = document.querySelector("[data-menu-toggle]");
const nav = document.getElementById("mainNav");

const tokenField = document.querySelector("[data-account-token]");
if (tokenField) {
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
  if (token && token.length <= 512) tokenField.value = token;
  if (window.location.hash) history.replaceState(null, "", window.location.pathname);
  if (tokenField.value) {
    tokenField.type = "hidden";
    document.querySelector("[data-account-token-label]").hidden = true;
  }
}

if (toggle && nav) {
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
}

document.querySelectorAll("[data-platform-toggle]").forEach((input) => {
  const row = document.querySelector(`[data-platform-row="${input.dataset.platformToggle}"]`);
  if (!row) return;
  const sync = () => {
    row.hidden = !input.checked;
    row.querySelectorAll("input").forEach((field) => {
      field.disabled = !input.checked;
    });
  };
  input.addEventListener("change", sync);
  sync();
});

document.querySelectorAll("[data-profile-photo]").forEach((image) => {
  image.addEventListener("error", () => image.classList.add("is-broken"));
});

document.querySelectorAll("[data-copy-value]").forEach((button) => {
  button.addEventListener("click", async () => {
    const status = document.querySelector("[data-copy-status]");
    try {
      await navigator.clipboard.writeText(button.dataset.copyValue);
      if (status) status.textContent = `${button.dataset.copyLabel} copied.`;
    } catch {
      if (status) status.textContent = "Copy unavailable. Transfer instructions are available to download.";
    }
  });
});
