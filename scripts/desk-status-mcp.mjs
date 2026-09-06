// desk-status-mcp.mjs — LOCAL read-only MCP: one tool `desk_status()` that summarizes the whole
// Agentic-Trading desk (lanes alive?, artifact freshness, pons/rh/fastlane state, newest research).
// Data-only: reads local files + pid existence. Never signs/sends/edits.
import fs from "fs";
import os from "os";
import path from "path";
import { spawnSync } from "child_process";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const ROOT = "/Users/earn/Agentic-Trading";
const FD = path.join(ROOT, "data", "live", "feed");
const LIVE = path.join(ROOT, "data", "live");
const LOGS = path.join(ROOT, "logs", "feed");
const read = (p, d) => { try { return JSON.parse(fs.readFileSync(p)); } catch { return d; } };
const now = () => new Date();
const ageSec = (iso) => { try { const t = new Date(String(iso).replace("Z", "+00:00")); return Math.max(0, Math.round((now() - t) / 1000)); } catch { return null; } };
const pidAlive = (name) => {
  if (name === "feed_dashboard") { // launchd-managed, no pid file: detect by process
    try { const r = spawnSync("pgrep", ["-f", "feed_dashboard.py"]); const pid = parseInt(String(r.stdout || "").split("\n")[0]); return { pid: pid || null, alive: !!(pid && pid > 0) }; } catch { return { pid: null, alive: false }; }
  }
  try { const pid = parseInt(fs.readFileSync(path.join(LOGS, name + ".pid"), "utf8")); process.kill(pid, 0); return { pid, alive: true }; }
  catch { return { pid: null, alive: false }; }
};
const newest = (glob, n) => { try { const pat = new RegExp(glob); return fs.readdirSync(path.join(ROOT, "research")).filter((f) => pat.test(f)).sort().slice(-n).reverse(); } catch { return []; } };
function deskStatus() {
  const feedState = read(path.join(FD, "feed-state.json"), {});
  const coins = read(path.join(FD, "coins.json"), {});
  const rhPot = read(path.join(FD, "rh-potential.json"), {});
  const ponsFresh = read(path.join(FD, "pons-live-fresh.json"), {});
  const ponsCfg = read(path.join(LIVE, "pons-autopilot.json"), {});
  const ponsSt = read(path.join(LIVE, "pons-autopilot-state.json"), {});
  const fastPos = read(path.join(LIVE, "fastlane-positions.json"), {});
  const fastSt = read(path.join(LIVE, "fastlane-state.json"), {});
  const lanes = {};
  for (const l of ["sol", "rh", "rhpot", "merge", "bench", "ponsfresh", "ponsauto", "feed_dashboard"]) lanes[l] = pidAlive(l);
  return {
    asOf: now().toISOString(),
    lanes,
    feed: { stateAsOfAgeSec: ageSec(feedState.asOf), coinsAgeSec: ageSec(coins.asOf), tiers: (coins.top || {}).robinhood ? (coins.top.robinhood || []).length : null },
    rh: { asOfAgeSec: ageSec(rhPot.asOf), tiers: Object.fromEntries(Object.entries((rhPot.tiers || {})).map(([k, v]) => [k, v.length])) },
    pons: { freshAsOfAgeSec: ageSec(ponsFresh.asOf), freshN: ponsFresh.freshN, fill20N: ponsFresh.fill20N, cfgMode: ponsCfg.mode, cfgWallet: ponsCfg.walletAddress, pos: ponsSt.pos ? { token: (ponsSt.pos.token || "").slice(0, 10), type: ponsSt.pos.type, enteredAtAgeSec: ageSec(ponsSt.enteredAt) } : null, nDry: ponsSt.nDry, nLive: ponsSt.nLive, lastCycleAgeSec: ageSec(ponsSt.lastCycle), lastNote: (ponsSt.notes || [])[0] || null },
    fastlane: { openPositions: Array.isArray(fastPos) ? fastPos.length : (fastPos.positions || []).length, stateAgeSec: ageSec(fastSt.updatedAt || fastSt.ts) },
    newestResearch: newest(/^2026-.*\.(md|json)$/, 5),
  };
}
// minimal MCP stdio (JSON-RPC 2.0 line-delimited)
let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (ch) => {
  buf += ch;
  let idx;
  while ((idx = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, idx).trim(); buf = buf.slice(idx + 1);
    if (!line) continue;
    let msg; try { msg = JSON.parse(line); } catch { continue; }
    if (msg.method === "initialize") process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: { protocolVersion: "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: "desk-status", version: "1.0.0" } } }) + "\n");
    else if (msg.method === "tools/list") process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: { tools: [{ name: "desk_status", description: "Summarize Agentic-Trading desk lane health (pids, artifact freshness, pons/rh/fastlane state, newest research). Read-only.", inputSchema: { type: "object", properties: {} } }] } }) + "\n");
    else if (msg.method === "tools/call") {
      const out = msg.params && msg.params.name === "desk_status" ? deskStatus() : { error: "unknown tool" };
      process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: { content: [{ type: "text", text: JSON.stringify(out, null, 1) }] } }) + "\n");
    }
    // notifications (initialized etc.) get no reply
  }
});
