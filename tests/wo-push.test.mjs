import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import puppeteer from 'puppeteer-core';
import { boiseHour, calendarDaysUntil, dueNotifications, parseBoise, placeOf } from '../push-api/due.js';
import { createHandler } from '../push-api/http.js';
import { runDue } from '../push-api/remind.js';
import { openStore } from '../push-api/store.js';

const html = readFileSync(new URL('../corrigo-app.html', import.meta.url), 'utf8');
const manifest = JSON.parse(readFileSync(new URL('../manifest.json', import.meta.url), 'utf8'));
const worker = readFileSync(new URL('../sw.js', import.meta.url), 'utf8');
const versionFile = JSON.parse(readFileSync(new URL('../corrigo-version.json', import.meta.url), 'utf8'));
const publicKey = readFileSync(new URL('../push-api/vapid-public.txt', import.meta.url), 'utf8').trim();

function wo(partial) {
  return Object.assign({
    number: 'J1000000-00001',
    status: 'inbox',
    acceptBy: '12/3/2026 8:00 AM',
    completeBy: '12/20/2026 8:35 PM',
    property: 'SODA SPRINGS 3, 4',
    location: '281 East Hooper Avenue, SODA SPRINGS, ID 83276-1418, US'
  }, partial);
}

function listen(handler) {
  const server = http.createServer((req, res) => {
    handler(req, res).catch(err => {
      res.writeHead(500, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    });
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, url: 'http://127.0.0.1:' + server.address().port });
    });
  });
}

test('calendar milestones use America/Boise dates', () => {
  const due = parseBoise('12/20/2026 8:35 PM');
  assert.equal(calendarDaysUntil(due, new Date('2026-12-13T15:00:00Z')), 7);
  assert.equal(calendarDaysUntil(due, new Date('2026-12-17T15:00:00Z')), 3);
  assert.equal(calendarDaysUntil(due, new Date('2026-12-19T15:00:00Z')), 1);
  assert.equal(calendarDaysUntil(due, new Date('2026-12-14T15:00:00Z')), 6);
  assert.equal(calendarDaysUntil(due, new Date('2026-12-20T15:00:00Z')), 0);
  assert.equal(boiseHour(new Date('2026-12-13T15:00:00Z')), 8);
  assert.equal(boiseHour(new Date('2026-12-13T14:00:00Z')), 7);
  assert.equal(boiseHour(new Date('2026-07-13T14:00:00Z')), 8);
  const summer = parseBoise('7/20/2026 8:35 PM');
  assert.equal(calendarDaysUntil(summer, new Date('2026-07-13T14:00:00Z')), 7);
});

test('inbox uses acceptBy and accepted or in-progress uses completeBy', () => {
  const now = new Date('2026-11-26T15:00:00Z');
  const inbox = dueNotifications([wo({ acceptBy: '12/3/2026 8:00 AM', completeBy: '11/27/2026 8:00 AM' })], now, new Set());
  assert.equal(inbox.length, 1);
  assert.equal(inbox[0].days, 7);
  assert.equal(inbox[0].title, 'Work order due in 7 days');
  assert.match(inbox[0].body, /J1000000-00001/);
  assert.match(inbox[0].body, /Soda Springs 3, 4/);
  assert.match(inbox[0].body, /Dec 3, 2026/);
  assert.equal(inbox[0].url, 'https://simzy420.github.io/big-brain-ape-dashboard/corrigo-app.html?wo=J1000000-00001');

  const accepted = dueNotifications([wo({ status: 'accepted', acceptBy: '11/27/2026 8:00 AM', completeBy: '12/3/2026 8:35 PM' })], now, new Set());
  assert.equal(accepted.length, 1);
  assert.match(accepted[0].body, /Dec 3, 2026/);

  const working = dueNotifications([wo({ status: 'in-progress', completeBy: '11/27/2026 9:00 AM' })], now, new Set());
  assert.equal(working[0].title, 'Work order due in 1 day');
  assert.equal(working[0].days, 1);
});

test('closed, paid, declined, sent, and completed lists are skipped', () => {
  const now = new Date('2026-11-26T15:00:00Z');
  const statuses = ['closed', 'paid', 'declined', 'sent_to_corrigo', 'completed', 'submitted', 'bidding', ''];
  statuses.forEach(status => {
    const notes = dueNotifications([wo({ status, acceptBy: '12/3/2026 8:00 AM', completeBy: '12/3/2026 8:00 AM' })], now, new Set());
    assert.equal(notes.length, 0, status || '(blank)');
  });
  const junk = dueNotifications([wo({ acceptBy: 'DO NOT EXCEED labor and materials of $500.00 USD' })], now, new Set());
  assert.equal(junk.length, 0);
  const once = dueNotifications([wo({ acceptBy: '12/3/2026 8:00 AM' })], now, new Set(['J1000000-00001|7|2026-12-03']));
  assert.equal(once.length, 0);
});

