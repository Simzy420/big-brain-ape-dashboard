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

async function openApp({ workOrders = [], overrides = [], actions = [], seed = {}, fail = {} } = {}) {
  const state = { fail, writes: [] };
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
  await page.setRequestInterception(true);
  page.on('request', req => {
    const url = req.url();
    const method = req.method();
    if (method !== 'GET' && method !== 'HEAD') {
      state.writes.push(method + ' ' + url.split('?')[0]);
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
    if (/corrigo-proof\/index\.json/.test(url)) return json(req, {});
    if (/corrigo-prewritten\.json/.test(url)) return json(req, { descriptions: {} });
    req.abort();
  });
  const dialogs = [];
  page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.accept(); });
  await page.evaluateOnNewDocument(saved => {
    localStorage.clear();
    Object.keys(saved || {}).forEach(key => localStorage.setItem(key, JSON.stringify(saved[key])));
  }, seed);
  await page.goto(origin + '/corrigo-app.html', { waitUntil: 'networkidle0', timeout: 20000 });
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
  const session = await openApp({ workOrders: [plain], fail: {} });
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
