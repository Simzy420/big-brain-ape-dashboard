// Railway function for Sims Construction push subscriptions.
// Deadline rules must stay in step with push-api/due.js.
import * as webpush from "web-push";

const APP_URL = "https://simzy420.github.io/big-brain-ape-dashboard/corrigo-app.html";
const MILESTONES = [7, 3, 1];
const SKIP_STATUS: Record<string, number> = {
  closed: 1,
  paid: 1,
  declined: 1,
  sent_to_corrigo: 1,
  completed: 1,
  submitted: 1,
};
const MAX_SUBS = 20;
const MAX_SENT = 5000;
const TEST_LIMIT = 5;
const TEST_WINDOW_MS = 60 * 60 * 1000;

function normStatus(value: unknown) {
  return String(value || "").toLowerCase().trim().replace(/[\s-]+/g, "_");
}
function normNumber(value: unknown) {
  return String(value || "").replace(/[\u2010-\u2015\u2212]/g, "-").trim();
}
function boiseParts(date: Date) {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Boise",
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const map: Record<string, string> = {};
  dtf.formatToParts(date).forEach((part) => {
    if (part.type !== "literal") map[part.type] = part.value;
  });
  let hour = Number(map.hour);
  if (hour === 24) hour = 0;
  return { y: Number(map.year), m: Number(map.month), d: Number(map.day), hour, minute: Number(map.minute), second: Number(map.second) };
}
function mountainWallTime(year: number, month: number, day: number, hour: number, minute: number) {
  let utc = Date.UTC(year, month - 1, day, hour, minute, 0);
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Boise",
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  for (let i = 0; i < 3; i++) {
    const map: Record<string, string> = {};
    dtf.formatToParts(new Date(utc)).forEach((part) => {
      if (part.type !== "literal") map[part.type] = part.value;
    });
    let shownHour = Number(map.hour);
    if (shownHour === 24) shownHour = 0;
    const shown = Date.UTC(Number(map.year), Number(map.month) - 1, Number(map.day), shownHour, Number(map.minute), Number(map.second));
    const diff = Date.UTC(year, month - 1, day, hour, minute, 0) - shown;
    if (diff === 0) break;
    utc += diff;
  }
  return new Date(utc);
}
function parseBoise(raw: unknown) {
  const match = String(raw == null ? "" : raw).match(/(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (!match) return null;
  let hour = parseInt(match[4], 10);
  const ap = match[6].toUpperCase();
  if (ap === "AM") { if (hour === 12) hour = 0; }
  else if (hour !== 12) hour += 12;
  return mountainWallTime(Number(match[3]), Number(match[1]), Number(match[2]), hour, Number(match[5]));
}
function calendarDaysUntil(deadline: Date, now: Date) {
  const today = boiseParts(now);
  const due = boiseParts(deadline);
  return Math.round((Date.UTC(due.y, due.m - 1, due.d) - Date.UTC(today.y, today.m - 1, today.d)) / 86400000);
}
function deadlineYmd(deadline: Date) {
  const part = boiseParts(deadline);
  return part.y + "-" + String(part.m).padStart(2, "0") + "-" + String(part.d).padStart(2, "0");
}
function titleCase(value: string) {
  return String(value || "").toLowerCase().replace(/\b([a-z])/g, (letter) => letter.toUpperCase());
}
function placeOf(wo: any) {
  const property = String(wo && wo.property || "").trim();
  if (property) return titleCase(property);
  let parts = String(wo && wo.location || "").split(",").map((part: string) => part.trim()).filter(Boolean);
  if (parts.length && /^(US|USA|United States)$/i.test(parts[parts.length - 1])) parts.pop();
  if (parts.length >= 2 && /^[A-Za-z]{2}(?:\s+\d{5}(?:-\d{4})?)?$/.test(parts[parts.length - 1])) return titleCase(parts[parts.length - 2]);
  if (parts.length >= 2) return titleCase(parts[parts.length - 1]);
  return parts[0] ? titleCase(parts[0]) : "Job site";
}
function formatDeadline(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Boise",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}
function dueNotifications(workOrders: any[], now: Date, sent: Set<string>) {
  const out: any[] = [];
  (Array.isArray(workOrders) ? workOrders : []).forEach((wo) => {
    if (!wo || !wo.number) return;
    const status = normStatus(wo.status);
    if (SKIP_STATUS[status]) return;
    const raw = status === "inbox" ? wo.acceptBy : (status === "accepted" || status === "in_progress" ? wo.completeBy : null);
    if (raw == null || raw === "") return;
    const due = parseBoise(raw);
    if (!due) return;
    const days = calendarDaysUntil(due, now);
    if (MILESTONES.indexOf(days) === -1) return;
    const key = normNumber(wo.number) + "|" + days + "|" + deadlineYmd(due);
    if (sent.has(key)) return;
    const number = normNumber(wo.number);
    out.push({
      key,
      number,
      days,
      title: days === 1 ? "Work order due in 1 day" : "Work order due in " + days + " days",
      body: number + " · " + placeOf(wo) + " · " + formatDeadline(due),
      url: APP_URL + "?wo=" + encodeURIComponent(number),
      tag: key,
    });
  });
  return out;
}

type Sub = { endpoint: string; expirationTime: number | null; keys: { p256dh: string; auth: string }; savedAt?: string };

function validSub(sub: any) {
  return !!(sub && typeof sub.endpoint === "string" && sub.endpoint.indexOf("https://") === 0 && sub.keys && typeof sub.keys.p256dh === "string" && sub.keys.p256dh.length >= 8 && typeof sub.keys.auth === "string" && sub.keys.auth.length >= 8);
}

let tail: Promise<unknown> = Promise.resolve();
function locked<T>(fn: () => Promise<T>): Promise<T> {
  const run = tail.then(fn, fn);
  tail = run.then(() => undefined, () => undefined);
  return run;
}

async function readJson<T>(name: string, fallback: T): Promise<T> {
  try {
    const text = await Bun.s3.file(name).text();
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}
async function writeJson(name: string, data: unknown) {
  await Bun.write(Bun.s3.file(name), JSON.stringify(data));
}
async function subscriptions() {
  const data = await readJson<{ subscriptions?: Sub[] }>("subscriptions.json", { subscriptions: [] });
  return Array.isArray(data.subscriptions) ? data.subscriptions : [];
}
async function sentKeys() {
  const data = await readJson<{ keys?: string[] }>("sent.json", { keys: [] });
  return Array.isArray(data.keys) ? data.keys : [];
}
function publicSub(sub: Sub) {
  return { endpoint: sub.endpoint, expirationTime: sub.expirationTime == null ? null : sub.expirationTime, keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth } };
}

function sender() {
  const pub = Bun.env.VAPID_PUBLIC_KEY || "";
  const priv = Bun.env.VAPID_PRIVATE_KEY || "";
  if (!pub || !priv) return null;
  webpush.setVapidDetails(Bun.env.VAPID_SUBJECT || "mailto:caseysims463@yahoo.com", pub, priv);
  return webpush;
}

async function sendPayload(subs: Sub[], note: any) {
  const push = sender();
  if (!push) return { ok: 0, gone: [] as string[] };
  const payload = JSON.stringify({ title: note.title, body: note.body, url: note.url, tag: note.tag || note.key });
  const gone: string[] = [];
  let ok = 0;
  for (const sub of subs) {
    try {
      await push.sendNotification(publicSub(sub), payload, { TTL: 60 * 60 * 24, urgency: "high" });
      ok += 1;
    } catch (err: any) {
      const code = err && (err.statusCode || err.status);
      if (code === 404 || code === 410) gone.push(sub.endpoint);
      else console.error("push failed", code || err?.message || "unknown");
    }
  }
  return { ok, gone };
}

async function loadOrders() {
  const urls = [
    "https://simzy420.github.io/big-brain-ape-dashboard/work-orders.json",
    "https://raw.githubusercontent.com/Simzy420/big-brain-ape-dashboard/main/work-orders.json",
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url + "?v=" + Date.now());
      if (!res.ok) continue;
      const data = await res.json();
      if (Array.isArray(data)) return data;
    } catch {
      console.error("work-orders fetch failed");
    }
  }
  throw new Error("Could not read work-orders.json");
}

async function runDue() {
  return locked(async () => {
    const subs = await subscriptions();
    if (!subs.length) return { sent: 0, claimed: 0, failed: [], reason: "no-subscriptions" };
    const notes = dueNotifications(await loadOrders(), new Date(), new Set(await sentKeys()));
    if (!notes.length) return { sent: 0, claimed: 0, failed: [], reason: "none-due" };
    const have = new Set(await sentKeys());
    const claimed: string[] = [];
    notes.forEach((note) => {
      if (!have.has(note.key)) { have.add(note.key); claimed.push(note.key); }
    });
    await writeJson("sent.json", { keys: Array.from(have).slice(-MAX_SENT) });
    const failed: string[] = [];
    let sent = 0;
    const claimedSet = new Set(claimed);
    for (const note of notes) {
      if (!claimedSet.has(note.key)) continue;
      const current = await subscriptions();
      const result = await sendPayload(current, note);
      sent += result.ok;
      if (result.gone.length) {
        const left = (await subscriptions()).filter((item) => result.gone.indexOf(item.endpoint) === -1);
        await writeJson("subscriptions.json", { subscriptions: left });
      }
      if (!result.ok) failed.push(note.key);
      else console.log("sent", note.number, note.days + "d");
    }
    if (failed.length) {
      const drop = new Set(failed);
      const keys = (await sentKeys()).filter((key) => !drop.has(key));
      await writeJson("sent.json", { keys });
    }
    return { sent, claimed: claimed.length, failed, reason: "sent" };
  });
}

function authorized(req: Request) {
  const token = Bun.env.PUSH_API_TOKEN || "";
  if (!token) return false;
  const header = req.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(\S+)\s*$/i);
  if (!match) return false;
  const got = new TextEncoder().encode(match[1]);
  const want = new TextEncoder().encode(token);
  if (got.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) diff |= got[i] ^ want[i];
  return diff === 0;
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "Content-Type, Authorization",
    },
  });
}

