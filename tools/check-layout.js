/**
 * Layout guard for the pages' screenshots and frames.
 *
 * These broke twice by drifting silently: a CSS aspect-ratio that no longer
 * matched the image file, and a fixed min-height that turned a phone-shaped
 * screenshot into a tablet-shaped bezel. Neither shows up in HTML or link
 * checks — it needs a real layout engine, so this measures the rendered boxes
 * in headless Chrome and fails when they stop making sense.
 *
 * Usage:  node tools/check-layout.js [baseUrl]   (default http://localhost:8899)
 */
const puppeteer = require("puppeteer");

const BASE = process.argv[2] || "http://localhost:8899";
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];
// Every page in every language: a screenshot only has to slip on one of them.
const LANGS = ["en", "de", "fr", "es", "it", "pt", "nl", "pl", "hu", "ja", "zh", "ko", "hi", "ru",
  "ar", "id", "vi", "tr", "fa", "fil", "da", "sv", "nb", "is"];
const FILES = ["", "parking-map.html", "public-toilet-map.html",
               "drinking-water-map.html", "free-shower-map.html"];
// City pages exist in English and one other language each, so they cannot be
// expanded from the language list like the rest. These are the awkward ones by
// script and word length rather than a sample: the longest headline (Rio de
// Janeiro), CJK (Tokyo, Seoul), a diacritic-heavy pair (Krakow, Vienna) and
// the widest figures (Tokyo at five digits).
const CITY_PAGES = [
  "/tokyo-map.html", "/ja/tokyo-map.html",
  "/rio-de-janeiro-map.html", "/pt/rio-de-janeiro-map.html",
  "/seoul-map.html", "/ko/seoul-map.html",
  "/krakow-map.html", "/pl/krakow-map.html",
  "/vienna-map.html", "/de/vienna-map.html",
  "/budapest-map.html", "/hu/budapest-map.html",
  "/new-york-map.html", "/singapore-map.html",
  // The all-cities index: a fifty-row table, the widest thing on the site.
  "/cities.html", "/hu/cities.html", "/ja/cities.html", "/hi/cities.html",
];
const PAGES = LANGS.flatMap((l) => FILES.map((f) => (l === "en" ? `/${f}` : `/${l}/${f}`)))
  .concat(CITY_PAGES);
const TOLERANCE = 0.02; // 2% — enough for sub-pixel rounding, not for a wrong ratio

const failures = [];
const fail = (where, msg) => failures.push(`${where}: ${msg}`);

async function checkPage(page, url, viewport) {
  const where = `${url} @ ${viewport.name}`;
  await page.setViewport(viewport);
  const response = await page.goto(BASE + url, { waitUntil: "networkidle0" });
  // ok() is 200-299 only, so a cache revalidation (304) would read as broken.
  if (!response.ok() && response.status() !== 304) {
    return fail(where, `HTTP ${response.status()}`);
  }

  // Most of the screenshots are loading="lazy", so at networkidle0 the ones
  // below the fold have not started. Measuring them then reports every one as
  // broken — and how far down they sit changes whenever a section is added
  // above. Scroll the page first, wait for what that starts, and measure from
  // the top again.
  await page.evaluate(async () => {
    const step = window.innerHeight;
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 60));
    }
    window.scrollTo(0, 0);
    await Promise.all([...document.images]
      .filter((i) => !i.complete)
      .map((i) => new Promise((r) => {
        i.addEventListener("load", r, { once: true });
        i.addEventListener("error", r, { once: true });
        setTimeout(r, 3000);
      })));
  });

  const report = await page.evaluate(() => {
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return { w: r.width, h: r.height, top: r.top, left: r.left, right: r.right };
    };
    // An image inside a horizontal scroller is off-screen on purpose — the
    // step row on the homepage is swiped, not stacked — so it is exempt from
    // the "must fit the viewport" rule below. Everything else is not.
    const scrolled = (el) => {
      for (let n = el.parentElement; n; n = n.parentElement) {
        const ov = getComputedStyle(n).overflowX;
        if (ov === "auto" || ov === "scroll") return true;
      }
      return false;
    };
    const images = [...document.querySelectorAll(".preview-shell img, .preview-image, .preview-image-phone")]
      .map((img) => ({
        inScroller: scrolled(img),
        src: img.currentSrc || img.src,
        natural: img.naturalWidth / img.naturalHeight,
        rendered: img.getBoundingClientRect().width / img.getBoundingClientRect().height,
        complete: img.complete && img.naturalWidth > 0,
        ...box(img),
      }));
    const frames = [...document.querySelectorAll(".preview-shell, .preview-frame, .preview-card")]
      .map((el) => ({ cls: el.className, ...box(el) }));
    return {
      images,
      frames,
      docWidth: document.documentElement.scrollWidth,
      viewWidth: document.documentElement.clientWidth,
    };
  });

  // The page must never scroll sideways.
  if (report.docWidth > report.viewWidth + 1) {
    fail(where, `horizontal overflow: content ${report.docWidth}px in ${report.viewWidth}px`);
  }

  for (const img of report.images) {
    const name = img.src.split("/").pop();
    if (!img.complete) {
      fail(where, `image did not load: ${name}`);
      continue;
    }
    // The rendered box has to keep the file's own proportions, otherwise
    // object-fit is quietly cropping the screenshot.
    const drift = Math.abs(img.rendered - img.natural) / img.natural;
    if (drift > TOLERANCE) {
      fail(where, `${name} distorted: rendered ${img.rendered.toFixed(3)} vs file ${img.natural.toFixed(3)}`);
    }
    if (img.w < 120) fail(where, `${name} rendered too small: ${Math.round(img.w)}px`);
    if (!img.inScroller && img.right > report.viewWidth + 1) {
      fail(where, `${name} overflows the viewport`);
    }
  }

  // A frame must hug its screenshot rather than stand around it as an empty box.
  for (const frame of report.frames) {
    const inner = report.images.find(
      (i) => i.top >= frame.top - 1 && i.left >= frame.left - 1);
    if (!inner) continue;
    const slackY = frame.h - inner.h;
    if (slackY > frame.h * 0.25) {
      fail(where, `${frame.cls}: ${Math.round(slackY)}px of empty height around the screenshot`);
    }
    const slackX = frame.w - inner.w;
    if (slackX > frame.w * 0.35) {
      fail(where, `${frame.cls}: ${Math.round(slackX)}px of empty width around the screenshot`);
    }
  }
}

(async () => {
  const browser = await puppeteer.launch({
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  let checks = 0;
  for (const url of PAGES) {
    for (const viewport of VIEWPORTS) {
      await checkPage(page, url, viewport);
      checks++;
    }
  }
  await browser.close();

  console.log(`${checks} page/viewport combinations measured`);
  if (failures.length) {
    console.log(`\n${failures.length} problem(s):`);
    failures.forEach((f) => console.log("  " + f));
    process.exit(1);
  }
  console.log("layout OK");
})();
