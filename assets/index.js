(function () {
  const dictionary = {};
  const initialDocumentLanguage = (document.documentElement.getAttribute("lang") || "en").toLowerCase().startsWith("hu")
    ? "hu"
    : "en";
  const GA_MEASUREMENT_ID = (document.querySelector('meta[name="ga4-measurement-id"]')?.content || "").trim();
  const isAnalyticsEnabled = /^G-[A-Z0-9]+$/i.test(GA_MEASUREMENT_ID);
  const CONSENT_STORAGE_KEY = "voyager_docs_consent_v1";
  const CONSENT_CHANGE_EVENT = "voyagerdocsconsentchange";
  const TRACK_EVENT_SUFFIX = "_web";
  let gaInitialized = false;
  let gaScriptLoading = null;
  let consentModeApplied = true;
  let currentLanguage = "en";
  let hasTrackedEngagedRead = false;
  const trackedScrollBuckets = new Set();
  const viewedSections = new Set();
  const viewedImages = new Set();
  const pageStartTime = Date.now();

  const flagSvgs = {
    en: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#012169"></rect><rect x="10" width="4" height="16" fill="#ffffff"></rect><rect y="6" width="24" height="4" fill="#ffffff"></rect><rect x="10.8" width="2.4" height="16" fill="#c8102e"></rect><rect y="6.8" width="24" height="2.4" fill="#c8102e"></rect></svg>',
    hu: '<svg class="flag-icon" viewBox="0 0 24 16" width="20" height="14" focusable="false" aria-hidden="true"><rect width="24" height="16" fill="#ce2939"></rect><rect y="5.333" width="24" height="5.333" fill="#ffffff"></rect><rect y="10.666" width="24" height="5.334" fill="#477050"></rect></svg>'
  };

  injectSharedUI(flagSvgs);

  function injectSharedUI(flags) {
    const main = document.querySelector("main.container");
    if (main && !main.querySelector(".site-header")) {
      main.insertAdjacentHTML("afterbegin", `
        <header class="site-header">
          <a class="brand" href="./index.html" data-i18n="brandLabel">Voyager Maps</a>
          <nav class="lang-switch" aria-label="Language switcher" data-i18n-aria="langSwitcherAria">
            <button type="button" class="lang-trigger" id="lang-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="lang-menu">
              <span class="lang-globe" id="lang-flag" aria-hidden="true">${flags.en}</span>
              <span class="lang-current" id="lang-current">EN</span>
              <span class="lang-caret" aria-hidden="true">&#x25BE;</span>
            </button>
            <ul class="lang-menu" id="lang-menu" role="listbox" aria-label="Language options" data-i18n-aria-label="langOptionsAria" hidden>
              <li>
                <button type="button" class="lang-option" data-lang="en" role="option" aria-selected="true">
                  <span aria-hidden="true">${flags.en}</span>
                  <span>English (EN)</span>
                  <span class="check" aria-hidden="true">&#x2713;</span>
                </button>
              </li>
              <li>
                <button type="button" class="lang-option" data-lang="hu" role="option" aria-selected="false">
                  <span aria-hidden="true">${flags.hu}</span>
                  <span>Magyar (HU)</span>
                  <span class="check" aria-hidden="true">&#x2713;</span>
                </button>
              </li>
            </ul>
          </nav>
        </header>
      `);
    }

    if (document.getElementById("consent-banner")) return;
    document.body.insertAdjacentHTML("beforeend", `
      <div class="consent-backdrop" id="consent-backdrop" aria-hidden="true" hidden></div>
      <section class="consent-banner" id="consent-banner" aria-labelledby="consent-title" aria-describedby="consent-description" hidden>
        <div class="consent-panel">
          <div class="consent-summary">
            <div class="consent-copy">
              <p class="consent-eyebrow" data-i18n="consentEyebrow">Privacy settings</p>
              <h2 class="consent-title" id="consent-title" data-i18n="consentTitle">Your privacy choices</h2>
              <p class="consent-description" id="consent-description" data-i18n="consentDescription">We only use optional analytics after your consent, for statistical purposes, to improve and refine Voyager Maps.</p>
            </div>
            <div class="consent-actions">
              <button type="button" class="consent-btn consent-btn-link" id="consent-reject" data-i18n="consentReject">Use necessary only</button>
              <button type="button" class="consent-btn consent-btn-secondary" id="consent-customize" data-i18n="consentCustomize" aria-expanded="false" aria-controls="consent-preferences">Customize</button>
              <button type="button" class="consent-btn consent-btn-primary" id="consent-accept" data-i18n="consentAccept">Accept analytics</button>
            </div>
          </div>
          <div class="consent-preferences" id="consent-preferences" hidden>
            <div class="consent-types">
              <div class="consent-type consent-type-static">
                <div>
                  <span class="consent-type-label" data-i18n="consentNecessaryLabel">Necessary</span>
                  <p class="consent-type-description" data-i18n="consentNecessaryDescription">Required for language selection, consent state, and core page functionality.</p>
                </div>
                <span class="consent-type-badge" data-i18n="consentNecessaryValue">Always active</span>
              </div>
              <label class="consent-type consent-type-toggle" for="consent-statistics-toggle">
                <div>
                  <span class="consent-type-label" data-i18n="consentStatisticsLabel">Statistics</span>
                  <p class="consent-type-description" data-i18n="consentStatisticsValue">Google Analytics 4 for visits and interaction events</p>
                </div>
                <span class="consent-switch-wrap">
                  <input type="checkbox" class="consent-switch-input" id="consent-statistics-toggle" />
                  <span class="consent-switch" aria-hidden="true"></span>
                </span>
              </label>
            </div>
            <div class="consent-preferences-actions">
              <p class="consent-note" data-i18n="consentNote">You can change this decision any time with the privacy button.</p>
              <button type="button" class="consent-btn consent-btn-secondary consent-save" id="consent-save" data-i18n="consentSave">Save preferences</button>
            </div>
          </div>
        </div>
      </section>
      <button type="button" class="consent-manage" id="consent-manage" data-i18n="consentManage" aria-haspopup="dialog">Privacy settings</button>
    `);
  }

  function ensureDataLayer() {
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function gtag() {
      dataLayer.push(arguments);
    };
  }

  function loadGtagScript(measurementId) {
    if (!isAnalyticsEnabled || !measurementId) return Promise.resolve(false);
    if (document.querySelector('script[data-ga-loader="true"]')) return Promise.resolve(true);
    if (gaScriptLoading) return gaScriptLoading;

    gaScriptLoading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
      script.dataset.gaLoader = "true";
      script.onload = () => resolve(true);
      script.onerror = () => {
        gaScriptLoading = null;
        reject(new Error("Failed to load Google Analytics"));
      };
      document.head.appendChild(script);
    });

    return gaScriptLoading;
  }

  function applyConsentMode() {
    if (!isAnalyticsEnabled) return;
    ensureDataLayer();

    window.gtag("consent", "default", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
      wait_for_update: 500
    });

    consentModeApplied = true;

    if (hasStatisticsConsent()) {
      window.gtag("consent", "update", {
        analytics_storage: "granted"
      });
    }
  }

  function updateConsentMode(statisticsEnabled) {
    if (!isAnalyticsEnabled) return;
    ensureDataLayer();
    if (!consentModeApplied) applyConsentMode();

    window.gtag("consent", "update", {
      analytics_storage: statisticsEnabled ? "granted" : "denied"
    });
  }

  function readConsentState() {
    try {
      const raw = localStorage.getItem(CONSENT_STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return {
        statistics: parsed.statistics === true,
        updated_at: typeof parsed.updated_at === "string" ? parsed.updated_at : ""
      };
    } catch {
      return null;
    }
  }

  function dispatchConsentChange(consent) {
    window.dispatchEvent(
      new CustomEvent(CONSENT_CHANGE_EVENT, {
        detail: consent
      })
    );
  }

  function writeConsentState(statistics) {
    const consent = {
      statistics: statistics === true,
      updated_at: new Date().toISOString()
    };

    try {
      localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify(consent));
    } catch {
      dispatchConsentChange(consent);
      return consent;
    }

    dispatchConsentChange(consent);
    return consent;
  }

  function hasStoredConsentDecision() {
    try {
      return localStorage.getItem(CONSENT_STORAGE_KEY) !== null;
    } catch {
      return !!readConsentState();
    }
  }

  function hasStatisticsConsent() {
    const consent = readConsentState();
    return !!(consent && consent.statistics);
  }

  async function initAnalytics() {
    if (!isAnalyticsEnabled || gaInitialized || !hasStatisticsConsent()) return;

    ensureDataLayer();

    try {
      await loadGtagScript(GA_MEASUREMENT_ID);
    } catch {
      return;
    }

    applyConsentMode();

    window.gtag("js", new Date());
    window.gtag("config", GA_MEASUREMENT_ID, {
      send_page_view: false,
      anonymize_ip: true,
      debug_mode: /localhost|127\.0\.0\.1/.test(window.location.hostname)
    });

    window.gtag("event", "page_view", {
      page_title: document.title,
      page_location: window.location.href,
      page_path: window.location.pathname + window.location.search
    });

    gaInitialized = true;
  }

  function trackEvent(eventName, params = {}) {
    if (!window.gtag || !isAnalyticsEnabled || !gaInitialized || !hasStatisticsConsent()) return;

    window.gtag("event", `${eventName}${TRACK_EVENT_SUFFIX}`, {
      page_type: "documentation_landing",
      page_language: document.documentElement.lang || currentLanguage || "en",
      ...params
    });
  }

  function trackCtaClick(anchor) {
    if (!anchor) return;

    const href = anchor.getAttribute("href") || "";
    let destinationHost = "";

    try {
      destinationHost = new URL(href, window.location.href).host;
    } catch (_) {
      destinationHost = "";
    }

    trackEvent("cta_click", {
      cta_type: anchor.dataset.ctaType || "unknown",
      cta_position: anchor.dataset.ctaPosition || "unknown",
      link_url: href,
      link_domain: destinationHost,
      outbound: true
    });
  }

  function trackLegalClick(anchor) {
    if (!anchor) return;

    const href = anchor.getAttribute("href") || "";
    trackEvent("legal_link_click", {
      legal_type: anchor.dataset.legalType || "unknown",
      link_url: href,
      outbound: false
    });
  }

  function getScrollPercent() {
    const doc = document.documentElement;
    const scrollable = doc.scrollHeight - window.innerHeight;
    if (scrollable <= 0) return 100;
    return Math.min(100, Math.round((window.scrollY / scrollable) * 100));
  }

  function trackScrollDepth() {
    const currentPercent = getScrollPercent();
    const buckets = [25, 50, 75, 90];

    buckets.forEach((bucket) => {
      if (currentPercent >= bucket && !trackedScrollBuckets.has(bucket)) {
        trackedScrollBuckets.add(bucket);
        trackEvent("scroll_depth", {
          scroll_percent_bucket: bucket
        });
      }
    });
  }

  function maybeTrackEngagedRead() {
    if (hasTrackedEngagedRead) return;

    const secondsOnPage = Math.round((Date.now() - pageStartTime) / 1000);
    const currentPercent = getScrollPercent();

    if (secondsOnPage >= 30 && currentPercent >= 50) {
      hasTrackedEngagedRead = true;
      trackEvent("engaged_read", {
        seconds_on_page: secondsOnPage,
        scroll_percent_bucket: 50,
        engagement_tier: "high"
      });
    }
  }

  function setupSectionObserver() {
    const sections = document.querySelectorAll("[data-track-section]");
    if (!sections.length || typeof IntersectionObserver !== "function") return;

    const sectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.45) return;
          const sectionId = entry.target.getAttribute("data-track-section");
          if (!sectionId || viewedSections.has(sectionId)) return;

          viewedSections.add(sectionId);
          trackEvent("section_view", {
            section_id: sectionId
          });
        });
      },
      { threshold: [0.45] }
    );

    sections.forEach((section) => sectionObserver.observe(section));
  }

  function setupImageObserver() {
    const images = document.querySelectorAll("[data-track-image]");
    if (!images.length || typeof IntersectionObserver !== "function") return;

    const imageObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.4) return;
          const imageName = entry.target.getAttribute("data-track-image");
          if (!imageName || viewedImages.has(imageName)) return;

          viewedImages.add(imageName);
          trackEvent("image_preview_view", {
            image_name: imageName
          });
        });
      },
      { threshold: [0.4] }
    );

    images.forEach((image) => imageObserver.observe(image));
  }

  function setupClickTracking() {
    document.querySelectorAll('[data-track="cta"]').forEach((anchor) => {
      anchor.addEventListener("click", () => trackCtaClick(anchor));
    });

    document.querySelectorAll('[data-track="legal"]').forEach((anchor) => {
      anchor.addEventListener("click", () => trackLegalClick(anchor));
    });
  }

  function setupEngagementTracking() {
    const onScroll = () => {
      trackScrollDepth();
      maybeTrackEngagedRead();
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    setTimeout(maybeTrackEngagedRead, 30000);
    onScroll();
  }

  function applyLanguage(lang, source = "system") {
    const previousLanguage = currentLanguage;
    const selected = dictionary[lang] || dictionary.en;
    if (!selected) return;

    document.documentElement.lang = selected.htmlLang || lang;
    document.title = selected.pageTitle || document.title;

    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const key = node.getAttribute("data-i18n");
      if (selected[key]) node.textContent = selected[key];
    });

    document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
      const key = node.getAttribute("data-i18n-aria");
      if (selected[key]) node.setAttribute("aria-label", selected[key]);
    });

    document.querySelectorAll(".lang-option").forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.lang === lang));
    });

    document.getElementById("lang-current").textContent = lang.toUpperCase();
    document.getElementById("lang-flag").innerHTML = flagSvgs[lang] || flagSvgs.en;

    currentLanguage = lang;

    if (source === "user" && previousLanguage !== lang) {
      trackEvent("language_change", {
        previous_language: previousLanguage,
        selected_language: lang
      });
    }
  }

  const langTrigger = document.getElementById("lang-trigger");
  const langMenu = document.getElementById("lang-menu");
  const consentBanner = document.getElementById("consent-banner");
  const consentManage = document.getElementById("consent-manage");
  const consentBackdrop = document.getElementById("consent-backdrop");
  const consentAccept = document.getElementById("consent-accept");
  const consentReject = document.getElementById("consent-reject");
  const consentCustomize = document.getElementById("consent-customize");
  const consentPreferences = document.getElementById("consent-preferences");
  const consentSave = document.getElementById("consent-save");
  const consentStatisticsToggle = document.getElementById("consent-statistics-toggle");

  function toggleConsentPreferences(forceState) {
    const isOpen = typeof forceState === "boolean" ? forceState : consentPreferences.hidden;
    consentPreferences.hidden = !isOpen;
    consentCustomize.setAttribute("aria-expanded", String(isOpen));
  }

  function toggleConsentBanner(forceState) {
    const isOpen = typeof forceState === "boolean" ? forceState : consentBanner.hidden;
    consentBanner.hidden = !isOpen;
    consentBackdrop.hidden = !isOpen;
    document.body.classList.toggle("consent-active", isOpen);
    consentManage.setAttribute("aria-expanded", String(isOpen));
    if (!isOpen) toggleConsentPreferences(false);
  }

  function syncConsentUi() {
    const hasDecision = hasStoredConsentDecision();
    consentStatisticsToggle.checked = hasStatisticsConsent();
    toggleConsentBanner(!hasDecision);
    if (hasDecision) toggleConsentPreferences(false);
  }

  function setStatisticsConsent(enabled) {
    const hadStatisticsConsent = hasStatisticsConsent();
    const consent = writeConsentState(enabled);
    updateConsentMode(consent.statistics);
    if (!enabled) gaInitialized = false;
    toggleConsentBanner(false);
    if (consent.statistics) {
      initAnalytics();
      setTimeout(() => {
        trackEvent("consent_update", {
          statistics: "granted"
        });
      }, 0);
    } else if (hadStatisticsConsent) {
      trackEvent("consent_update", {
        statistics: "denied"
      });
    }
  }

  function toggleMenu(forceState) {
    const wasOpen = !langMenu.hidden;
    const open = typeof forceState === "boolean" ? forceState : langMenu.hidden;
    langMenu.hidden = !open;
    langTrigger.setAttribute("aria-expanded", String(open));

    if (open && !wasOpen) {
      trackEvent("language_menu_open", {
        menu_id: "language"
      });
    }
  }

  langTrigger.addEventListener("click", () => toggleMenu());

  document.querySelectorAll(".lang-option").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyLanguage(btn.dataset.lang, "user");
      toggleMenu(false);
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".lang-switch")) toggleMenu(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") toggleMenu(false);
    if (event.key === "Escape") toggleConsentBanner(false);
  });

  consentManage.addEventListener("click", () => {
    toggleConsentBanner();
  });

  consentCustomize.addEventListener("click", () => {
    toggleConsentPreferences();
  });

  consentAccept.addEventListener("click", () => {
    setStatisticsConsent(true);
  });

  consentReject.addEventListener("click", () => {
    setStatisticsConsent(false);
  });

  consentSave.addEventListener("click", () => {
    setStatisticsConsent(consentStatisticsToggle.checked);
  });

  window.addEventListener(CONSENT_CHANGE_EVENT, () => {
    if (hasStatisticsConsent()) initAnalytics();
  });

  function initLanguages() {
    dictionary.en = window.voyagerLocales?.en;
    dictionary.hu = window.voyagerLocales?.hu;
    applyConsentMode();
    applyLanguage(initialDocumentLanguage, "init");
    syncConsentUi();
    initAnalytics();
    trackEvent("landing_view", {
      engagement_point: "initial_load"
    });
  }

  initLanguages();
  setupClickTracking();
  setupSectionObserver();
  setupImageObserver();
  setupEngagementTracking();
})();