test('a missing property falls back to the city', () => {
  assert.equal(placeOf({ location: '281 East Hooper Avenue, SODA SPRINGS, ID 83276-1418, US' }), 'Soda Springs');
});

test('the live work order file never reminds on a skipped status', () => {
  const orders = JSON.parse(readFileSync(new URL('../work-orders.json', import.meta.url), 'utf8'));
  const notes = dueNotifications(orders, new Date('2026-11-26T15:00:00Z'), new Set());
  notes.forEach(note => {
    const match = orders.find(order => String(order.number).replace(/[\u2010-\u2015\u2212]/g, '-') === note.number);
    assert.ok(match);
    assert.match(match.status, /^(inbox|accepted|in[-_ ]progress)$/i);
  });
});

test('each work order milestone is claimed once', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'wo-push-'));
  const store = openStore(dir);
  const orders = [wo({ acceptBy: '12/3/2026 8:00 AM' })];
  const now = new Date('2026-11-26T15:00:00Z');
  const calls = [];
  const first = await runDue({
    store,
    now,
    orders,
    send: async (subs, note) => {
      calls.push(note.key);
      return { ok: subs.length, gone: [] };
    }
  });
  assert.equal(first.reason, 'no-subscriptions');
  store.saveSub({ endpoint: 'https://push.example/1', keys: { p256dh: 'p256dh-key', auth: 'auth-key' } });
  const second = await runDue({
    store,
    now,
    orders,
    send: async () => ({ ok: 1, gone: [] })
  });
  assert.equal(second.sent, 1);
  assert.equal(calls.length, 0);
  const third = await runDue({
    store,
    now,
    orders,
    send: async () => { calls.push('again'); return { ok: 1, gone: [] }; }
  });
  assert.equal(third.reason, 'none-due');
  assert.deepEqual(calls, []);
});

test('a failed send is released so it can be tried again', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'wo-push-'));
  const store = openStore(dir);
  store.saveSub({ endpoint: 'https://push.example/1', keys: { p256dh: 'p256dh-key', auth: 'auth-key' } });
  const orders = [wo({ acceptBy: '12/3/2026 8:00 AM' })];
  const now = new Date('2026-11-26T15:00:00Z');
  const failed = await runDue({ store, now, orders, send: async () => ({ ok: 0, gone: ['https://push.example/1'] }) });
  assert.equal(failed.sent, 0);
  assert.equal(store.listSubs().length, 0);
  store.saveSub({ endpoint: 'https://push.example/2', keys: { p256dh: 'p256dh-key', auth: 'auth-key' } });
  const again = await runDue({ store, now, orders, send: async () => ({ ok: 1, gone: [] }) });
  assert.equal(again.sent, 1);
});

test('the phone API saves a subscription and sends one test', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'wo-push-'));
  const store = openStore(dir);
  const sent = [];
  const handler = createHandler({
    store,
    token: 'secret-token',
    sendTest: async (subs, note) => {
      sent.push(note.title);
      assert.equal(subs.length, 1);
      return { ok: 1, gone: [] };
    }
  });
  const { server, url } = await listen(handler);
  try {
    const sub = { endpoint: 'https://push.example/casey', keys: { p256dh: 'p256dh-key', auth: 'auth-key' } };
    const saved = await fetch(url + '/subscribe', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ subscription: sub }) });
    assert.equal(saved.status, 200);
    const hidden = await fetch(url + '/subscriptions');
    assert.equal(hidden.status, 401);
    const listed = await fetch(url + '/subscriptions', { headers: { authorization: 'Bearer secret-token' } });
    assert.equal((await listed.json()).subscriptions.length, 1);
    const testRes = await fetch(url + '/test', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: sub.endpoint }) });
    assert.equal(testRes.status, 200);
    assert.deepEqual(sent, ['Sims Construction']);
    const claim = await fetch(url + '/claim', {
      method: 'POST',
      headers: { authorization: 'Bearer secret-token', 'content-type': 'application/json' },
      body: JSON.stringify({ keys: ['J1|7|2026-12-03', 'J1|7|2026-12-03'] })
    });
    assert.deepEqual((await claim.json()).claimed, ['J1|7|2026-12-03']);
    const again = await fetch(url + '/claim', {
      method: 'POST',
      headers: { authorization: 'Bearer secret-token', 'content-type': 'application/json' },
      body: JSON.stringify({ keys: ['J1|7|2026-12-03'] })
    });
    assert.deepEqual((await again.json()).claimed, []);
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});

