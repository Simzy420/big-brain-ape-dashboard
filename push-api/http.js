import crypto from 'node:crypto';
import { testNote } from './due.js';

const MAX_BODY = 65536;
const TEST_LIMIT = 5;
const TEST_WINDOW_MS = 60 * 60 * 1000;

function authorized(req, token) {
  if (!token) return false;
  const header = String(req.headers.authorization || '');
  const match = header.match(/^Bearer\s+(\S+)\s*$/i);
  if (!match) return false;
  const got = Buffer.from(match[1]);
  const want = Buffer.from(token);
  if (got.length !== want.length) return false;
  return crypto.timingSafeEqual(got, want);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(Object.assign(new Error('too big'), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (!chunks.length) return resolve({});
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
      catch (err) { reject(Object.assign(new Error('bad json'), { status: 400 })); }
    });
    req.on('error', reject);
  });
}

function send(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'Content-Type, Authorization'
  });
  res.end(data);
}

export function createHandler({ store, token, sendTest, runDue, now }) {
  const tests = new Map();

  function allowTest(endpoint) {
    const nowMs = Date.now();
    const prev = (tests.get(endpoint) || []).filter(stamp => nowMs - stamp < TEST_WINDOW_MS);
    if (prev.length >= TEST_LIMIT) {
      tests.set(endpoint, prev);
      return false;
    }
    prev.push(nowMs);
    tests.set(endpoint, prev);
    return true;
  }

  return async function handle(req, res) {
    const url = new URL(req.url || '/', 'http://localhost');
    const path = url.pathname;
    if (req.method === 'OPTIONS') {
      res.writeHead(204, {
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'GET, POST, OPTIONS',
        'access-control-allow-headers': 'Content-Type, Authorization',
        'access-control-max-age': '86400'
      });
      res.end();
      return;
    }
    try {
      if (req.method === 'GET' && path === '/health') {
        send(res, 200, { ok: true });
        return;
      }
      if (req.method === 'POST' && path === '/subscribe') {
        const body = await readBody(req);
        const saved = store.saveSub(body.subscription || body);
        if (!saved.ok) {
          send(res, 400, { error: 'That is not a push subscription.' });
          return;
        }
        send(res, 200, { ok: true });
        return;
      }
      if (req.method === 'POST' && path === '/unsubscribe') {
        const body = await readBody(req);
        const endpoint = body.endpoint || (body.subscription && body.subscription.endpoint);
        if (typeof endpoint === 'string' && endpoint) store.removeSub(endpoint);
        send(res, 200, { ok: true });
        return;
      }
      if (req.method === 'POST' && path === '/test') {
        const body = await readBody(req);
        const endpoint = body.endpoint || (body.subscription && body.subscription.endpoint);
        if (!endpoint || !store.hasSub(endpoint)) {
          send(res, 404, { error: 'This phone is not signed up yet.' });
          return;
        }
        if (!allowTest(endpoint)) {
          send(res, 429, { error: 'A test was just sent. Wait a little while and try again.' });
          return;
        }
        if (!sendTest) {
          send(res, 503, { error: 'Test notifications are not set up yet.' });
          return;
        }
        const sub = store.listSubs().find(item => item.endpoint === endpoint);
        const result = await sendTest([sub], testNote());
        if (!result || !result.ok) {
          send(res, 502, { error: 'The test did not go through. Try again in a minute.' });
          return;
        }
        send(res, 200, { ok: true });
        return;
      }
      if (!authorized(req, token)) {
        send(res, 401, { error: 'Unauthorized' });
        return;
      }
      if (req.method === 'GET' && path === '/subscriptions') {
        send(res, 200, { subscriptions: store.listSubs() });
        return;
      }
      if (req.method === 'GET' && path === '/sent') {
        send(res, 200, { keys: store.readSent() });
        return;
      }
      if (req.method === 'POST' && path === '/claim') {
        const body = await readBody(req);
        const keys = Array.isArray(body.keys) ? body.keys.map(key => String(key)).filter(Boolean) : [];
        send(res, 200, { claimed: store.claim(keys) });
        return;
      }
      if (req.method === 'POST' && path === '/release') {
        const body = await readBody(req);
        const keys = Array.isArray(body.keys) ? body.keys.map(key => String(key)) : [];
        store.release(keys);
        send(res, 200, { ok: true });
        return;
      }
      if (req.method === 'POST' && path === '/run-due') {
        if (!runDue) {
          send(res, 503, { error: 'Reminders are not set up yet.' });
          return;
        }
        const result = await runDue(typeof now === 'function' ? now() : new Date());
        send(res, 200, result);
        return;
      }
      send(res, 404, { error: 'Not found' });
    } catch (err) {
      const status = err && err.status ? err.status : 500;
      if (status === 400) send(res, 400, { error: 'Could not read that request.' });
      else if (status === 413) send(res, 413, { error: 'That request is too large.' });
      else {
        console.error('request failed', path);
        send(res, 500, { error: 'Something went wrong.' });
      }
    }
  };
}
