import webpush from 'web-push';

export function configureWebPush(env) {
  const source = env || process.env;
  const pub = source.VAPID_PUBLIC_KEY || '';
  const priv = source.VAPID_PRIVATE_KEY || '';
  const subject = source.VAPID_SUBJECT || 'mailto:caseysims463@yahoo.com';
  if (!pub || !priv) return null;
  webpush.setVapidDetails(subject, pub, priv);
  return webpush;
}

export async function sendPayload(sender, subs, note) {
  const payload = JSON.stringify({
    title: note.title,
    body: note.body,
    url: note.url,
    tag: note.tag || note.key
  });
  const gone = [];
  let ok = 0;
  for (const sub of subs) {
    try {
      await sender.sendNotification(sub, payload, { TTL: 60 * 60 * 24, urgency: 'high' });
      ok += 1;
    } catch (err) {
      const code = err && (err.statusCode || err.status);
      if (code === 404 || code === 410) gone.push(sub.endpoint);
      else console.error('push failed', code || (err && err.message) || 'unknown');
    }
  }
  return { ok, gone };
}
