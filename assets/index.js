(function () {
  const dictionary = {};
  const GA_MEASUREMENT_ID = (document.querySelector('meta[name="ga4-measurement-id"]')?.content || "").trim();
  const isAnalyticsEnabled = /^G-[A-Z0-9]+$/i.test(GA_MEASUREMENT_ID);
  const CONSENT_STORAGE_KEY = "voyager_docs_consent_v1";
  // App Store Connect → Analytics → Campaigns issues this. Apple ignores the
  // campaign on a link without it; Play attribution works regardless.
  const APPLE_PROVIDER_TOKEN = "";
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

  const LANGUAGES = window.voyagerLanguages || [{ code: "en", label: "English", flag: "" }];
  const flagSvgs = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.flag]));

  // The document's lang attribute is authoritative — each language is its own URL.
  const documentLang = (document.documentElement.getAttribute("lang") || "en").toLowerCase();
  const initialDocumentLanguage = LANGUAGES.some((l) => l.code === documentLang) ? documentLang : "en";

  injectSharedUI(flagSvgs);



  /** A shared asset, relative to where this page sits. */
  function asset(p) {
    return (initialDocumentLanguage === "en" ? "./" : "../") + p;
  }

  /**
   * A directory URL relies on the server serving its index.html. Opened straight
   * from disk there is no server, and the browser shows a directory listing
   * instead — so name the file explicitly in that case.
   */
  function dirHref(prefix) {
    return window.location.protocol === "file:" ? `${prefix}index.html` : prefix;
  }

  /** The site's own home for a language, relative to the current page. */
  function homeHref(lang) {
    if (lang === initialDocumentLanguage) return dirHref("./");
    const up = initialDocumentLanguage === "en" ? "" : "../";
    return dirHref(lang === "en" ? up || "./" : `${up}${lang}/`);
  }

  /**
   * Same page, different language, as a path relative to the current one.
   *
   * The language comes from the document rather than the URL: opened from disk
   * the path holds the whole filesystem location, so there is no language
   * segment to read. The hreflang links are absolute production URLs — right
   * for search engines, but following them would jump off a local host.
   */
  function localizedHref(lang) {
    const from = initialDocumentLanguage;
    const up = from === "en" ? "" : "../";
    const file = window.location.pathname.split("/").pop();
    const page = !file || file === "index.html" ? "" : file;
    const base = lang === from ? "./" : lang === "en" ? up || "./" : `${up}${lang}/`;
    return page ? `${base}${page}` : dirHref(base);
  }

  /** The switcher list, built from the shared language register. */
  function languageOptions(flags) {
    return LANGUAGES.map((l) => `
              <li>
                <button type="button" class="lang-option" data-lang="${l.code}" role="option" aria-selected="${l.code === "en"}">
                  <span aria-hidden="true">${flags[l.code] || ""}</span>
                  <span>${l.label} (${l.code.toUpperCase()})</span>
                  <span class="check" aria-hidden="true">&#x2713;</span>
                </button>
              </li>`).join("");
  }

  function injectSharedUI(flags) {
    const main = document.querySelector("main.container");
    if (main && !main.querySelector(".site-header")) {
      main.insertAdjacentHTML("afterbegin", `
        <header class="site-header">
          <a class="brand" href="${homeHref(initialDocumentLanguage)}" aria-label="Voyager Maps"><img class="brand-mark" src="${asset("pictures/icon/brand-mark.png")}" width="24" height="24" alt="" aria-hidden="true" /><span class="brand-name"><span class="brand-name-lead">Voyager</span> Maps</span></a>
          <nav class="lang-switch" aria-label="Language switcher" data-i18n-aria="langSwitcherAria">
            <button type="button" class="lang-trigger" id="lang-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="lang-menu">
              <span class="lang-globe" id="lang-flag" aria-hidden="true">${flags.en}</span>
              <span class="lang-current" id="lang-current">EN</span>
              <span class="lang-caret" aria-hidden="true">&#x25BE;</span>
            </button>
            <ul class="lang-menu" id="lang-menu" role="listbox" aria-label="Language options" data-i18n-aria-label="langOptionsAria" hidden>
${languageOptions(flags)}
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

  /**
   * The campaign that brought this visitor here, ready to be handed on to the
   * stores. An inbound utm_* wins; without one the page names itself, so a
   * plain organic visit is still distinguishable from a campaign one.
   */
  function inboundCampaign() {
    const params = new URLSearchParams(window.location.search);
    const read = (key, fallback) => {
      const raw = (params.get(key) || "").toLowerCase().replace(/[^a-z0-9_-]/g, "");
      return raw.slice(0, 40) || fallback;
    };

    return {
      source: read("utm_source", "website"),
      medium: read("utm_medium", "owned"),
      campaign: read("utm_campaign", `home_${initialDocumentLanguage}`)
    };
  }

  /**
   * Carry that campaign into the store links, so an install can be traced back
   * to the post that earned it.
   *
   * Play reads utm_* out of a single `referrer` value via the Install Referrer
   * API. Apple reads `ct`, but only counts it alongside the provider token from
   * App Store Connect — the campaign is appended either way, so the link starts
   * reporting the moment APPLE_PROVIDER_TOKEN is filled in.
   */
  function decorateStoreLinks() {
    const { source, medium, campaign } = inboundCampaign();

    document
      .querySelectorAll('a[href*="play.google.com"], a[href*="apps.apple.com"]')
      .forEach((anchor) => {
        let url;
        try {
          url = new URL(anchor.getAttribute("href") || "", window.location.href);
        } catch (_) {
          return;
        }

        if (url.host.endsWith("play.google.com")) {
          if (url.searchParams.has("referrer")) return;
          url.searchParams.set(
            "referrer",
            `utm_source=${source}&utm_medium=${medium}&utm_campaign=${campaign}`
          );
        } else {
          if (url.searchParams.has("ct")) return;
          url.searchParams.set("ct", `${source}_${campaign}`.slice(0, 40));
          url.searchParams.set("mt", "8");
          if (APPLE_PROVIDER_TOKEN) url.searchParams.set("pt", APPLE_PROVIDER_TOKEN);
        }

        anchor.setAttribute("href", url.toString());
      });
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
      const lang = btn.dataset.lang;
      toggleMenu(false);
      // Every language has its own URL, declared in the hreflang links this page
      // already carries for search engines. Navigate there rather than swapping
      // the text in place, so the address bar keeps telling the truth.
      if (lang !== currentLanguage) {
        window.location.href = localizedHref(lang);
        return;
      }
      applyLanguage(lang, "user");
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
    LANGUAGES.forEach((l) => {
      const dict = window.voyagerLocales?.[l.code];
      if (dict) dictionary[l.code] = dict;
    });
    applyConsentMode();
    applyLanguage(initialDocumentLanguage, "init");
    syncConsentUi();
    initAnalytics();
    trackEvent("landing_view", {
      engagement_point: "initial_load"
    });
  }

  initLanguages();
  decorateStoreLinks();
  setupClickTracking();
  setupSectionObserver();
  setupImageObserver();
  setupEngagementTracking();
})();
