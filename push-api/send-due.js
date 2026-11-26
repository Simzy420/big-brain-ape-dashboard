import { boiseHour, testNote } from './due.js';
import { configureWebPush, sendPayload } from './deliver.js';
import { loadOrders } from './orders.js';
import { dueNotifications } from './due.js';

function apiBase() {
  return String(process.env.PUSH_API_URL || '').replace(/\/$/, '');
}

async function api(path, body) {
  const token = process.env.PUSH_API_TOKEN || '';
  const res = await fetch(apiBase() + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      authorization: 'Bearer ' + token,
      'content-type': 'application/json'
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000)
  });
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (err) { data = { error: text }; }
  if (!res.ok) {
    const message = data.error || ('HTTP ' + res.status);
    throw new Error(path + ' failed: ' + message);
  }
  return data;
}

async function dropGone(gone) {
  for (const endpoint of gone) {
    try { await api('/unsubscribe', { endpoint }); }
    catch (err) { console.error('could not remove an old phone'); }
  }
}

async function main() {
  const mode = process.env.MODE || 'daily';
  const ignoreHour = process.env.IGNORE_HOUR === '1';
  if (mode === 'daily' && !ignoreHour && boiseHour(new Date()) !== 8) {
    console.log('Not 8 AM America/Boise. Nothing to send.');
    return;
  }
  const base = apiBase();
  if (!base || !process.env.PUSH_API_TOKEN || !process.env.VAPID_PUBLIC_KEY || !process.env.VAPID_PRIVATE_KEY) {
    const message = 'GitHub Actions secrets are not set, so this workflow did not send. The Railway backup still sends reminders.';
    if (ignoreHour) throw new Error(message);
    console.error(message);
    return;
  }
  const sender = configureWebPush();
  if (!sender) throw new Error('VAPID keys could not be loaded.');
  const listed = await api('/subscriptions');
  const subs = listed.subscriptions || [];
  if (!subs.length) {
    console.log('No phones are subscribed.');
    return;
  }
  if (mode === 'test') {
    const note = testNote();
    const result = await sendPayload(sender, subs, note);
    await dropGone(result.gone);
    console.log('test sent', result.ok, 'of', subs.length);
    if (!result.ok) throw new Error('Test notification was not delivered.');
    return;
  }
  const orders = await loadOrders();
  const sent = await api('/sent');
  const notes = dueNotifications(orders, new Date(), new Set(sent.keys || []));
  if (!notes.length) {
    console.log('No reminders due today.');
    return;
  }
  const claim = await api('/claim', { keys: notes.map(note => note.key) });
  const claimed = new Set(claim.claimed || []);
  const failed = [];
  let sentCount = 0;
  for (const note of notes) {
    if (!claimed.has(note.key)) continue;
    const fresh = await api('/subscriptions');
    const result = await sendPayload(sender, fresh.subscriptions || [], note);
    await dropGone(result.gone);
    if (result.ok) {
      sentCount += 1;
      console.log('sent', note.number, note.days + 'd');
    } else {
      failed.push(note.key);
      console.error('not delivered', note.number, note.days + 'd');
    }
  }
  if (failed.length) await api('/release', { keys: failed });
  console.log('reminders delivered', sentCount, 'failed', failed.length);
  if (failed.length) throw new Error('Some reminders were not delivered.');
}

main().catch(err => {
  console.error(err && err.message ? err.message : err);
  process.exit(1);
});
