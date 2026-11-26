import fs from 'node:fs';

const URLS = [
  'https://simzy420.github.io/big-brain-ape-dashboard/work-orders.json',
  'https://raw.githubusercontent.com/Simzy420/big-brain-ape-dashboard/main/work-orders.json'
];

export async function loadOrders() {
  for (const url of URLS) {
    try {
      const res = await fetch(url + '?v=' + Date.now(), { cache: 'no-store', signal: AbortSignal.timeout(20000) });
      if (!res.ok) continue;
      const data = await res.json();
      if (Array.isArray(data)) return data;
    } catch (err) {
      console.error('work-orders fetch failed', url);
    }
  }
  try {
    const file = new URL('../work-orders.json', import.meta.url);
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.error('local work-orders.json unavailable');
  }
  throw new Error('Could not read work-orders.json');
}
