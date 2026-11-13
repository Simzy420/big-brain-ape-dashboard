import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { after, before, test } from 'node:test';
import puppeteer from 'puppeteer-core';

const ADDR = '5307 East Cub River Road, PRESTON, IDAHO 83263, US';
const OTHER_ADDR = '75 North Main Street, ST CHARLES, IDAHO 83272, US';
const html = readFileSync(new URL('../corrigo-app.html', import.meta.url), 'utf8');
const APP_VERSION = html.match(/const APP_VERSION = '([^']+)'/)[1];

function chromePath() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  for (const p of ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']) {
    if (existsSync(p)) return p;
  }
  try { return execFileSync('which', ['google-chrome'], { encoding: 'utf8' }).trim(); } catch (e) {}
  throw new Error('Set CHROME_PATH to a Chrome or Chromium binary');
}

function wo(partial) {
  return Object.assign({
    id: 'id-' + String(partial.number).replace(/[^\w]+/g, '_'),
    status: 'inbox',
    location: ADDR,
    description: 'Tree fell and hit the roof. Please verify the roof is intact. Location: Southwest of the meeting house.',
    emailJobDescription: 'Tree fell and hit the roof. Please verify the roof is intact. Location: Southwest of the meeting house.',
    emailSummary: 'Tree fell and hit the roof. Please verify the roof is intact. NTE is $500.00 (labor and materials). Accept or decline by 11/06/26. Complete by 12/03/26.',
    emailSubject: 'FW: work order #' + partial.number,
    emailContent: 'Subject: work order #' + partial.number + '\nDescription: Tree fell and hit the roof. Please verify the roof is intact. Location: Southwest of the meeting house.\nNTE: $500.00\nAccept/Reject By:\n11/6/2026 8:55 AM\nComplete By:\n12/3/2026 8:55 AM\n',
    estimatedAmount: 500,
    customer: 'The Church',
    prewrittenDescription: 'Roof is cleaned off and intact and looks good',
    dateCreated: '11/3/2026 8:56 AM',
    acceptBy: '11/6/2026 8:55 AM',
    completeBy: '12/3/2026 8:55 AM'
  }, partial);
}

const base = wo({ id: 'base-preston', number: 'I5376025-00135' });
const child = wo({
  id: 'child-preston',
  number: 'I5376025-00135.01.01',
  corrigoAccepted: true,
  corrigoAcceptedAt: '2026-11-05T19:10:52.299826-07:00',
  corrigoProofUrl: 'https://example.test/proof.png'
});
const heater = wo({
  id: 'heater',
  number: 'J8888888-00077',
  description: 'Replace the water heater in the mechanical room.',
  emailJobDescription: 'Replace the water heater in the mechanical room.',
  emailSummary: 'Replace the water heater. NTE is $500.00 (labor and materials).',
  emailContent: 'Description: Replace the water heater in the mechanical room.\nNTE: $500.00\n',
  prewrittenDescription: 'Replaced the water heater.'
});
const plain = wo({
  id: 'plain',
  number: 'J5012937-00391',
  location: '2060 Niter Bench Road, GRACE, IDAHO 83241, US',
  description: 'Roof leak in room 115.',
  emailSummary: 'Roof leak in room 115.',
  emailContent: 'Description: Roof leak in room 115.\n'
});

const keptSubmitted = {
  id: 'sub1',
  number: 'I5013453-00999',
  status: 'submitted',
  location: '109 South Main Street, PARIS, ID 83261, US',
  description: 'Roof inspection',
  workDescription: 'Roof inspection complete',
  comment: 'Roof inspection complete',
  invoiceNumber: '1414',
  hours: '16',
  rate: '30',
  materialsCost: '20',
  corrigoTotal: 500,
  photos: [{ name: 'roof.jpg', url: 'https://example.test/roof.jpg', data: 'data:image/jpeg;base64,abc' }],
  emailContent: 'Description: Roof inspection\n'
};

let browser, server, origin;

before(async () => {
  server = http.createServer((req, res) => {
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

function json(req, body, status = 200) {
  return req.respond({
    status,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*', 'cache-control': 'no-store' },
    body: typeof body === 'string' ? body : JSON.stringify(body)
  });
}

async function openApp({ workOrders = [], overrides = [], actions = [], seed = {}, fail = {}, allowRelay = false, rejectSavedToken = false, proof = {}, decisionStatus = 0 } = {}) {
  const state = { fail, allowRelay, rejectSavedToken, writes: [], relayBodies: [], relayUsedAuth: false, githubCalls: [], githubWrites: [], decisionPosts: [], decisionStatus };
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
  await page.setRequestInterception(true);
  page.on('request', req => {
    const url = req.url();
    const method = req.method();
    if (/api\.github\.com/i.test(url)) {
      state.githubCalls.push(method);
      if (method === 'OPTIONS') {
        return req.respond({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'Authorization, Content-Type, Accept', 'access-control-allow-methods': 'GET, PUT, OPTIONS' } });
      }
      if (method === 'PUT' || method === 'POST') {
        state.githubWrites.push(method);
        return json(req, { message: 'blocked by test' }, 401);
      }
      if (state.rejectSavedToken && method === 'GET') return json(req, { message: 'Bad credentials' }, 401);
      req.abort();
      return;
    }
    if (method !== 'GET' && method !== 'HEAD') {
      state.writes.push(method + ' ' + url.split('?')[0]);
      if (/doorbell-relay-production-c59989ff\.up\.railway\.app\/decision/.test(url)) {
        if (method === 'OPTIONS') {
          return req.respond({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'Content-Type', 'access-control-allow-methods': 'POST, OPTIONS' } });
        }
        if (method === 'POST') {
          state.decisionPosts.push({ contentType: req.headers()['content-type'] || '', body: req.postData() || '' });
          if (state.decisionStatus) return json(req, { ok: state.decisionStatus >= 200 && state.decisionStatus < 300 }, state.decisionStatus);
          req.abort();
          return;
        }
      }
      if (state.allowRelay && url.includes('/api/sync')) {
        if (method === 'OPTIONS') {
          return req.respond({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'Content-Type, X-App-Key', 'access-control-allow-methods': 'POST, OPTIONS' } });
        }
        let body = {};
        try { body = JSON.parse(req.postData() || '{}'); } catch (e) {}
        state.relayBodies.push(body);
        if (req.headers()['authorization']) state.relayUsedAuth = true;
        if (state.failRelay && method === 'POST') return json(req, { error: 'bad app key' }, 401);
        const bad = (body.actions || []).some(a => /_delete$/.test(a.action));
        if (bad) return json(req, { error: 'bad action entry' }, 400);
        return json(req, { ok: true });
      }
      req.abort();
      return;
    }
    if (url.startsWith(origin)) { req.continue(); return; }
    if (/corrigo-version\.json/.test(url)) return json(req, { version: APP_VERSION });
    if (/work-orders\.json/.test(url)) {
      if (state.fail.workOrders) return json(req, 'nope', 500);
      return json(req, workOrders);
    }
    if (/corrigo-overrides\.json/.test(url)) {
      if (state.fail.overrides) return json(req, 'nope', 500);
      return json(req, { overrides });
    }
    if (/corrigo-actions\.json/.test(url)) {
      if (state.fail.actions) return json(req, 'nope', 500);
      return json(req, { schemaVersion: 2, pendingActions: actions, devices: {} });
    }
    if (/corrigo-proof\/index\.json/.test(url)) return json(req, proof);
    if (/corrigo-prewritten\.json/.test(url)) return json(req, { descriptions: {} });
    req.abort();
  });
  const dialogs = [];
  page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.accept(); });
  await page.evaluateOnNewDocument(saved => {
    localStorage.clear();
    Object.keys(saved || {}).forEach(key => localStorage.setItem(key, JSON.stringify(saved[key])));
  }, seed);
  await page.goto(origin + '/corrigo-app.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForFunction(() => {
    const pill = (document.getElementById('syncStatus') || {}).innerText || '';
    const inbox = document.getElementById('inbox');
    return !!(inbox && inbox.innerText && !/Syncing|starting/i.test(pill));
  }, { timeout: 15000 });
  return { page, dialogs, state };
}

