import { dueNotifications } from './due.js';

export async function runDue({ store, now, orders, send }) {
  const subs = store.listSubs();
  if (!subs.length) return { sent: 0, claimed: 0, failed: [], reason: 'no-subscriptions' };
  const notes = dueNotifications(orders, now || new Date(), new Set(store.readSent()));
  if (!notes.length) return { sent: 0, claimed: 0, failed: [], reason: 'none-due' };
  const claimed = store.claim(notes.map(note => note.key));
  const claimedSet = new Set(claimed);
  const failed = [];
  let sent = 0;
  for (const note of notes) {
    if (!claimedSet.has(note.key)) continue;
    try {
      const result = await send(store.listSubs(), note);
      const ok = result && result.ok ? result.ok : 0;
      sent += ok;
      const gone = result && result.gone ? result.gone : [];
      gone.forEach(endpoint => store.removeSub(endpoint));
      if (!ok) failed.push(note.key);
    } catch (err) {
      console.error('reminder send failed', note.number);
      failed.push(note.key);
    }
  }
  if (failed.length) store.release(failed);
  return { sent, claimed: claimed.length, failed, reason: 'sent' };
}
