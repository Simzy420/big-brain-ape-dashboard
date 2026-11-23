import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { after, before, test } from 'node:test';
import puppeteer from 'puppeteer-core';

const html = readFileSync(new URL('../wo.html', import.meta.url), 'utf8');
const workOrders = JSON.parse(readFileSync(new URL('../work-orders.json', import.meta.url), 'utf8'));
workOrders.push({
  number: 'Z9999999-00001',
  status: 'inbox',
  location: '1 Test Street, FAKEVILLE, ID 83254, US',
  estimatedAmount: 500,
  acceptBy: '11/1/2026 8:00 AM',
  completeBy: '12/1/2026 8:00 AM',
  emailJobDescription: 'Test the hinge only.',
  property: 'Fakeville'
});

function chromePath() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  for (const p of ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium']) {
    if (existsSync(p)) return p;
  }
  return execFileSync('which', ['google-chrome'], { encoding: 'utf8' }).trim();
}

let browser, server, origin;

before(async () => {
  server = http.createServer((req, res) => {
    const path = req.url.split('?')[0];
    if (path === '/work-orders.json') {
      res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify(workOrders));
      return;
    }
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    res.end(html);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
  browser = await puppeteer.launch({
    executablePath: chromePath(),
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
});

after(async () => {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

async function openPage(query) {
  const page = await browser.newPage();
  const posts = [];
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
  await page.setRequestInterception(true);
  page.on('request', req => {
    const url = req.url();
    if (req.method() !== 'GET' && req.method() !== 'HEAD') {
      posts.push(req.method() + ' ' + url);
      req.abort();
      return;
    }
    if (url.startsWith(origin)) { req.continue(); return; }
    req.abort();
  });
  await page.evaluateOnNewDocument(() => {
    window.__decisionPosts = [];
    const orig = window.fetch;
    window.fetch = function (url, opts) {
      if (String(url).indexOf('/decision') >= 0) {
        window.__decisionPosts.push({ url: String(url), body: opts && opts.body, method: opts && opts.method, headers: opts && opts.headers });
        return Promise.resolve({ ok: true, status: 200 });
      }
      return orig.apply(this, arguments);
    };
  });
  await page.goto(origin + '/wo.html' + query, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForFunction(() => {
    const t = document.body.innerText;
    return t && !/^Loading/.test(t);
  }, { timeout: 10000 });
  return { page, posts };
}

test('the dad page shows the Soda Springs job in plain language', async () => {
  const { page, posts } = await openPage('?wo=J5013895-00418&test=1');
  const text = await page.evaluate(() => document.body.innerText);
  assert.match(text, /J5013895-00418/);
  assert.match(text, /Soda Springs Church/);
  assert.match(text, /281 East Hooper Avenue/);
  assert.match(text, /Wet carpet after snow storm/);
  assert.match(text, /Accept or Decline/);
  assert.match(text, /Before Monday/);
  assert.match(text, /Nov 23/);
  assert.match(text, /8:35/);
  assert.match(text, /The Job Needs to be Finished/);
  assert.match(text, /Before Sunday/);
  assert.match(text, /Dec 20/);
  assert.match(text, /NTE: \$500/);
  assert.match(text, /Already accepted/);
  assert.equal(await page.$('#acceptBtn'), null);
  assert.equal(await page.$('#declineBtn'), null);
  const past = Date.now() >= Date.parse('2026-11-24T03:35:00.000Z');
  assert.equal(/Past deadline/.test(text), past);
  assert.equal(posts.length, 0);
  await page.close();
});

test('an en dash in the link still finds the work order', async () => {
  const { page } = await openPage('?wo=' + encodeURIComponent('J5013895\u201300418') + '&test=1');
  const text = await page.evaluate(() => document.body.innerText);
  assert.match(text, /Soda Springs Church/);
  await page.close();
});

test('test mode confirms Accept without posting', async () => {
  const { page, posts } = await openPage('?wo=Z9999999-00001&test=1');
  await page.click('#acceptBtn');
  const ask = await page.evaluate(() => document.getElementById('confirm').innerText);
  assert.match(ask, /Are you sure\?/);
  await page.click('#noBtn');
  assert.equal(await page.evaluate(() => document.getElementById('confirm').style.display), 'none');
  await page.click('#acceptBtn');
  await page.click('#yesBtn');
  const done = await page.evaluate(() => document.getElementById('resultText').textContent);
  assert.equal(done, '✅ Accepted — thanks Dad!');
  const sent = await page.evaluate(() => window.__decisionPosts);
  assert.deepEqual(sent, []);
  assert.equal(posts.length, 0);
  await page.close();
});

test('test mode confirms Decline without posting', async () => {
  const { page, posts } = await openPage('?wo=Z9999999-00001&test=1');
  const text = await page.evaluate(() => document.body.innerText);
  assert.match(text, /Past deadline/);
  assert.match(text, /Fakeville Church/);
  await page.click('#declineBtn');
  await page.click('#yesBtn');
  const done = await page.evaluate(() => document.getElementById('resultText').textContent);
  assert.equal(done, '❌ Declined');
  assert.deepEqual(await page.evaluate(() => window.__decisionPosts), []);
  assert.equal(posts.length, 0);
  await page.close();
});

test('a closed work order shows its status and no buttons', async () => {
  const { page } = await openPage('?wo=J5991021-00465&test=1');
  const text = await page.evaluate(() => document.body.innerText);
  assert.match(text, /Already submitted/);
  assert.equal(await page.$('#acceptBtn'), null);
  assert.equal(await page.$('#declineBtn'), null);
  await page.close();
});

test('a fake work order posts the same decision payload and never leaves the browser', async () => {
  const { page, posts } = await openPage('?wo=Z9999999-00001');
  await page.click('#acceptBtn');
  await page.click('#yesBtn');
  await page.waitForFunction(() => document.getElementById('resultText').textContent.includes('Accepted'));
  const sent = await page.evaluate(() => window.__decisionPosts);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].method, 'POST');
  assert.equal(sent[0].url, 'https://doorbell-relay-production-c59989ff.up.railway.app/decision');
  assert.match(sent[0].headers['Content-Type'], /application\/json/);
  const body = JSON.parse(sent[0].body);
  assert.equal(body.wo, 'Z9999999-00001');
  assert.equal(body.decision, 'accept');
  assert.equal(typeof body.ts, 'string');
  assert.equal(body.type, undefined);
  assert.equal(posts.length, 0);
  await page.close();
});
