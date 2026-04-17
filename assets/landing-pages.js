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

  const DEMO_CENTER = [41.9028, 12.4964];
  const DEMO_CATEGORIES = {
    drinking_water: {
      typeLabel: "Water",
      markerClass: "water",
      icon: "💧"
    },
    public_toilet: {
      typeLabel: "Toilet",
      markerClass: "toilet",
      icon: "🚻"
    },
    free_shower: {
      typeLabel: "Shower",
      markerClass: "shower",
      icon: "🚿"
    }
  };
  const FIXED_POIS = {
    drinking_water: [
      {
        title: "Fontanella Piazza della Rotonda",
        latLng: [41.89928, 12.47684],
        description: "Historic public drinking fountain close to the Pantheon with reliable refill access.",
        location: "Piazza della Rotonda, Rome, Italy",
        hours: "Open 24/7",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "260 m away"
      },
      {
        title: "Nasone Piazza Navona",
        latLng: [41.89907, 12.47308],
        description: "Classic Rome nasone fountain near one of the busiest pedestrian routes in the center.",
        location: "Piazza Navona, Rome, Italy",
        hours: "Open 24/7",
        accessibility: "Wheelchair: Yes",
        fee: "Fee: Free",
        wifi: "WiFi: Nearby cafe",
        distance: "340 m away"
      },
      {
        title: "Drinking Fountain Largo di Torre Argentina",
        latLng: [41.89578, 12.47693],
        description: "Convenient refill point near Torre Argentina and major walking connections.",
        location: "Largo di Torre Argentina, Rome, Italy",
        hours: "Open 24/7",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "520 m away"
      },
      {
        title: "Fontanella Via dei Fori Imperiali",
        latLng: [41.89505, 12.48648],
        description: "Useful drinking water stop between Colosseo and the historic center.",
        location: "Via dei Fori Imperiali, Rome, Italy",
        hours: "Open 24/7",
        accessibility: "Wheelchair: Yes",
        fee: "Fee: Free",
        wifi: "WiFi: Unknown",
        distance: "880 m away"
      },
      {
        title: "Water Point Villa Borghese Entrance",
        latLng: [41.91041, 12.48876],
        description: "Practical bottle refill stop for park visits and longer central Rome walks.",
        location: "Villa Borghese, Rome, Italy",
        hours: "Usually available all day",
        accessibility: "Wheelchair: Varies",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "1.4 km away"
      },
      {
        title: "Nasone Trastevere Riverfront",
        latLng: [41.88996, 12.47191],
        description: "Reliable public fountain near the Tiber and Trastevere walking corridor.",
        location: "Lungotevere in Trastevere, Rome, Italy",
        hours: "Open 24/7",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: Nearby cafe",
        distance: "1.6 km away"
      }
    ],
    public_toilet: [
      {
        title: "Public Toilets Villa Borghese",
        latLng: [41.91418, 12.49252],
        description: "Large public toilet point serving visitors near the Villa Borghese paths.",
        location: "Villa Borghese, Rome, Italy",
        hours: "07:00 - 21:00",
        accessibility: "Wheelchair: Yes",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "1.7 km away"
      },
      {
        title: "Toilets Roma Termini",
        latLng: [41.90155, 12.50122],
        description: "Relevant station restroom option for transfers and onward travel in central Rome.",
        location: "Roma Termini, Rome, Italy",
        hours: "06:00 - 23:00",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Small coin fee",
        wifi: "WiFi: Unknown",
        distance: "1.1 km away"
      },
      {
        title: "Public Toilets Colle Oppio Park",
        latLng: [41.89312, 12.49342],
        description: "Useful restroom stop close to Colosseo foot traffic and park routes.",
        location: "Parco del Colle Oppio, Rome, Italy",
        hours: "08:00 - 20:00",
        accessibility: "Wheelchair: Varies",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "1.2 km away"
      },
      {
        title: "Restroom Point Gianicolo",
        latLng: [41.88918, 12.46636],
        description: "Public toilet stop useful for hilltop viewpoints and Trastevere walking routes.",
        location: "Gianicolo, Rome, Italy",
        hours: "Hours vary by site",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "1.8 km away"
      },
      {
        title: "Toilets Circus Maximus Area",
        latLng: [41.88612, 12.48689],
        description: "Relevant restroom facility near one of the main open visitor corridors in Rome.",
        location: "Circus Maximus, Rome, Italy",
        hours: "07:00 - 21:00",
        accessibility: "Wheelchair: Yes",
        fee: "Fee: Free",
        wifi: "WiFi: Unknown",
        distance: "1.9 km away"
      },
      {
        title: "Public Toilets Castel Sant'Angelo Area",
        latLng: [41.90346, 12.46688],
        description: "Convenient toilet point for riverfront visitors and Vatican-bound walks.",
        location: "Castel Sant'Angelo, Rome, Italy",
        hours: "08:00 - 22:00",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Small coin fee",
        wifi: "WiFi: No",
        distance: "960 m away"
      }
    ],
    free_shower: [
      {
        title: "Centro Astalli Shower Service",
        latLng: [41.89762, 12.48039],
        description: "Known central Rome service point associated with practical shower access for people in need.",
        location: "Via del Collegio Romano area, Rome, Italy",
        hours: "Hours vary by facility",
        accessibility: "Wheelchair: Varies",
        fee: "Fee: Free",
        wifi: "WiFi: Unknown",
        distance: "450 m away"
      },
      {
        title: "Binario 95 Support Shower Point",
        latLng: [41.90088, 12.49963],
        description: "Service-oriented shower access point near the Termini area.",
        location: "Termini district, Rome, Italy",
        hours: "Daytime access",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: Sometimes",
        distance: "1.0 km away"
      },
      {
        title: "Caritas Shower Service Esquilino",
        latLng: [41.89479, 12.50354],
        description: "Relevant urban support shower location within the broader central Rome area.",
        location: "Esquilino, Rome, Italy",
        hours: "Hours vary by facility",
        accessibility: "Wheelchair: Varies",
        fee: "Fee: Free",
        wifi: "WiFi: No",
        distance: "1.4 km away"
      },
      {
        title: "Shower Access San Lorenzo Support Hub",
        latLng: [41.89843, 12.51627],
        description: "Practical support-location style shower marker on the eastern side of the central area.",
        location: "San Lorenzo, Rome, Italy",
        hours: "08:00 - 20:00",
        accessibility: "Wheelchair: Partial",
        fee: "Fee: Free",
        wifi: "WiFi: Nearby building",
        distance: "2.0 km away"
      },
      {
        title: "Traveler Shower Point Ostiense Corridor",
        latLng: [41.87454, 12.48218],
        description: "Fixed demo shower POI representing a relevant support-access corridor south of the center.",
        location: "Ostiense corridor, Rome, Italy",
        hours: "Daytime access",
        accessibility: "Wheelchair: Varies",
        fee: "Fee: Free",
        wifi: "WiFi: Unknown",
        distance: "3.0 km away"
      }
    ]
  };

  function buildDemoPois(topic) {
    const category = DEMO_CATEGORIES[topic] || DEMO_CATEGORIES.drinking_water;
    const pois = FIXED_POIS[topic] || FIXED_POIS.drinking_water;
    return pois.map((poi) => ({
      ...poi,
      markerClass: category.markerClass,
      typeLabel: category.typeLabel,
      icon: category.icon,
      coordinates: `Coordinates ${poi.latLng[0].toFixed(6)}, ${poi.latLng[1].toFixed(6)}`
    }));
  }

  function getPoisBounds(pois) {
    return L.latLngBounds(pois.map((poi) => poi.latLng));
  }

  function createMarkerIcon(poi) {
    return L.divIcon({
      className: "",
      html: `<div class="map-marker ${poi.markerClass}" aria-hidden="true">${poi.icon}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });
  }

  function updateDemoSheet(root, poi, open) {
    const sheet = root.querySelector("[data-map-sheet]");
    const title = root.querySelector("[data-map-title]");
    const desc = root.querySelector("[data-map-desc]");
    const type = root.querySelector("[data-map-type]");
    const distance = root.querySelector("[data-map-distance]");
    const location = root.querySelector("[data-map-location]");
    const hours = root.querySelector("[data-map-hours]");
    const accessible = root.querySelector("[data-map-accessible]");
    const fee = root.querySelector("[data-map-fee]");
    const wifi = root.querySelector("[data-map-wifi]");
    const coordinates = root.querySelector("[data-map-coordinates]");
    if (!sheet || !title || !desc || !type || !distance || !location || !hours || !accessible || !fee || !wifi || !coordinates) return;

    if (poi) {
      title.textContent = poi.title;
      desc.textContent = poi.description;
      type.textContent = poi.typeLabel;
      type.className = `map-bottom-sheet-badge ${poi.markerClass}`;
      distance.textContent = poi.distance;
      location.textContent = poi.location;
      hours.textContent = poi.hours;
      accessible.textContent = poi.accessibility;
      fee.textContent = poi.fee;
      wifi.textContent = poi.wifi;
      coordinates.textContent = poi.coordinates;
    }

    sheet.classList.toggle("is-open", !!open);
    sheet.classList.toggle("is-collapsed", !open);
  }

  function bindDemoSheet(root) {
    const handle = root.querySelector("[data-map-sheet-handle]");
    const sheet = root.querySelector("[data-map-sheet]");
    if (!handle || !sheet) return;

    handle.addEventListener("click", () => {
      const open = sheet.classList.contains("is-open");
      sheet.classList.toggle("is-open", !open);
      sheet.classList.toggle("is-collapsed", open);
    });
  }

  function initDemoMaps() {
    if (typeof L === "undefined") return;

    document.querySelectorAll("[data-demo-map]").forEach((root, index) => {
      const canvas = root.querySelector("[data-map-canvas]");
      if (!canvas) return;

      const topic = root.getAttribute("data-demo-category") || pageConfig.topic || "drinking_water";
      const pois = buildDemoPois(topic);
      const map = L.map(canvas, {
        zoomControl: false,
        attributionControl: false,
        dragging: true,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        keyboard: false,
        tap: true
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18
      }).addTo(map);

      if (pois.length) {
        map.fitBounds(getPoisBounds(pois), {
          paddingTopLeft: [26, 170],
          paddingBottomRight: [26, 190],
          maxZoom: 15
        });
      } else {
        map.setView(DEMO_CENTER, 14);
      }

      pois.forEach((poi) => {
        const marker = L.marker(poi.latLng, { icon: createMarkerIcon(poi), keyboard: false }).addTo(map);
        marker.on("click", () => updateDemoSheet(root, poi, true));
      });

      map.on("click", () => updateDemoSheet(root, null, false));
      bindDemoSheet(root);
      updateDemoSheet(root, pois[index % pois.length], false);

      const controls = root.querySelectorAll(".app-demo-controls .app-demo-fab");
      if (controls.length >= 3) {
        controls[0].addEventListener("click", () => map.zoomIn());
        controls[1].addEventListener("click", () => map.zoomOut());
        controls[2].addEventListener("click", () => {
          if (pois.length) {
            map.flyToBounds(getPoisBounds(pois), {
              paddingTopLeft: [26, 170],
              paddingBottomRight: [26, 190],
              maxZoom: 15,
              duration: 0.5
            });
          } else {
            map.flyTo(DEMO_CENTER, 14, { duration: 0.5 });
          }
        });
      }

      setTimeout(() => map.invalidateSize(), 0);
    });
  }

  bindUiEvents();
  initLanguages();
  setupClickTracking();
  setupSectionObserver();
  setupImageObserver();
  setupEngagementTracking();
  initDemoMaps();
})();
