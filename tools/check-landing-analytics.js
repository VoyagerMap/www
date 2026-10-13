/** Browser regression checks. GA is mocked: no analytics leaves this test. */
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  const file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname);
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404).end(); return; }
    const type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)];
    if (type) res.setHeader('Content-Type', type + '; charset=utf-8');
    res.end(data);
  });
});
const pause = ms => new Promise(r => setTimeout(r, ms));
let browser;
(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  browser = await puppeteer.launch({ headless: true });
  async function fixture(url, delayed = false) {
    const context = await browser.createBrowserContext();
    const page = await context.newPage();
    await page.setViewport({ width: 390, height: 844 });
    let requests = 0, pending;
    await page.setRequestInterception(true);
    page.on('request', req => {
      if (req.url().startsWith(base)) return req.continue();
      if (req.url().includes('googletagmanager.com/gtag/js')) {
        requests++;
        if (delayed) pending = req;
        else return req.respond({ status: 200, contentType: 'text/javascript', body: '' });
      } else return req.abort();
    });
    await page.evaluateOnNewDocument(() => {
      window.testNow = 100000;
      Date.now = () => window.testNow;
      const timers = new Set();
      const originalSetInterval = window.setInterval.bind(window);
      const originalClearInterval = window.clearInterval.bind(window);
      window.testStoppedReadTimers = 0;
      window.setInterval = (callback, delay, ...args) => {
        const id = originalSetInterval(callback, delay, ...args);
        if (delay === 1000) timers.add(id);
        return id;
      };
      window.clearInterval = id => {
        if (timers.delete(id)) window.testStoppedReadTimers++;
        originalClearInterval(id);
      };
    });
    await page.goto(base + url, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#consent-accept');
    const commands = () => page.evaluate(() => (window.dataLayer || []).map(x => Array.from(x)));
    const count = async name => (await commands()).filter(x => x[0] === 'event' && x[1] === name).length;
    const button = id => page.evaluate(id => document.getElementById(id).click(), id);
    return { page, context, commands, count, button,
      requests: () => requests,
      release: async () => { await page.waitForFunction(() => document.querySelector('[data-ga-loader]')); await pause(100); assert(pending); await pending.respond({ status: 200, contentType: 'text/javascript', body: '' }); },
      ready: () => page.waitForFunction(() => (window.dataLayer || []).some(x => x[0] === 'event' && x[1] === 'landing_view_web')),
    };
  }
  for (const url of ['/fr/free-shower-map.html', '/it/free-shower-map.html', '/pl/free-shower-map.html', '/pl/drinking-water-map.html']) {
    const f = await fixture(url + '?utm_source=long_campaign_source&utm_campaign=long_campaign_identifier');
    await pause(100);
    assert.equal(f.requests(), 0, 'no GA loader before consent');
    assert.equal(await f.count('page_view'), 0);
    const staticTitle = fs.readFileSync(path.join(root, url), 'utf8').match(/<title>(.*?)<\/title>/s)[1];
    assert.equal(await f.page.title(), staticTitle, 'localized server title survives initialization');
    await f.button('consent-accept'); await f.ready(); await pause(150);
    assert.equal(f.requests(), 1);
    assert.equal((await f.commands()).filter(x => x[0] === 'config').length, 1);
    for (const event of ['page_view', 'landing_view_web', 'consent_update_web']) assert.equal(await f.count(event), 1, event);
    const ct = await f.page.$eval('[data-cta-type="app_store_ios"]', a => new URL(a.href).searchParams.get('ct'));
    assert.equal(ct.length, 30, 'Apple campaign capped at 30 characters');
    await f.page.evaluate(() => {
      const a = document.querySelector('[data-cta-type="app_store_android"]');
      a.addEventListener('click', e => e.preventDefault()); a.click();
    });
    assert.equal(await f.count('cta_click_web'), 1);
    await f.button('consent-reject');
    await f.page.evaluate(() => document.querySelector('[data-cta-type="app_store_android"]').click());
    assert.equal(await f.count('cta_click_web'), 1, 'withdrawal blocks CTA tracking');
    await f.button('consent-accept'); await pause(150);
    assert.equal(await f.count('page_view'), 1, 'regrant does not duplicate the page view');
    await f.page.reload({ waitUntil: 'domcontentloaded' }); await f.ready();
    assert.equal(await f.count('page_view'), 1, 'stored consent initializes once on a new page load');
    await f.context.close();
    console.log(`PASS consent, CTA, title and campaign: ${url}`);
  }
  for (const regrant of [false, true]) {
    const f = await fixture('/fr/free-shower-map.html', true);
    await f.button('consent-accept');
    await f.button('consent-reject');
    if (regrant) await f.button('consent-accept');
    await f.release(); await pause(300);
    assert.equal(await f.count('page_view'), regrant ? 1 : 0, 'consent race');
    assert.equal(await f.count('landing_view_web'), regrant ? 1 : 0);
    await f.context.close();
  }
  console.log('PASS pending loader withdrawal and regrant');
  const imageFixture = await fixture('/fr/free-shower-map.html');
  await imageFixture.page.evaluate(() => {
    document.getElementById('consent-reject').click();
    document.querySelector('[data-track-image]').scrollIntoView({ block: 'center' });
  });
  await pause(250);
  assert.equal(await imageFixture.count('image_preview_view_web'), 0);
  await imageFixture.button('consent-accept'); await imageFixture.ready();
  await imageFixture.page.waitForFunction(() => window.dataLayer.some(x => x[1] === 'image_preview_view_web'));
  assert.equal(await imageFixture.count('image_preview_view_web'), 1, 'visible preview is measured after consent');
  await imageFixture.context.close();
  console.log('PASS visible image after consent');
  const f = await fixture('/fr/free-shower-map.html');
  // Dismiss the consent dialog before scrolling: its body scroll lock must
  // not make this assertion depend on the current headline's layout.
  await f.button('consent-reject');
  await f.page.evaluate(() => { window.testNow += 60000; window.scrollTo(0, document.body.scrollHeight); });
  await f.page.waitForFunction(() => window.scrollY >=
    (document.documentElement.scrollHeight - window.innerHeight) * 0.5);
  await f.button('consent-accept'); await f.ready(); await pause(200);
  assert.equal(await f.count('engaged_read_web'), 0, 'pre-consent dwell time excluded');
  assert((await f.count('scroll_depth_web')) > 0, 'pre-consent scroll does not consume permitted measurement');
  await f.page.evaluate(() => {
    window.testNow += 10000;
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
    window.testNow += 60000;
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await pause(1100);
  assert.equal(await f.count('engaged_read_web'), 0, 'background time excluded');
  await f.page.evaluate(() => { window.testNow += 21000; }); await pause(1100);
  assert.equal(await f.count('engaged_read_web'), 1);
  assert.equal(await f.page.evaluate(() => window.testStoppedReadTimers), 1,
    'foreground read interval stops after successful measurement');
  await pause(1100); assert.equal(await f.count('engaged_read_web'), 1, 'engagement deduplicated');
  await f.context.close();
  console.log('PASS foreground engagement and scroll after consent');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close(); server.close();
});