async function tabs(page) {
  return page.evaluate(() => {
    const read = key => JSON.parse(localStorage.getItem(key) || '[]');
    const nums = key => read(key).map(w => w.number);
    return {
      inbox: nums('corrigo_inbox'),
      accepted: nums('corrigo_accepted'),
      submitted: read('corrigo_submitted'),
      completed: read('corrigo_completed'),
      sent: read('corrigo_sent_to_corrigo'),
      paid: read('corrigo_paid'),
      inboxHtml: document.getElementById('inbox').innerHTML,
      acceptedHtml: document.getElementById('accepted').innerHTML,
      versionSize: getComputedStyle(document.getElementById('appVersion')).fontSize,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
    };
  });
}

test('confirmed corrigoAccepted suffix duplicate leaves Inbox and keeps the real number', async () => {
  const staleChild = Object.assign({}, child);
  delete staleChild.corrigoAccepted;
  delete staleChild.corrigoAcceptedAt;
  const { page, state } = await openApp({
    workOrders: [base, child, heater],
    seed: { corrigo_inbox: [base, staleChild, heater] }
  });
  const got = await tabs(page);
  assert.deepEqual(got.inbox, ['J8888888-00077']);
  assert.deepEqual(got.accepted, ['I5376025-00135.01.01']);
  assert.equal(got.inboxHtml.includes('Add Work Description'), false);
  assert.equal(got.inboxHtml.includes('I5376025-00135<'), false);
  assert.equal(got.acceptedHtml.includes('I5376025-00135.01.01'), true);
  assert.equal(got.acceptedHtml.includes('View Original Email'), true);
  assert.ok(state.writes.some(line => line.startsWith('POST ') || line.startsWith('OPTIONS ')));
  assert.equal(state.writes.some(line => line.startsWith('GET ')), false);
  await page.close();
});

test('same address does not merge a different work order', async () => {
  const { page } = await openApp({ workOrders: [child, heater] });
  const got = await tabs(page);
  assert.deepEqual(got.inbox, ['J8888888-00077']);
  assert.deepEqual(got.accepted, ['I5376025-00135.01.01']);
  assert.equal(got.inboxHtml.includes('water heater'), true);
  await page.close();
});

test('a suffixed number at a different address stays a separate job', async () => {
  const elsewhere = wo({ id: 'elsewhere', number: 'I5376025-00135', location: OTHER_ADDR, description: 'Paint the chapel door.' });
  const { page } = await openApp({ workOrders: [elsewhere, child] });
  const got = await tabs(page);
  assert.ok(got.inbox.includes('I5376025-00135'));
  assert.ok(got.accepted.includes('I5376025-00135.01.01'));
  assert.equal(got.inbox.filter(n => n === 'I5376025-00135.01.01').length, 0);
  await page.close();
});

test('Submitted, Finalize, and Paid keep invoices, photos, and totals', async () => {
  const paid = {
    id: 'paid1',
    number: 'I5016118-00394',
    status: 'paid',
    location: '294 North 100 East, LOGAN, UT 84321, US',
    description: 'Invoice paid',
    invoiceNumber: '1294',
    invoiceAmount: 500,
    paidAmount: 500,
    corrigoTotal: 500,
    photos: [{ name: 'paid.jpg', url: 'https://example.test/paid.jpg' }],
    customer: 'The Church'
  };
  const finalized = {
    id: 'fin1',
    number: 'J5013755-00360',
    status: 'completed',
    location: '1 North St, MONTPELIER, ID 83254, US',
    invoiceNumber: '1400',
    hours: '8',
    rate: '30',
    materialsCost: '10',
    corrigoTotal: 250,
    photos: [{ name: 'fin.jpg', url: 'https://example.test/fin.jpg' }],
    workDescription: 'Gutters cleaned'
  };
  const sentKept = {
    id: 'sent-keep',
    number: 'I5000000-00011',
    status: 'sent_to_corrigo',
    location: '10 East St, PARIS, ID 83261, US',
    invoiceNumber: '1399',
    corrigoTotal: 475,
    photos: [{ name: 'sent.jpg', url: 'https://example.test/sent.jpg' }],
    workDescription: 'Already submitted'
  };
  const serverBlank = number => wo({
    number,
    status: 'inbox',
    corrigoAccepted: true,
    invoiceNumber: '',
    photos: [],
    workDescription: '',
    corrigoTotal: null
  });
  const { page } = await openApp({
    workOrders: [
      serverBlank(keptSubmitted.number),
      serverBlank(paid.number),
      serverBlank(finalized.number),
      Object.assign({}, sentKept, { photos: [], corrigoTotal: null, workDescription: '' }),
      wo({ id: 'sent-del', number: 'I5000000-00010', status: 'sent_to_corrigo', description: 'Deleted on the phone' })
    ],
    actions: [{
      number: keptSubmitted.number,
      action: 'accept',
      deviceId: 'dev-other-phone',
      deviceName: 'Gary',
      updatedAt: '2026-11-08T00:00:00.000Z',
      location: keptSubmitted.location,
      description: keptSubmitted.description
    }],
    seed: {
      corrigo_submitted: [keptSubmitted],
      corrigo_paid: [paid],
      corrigo_completed: [finalized],
      corrigo_sent_to_corrigo: [sentKept],
      corrigo_sent_deleted: { 'I5000000-00010': '2026-11-01T00:00:00.000Z' },
      corrigo_paid_deleted: {}
    }
  });
  const got = await tabs(page);
  assert.equal(got.accepted.includes(keptSubmitted.number), false);
  assert.equal(got.inbox.includes(keptSubmitted.number), false);
  assert.equal(got.submitted.length, 1);
  assert.equal(got.submitted[0].invoiceNumber, '1414');
  assert.equal(got.submitted[0].corrigoTotal, 500);
  assert.equal(got.submitted[0].photos[0].url, 'https://example.test/roof.jpg');
  assert.equal(got.submitted[0].workDescription, 'Roof inspection complete');
  assert.equal(got.paid[0].invoiceNumber, '1294');
  assert.equal(got.paid[0].paidAmount, 500);
  assert.equal(got.paid[0].status, 'paid');
  assert.equal(got.completed[0].invoiceNumber, '1400');
  assert.equal(got.completed[0].photos[0].name, 'fin.jpg');
  assert.deepEqual(got.sent.map(w => w.number), ['I5000000-00011']);
  assert.equal(got.sent[0].corrigoTotal, 475);
  assert.equal(got.sent[0].photos[0].url, 'https://example.test/sent.jpg');
  await page.close();
});

