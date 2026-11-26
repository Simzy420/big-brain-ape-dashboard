import fs from 'node:fs';
import path from 'node:path';

const MAX_SUBS = 20;
const MAX_SENT = 5000;

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    return fallback;
  }
}

function writeJson(file, data) {
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data));
  fs.renameSync(tmp, file);
}

export function validSubscription(sub) {
  if (!sub || typeof sub !== 'object') return false;
  if (typeof sub.endpoint !== 'string' || sub.endpoint.indexOf('https://') !== 0) return false;
  if (!sub.keys || typeof sub.keys.p256dh !== 'string' || typeof sub.keys.auth !== 'string') return false;
  if (sub.keys.p256dh.length < 8 || sub.keys.auth.length < 8) return false;
  return true;
}

export function openStore(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const subsFile = path.join(dir, 'subscriptions.json');
  const sentFile = path.join(dir, 'sent.json');

  function subscriptions() {
    const data = readJson(subsFile, { subscriptions: [] });
    return Array.isArray(data.subscriptions) ? data.subscriptions : [];
  }

  function sentKeys() {
    const data = readJson(sentFile, { keys: [] });
    return Array.isArray(data.keys) ? data.keys : [];
  }

  return {
    listSubs() {
      return subscriptions().map(sub => ({
        endpoint: sub.endpoint,
        expirationTime: sub.expirationTime == null ? null : sub.expirationTime,
        keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth }
      }));
    },
    saveSub(sub) {
      if (!validSubscription(sub)) return { ok: false };
      const list = subscriptions();
      const next = {
        endpoint: sub.endpoint,
        expirationTime: sub.expirationTime == null ? null : sub.expirationTime,
        keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth },
        savedAt: new Date().toISOString()
      };
      const idx = list.findIndex(item => item.endpoint === sub.endpoint);
      if (idx >= 0) list[idx] = next;
      else list.push(next);
      const trimmed = list.slice(-MAX_SUBS);
      writeJson(subsFile, { subscriptions: trimmed });
      return { ok: true, created: idx < 0 };
    },
    removeSub(endpoint) {
      const list = subscriptions().filter(item => item.endpoint !== endpoint);
      writeJson(subsFile, { subscriptions: list });
    },
    hasSub(endpoint) {
      return subscriptions().some(item => item.endpoint === endpoint);
    },
    readSent() {
      return sentKeys();
    },
    claim(keys) {
      const have = new Set(sentKeys());
      const claimed = [];
      (Array.isArray(keys) ? keys : []).forEach(key => {
        const id = String(key || '');
        if (!id || have.has(id)) return;
        have.add(id);
        claimed.push(id);
      });
      const stored = Array.from(have).slice(-MAX_SENT);
      writeJson(sentFile, { keys: stored });
      return claimed;
    },
    release(keys) {
      const drop = new Set((Array.isArray(keys) ? keys : []).map(key => String(key)));
      const stored = sentKeys().filter(key => !drop.has(key));
      writeJson(sentFile, { keys: stored });
    }
  };
}
