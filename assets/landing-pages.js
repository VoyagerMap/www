(function () {
  const dictionary = {};
  const pageConfigNode = document.getElementById("page-config");
  const pageConfig = pageConfigNode ? JSON.parse(pageConfigNode.textContent) : {};
  const GA_MEASUREMENT_ID = (document.querySelector('meta[name="ga4-measurement-id"]')?.content || "").trim();
  const isAnalyticsEnabled = /^G-[A-Z0-9]+$/i.test(GA_MEASUREMENT_ID);
  const CONSENT_STORAGE_KEY = "voyager_docs_consent_v1";
  const CONSENT_CHANGE_EVENT = "voyagerdocsconsentchange";
  const TRACK_EVENT_SUFFIX = "_web";
  const LANGUAGE_STORAGE_KEY = "voyager_docs_language_v1";
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
      page_type: pageConfig.pageType || "landing_page",
      page_language: document.documentElement.lang || currentLanguage || "en",
      landing_topic: pageConfig.topic || "general",
      ...params
    });
  }

  function trackCtaClick(anchor) {
    if (!anchor) return;

    const href = anchor.getAttribute("href") || "";
    let destinationHost = "";

    try {
      destinationHost = new URL(href, window.location.href).host;
    } catch {
      destinationHost = "";
    }

    trackEvent("cta_click", {
      cta_type: anchor.dataset.ctaType || "unknown",
      cta_position: anchor.dataset.ctaPosition || "unknown",
      link_url: href,
      link_domain: destinationHost,
      outbound: anchor.target === "_blank" || /^https?:/i.test(href)
    });
  }

  function trackLegalClick(anchor) {
    if (!anchor) return;

    trackEvent("legal_link_click", {
      legal_type: anchor.dataset.legalType || "unknown",
      link_url: anchor.getAttribute("href") || "",
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
    [25, 50, 75, 90].forEach((bucket) => {
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

  function readStoredLanguage() {
    try {
      const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      return stored === "hu" || stored === "en" ? stored : null;
    } catch {
      return null;
    }
  }

  function detectPreferredLanguage() {
    const preferred = Array.isArray(navigator.languages) ? navigator.languages : [navigator.language || navigator.userLanguage || "en"];
    const normalized = preferred
      .filter(Boolean)
      .map((value) => String(value).toLowerCase());

    if (normalized.some((value) => value === "hu" || value.startsWith("hu-"))) return "hu";
    return "en";
  }

  function writeStoredLanguage(lang) {
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch {
      return;
    }
  }

  function applyLanguage(lang, source) {
    const previousLanguage = currentLanguage;
    const selected = dictionary[lang] || dictionary.en;
    if (!selected) return;

    document.documentElement.lang = selected.htmlLang || lang;
    document.title = selected.pageTitle || document.title;

    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription && selected.meta?.description) {
      metaDescription.setAttribute("content", selected.meta.description);
    }

    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const key = node.getAttribute("data-i18n");
      if (selected[key]) node.textContent = selected[key];
    });

    document.querySelectorAll("[data-i18n-html]").forEach((node) => {
      const key = node.getAttribute("data-i18n-html");
      if (selected[key]) node.innerHTML = selected[key];
    });

    document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
      const key = node.getAttribute("data-i18n-aria");
      if (selected[key]) node.setAttribute("aria-label", selected[key]);
    });

    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
      const key = node.getAttribute("data-i18n-aria-label");
      if (selected[key]) node.setAttribute("aria-label", selected[key]);
    });

    document.querySelectorAll("[data-i18n-alt]").forEach((node) => {
      const key = node.getAttribute("data-i18n-alt");
      if (selected[key]) node.setAttribute("alt", selected[key]);
    });

    document.querySelectorAll(".lang-option").forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.lang === lang));
    });

    const currentLabel = document.getElementById("lang-current");
    const flag = document.getElementById("lang-flag");
    if (currentLabel) currentLabel.textContent = lang.toUpperCase();
    if (flag) flag.innerHTML = flagSvgs[lang] || flagSvgs.en;

    currentLanguage = lang;
    writeStoredLanguage(lang);

    if (pageConfig.pageType === "routing_page") {
      const routing = window.voyagerRouting || {};
      const statusNode = document.getElementById("routing-status");
      if (statusNode) {
        statusNode.textContent = routing.isAndroid
          ? selected.statusAndroid || selected.statusChecking || statusNode.textContent
          : routing.isAppleMobile
            ? selected.statusApple || selected.statusChecking || statusNode.textContent
            : routing.isDesktopLike
              ? selected.statusDesktop || selected.statusFallback || statusNode.textContent
              : selected.statusFallback || selected.statusChecking || statusNode.textContent;
      }
    }

    if (source === "user" && previousLanguage !== lang) {
      trackEvent("language_change", {
        previous_language: previousLanguage,
        selected_language: lang
      });
    }
  }

  function toggleConsentPreferences(forceState) {
    if (!consentPreferences || !consentCustomize) return;
    const isOpen = typeof forceState === "boolean" ? forceState : consentPreferences.hidden;
    consentPreferences.hidden = !isOpen;
    consentCustomize.setAttribute("aria-expanded", String(isOpen));
  }

  function toggleConsentBanner(forceState) {
    if (!consentBanner || !consentBackdrop || !consentManage) return;
    const isOpen = typeof forceState === "boolean" ? forceState : consentBanner.hidden;
    consentBanner.hidden = !isOpen;
    consentBackdrop.hidden = !isOpen;
    document.body.classList.toggle("consent-active", isOpen);
    consentManage.setAttribute("aria-expanded", String(isOpen));
    if (!isOpen) toggleConsentPreferences(false);
  }

  function syncConsentUi() {
    if (!consentStatisticsToggle) return;
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
    if (!langMenu || !langTrigger) return;
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

  function bindUiEvents() {
    if (langTrigger) {
      langTrigger.addEventListener("click", () => toggleMenu());
    }

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

    if (consentManage) consentManage.addEventListener("click", () => toggleConsentBanner());
    if (consentCustomize) consentCustomize.addEventListener("click", () => toggleConsentPreferences());
    if (consentAccept) consentAccept.addEventListener("click", () => setStatisticsConsent(true));
    if (consentReject) consentReject.addEventListener("click", () => setStatisticsConsent(false));
    if (consentSave) consentSave.addEventListener("click", () => setStatisticsConsent(!!consentStatisticsToggle?.checked));

    window.addEventListener(CONSENT_CHANGE_EVENT, () => {
      if (hasStatisticsConsent()) initAnalytics();
    });
  }

  function initLanguages() {
    const localeKey = pageConfig.localeKey;
    const localeGroup = pageConfig.localeGroup || "landingPages";
    dictionary.en = window.voyagerLocales?.en?.[localeGroup]?.[localeKey];
    dictionary.hu = window.voyagerLocales?.hu?.[localeGroup]?.[localeKey];
    applyConsentMode();
    const initialLang = readStoredLanguage() || detectPreferredLanguage();
    applyLanguage(initialLang, "init");
    syncConsentUi();
    initAnalytics();
    trackEvent("landing_view", {
      engagement_point: "initial_load"
    });
  }

  bindUiEvents();
  initLanguages();
  setupClickTracking();
  setupSectionObserver();
  setupImageObserver();
  setupEngagementTracking();
})();