test('another phone accepting one job leaves the same-address neighbor in Inbox', async () => {
  const neighbor = wo({ id: 'neighbor', number: 'J7777777-00002', description: 'Service the boiler.' });
  const { page } = await openApp({
    workOrders: [plain, neighbor],
    seed: { corrigo_inbox: [plain, neighbor] },
    actions: [{
      number: plain.number,
      action: 'accept',
      deviceId: 'dev-other-phone',
      deviceName: 'Gary',
      updatedAt: '2026-11-08T12:00:00.000Z',
      location: plain.location,
      description: plain.description
    }]
  });
  const got = await tabs(page);
  assert.deepEqual(got.accepted, [plain.number]);
  assert.deepEqual(got.inbox, [neighbor.number]);
  await page.close();
});

test('Reload reports a failed work-order fetch and a real success', async () => {
  const session = await openApp({ workOrders: [plain], fail: {}, allowRelay: true });
  session.state.fail.workOrders = true;
  const failed = await session.page.evaluate(async () => {
    await forceReload();
    const toast = document.getElementById('reloadToast');
    return toast ? toast.textContent : '';
  });
  assert.match(failed, /Reload failed: work orders did not load/);
  assert.equal(failed.includes('Synced from server'), false);
  session.state.fail.workOrders = false;
  session.state.fail.actions = true;
  const actionsFailed = await session.page.evaluate(async () => {
    await forceReload();
    return document.getElementById('reloadToast').textContent;
  });
  assert.match(actionsFailed, /Reload failed: the accept list did not load/);
  session.state.fail.actions = false;
  const ok = await session.page.evaluate(async () => {
    await forceReload();
    return document.getElementById('reloadToast').textContent;
  });
  assert.equal(ok, '✅ Synced from server!');
  const pill = await session.page.evaluate(() => document.getElementById('syncStatus').innerText);
  assert.match(pill, /Synced to bot/);
  await session.page.close();
});

test('a phone delete is not reported as synced and stays on the phone', async () => {
  const accepted = Object.assign({}, plain, { status: 'accepted' });
  const session = await openApp({
    workOrders: [plain],
    allowRelay: true,
    seed: {
      corrigo_accepted: [accepted],
      corrigo_sent_deleted: { 'J5013259-00415': '2026-11-01T21:17:21.194Z' }
    }
  });
  await session.page.evaluate(() => forceReload());
  const got = await session.page.evaluate(() => ({
    toast: document.getElementById('reloadToast').textContent,
    pill: document.getElementById('syncStatus').innerText,
    deleted: JSON.parse(localStorage.getItem('corrigo_sent_deleted') || '{}'),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number)
  }));
  assert.equal(session.state.relayBodies.length, 0);
  assert.equal(got.deleted['J5013259-00415'] != null, true);
  assert.deepEqual(got.accepted, [plain.number]);
  assert.match(got.toast, /could not send its changes/);
  assert.equal(got.toast.includes('Synced from server'), false);
  assert.match(got.pill, /List reloaded/);
  assert.match(got.pill, /Sync failed/);
  assert.match(got.pill, /still on this phone/);
  assert.equal(/Synced to bot/.test(got.pill), false);
  await session.page.close();
});

test('Accept stays in Inbox when the phone cannot store it', async () => {
  const { page, dialogs } = await openApp({ workOrders: [plain] });
  await page.evaluate(() => {
    Storage.prototype.setItem = function () {
      throw new DOMException('quota', 'QuotaExceededError');
    };
  });
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('#inbox button')].find(b => b.textContent.trim() === 'Accept');
    if (!button) throw new Error('Accept button missing');
    button.click();
  });
  const got = await tabs(page);
  assert.deepEqual(got.inbox, [plain.number]);
  assert.deepEqual(got.accepted, []);
  assert.match(dialogs.join('\n'), /could not store/);
  assert.equal(dialogs.some(m => m.includes('You Accepted the Job')), false);
  await page.close();
});

test('Accept moves the job only after it is stored', async () => {
  const { page, dialogs } = await openApp({ workOrders: [plain, heater] });
  await page.evaluate(id => {
    const button = [...document.querySelectorAll('#inbox button')].find(b => (b.getAttribute('onclick') || '').includes(id));
    if (!button) throw new Error('Accept button missing');
    button.click();
  }, plain.id);
  const got = await tabs(page);
  assert.deepEqual(got.accepted, [plain.number]);
  assert.deepEqual(got.inbox, [heater.number]);
  assert.ok(dialogs.some(m => m.includes('You Accepted the Job')));
  assert.equal(dialogs.some(m => m.includes('could not store')), false);
  await page.close();
});

test('mobile Inbox has no work-description button and the email summary stays', async () => {
  const { page } = await openApp({ workOrders: [child, heater] });
  const wide = await tabs(page);
  assert.equal(wide.versionSize, '20px');
  assert.ok(wide.overflow <= 1);
  assert.equal(wide.inboxHtml.includes('Add Work Description'), false);
  assert.equal(wide.inboxHtml.includes('>Accept<'), true);
  await page.setViewport({ width: 320, height: 700, isMobile: true, hasTouch: true });
  const narrow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(narrow <= 1);
  await page.evaluate(() => show('accepted'));
  const summary = await page.evaluate(() => {
    const button = [...document.querySelectorAll('#accepted button')].find(b => b.textContent.includes('View Original Email'));
    button.click();
    return document.getElementById('emailModalSummary').innerText;
  });
  assert.match(summary, /I5376025-00135\.01\.01/);
  assert.match(summary, /Tree fell and hit the roof/);
  assert.match(summary, /NTE is \$500\.00/);
  await page.close();
});

