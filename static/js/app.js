// ── Theme — apply immediately via inline script in <head>, here just the toggle
const html = document.documentElement;

function applyTheme(dark) {
  html.classList.toggle('dark', dark);
  localStorage.setItem('theme', dark ? 'dark' : 'light');
  const icon  = dark ? '☀️' : '🌙';
  const label = dark ? 'Light' : 'Dark';
  const mob  = document.getElementById('themeToggleMob');
  const desk = document.getElementById('themeToggleDesk');
  const lbl  = document.getElementById('themeLabel');
  if (mob)  mob.textContent  = icon;
  if (desk) desk.querySelector('span') ? null : null;
  if (lbl)  lbl.textContent  = label;
  if (desk) { desk.childNodes[0].textContent = icon + ' '; }
}

// Sync button state on load
const isDark = html.classList.contains('dark');
document.addEventListener('DOMContentLoaded', () => applyTheme(isDark));

document.getElementById('themeToggleMob')  ?.addEventListener('click', () => applyTheme(!html.classList.contains('dark')));
document.getElementById('themeToggleDesk') ?.addEventListener('click', () => applyTheme(!html.classList.contains('dark')));

// ── Auto-dismiss alerts ──
document.querySelectorAll('.alert-msg').forEach(el => {
  setTimeout(() => { el.style.transition = 'opacity .5s'; el.style.opacity = '0'; }, 3500);
  setTimeout(() => el.remove(), 4000);
});
