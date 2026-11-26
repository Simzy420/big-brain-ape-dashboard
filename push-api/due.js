// Deadline reminders for Sims Construction work orders.
// Calendar days are America/Boise. Each work order and milestone fires once.

export const APP_URL = 'https://simzy420.github.io/big-brain-ape-dashboard/corrigo-app.html';
export const MILESTONES = [7, 3, 1];

const SKIP_STATUS = {
  closed: 1,
  paid: 1,
  declined: 1,
  sent_to_corrigo: 1,
  completed: 1,
  submitted: 1
};

export function normStatus(value) {
  return String(value || '').toLowerCase().trim().replace(/[\s-]+/g, '_');
}

export function normNumber(value) {
  return String(value || '').replace(/[\u2010-\u2015\u2212]/g, '-').trim();
}

export function boiseParts(date) {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Boise',
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
  const map = {};
  dtf.formatToParts(date).forEach(part => {
    if (part.type !== 'literal') map[part.type] = part.value;
  });
  let hour = Number(map.hour);
  if (hour === 24) hour = 0;
  return {
    y: Number(map.year),
    m: Number(map.month),
    d: Number(map.day),
    hour,
    minute: Number(map.minute),
    second: Number(map.second)
  };
}

export function boiseHour(date) {
  return boiseParts(date).hour;
}

function mountainWallTime(year, month, day, hour, minute) {
  const timeZone = 'America/Boise';
  let utc = Date.UTC(year, month - 1, day, hour, minute, 0);
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
  for (let i = 0; i < 3; i++) {
    const map = {};
    dtf.formatToParts(new Date(utc)).forEach(part => {
      if (part.type !== 'literal') map[part.type] = part.value;
    });
    let shownHour = Number(map.hour);
    if (shownHour === 24) shownHour = 0;
    const shown = Date.UTC(Number(map.year), Number(map.month) - 1, Number(map.day), shownHour, Number(map.minute), Number(map.second));
    const target = Date.UTC(year, month - 1, day, hour, minute, 0);
    const diff = target - shown;
    if (diff === 0) break;
    utc += diff;
  }
  return new Date(utc);
}

export function parseBoise(raw) {
  const text = String(raw == null ? '' : raw);
  const match = text.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (!match) return null;
  let hour = parseInt(match[4], 10);
  const ap = match[6].toUpperCase();
  if (ap === 'AM') {
    if (hour === 12) hour = 0;
  } else if (hour !== 12) hour += 12;
  return mountainWallTime(Number(match[3]), Number(match[1]), Number(match[2]), hour, Number(match[5]));
}

export function calendarDaysUntil(deadline, now) {
  const today = boiseParts(now);
  const due = boiseParts(deadline);
  const from = Date.UTC(today.y, today.m - 1, today.d);
  const to = Date.UTC(due.y, due.m - 1, due.d);
  return Math.round((to - from) / 86400000);
}

export function deadlineYmd(deadline) {
  const part = boiseParts(deadline);
  const month = String(part.m).padStart(2, '0');
  const day = String(part.d).padStart(2, '0');
  return part.y + '-' + month + '-' + day;
}

export function milestoneKey(number, days, deadline) {
  return normNumber(number) + '|' + days + '|' + deadlineYmd(deadline);
}

function titleCase(value) {
  return String(value || '').toLowerCase().replace(/\b([a-z])/g, letter => letter.toUpperCase());
}

export function placeOf(wo) {
  const property = String(wo && wo.property || '').trim();
  if (property) return titleCase(property);
  let parts = String(wo && wo.location || '').split(',').map(part => part.trim()).filter(Boolean);
  if (parts.length && /^(US|USA|United States)$/i.test(parts[parts.length - 1])) parts.pop();
  if (parts.length >= 2 && /^[A-Za-z]{2}(?:\s+\d{5}(?:-\d{4})?)?$/.test(parts[parts.length - 1])) {
    return titleCase(parts[parts.length - 2]);
  }
  if (parts.length >= 2) return titleCase(parts[parts.length - 1]);
  return parts[0] ? titleCase(parts[0]) : 'Job site';
}

export function formatDeadline(date) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Boise',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short'
  }).format(date);
}

function deadlineRaw(wo) {
  const status = normStatus(wo.status);
  if (SKIP_STATUS[status]) return null;
  if (status === 'inbox') return wo.acceptBy;
  if (status === 'accepted' || status === 'in_progress') return wo.completeBy;
  return null;
}

export function dueNotifications(workOrders, now, sent) {
  const sentSet = sent instanceof Set ? sent : new Set(sent || []);
  const out = [];
  (Array.isArray(workOrders) ? workOrders : []).forEach(wo => {
    if (!wo || !wo.number) return;
    const raw = deadlineRaw(wo);
    if (raw == null || raw === '') return;
    const due = parseBoise(raw);
    if (!due) return;
    const days = calendarDaysUntil(due, now);
    if (MILESTONES.indexOf(days) === -1) return;
    const key = milestoneKey(wo.number, days, due);
    if (sentSet.has(key)) return;
    const number = normNumber(wo.number);
    out.push({
      key,
      number,
      days,
      title: days === 1 ? 'Work order due in 1 day' : 'Work order due in ' + days + ' days',
      body: number + ' · ' + placeOf(wo) + ' · ' + formatDeadline(due),
      url: APP_URL + '?wo=' + encodeURIComponent(number),
      tag: key
    });
  });
  return out;
}

export function testNote() {
  return {
    title: 'Sims Construction',
    body: 'Test notification. If you hear this, reminders are on.',
    url: APP_URL,
    tag: 'wo-test-' + Date.now()
  };
}