test('the installed app has a standalone manifest, icons, and a notification button', () => {
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.name, 'Sims Construction');
  assert.equal(manifest.start_url, './corrigo-app.html');
  assert.ok(manifest.icons.some(icon => icon.sizes === '192x192' && icon.src === 'icons/icon-192.png'));
  assert.ok(manifest.icons.some(icon => icon.sizes === '512x512'));
  assert.match(html, /rel="manifest" href="manifest\.json"/);
  assert.match(html, /apple-mobile-web-app-capable/);
  assert.match(html, /apple-touch-icon/);
  assert.match(html, /id="notifyOnBtn"[^>]*>Turn on notifications/);
  assert.match(html, /id="notifyTestBtn"[^>]*>Send test notification/);
  assert.match(html, /Add to Home Screen/);
  assert.match(html, new RegExp(publicKey));
  assert.match(worker, /showNotification/);
  assert.match(worker, /vibrate:\s*\[200,\s*100,\s*200,\s*100,\s*200\]/);
  assert.match(worker, /silent:\s*false/);
  assert.match(worker, /notificationclick/);
  assert.match(worker, /openWindow|navigate/);
  const appVersion = html.match(/const APP_VERSION = '([^']+)'/)[1];
  assert.equal(html.includes('>' + appVersion + '<'), true);
  assert.equal(versionFile.version, appVersion);
  assert.notEqual(appVersion, 'v60-202611231830');
  const api = html.match(/var WO_PUSH_API = '([^']+)'/)[1];
  assert.match(api, /^https:\/\/[a-z0-9-]+\.up\.railway\.app$/);
});

function chromePath() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  for (const candidate of ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome', '/usr/local/bin/google-chrome', '/usr/bin/chromium']) {
    if (existsSync(candidate)) return candidate;
  }
  return execFileSync('which', ['google-chrome'], { encoding: 'utf8' }).trim();
}

test('the notification button follows whether the phone is on the Home Screen', async () => {
  const server = http.createServer((req, res) => {
    const name = (req.url || '/').split('?')[0];
    const file = name === '/' ? '/corrigo-app.html' : name;
    const target = path.join(new URL('..', import.meta.url).pathname, file);
    if (!existsSync(target) || !target.startsWith(new URL('..', import.meta.url).pathname)) {
      res.writeHead(404);
      res.end('missing');
      return;
    }
    const type = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : file.endsWith('.png') ? 'image/png' : 'text/html';
    res.writeHead(200, { 'content-type': type, 'cache-control': 'no-store' });
    res.end(readFileSync(target));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const browser = await puppeteer.launch({ executablePath: chromePath(), headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    async function open(userAgent) {
      const page = await browser.newPage();
      if (userAgent) await page.setUserAgent(userAgent);
      await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
      await page.setRequestInterception(true);
      page.on('request', req => {
        const url = req.url();
        if (url.startsWith(origin)) { req.continue(); return; }
        if (/corrigo-version\.json/.test(url)) {
          req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ version: versionFile.version }) });
          return;
        }
        if (/work-orders\.json|corrigo-overrides|corrigo-actions|corrigo-proof|corrigo-prewritten/.test(url)) {
          req.respond({ status: 200, contentType: 'application/json', body: url.includes('work-orders') ? '[]' : '{}' });
          return;
        }
        req.abort();
      });
      const errors = [];
      page.on('pageerror', err => errors.push(String(err)));
      await page.goto(origin + '/corrigo-app.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForFunction(() => document.getElementById('notifyBox') && document.getElementById('notifyBox').style.display === 'block', { timeout: 10000 });
      const state = await page.evaluate(() => ({
        help: document.getElementById('notifyIosHelp').style.display,
        button: document.getElementById('notifyOnBtn').style.display,
        testBtn: document.getElementById('notifyTestBtn').style.display,
        helpText: document.getElementById('notifyIosHelp').innerText,
        version: document.getElementById('appVersion').textContent
      }));
      await page.close();
      return { state, errors };
    }
    const desktop = await open('');
    assert.deepEqual(desktop.errors, []);
    assert.equal(desktop.state.button, 'block');
    assert.equal(desktop.state.help, 'none');
    assert.equal(desktop.state.testBtn, 'none');
    assert.equal(desktop.state.version, versionFile.version);
    const iphone = await open('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1');
    assert.deepEqual(iphone.errors, []);
    assert.equal(iphone.state.button, 'none');
    assert.equal(iphone.state.help, 'block');
    assert.match(iphone.state.helpText, /Share button/);
    assert.match(iphone.state.helpText, /Add to Home Screen/);
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});
