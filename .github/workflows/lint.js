const fs = require("fs");
const html = fs.readFileSync("app35.html", "utf8");

// Extract all script blocks
const re = /<script[^>]*>([\s\S]*?)<\/script>/g;
let m, js = "", idx = 0;
while ((m = re.exec(html)) !== null) {
  js += m[1] + "\n;\n";
  idx++;
}
console.log("Found " + idx + " script blocks, " + js.length + " chars total");

// String-aware brace counter
let depth = 0;
let inStr = false, strChar = "";
let inBlockComment = false, inLineComment = false;

for (let i = 0; i < js.length; i++) {
  const c = js[i];
  const nxt = js[i+1] || "";
  
  if (inLineComment) {
    if (c === "\n") inLineComment = false;
  } else if (inBlockComment) {
    if (c === "*" && nxt === "/") { inBlockComment = false; i++; }
  } else if (inStr) {
    if (c === "\\") i++;
    else if (c === strChar) inStr = false;
  } else {
    if (c === "/" && nxt === "/") { inLineComment = true; i++; }
    else if (c === "/" && nxt === "*") { inBlockComment = true; i++; }
    else if (c === "'" || c === '"' || c === "`") { inStr = true; strChar = c; }
    else if (c === "{") depth++;
    else if (c === "}") depth--;
  }
}

console.log("Final brace depth: " + depth);

// Final validation: extract JS and run node --check for real syntax validation
const { execSync } = require("child_process");
const tmpFile = "/tmp/bba_lint_check.js";
fs.writeFileSync(tmpFile, js);
try {
  execSync("node --check " + tmpFile, { stdio: "pipe" });
  console.log("OK: node --check passed — JavaScript is syntactically valid.");
  console.log("\nBrace check passed.");
} catch (e) {
  console.error("FAIL: node --check found syntax errors:");
  console.error(e.stderr ? e.stderr.toString() : e.message);
  process.exit(1);
}
