// 8:20 AM America/Boise backup. The GitHub Action sends at 8:00.
// This only delivers milestones that action has not already claimed.
const parts = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Boise",
  hourCycle: "h23",
  hour: "2-digit",
}).formatToParts(new Date());
let hour = Number(parts.find((part) => part.type === "hour")?.value || "0");
if (hour === 24) hour = 0;
if (hour !== 8) {
  console.log("Not 8 AM America/Boise. Backup skipped.");
  process.exit(0);
}
const base = String(Bun.env.PUSH_API_URL || "").replace(/\/$/, "");
const token = Bun.env.PUSH_API_TOKEN || "";
if (!base || !token) {
  console.error("PUSH_API_URL or PUSH_API_TOKEN is missing.");
  process.exit(1);
}
const res = await fetch(base + "/run-due", {
  method: "POST",
  headers: { authorization: "Bearer " + token },
});
const text = await res.text();
console.log(text);
if (!res.ok) process.exit(1);