test('a rejected saved GitHub token is reported and the phone falls back without deleting it', async () => {
  const kept = Object.assign({}, plain, { status: 'accepted', photos: [{ name: 'roof.jpg', url: 'https://example.test/roof.jpg' }] });
  const session = await openApp({ workOrders: [plain], allowRelay: true, rejectSavedToken: true, seed: { corrigo_accepted: [kept] } });
  session.state.relayBodies = [];
  session.state.githubCalls = [];
  session.state.githubWrites = [];
  await session.page.evaluate(() => localStorage.setItem('github_token', 'rejected-test-token'));
  await session.page.evaluate(() => forceReload());
  const got = await session.page.evaluate(() => ({
    toast: (document.getElementById('reloadToast') || {}).textContent || '',
    pill: document.getElementById('syncStatus').innerText,
    token: localStorage.getItem('github_token'),
    photo: (JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').find(w => w.number === 'J5012937-00391') || {}).photos
  }));
  assert.equal(got.token, 'rejected-test-token');
  assert.equal(session.state.githubWrites.length, 0);
  assert.ok(session.state.githubCalls.includes('GET'));
  assert.equal(session.state.relayUsedAuth, false);
  assert.ok(session.state.relayBodies.length >= 1);
  assert.equal(JSON.stringify(session.state.relayBodies).includes('rejected-test-token'), false);
  assert.equal(got.photo && got.photo[0] && got.photo[0].url, 'https://example.test/roof.jpg');
  assert.match(got.pill, /Saved GitHub token was rejected/);
  assert.match(got.pill, /Sent without that token/);
  assert.equal(/read HTTP 401/.test(got.pill), false);
  assert.match(got.toast, /Sent without the saved GitHub token/);
  assert.equal(got.toast.includes('could not send'), false);
  await session.page.close();
});

test('a rejected token does not send or drop a phone delete', async () => {
  const session = await openApp({
    workOrders: [],
    allowRelay: true,
    rejectSavedToken: true,
    seed: { corrigo_sent_deleted: { 'PHONE-LOCAL-DELETE': '2026-11-08T20:00:00.000Z' } }
  });
  session.state.relayBodies = [];
  session.state.githubWrites = [];
  await session.page.evaluate(() => localStorage.setItem('github_token', 'rejected-test-token'));
  await session.page.evaluate(() => forceReload());
  const got = await session.page.evaluate(() => ({
    pill: document.getElementById('syncStatus').innerText,
    toast: (document.getElementById('reloadToast') || {}).textContent || '',
    token: localStorage.getItem('github_token'),
    deleted: JSON.parse(localStorage.getItem('corrigo_sent_deleted') || '{}')
  }));
  assert.equal(got.token, 'rejected-test-token');
  assert.equal(session.state.relayBodies.length, 0);
  assert.equal(session.state.githubWrites.length, 0);
  assert.equal(got.deleted['PHONE-LOCAL-DELETE'], '2026-11-08T20:00:00.000Z');
  assert.match(got.pill, /Saved GitHub token was rejected/);
  assert.match(got.pill, /still on this phone/);
  assert.match(got.pill, /Nothing was sent/);
  assert.match(got.toast, /could not send its changes/);
  await session.page.close();
});

test('Accepted cards use the same four buttons and Corrigo proof is not a button', async () => {
  const withEmail = wo({
    id: 'with-email',
    number: 'I5013496-00375.01',
    status: 'accepted',
    location: OTHER_ADDR,
    description: 'Curb in front of the storage shed is damaged.',
    emailJobDescription: 'Curb in front of the storage shed is damaged.',
    emailSummary: 'Curb in front of the storage shed is damaged. NTE is $2,800.00 (labor and materials).',
    bidAmount: 2800,
    emailContent: 'Description: Curb in front of the storage shed is damaged.\nNTE: $2800.00\n',
    emailSubject: 'FW: work order #I5013496-00375.01'
  });
  const noEmail = wo({
    id: 'no-email',
    number: 'I5017025-00256.01',
    status: 'accepted',
    description: 'Clear rain gutters on all 4 sides',
    emailContent: '   ',
    emailSubject: '',
    emailSummary: '',
    emailJobDescription: ''
  });
  const withProof = wo({
    id: 'with-proof',
    number: 'I5376025-00135.01.01',
    status: 'accepted',
    corrigoProofUrl: 'https://example.test/accepted.png'
  });
  const declinedProof = wo({
    id: 'declined-proof',
    number: 'J9999999-00001',
    status: 'declined',
    description: 'Declined job that has a Corrigo proof file.',
    emailContent: '',
    emailSummary: '',
    emailJobDescription: ''
  });
  const sent = {
    id: 'sent-proof',
    number: 'J5075335-00131',
    status: 'sent_to_corrigo',
    location: '406 South Main Street, GRACE, IDAHO 83241, US',
    invoiceNumber: '1425',
    hours: '1',
    corrigoTotal: 485,
    cruChatScreenshotUrl: 'https://example.test/cru.png'
  };
  const { page, dialogs } = await openApp({
    workOrders: [],
    proof: {
      'I5376025-00135.01.01': [{ action: 'accepted', at: '2026-11-05T19:10:52.299826-07:00', url: 'https://example.test/accepted.png' }],
      'J9999999-00001': [{ action: 'declined', at: '2026-11-01T12:00:00-07:00', url: 'https://example.test/declined.png' }],
      'J5075335-00131': [{ action: 'invoice_submitted', at: '2026-11-03T22:22:00Z', url: 'https://example.test/cru.png' }]
    },
    seed: {
      corrigo_accepted: [withEmail, noEmail, withProof],
      corrigo_declined: [declinedProof],
      corrigo_sent_to_corrigo: [sent]
    }
  });
  await page.evaluate(async () => { await loadProof(); render(); });
  const layout = await page.evaluate(() => {
    const buttons = root => [...root.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
    const sideBySide = root => {
      const rows = [...root.querySelectorAll('.btn-row')];
      const row = rows[rows.length - 1];
      const pair = row ? [...row.querySelectorAll('button')] : [];
      if (pair.length !== 2) return false;
      const a = pair[0].getBoundingClientRect();
      const b = pair[1].getBoundingClientRect();
      return Math.abs(a.top - b.top) < 4 && b.left >= a.right - 1 && a.width > 40 && b.width > 40;
    };
    const accepted = [...document.querySelectorAll('#accepted .card')].map(card => ({
      num: card.querySelector('strong').textContent.trim(),
      buttons: buttons(card),
      sideBySide: sideBySide(card),
      line: (card.querySelector('.proof-box') || {}).innerText || ''
    }));
    show('accepted');
    const acceptedNow = [...document.querySelectorAll('#accepted .card')].map(card => sideBySide(card));
    const declined = document.querySelector('#declined .card');
    const sentCard = document.querySelector('#sentToCorrigoList .card');
    return {
      accepted,
      acceptedNow,
      pageText: document.body.innerText,
      declinedButtons: buttons(declined),
      declinedLine: (declined.querySelector('.proof-box') || {}).innerText || '',
      sentButtons: buttons(sentCard),
      version: document.getElementById('appVersion').textContent,
      steps: [...document.querySelectorAll('.steplabel')].map(el => el.textContent)
    };
  });
  const four = ['Decline', '↩ Unaccept', '🗑️ Delete', '📝 Add Work Description', '📧 View Original Email', '📷 Corrigo Photos'];
  assert.equal(layout.accepted.length, 3);
  layout.accepted.forEach(card => assert.deepEqual(card.buttons, four));
  assert.deepEqual(layout.acceptedNow, [true, true, true]);
  assert.equal(layout.pageText.includes('See Corrigo proof'), false);
  assert.equal(layout.accepted[0].line, '');
  assert.equal(layout.accepted[1].line, '');
  assert.match(layout.accepted[2].line, /Accepted in Corrigo ✓ 11\/05\/26/);
  assert.equal(layout.declinedButtons.includes('📧 View Original Email'), false);
  assert.equal(layout.declinedButtons.includes('📸 See Corrigo proof'), false);
  assert.match(layout.declinedLine, /Declined in Corrigo/);
  assert.ok(layout.sentButtons.some(label => label.includes('Proof It Was Submitted')));
  assert.deepEqual(layout.steps, ['Step 1 ⭐️', 'Step 2 ⭐️']);
  assert.equal(layout.version, APP_VERSION);
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#accepted .card')].find(c => c.innerText.includes('I5017025-00256.01'));
    [...card.querySelectorAll('button')].find(b => b.textContent.includes('View Original Email')).click();
  });
  assert.ok(dialogs.some(m => m === 'No original email is saved for this work order.'));
  const summary = await page.evaluate(() => {
    const card = [...document.querySelectorAll('#accepted .card')].find(c => c.innerText.includes('I5013496-00375.01'));
    [...card.querySelectorAll('button')].find(b => b.textContent.includes('View Original Email')).click();
    return document.getElementById('emailModalSummary').innerText;
  });
  assert.match(summary, /I5013496-00375\.01/);
  assert.match(summary, /Curb in front of the storage shed/);
  const stored = await page.evaluate(() => ({
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    proofUrl: (JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').find(w => w.number === 'I5376025-00135.01.01') || {}).corrigoProofUrl
  }));
  assert.deepEqual(stored.accepted, ['I5013496-00375.01', 'I5017025-00256.01', 'I5376025-00135.01.01']);
  assert.equal(stored.proofUrl, 'https://example.test/accepted.png');
  await page.close();
});

function mountainStamp(msFromNow) {
  const target = new Date(Date.now() + msFromNow);
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Boise',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).formatToParts(target);
  const get = type => parts.find(p => p.type === type).value;
  return get('month') + '/' + get('day') + '/' + get('year') + ' ' + get('hour') + ':' + get('minute') + ' ' + get('dayPeriod');
}

test('Almost Due uses the 3-day accept and complete deadlines', async () => {
  const soon = wo({
    id: 'soon-accept',
    number: 'J5015189-00435',
    status: 'inbox',
    acceptBy: '11/13/2026 1:48 PM',
    completeBy: '12/7/2026 5:00 PM'
  });
  const late = wo({
    id: 'late-accept',
    number: 'J5991021-00465',
    status: 'inbox',
    acceptBy: '11/11/2026 11:48 AM',
    completeBy: '12/8/2026 11:48 AM'
  });
  const far = wo({
    id: 'far-accept',
    number: 'J0000000-00991',
    status: 'inbox',
    acceptBy: mountainStamp(10 * 24 * 60 * 60 * 1000),
    completeBy: mountainStamp(20 * 24 * 60 * 60 * 1000)
  });
  const emailOnly = wo({
    id: 'email-accept',
    number: 'J0000000-00992',
    status: 'inbox',
    acceptBy: '',
    completeBy: mountainStamp(20 * 24 * 60 * 60 * 1000),
    emailContent: 'Accept/Reject By:\n' + mountainStamp(26 * 60 * 60 * 1000) + '\n'
  });
  const acceptedSoon = wo({
    id: 'accepted-soon',
    number: 'J0000000-00993',
    status: 'accepted',
    acceptBy: '11/01/2026 8:00 AM',
    completeBy: mountainStamp(26 * 60 * 60 * 1000)
  });
  const acceptedFar = wo({
    id: 'accepted-far',
    number: 'J0000000-00994',
    status: 'accepted',
    acceptBy: '11/01/2026 8:00 AM',
    completeBy: mountainStamp(10 * 24 * 60 * 60 * 1000)
  });
  const declined = wo({
    id: 'declined-past',
    number: 'J0000000-00995',
    status: 'declined',
    acceptBy: '11/01/2026 8:00 AM'
  });
  const paid = wo({
    id: 'paid-past',
    number: 'J0000000-00996',
    status: 'paid',
    acceptBy: '11/01/2026 8:00 AM',
    completeBy: '11/02/2026 8:00 AM'
  });
  const sent = wo({
    id: 'sent-past',
    number: 'J0000000-00997',
    status: 'sent_to_corrigo',
    acceptBy: '11/01/2026 8:00 AM',
    completeBy: '11/02/2026 8:00 AM'
  });
  const completed = wo({
    id: 'completed-past',
    number: 'J0000000-00998',
    status: 'completed',
    acceptBy: '11/01/2026 8:00 AM',
    completeBy: '11/02/2026 8:00 AM'
  });
  const { page, dialogs } = await openApp({
    workOrders: [],
    seed: {
      corrigo_inbox: [soon, late, far, emailOnly],
      corrigo_accepted: [acceptedSoon, acceptedFar],
      corrigo_declined: [declined],
      corrigo_paid: [paid],
      corrigo_sent_to_corrigo: [sent],
      corrigo_completed: [completed]
    }
  });
  const view = await page.evaluate(() => {
    show('almostdue');
    const tabButtons = [...document.querySelectorAll('.tabs .tab')];
    const almostDueButtons = tabButtons.filter(b => /Almost Due/.test(b.textContent));
    const cards = [...document.querySelectorAll('#almostdue .card')].map(card => {
      const flag = card.querySelector('.due-flag');
      return {
        num: (card.querySelector('strong') || {}).textContent || '',
        text: flag ? flag.textContent : card.innerText,
        overdue: card.classList.contains('overdue'),
        color: flag ? getComputedStyle(flag).color : '',
        accept: [...card.querySelectorAll('button')].some(b => b.textContent.trim() === 'Accept')
      };
    });
    const readCards = root => [...root.querySelectorAll('.card')].map(card => {
      const flag = card.querySelector('.due-flag');
      const labels = [...card.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
      return {
        num: (card.querySelector('strong') || {}).textContent || '',
        text: flag ? flag.textContent : card.innerText,
        overdue: card.classList.contains('overdue'),
        color: flag ? getComputedStyle(flag).color : '',
        accept: labels.includes('Accept'),
        decline: labels.includes('Decline'),
        unaccept: labels.includes('↩ Unaccept')
      };
    });
    const inboxNums = [...document.querySelectorAll('#inbox .card strong')].map(el => el.textContent.trim());
    const acceptedNums = [...document.querySelectorAll('#accepted .card strong')].map(el => el.textContent.trim());
    return {
      tabs: almostDueButtons.length,
      tabOrder: tabButtons.map(b => b.textContent.replace(/\s+/g, ' ').trim()),
      count: document.getElementById('almostDueCount').textContent,
      overdueCount: document.getElementById('overdueCount').textContent,
      cards,
      overdueCards: readCards(document.getElementById('overdue')),
      help: (document.querySelector('#almostdue .howto-line') || {}).innerText || '',
      inboxNums,
      acceptedNums,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      expectedSoon: formatDueIn(parseMountain('11/13/2026 1:48 PM'), new Date())
    };
  });
  assert.equal(view.tabs, 1);
  const names = view.tabOrder.map(label => label.replace(/^\W+\s*/, '').replace(/\s+\d+$/, '').trim());
  assert.deepEqual(names, ['Inbox', 'Accepted', 'Almost Due', 'Bidding', 'Overdue', 'Disputed', 'Resolved', 'Finalize', 'Completed', 'Submitted', 'Paid', 'Declined', 'Add WO', 'Settings']);
  assert.equal(view.overflow <= 1, true);
  assert.equal(view.count, String(view.cards.length));
  assert.equal(view.overdueCount, String(view.overdueCards.filter(c => c.num).length));
  assert.match(view.help, /Past-due jobs are in Overdue/);
  const byNum = Object.fromEntries(view.cards.filter(c => c.num).map(c => [c.num, c]));
  const overdueByNum = Object.fromEntries(view.overdueCards.filter(c => c.num).map(c => [c.num, c]));
  assert.equal(byNum['J5991021-00465'], undefined);
  assert.ok(overdueByNum['J5991021-00465'], 'J5991021-00465 should be on Overdue');
  assert.match(overdueByNum['J5991021-00465'].text, /overdue/);
  assert.equal(overdueByNum['J5991021-00465'].overdue, true);
  assert.equal(overdueByNum['J5991021-00465'].color, 'rgb(255, 59, 48)');
  assert.equal(overdueByNum['J5991021-00465'].accept, true);
  assert.equal(overdueByNum['J5991021-00465'].decline, true);
  assert.equal(overdueByNum['J5991021-00465'].unaccept, true);
  if (view.expectedSoon === 'overdue') {
    assert.equal(byNum['J5015189-00435'], undefined);
    assert.ok(overdueByNum['J5015189-00435']);
    assert.equal(overdueByNum['J5015189-00435'].accept, true);
    assert.equal(overdueByNum['J5015189-00435'].unaccept, true);
  } else {
    assert.ok(byNum['J5015189-00435'], 'J5015189-00435 should be on Almost Due');
    assert.equal(overdueByNum['J5015189-00435'], undefined);
    assert.match(byNum['J5015189-00435'].text, /due in \d+d(?: \d+h)?|due in \d+h(?: \d+m)?|due in \d+m/);
    assert.equal(byNum['J5015189-00435'].text.includes(view.expectedSoon), true);
    assert.equal(byNum['J5015189-00435'].overdue, false);
  }
  assert.ok(byNum['J0000000-00992']);
  assert.match(byNum['J0000000-00992'].text, /due in /);
  assert.ok(byNum['J0000000-00993']);
  assert.match(byNum['J0000000-00993'].text, /Complete By/);
  assert.equal(byNum['J0000000-00991'], undefined);
  assert.equal(byNum['J0000000-00994'], undefined);
  assert.equal(byNum['J0000000-00995'], undefined);
  assert.equal(byNum['J0000000-00996'], undefined);
  assert.equal(byNum['J0000000-00997'], undefined);
  assert.equal(byNum['J0000000-00998'], undefined);
  for (const num of ['J5015189-00435', 'J5991021-00465', 'J0000000-00991', 'J0000000-00992']) {
    assert.equal(view.inboxNums.includes(num), true);
  }
  assert.equal(view.acceptedNums.includes('J0000000-00993'), true);
  assert.equal(view.acceptedNums.includes('J0000000-00994'), true);
  await page.setViewport({ width: 320, height: 700, isMobile: true, hasTouch: true });
  const narrow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(narrow <= 1);
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#almostdue .card')].find(c => c.innerText.includes('J0000000-00992'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Accept').click();
  });
  const after = await page.evaluate(() => ({
    almost: [...document.querySelectorAll('#almostdue .card strong')].map(el => el.textContent.trim()),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number)
  }));
  assert.equal(after.almost.includes('J0000000-00992'), false);
  assert.equal(after.accepted.includes('J0000000-00992'), true);
  assert.equal(after.inbox.includes('J0000000-00992'), false);
  assert.equal(after.inbox.includes('J5015189-00435'), true);
  assert.ok(dialogs.some(m => m.includes('You Accepted the Job')));
  await page.close();
});

