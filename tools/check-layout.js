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
const LANGS = ["en", "de", "fr", "es", "it", "pt", "nl", "pl", "hu", "ja", "zh", "ko", "hi"];
const FILES = ["", "parking-map.html", "public-toilet-map.html",
               "drinking-water-map.html", "free-shower-map.html"];
const PAGES = LANGS.flatMap((l) => FILES.map((f) => (l === "en" ? `/${f}` : `/${l}/${f}`)));
const TOLERANCE = 0.02; // 2% — enough for sub-pixel rounding, not for a wrong ratio

const failures = [];
const fail = (where, msg) => failures.push(`${where}: ${msg}`);

async function checkPage(page, url, viewport) {
  const where = `${url} @ ${viewport.name}`;
  await page.setViewport(viewport);
  const response = await page.goto(BASE + url, { waitUntil: "networkidle0" });
  if (!response.ok()) return fail(where, `HTTP ${response.status()}`);

  const report = await page.evaluate(() => {
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return { w: r.width, h: r.height, top: r.top, left: r.left, right: r.right };
    };
    const images = [...document.querySelectorAll(".preview-shell img, .preview-image, .preview-image-phone")]
      .map((img) => ({
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
    if (img.right > report.viewWidth + 1) fail(where, `${name} overflows the viewport`);
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
