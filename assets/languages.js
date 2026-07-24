/**
 * Single source of truth for the site's languages.
 *
 * Every language has its own URL (/ for English, /<code>/ for the rest), so the
 * switcher navigates instead of swapping text in place. Add a language here and
 * the switcher, the flag and the label all follow; the pages themselves are
 * produced by tools/build-pages.py from the matching locales/<code>.js.
 */
window.voyagerLanguages = [
  // Union Jack. The saltires are drawn as strokes rather than clipped polygons
  // so the markup carries no ids — the same string is injected twice per page
  // (trigger and menu), and duplicate ids would be invalid.
  { code: "en", label: "English", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#012169"/><path d="M0,0 24,16 M24,0 0,16" stroke="#fff" stroke-width="3.2"/><path d="M0,0 24,16 M24,0 0,16" stroke="#c8102e" stroke-width="1.8"/><path d="M12,0 V16 M0,8 H24" stroke="#fff" stroke-width="5.4"/><path d="M12,0 V16 M0,8 H24" stroke="#c8102e" stroke-width="3.2"/></svg>' },
  { code: "de", label: "Deutsch", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="5.333" fill="#000"/><rect y="5.333" width="24" height="5.333" fill="#dd0000"/><rect y="10.666" width="24" height="5.334" fill="#ffce00"/></svg>' },
  { code: "fr", label: "Français", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="8" height="16" fill="#002395"/><rect x="8" width="8" height="16" fill="#fff"/><rect x="16" width="8" height="16" fill="#ed2939"/></svg>' },
  { code: "es", label: "Español", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#aa151b"/><rect y="4" width="24" height="8" fill="#f1bf00"/></svg>' },
  { code: "it", label: "Italiano", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="8" height="16" fill="#008c45"/><rect x="8" width="8" height="16" fill="#fff"/><rect x="16" width="8" height="16" fill="#cd212a"/></svg>' },
  { code: "pt", label: "Português", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#009b3a"/><path d="M12 2.2 22 8l-10 5.8L2 8z" fill="#fedf00"/><circle cx="12" cy="8" r="3.4" fill="#002776"/><path d="M8.9 6.9a6 6 0 0 1 6.2 2.3" stroke="#fff" stroke-width="1" fill="none"/></svg>' },
  { code: "nl", label: "Nederlands", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="5.333" fill="#ae1c28"/><rect y="5.333" width="24" height="5.333" fill="#fff"/><rect y="10.666" width="24" height="5.334" fill="#21468b"/></svg>' },
  { code: "pl", label: "Polski", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="8" fill="#fff"/><rect y="8" width="24" height="8" fill="#dc143c"/></svg>' },
  { code: "hu", label: "Magyar", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#ce2939"/><rect y="5.333" width="24" height="5.333" fill="#fff"/><rect y="10.666" width="24" height="5.334" fill="#477050"/></svg>' },
  { code: "ja", label: "日本語", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#fff"/><circle cx="12" cy="8" r="4.8" fill="#bc002d"/></svg>' },
  { code: "zh", label: "中文", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#de2910"/><path d="m5 2.6 1 3.1h3.2L6.6 7.6l1 3.1L5 8.8 2.4 10.7l1-3.1L.8 5.7H4z" fill="#ffde00" transform="scale(.62) translate(4 2)"/><circle cx="9.2" cy="2.6" r=".9" fill="#ffde00"/><circle cx="11" cy="4.4" r=".9" fill="#ffde00"/><circle cx="11" cy="6.9" r=".9" fill="#ffde00"/><circle cx="9.2" cy="8.6" r=".9" fill="#ffde00"/></svg>' },
  { code: "ko", label: "한국어", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#fff"/><path d="M12 4.4a3.6 3.6 0 0 1 0 7.2 3.6 3.6 0 0 0 0-7.2z" fill="#003478"/><path d="M12 4.4a3.6 3.6 0 0 0 0 7.2 3.6 3.6 0 0 1 0-7.2z" fill="#cd2e3a"/><g stroke="#000" stroke-width=".7"><path d="M3.6 3.6 6 6M4.8 2.6 7.2 5"/><path d="M17 11 19.4 13.4M18.2 10 20.6 12.4"/></g></svg>' },
  { code: "hi", label: "हिन्दी", flag: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="5.333" fill="#ff9933"/><rect y="5.333" width="24" height="5.333" fill="#fff"/><rect y="10.666" width="24" height="5.334" fill="#138808"/><circle cx="12" cy="8" r="2.1" fill="none" stroke="#000080" stroke-width=".6"/><circle cx="12" cy="8" r=".5" fill="#000080"/></svg>' }
];