test('Accept and Decline confirm before they move a job, and the local decision wins', async () => {
  const job = wo({
    id: 'decide-me',
    number: 'J5015189-00435',
    status: 'inbox',
    acceptBy: '11/13/2026 1:48 PM',
    completeBy: '12/07/2026 5:00 PM'
  });
  const other = wo({
    id: 'decide-other',
    number: 'J5991021-00465',
    status: 'inbox',
    acceptBy: '11/11/2026 11:48 AM',
    completeBy: '12/08/2026 11:48 AM'
  });
  const { page, state } = await openApp({ workOrders: [job, other] });
  const before = await page.evaluate(() => {
    const buttons = root => [...root.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
    const inbox = [...document.querySelectorAll('#inbox .card')].find(c => c.innerText.includes('J5015189-00435'));
    const soon = [...document.querySelectorAll('#almostdue .card, #overdue .card')].find(c => c.innerText.includes('J5015189-00435'));
    return { inbox: buttons(inbox), soon: buttons(soon) };
  });
  assert.equal(before.inbox.includes('Accept'), true);
  assert.equal(before.inbox.includes('Decline'), true);
  assert.equal(before.soon.includes('Accept'), true);
  assert.equal(before.soon.includes('Decline'), true);

  await page.evaluate(() => {
    window.confirm = msg => { window.__confirms = (window.__confirms || []).concat(msg); return false; };
    const card = [...document.querySelectorAll('#inbox .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Accept').click();
  });
  const cancelled = await page.evaluate(() => ({
    confirms: window.__confirms || [],
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    queue: JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]')
  }));
  assert.deepEqual(cancelled.confirms, ['Accept J5015189-00435?']);
  assert.equal(cancelled.inbox.includes('J5015189-00435'), true);
  assert.equal(cancelled.queue.length, 0);

  await page.evaluate(() => {
    window.confirm = msg => { window.__confirms.push(msg); return true; };
    const card = [...document.querySelectorAll('#almostdue .card, #overdue .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Accept').click();
  });
  const accepted = await page.evaluate(() => ({
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    almost: [...document.querySelectorAll('#almostdue strong')].map(el => el.textContent.trim()),
    decisions: JSON.parse(localStorage.getItem('corrigoDecisions') || '{}'),
    queue: JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]'),
    undo: [...document.querySelectorAll('#accepted .undo-btn')].map(b => b.textContent.trim()),
    endpoint: DECISION_ENDPOINT
  }));
  assert.equal(accepted.inbox.includes('J5015189-00435'), false);
  assert.equal(accepted.accepted.includes('J5015189-00435'), true);
  assert.equal(accepted.almost.includes('J5015189-00435'), false);
  assert.equal(accepted.decisions['J5015189-00435'], 'accept');
  assert.equal(accepted.queue.length, 1);
  assert.equal(accepted.queue[0].wo, 'J5015189-00435');
  assert.equal(accepted.queue[0].decision, 'accept');
  assert.equal(typeof accepted.queue[0].ts, 'string');
  assert.deepEqual(accepted.undo, ['Undo']);
  assert.equal(accepted.endpoint, 'https://doorbell-relay-production-c59989ff.up.railway.app/decision');
  assert.equal(state.decisionPosts.length, 1);
  assert.match(state.decisionPosts[0].contentType, /application\/json/i);
  const posted = JSON.parse(state.decisionPosts[0].body);
  assert.deepEqual(Object.keys(posted).sort(), ['decision', 'ts', 'wo']);
  assert.equal(posted.wo, 'J5015189-00435');
  assert.equal(posted.decision, 'accept');
  assert.equal(typeof posted.ts, 'string');

  await page.evaluate(() => {
    const wo = JSON.parse(localStorage.getItem('corrigo_accepted')).find(w => w.number === 'J5015189-00435');
    wo.status = 'inbox';
    const inbox = JSON.parse(localStorage.getItem('corrigo_inbox') || '[]');
    inbox.unshift(wo);
    localStorage.setItem('corrigo_inbox', JSON.stringify(inbox));
    localStorage.setItem('corrigo_accepted', '[]');
    render();
  });
  const reapplied = await page.evaluate(() => ({
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number)
  }));
  assert.equal(reapplied.accepted.includes('J5015189-00435'), true);
  assert.equal(reapplied.inbox.includes('J5015189-00435'), false);

  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#accepted .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Undo').click();
  });
  const undone = await page.evaluate(() => ({
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    decisions: JSON.parse(localStorage.getItem('corrigoDecisions') || '{}'),
    queue: JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]')
  }));
  assert.equal(undone.inbox.includes('J5015189-00435'), true);
  assert.equal(undone.accepted.includes('J5015189-00435'), false);
  assert.equal(undone.decisions['J5015189-00435'], undefined);
  assert.equal(undone.queue.length, 0);
  assert.equal(state.decisionPosts.length, 1);

  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#inbox .card')].find(c => c.innerText.includes('J5991021-00465'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Accept').click();
  });
  const acceptedButtons = await page.evaluate(() => {
    const card = [...document.querySelectorAll('#accepted .card')].find(c => c.innerText.includes('J5991021-00465'));
    return [...card.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
  });
  assert.equal(acceptedButtons.includes('Accept'), false);
  assert.equal(acceptedButtons.includes('Decline'), true);
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#accepted .card')].find(c => c.innerText.includes('J5991021-00465'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Decline').click();
  });
  const declined = await page.evaluate(() => ({
    declined: JSON.parse(localStorage.getItem('corrigo_declined') || '[]').map(w => w.number),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    almost: [...document.querySelectorAll('#almostdue strong')].map(el => el.textContent.trim()),
    decisions: JSON.parse(localStorage.getItem('corrigoDecisions') || '{}'),
    undo: [...document.querySelectorAll('#declined .undo-btn')].map(b => b.textContent.trim()),
    confirms: window.__confirms
  }));
  assert.equal(declined.declined.includes('J5991021-00465'), true);
  assert.equal(declined.accepted.includes('J5991021-00465'), false);
  assert.equal(declined.inbox.includes('J5991021-00465'), false);
  assert.equal(declined.almost.includes('J5991021-00465'), false);
  assert.equal(declined.decisions['J5991021-00465'], 'decline');
  assert.deepEqual(declined.undo, ['Undo']);
  assert.equal(declined.confirms.includes('Decline J5991021-00465?'), true);
  await page.close();
});