const tests = new Map<string, number[]>();
function allowTest(endpoint: string) {
  const now = Date.now();
  const prev = (tests.get(endpoint) || []).filter((stamp) => now - stamp < TEST_WINDOW_MS);
  if (prev.length >= TEST_LIMIT) { tests.set(endpoint, prev); return false; }
  prev.push(now);
  tests.set(endpoint, prev);
  return true;
}

Bun.serve({
  port: Number(Bun.env.PORT || 3000),
  hostname: "0.0.0.0",
  async fetch(req) {
    const url = new URL(req.url);
    const path = url.pathname;
    if (req.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "Content-Type, Authorization",
          "access-control-max-age": "86400",
        },
      });
    }
    try {
      if (req.method === "GET" && path === "/health") return json(200, { ok: true });
      const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
      if (req.method === "POST" && path === "/subscribe") {
        const sub = body.subscription || body;
        if (!validSub(sub)) return json(400, { error: "That is not a push subscription." });
        await locked(async () => {
          const list = await subscriptions();
          const next: Sub = { endpoint: sub.endpoint, expirationTime: sub.expirationTime == null ? null : sub.expirationTime, keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth }, savedAt: new Date().toISOString() };
          const idx = list.findIndex((item) => item.endpoint === sub.endpoint);
          if (idx >= 0) list[idx] = next;
          else list.push(next);
          await writeJson("subscriptions.json", { subscriptions: list.slice(-MAX_SUBS) });
        });
        return json(200, { ok: true });
      }
      if (req.method === "POST" && path === "/unsubscribe") {
        const endpoint = body.endpoint || (body.subscription && body.subscription.endpoint);
        if (typeof endpoint === "string" && endpoint) {
          await locked(async () => {
            const list = (await subscriptions()).filter((item) => item.endpoint !== endpoint);
            await writeJson("subscriptions.json", { subscriptions: list });
          });
        }
        return json(200, { ok: true });
      }
      if (req.method === "POST" && path === "/test") {
        const endpoint = body.endpoint || (body.subscription && body.subscription.endpoint);
        const list = await subscriptions();
        const sub = list.find((item) => item.endpoint === endpoint);
        if (!sub) return json(404, { error: "This phone is not signed up yet." });
        if (!allowTest(endpoint)) return json(429, { error: "A test was just sent. Wait a little while and try again." });
        if (!sender()) return json(503, { error: "Test notifications are not set up yet." });
        const result = await sendPayload([sub], {
          title: "Sims Construction",
          body: "Test notification. If you hear this, reminders are on.",
          url: APP_URL,
          tag: "wo-test-" + Date.now(),
        });
        if (!result.ok) return json(502, { error: "The test did not go through. Try again in a minute." });
        return json(200, { ok: true });
      }
      if (!authorized(req)) return json(401, { error: "Unauthorized" });
      if (req.method === "GET" && path === "/subscriptions") return json(200, { subscriptions: (await subscriptions()).map(publicSub) });
      if (req.method === "GET" && path === "/sent") return json(200, { keys: await sentKeys() });
      if (req.method === "POST" && path === "/claim") {
        const keys = Array.isArray(body.keys) ? body.keys.map((key: unknown) => String(key)).filter(Boolean) : [];
        const claimed = await locked(async () => {
          const have = new Set(await sentKeys());
          const fresh: string[] = [];
          keys.forEach((key: string) => { if (!have.has(key)) { have.add(key); fresh.push(key); } });
          await writeJson("sent.json", { keys: Array.from(have).slice(-MAX_SENT) });
          return fresh;
        });
        return json(200, { claimed });
      }
      if (req.method === "POST" && path === "/release") {
        const keys = Array.isArray(body.keys) ? body.keys.map((key: unknown) => String(key)) : [];
        await locked(async () => {
          const drop = new Set(keys);
          const kept = (await sentKeys()).filter((key) => !drop.has(key));
          await writeJson("sent.json", { keys: kept });
        });
        return json(200, { ok: true });
      }
      if (req.method === "POST" && path === "/run-due") return json(200, await runDue());
      return json(404, { error: "Not found" });
    } catch (err) {
      console.error("request failed", path);
      return json(500, { error: "Something went wrong." });
    }
  },
});
console.log("wo-push listening");
