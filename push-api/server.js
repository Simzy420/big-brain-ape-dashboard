import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { boiseParts } from './due.js';
import { configureWebPush, sendPayload } from './deliver.js';
import { createHandler } from './http.js';
import { loadOrders } from './orders.js';
import { runDue } from './remind.js';
import { openStore } from './store.js';

export function dataDir() {
  return process.env.DATA_DIR || process.env.RAILWAY_VOLUME_MOUNT_PATH || path.join(process.cwd(), 'data');
}

export function startServer({ store, token, sender, port, host } = {}) {
  const active = store || openStore(dataDir());
  const push = sender === undefined ? configureWebPush() : sender;
  const handler = createHandler({
    store: active,
    token: token == null ? (process.env.PUSH_API_TOKEN || '') : token,
    sendTest: push ? (subs, note) => sendPayload(push, subs, note) : null,
    runDue: async () => {
      const orders = await loadOrders();
      if (!push) return { sent: 0, reason: 'no-vapid' };
      return runDue({
        store: active,
        now: new Date(),
        orders,
        send: (subs, note) => sendPayload(push, subs, note)
      });
    }
  });
  const server = http.createServer((req, res) => {
    handler(req, res).catch(err => {
      console.error(err);
      if (!res.headersSent) res.writeHead(500, { 'content-type': 'application/json' });
      res.end('{"error":"Something went wrong."}');
    });
  });
  const listenPort = port == null ? Number(process.env.PORT || 3000) : port;
  const listenHost = host || '0.0.0.0';
  return new Promise(resolve => {
    server.listen(listenPort, listenHost, () => {
      const address = server.address();
      resolve({
        server,
        store: active,
        url: 'http://127.0.0.1:' + address.port
      });
    });
  });
}

let lastBackup = '';

export async function maybeBackup(store, sender) {
  const now = new Date();
  const parts = boiseParts(now);
  if (parts.hour !== 8 || parts.minute < 20 || parts.minute > 35) return;
  const slot = parts.y + '-' + parts.m + '-' + parts.d;
  if (lastBackup === slot) return;
  lastBackup = slot;
  try {
    if (!sender) throw new Error('no vapid');
    const orders = await loadOrders();
    const result = await runDue({
      store,
      now,
      orders,
      send: (subs, note) => sendPayload(sender, subs, note)
    });
    console.log('backup', result.reason, 'sent', result.sent);
  } catch (err) {
    lastBackup = '';
    console.error('backup failed');
  }
}

function invokedDirectly() {
  if (!process.argv[1]) return false;
  return import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (invokedDirectly()) {
  const store = openStore(dataDir());
  const sender = configureWebPush();
  if (!sender) console.error('VAPID keys are missing. Saving phones will work. Sending will not.');
  if (!process.env.PUSH_API_TOKEN) console.error('PUSH_API_TOKEN is missing. The daily job cannot read subscriptions.');
  startServer({ store, sender }).then(({ url }) => {
    console.log('listening', url);
    setInterval(() => { maybeBackup(store, sender); }, 60 * 1000);
  });
}