test('queued decisions stay until the relay returns 2xx and are retried on the next flush', async () => {
  const queued = { wo: 'TEST-NO-SEND', decision: 'decline', ts: '2026-11-12T00:00:00.000Z' };
  const { page, state } = await openApp({
    workOrders: [],
    decisionStatus: 500,
    seed: { corrigoDecisionQueue: [queued] }
  });
  for (let i = 0; i < 50 && !state.decisionPosts.length; i++) {
    await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 20)));
  }
  assert.equal(state.decisionPosts.length >= 1, true);
  const first = JSON.parse(state.decisionPosts[0].body);
  assert.deepEqual(first, queued);
  assert.match(state.decisionPosts[0].contentType, /application\/json/i);
  const before = state.decisionPosts.length;
  state.decisionStatus = 204;
  await page.evaluate(() => flushDecisionQueue());
  await page.waitForFunction(() => JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]').length === 0, { timeout: 5000 });
  assert.equal(state.decisionPosts.length > before, true);
  await page.close();
});

test('Unaccept on a Declined card returns the job to Inbox and does not post', async () => {
  const job = wo({
    id: 'unaccept-declined',
    number: 'J5015189-00435',
    status: 'inbox',
    acceptBy: '11/13/2026 1:48 PM'
  });
  const { page, state } = await openApp({ workOrders: [job] });
  await page.evaluate(() => { window.confirm = () => true; });
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#inbox .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.trim() === 'Decline').click();
  });
  const declined = await page.evaluate(() => ({
    tab: JSON.parse(localStorage.getItem('corrigo_declined') || '[]').map(w => w.number),
    hasUnaccept: [...document.querySelectorAll('#declined button')].some(b => b.textContent.includes('Unaccept'))
  }));
  assert.deepEqual(declined.tab, ['J5015189-00435']);
  assert.equal(declined.hasUnaccept, true);
  const posts = state.decisionPosts.length;
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#declined .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.includes('Unaccept')).click();
  });
  const after = await page.evaluate(() => {
    render();
    return {
      inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
      declined: JSON.parse(localStorage.getItem('corrigo_declined') || '[]').map(w => w.number),
      accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
      decisions: JSON.parse(localStorage.getItem('corrigoDecisions') || '{}'),
      queue: JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]')
    };
  });
  assert.deepEqual(after.inbox, ['J5015189-00435']);
  assert.deepEqual(after.declined, []);
  assert.deepEqual(after.accepted, []);
  assert.equal(after.decisions['J5015189-00435'], undefined);
  assert.deepEqual(after.queue, []);
  assert.equal(state.decisionPosts.length, posts);
  await page.close();
});

test('Almost Due Unaccept returns the job to Inbox and a reload keeps it there', async () => {
  const savedJob = wo({
    id: 'almost-saved',
    number: 'J5015189-00435',
    status: 'saved',
    acceptBy: mountainStamp(26 * 60 * 60 * 1000),
    completeBy: mountainStamp(20 * 24 * 60 * 60 * 1000)
  });
  const { page, state } = await openApp({ workOrders: [], seed: { corrigo_saved: [savedJob] } });
  const buttons = await page.evaluate(() => {
    show('almostdue');
    const card = [...document.querySelectorAll('#almostdue .card')].find(c => c.innerText.includes('J5015189-00435'));
    return [...card.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
  });
  assert.equal(buttons.includes('Accept'), true);
  assert.equal(buttons.includes('Decline'), true);
  assert.equal(buttons.includes('↩ Unaccept'), true);
  const posts = state.decisionPosts.length;
  await page.evaluate(() => {
    const card = [...document.querySelectorAll('#almostdue .card')].find(c => c.innerText.includes('J5015189-00435'));
    [...card.querySelectorAll('button')].find(b => b.textContent.includes('Unaccept')).click();
  });
  const moved = await page.evaluate(() => ({
    inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
    saved: JSON.parse(localStorage.getItem('corrigo_saved') || '[]').map(w => w.number),
    accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number),
    decisions: JSON.parse(localStorage.getItem('corrigoDecisions') || '{}'),
    queue: JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]'),
    shown: document.getElementById('inbox').style.display
  }));
  assert.deepEqual(moved.inbox, ['J5015189-00435']);
  assert.deepEqual(moved.saved, []);
  assert.deepEqual(moved.accepted, []);
  assert.equal(moved.decisions['J5015189-00435'], undefined);
  assert.deepEqual(moved.queue, []);
  assert.equal(moved.shown, 'block');
  assert.equal(state.decisionPosts.length, posts);
  const kept = await page.evaluate(() => {
    const wo = JSON.parse(localStorage.getItem('corrigo_inbox'))[0];
    wo.status = 'accepted';
    wo.corrigoAccepted = true;
    localStorage.setItem('corrigo_accepted', JSON.stringify([wo]));
    localStorage.setItem('corrigo_inbox', '[]');
    render();
    return {
      inbox: JSON.parse(localStorage.getItem('corrigo_inbox') || '[]').map(w => w.number),
      accepted: JSON.parse(localStorage.getItem('corrigo_accepted') || '[]').map(w => w.number)
    };
  });
  assert.deepEqual(kept.inbox, ['J5015189-00435']);
  assert.deepEqual(kept.accepted, []);
  await page.close();
});

test('Finalize submit queues a fake finalize payload and a 400 drops only that item', async () => {
  const wo = {
    id: 'fake-fin',
    number: 'Z9999999-00001',
    status: 'completed',
    description: 'Fake hinge',
    workDescription: 'Fixed the test hinge',
    comment: '',
    photos: [
      { url: 'https://evil.example/a.jpg' },
      { url: 'https://simzy420.github.io/big-brain-ape-dashboard/wo-photos/a.jpg' },
      { data: 'data:image/jpeg;base64,abc' }
    ]
  };
  const { page, state } = await openApp({
    workOrders: [],
    decisionStatus: 500,
    seed: { corrigo_completed: [wo] }
  });
  await page.evaluate(() => openCompleteForm('fake-fin'));
  await page.evaluate(() => {
    document.getElementById('cf_hours').value = '3.5';
    document.getElementById('cf_rate').value = '65';
    document.getElementById('cf_materials').value = '42.18';
    document.getElementById('cf_dateStart').value = '2026-11-16';
    document.getElementById('cf_dateEnd').value = '2026-11-16';
    document.getElementById('cf_invoice').value = 'INV-1';
    document.getElementById('cfSubmitBtn').click();
  });
  for (let i = 0; i < 50 && !state.decisionPosts.length; i++) {
    await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 20)));
  }
  const first = JSON.parse(state.decisionPosts[0].body);
  assert.equal(first.type, 'finalize');
  assert.equal(first.wo, 'Z9999999-00001');
  assert.equal(typeof first.ts, 'string');
  assert.equal(first.data.edit, false);
  assert.equal(first.data.hours, '3.5');
  assert.equal(first.data.rate, '65');
  assert.equal(first.data.materialsCost, '42.18');
  assert.equal(first.data.dateStarted, '2026-11-16');
  assert.equal(first.data.dateCompleted, '2026-11-16');
  assert.equal(first.data.invoiceNumber, 'INV-1');
  assert.equal(first.data.workDescription, 'Fixed the test hinge');
  assert.equal(first.data.comment, 'Fixed the test hinge');
  assert.deepEqual(first.data.photos, [
    'https://evil.example/a.jpg',
    'https://simzy420.github.io/big-brain-ape-dashboard/wo-photos/a.jpg'
  ]);
  assert.match(state.decisionPosts[0].contentType, /application\/json/i);
  let queued = await page.evaluate(() => JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]'));
  assert.equal(queued.length, 1);
  await page.evaluate(() => {
    editSubmittedForm('fake-fin');
    document.getElementById('cf_hours').value = '4';
    saveCompleteForm('fake-fin');
  });
  for (let i = 0; i < 50 && state.decisionPosts.length < 2; i++) {
    await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 20)));
  }
  queued = await page.evaluate(() => JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]'));
  assert.equal(queued.length, 1);
  assert.equal(queued[0].data.edit, true);
  assert.equal(queued[0].data.hours, '4');
  assert.equal(queued[0].wo, 'Z9999999-00001');
  state.decisionStatus = 400;
  await page.evaluate(() => {
    const q = getDecisionQueue();
    q.push({ wo: 'Z9999999-00001', decision: 'accept', ts: '2026-11-13T00:00:00.000Z' });
    setDecisionQueue(q);
    flushDecisionQueue();
  });
  await page.waitForFunction(() => {
    const q = JSON.parse(localStorage.getItem('corrigoDecisionQueue') || '[]');
    return q.length === 1 && q[0].decision === 'accept';
  }, { timeout: 5000 });
  const pill = await page.evaluate(() => document.getElementById('syncStatus').innerText);
  assert.match(pill, /Finalize not sent to bot \(bad data\) - check the numbers/);
  await page.close();
});

test('a relay 401 without a saved token is not called a GitHub read failure', async () => {
  const session = await openApp({ workOrders: [plain], allowRelay: true });
  session.state.failRelay = true;
  await session.page.evaluate(() => forceReload());
  const pill = await session.page.evaluate(() => document.getElementById('syncStatus').innerText);
  assert.match(pill, /Sync failed: HTTP 401/);
  assert.equal(/read HTTP 401/.test(pill), false);
  assert.equal(/Saved GitHub token was rejected/.test(pill), false);
  await session.page.close();
});
