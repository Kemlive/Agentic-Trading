// pons_size_scan.cjs — freshness gate (phase=0 + real $5 sim NOW) + $20 sizing + impact rank.
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");
const fs = require("fs");
const R = "https://rpc.mainnet.chain.robinhood.com";
const FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e";
const USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168";
const TEST = "0x1111111111111111111111111111111111111111";
const ROOT = "/Users/earn/Agentic-Trading";
const FEED = ROOT + "/data/live/feed/rh-potential.json";
const MAX = parseInt(process.env.MAX || "80", 10);
async function rpc(m, p) { const x = await fetch(R, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) }); return x.json(); }
async function ec(tx, ov) {
  const r = await rpc("eth_call", ov ? [tx, "latest", ov] : [tx, "latest"]);
  if ("result" in r) return { ok: true, out: r.result };
  return { ok: false, reason: String((r.error || {}).message || "revert").slice(0, 70) };
}
const a40 = (w) => "0x" + w.toString(16).padStart(64, "0").slice(24);
const erc = new ethers.Interface(["function allowance(address,address) view returns (uint256)"]);
const bi = new ethers.Interface(["function buy(uint256,uint256,address) payable returns (uint256)"]);
async function ethUsd() {
  try { const j = await (await fetch("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")).json(); const p = Number(((j || {}).ethereum || {}).usd); if (p > 50) return p; } catch (e) { }
  return null;
}
async function launchState(tok) {
  const gt = await ec({ to: FACTORY, data: "0x3cf28b5a" + tok.slice(2).toLowerCase().padStart(64, "0") });
  if (!gt.ok || !gt.out) return null;
  let h = gt.out.slice(2); h = h.length % 64 ? h.slice(0, h.length - (h.length % 64)) : h;
  if (h.length < 64 * 15) return null;
  const w = []; for (let i = 0; i + 64 <= h.length && w.length < 15; i += 64) w.push(BigInt("0x" + h.slice(i, i + 64)));
  return { exists: w[14] !== 0n, phase: Number(w[10]), curve: a40(w[1]), pair: a40(w[4]) };
}
(async () => {
  const eth = await ethUsd();
  const feed = JSON.parse(fs.readFileSync(FEED));
  const rows = ((feed.tiers || {})["pons-live"] || []).slice(0, MAX);
  // owner map for USDG-pair rows (real-holder replay source)
  const ownerMap = {};
  try {
    const rep = JSON.parse(fs.readFileSync(ROOT + "/research/pons-usdg-pair-replay-20260905-1123.json"));
    for (const rr of rep.rows || []) { if (rr.verdict === "PASS" && rr.detail && rr.detail.owner) ownerMap[rr.token.toLowerCase()] = rr.detail.owner; }
  } catch (e) { }
  const out = [];
  for (const c of rows) {
    const tok = String(c.key || "").toLowerCase();
    const typ = String(c.type || "");
    const st = await launchState(tok);
    if (!st || !st.exists || st.phase !== 0) { out.push({ token: tok, type: typ, status: "stale-or-not-live", reason: st ? "phase=" + st.phase : "launch-decode-fail" }); console.log(JSON.stringify(out[out.length - 1])); continue; }
    let t5 = null, t20 = null, note = null;
    if (typ === "pons-native") {
      if (!eth) { out.push({ token: tok, type: typ, status: "no-price" }); continue; }
      const w5 = BigInt(Math.floor((5 / eth) * 1e18)), w20 = BigInt(Math.floor((20 / eth) * 1e18));
      const ov = (w) => ({ [TEST]: { balance: "0x" + (w + 1000000000000000n).toString(16) } });
      const d5 = bi.encodeFunctionData("buy", [w5, 0n, TEST]);
      const s5 = await ec({ from: TEST, to: st.curve, data: d5, value: "0x" + w5.toString(16) }, ov(w5));
      t5 = s5.ok ? BigInt(s5.out) : null;
      if (t5) { const d20 = bi.encodeFunctionData("buy", [w20, 0n, TEST]); const s20 = await ec({ from: TEST, to: st.curve, data: d20, value: "0x" + w20.toString(16) }, ov(w20)); t20 = s20.ok ? BigInt(s20.out) : null; if (!t20) note = "fill20-revert"; }
    } else if (typ === "pons-usdg") {
      const owner = ownerMap[tok];
      if (!owner) { out.push({ token: tok, type: typ, status: "no-holder-on-record" }); continue; }
      const al = await ec({ to: USDG, data: erc.encodeFunctionData("allowance", [owner, st.curve]) });
      const allow = al.ok ? BigInt(al.out) : 0n;
      const d5 = bi.encodeFunctionData("buy", [5n * 10n ** 6n, 0n, TEST]);
      const s5 = await ec({ from: owner, to: st.curve, data: d5 });
      t5 = s5.ok ? BigInt(s5.out) : null;
      if (allow >= 20n * 10n ** 6n && t5) { const d20 = bi.encodeFunctionData("buy", [20n * 10n ** 6n, 0n, TEST]); const s20 = await ec({ from: owner, to: st.curve, data: d20 }); t20 = s20.ok ? BigInt(s20.out) : null; if (!t20) note = "fill20-revert"; }
    } else { out.push({ token: tok, type: typ, status: "unknown-type" }); continue; }
    const fresh = t5 !== null && t5 > 0n;
    let impactPct = null;
    if (fresh && t20 && t20 > 0n) {
      const q5 = typ === "pons-native" ? 5 : 5; const q20 = 20; // quote not needed in raw terms (ratio independent of scale/decimals when quote unit same)
      const p5 = q5 / Number(t5), p20 = q20 / Number(t20);
      impactPct = Math.round((p20 / p5 - 1) * 10000) / 100;
    }
    out.push({ token: tok, type: typ, curve: st.curve, phase: st.phase, status: fresh ? "fresh-PASS" : "no-fill5", t5: t5 ? t5.toString() : null, t20: t20 ? t20.toString() : null, impactPct, note });
    console.log(JSON.stringify(out[out.length - 1]));
  }
  const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 12) + "-" + new Date().toISOString().slice(11, 16).replace(":", "");
  const base = ROOT + "/research/pons-size-rank-" + ts;
  fs.writeFileSync(base + ".json", JSON.stringify({ asOf: new Date().toISOString(), ethUsd: eth, n: out.length, rows: out }, null, 1));
  const f = out.filter((r) => r.status === "fresh-PASS");
  const ok20 = f.filter((r) => r.t20);
  f.sort((a, b) => (a.impactPct ?? 1e9) - (b.impactPct ?? 1e9));
  const md = ["# Pons live candidates — freshness gate + $5→$20 sizing (" + ts + " UTC)", "",
    "Universe: pons-live feed tier (" + out.length + "). Fresh = phase 0 AND real non-revert $5 buy NOW. impact = avg-price lift moving $5→$20.",
    "Fresh PASS: " + f.length + " | also fill $20: " + ok20.length + " | stale/not-phase0/no-fill5: " + (out.length - f.length),
    "", "## Top 30 by impact (fresh, fills $5)", "| token | type | impact% | t5 | t20 |", "|---|---|---|---|---|"];
  for (const r of f.slice(0, 30)) md.push("| `" + r.token.slice(0, 10) + "` | " + r.type + " | " + (r.impactPct ?? "n/a") + " | " + (r.t5 || "-").slice(0, 18) + "… | " + (r.t20 ? (r.t20.slice(0, 18) + "…") : "-") + " |");
  md.push("", "## Stale / not-fresh (" + (out.length - f.length) + ")", "");
  for (const r of out.filter((x) => x.status !== "fresh-PASS")) md.push("- `" + r.token.slice(0, 10) + "` " + r.type + " → " + r.status + (r.reason ? " (" + r.reason + ")" : "") + (r.note ? " " + r.note : ""));
  fs.writeFileSync(base + ".md", md.join("\n"));
  // Live freshness feed (downstream/dashboard read this; rh_potential publishes it into pons-live tier)
  const freshFeed = { asOf: new Date().toISOString(), ethUsd: eth, universeN: out.length,
    freshN: f.length, fill20N: ok20.length,
    rows: f.map((r) => ({ token: r.token, type: r.type, curve: r.curve, t5: r.t5, t20: r.t20, impactPct: r.impactPct })),
    stale: out.filter((r) => r.status !== "fresh-PASS") };
  fs.writeFileSync(ROOT + "/data/live/feed/pons-live-fresh.json", JSON.stringify(freshFeed, null, 1));
  console.log("DONE n=" + out.length + " fresh=" + f.length + " fill20=" + ok20.length + " → " + base);
})().catch((e) => { console.error("ERR", e.stack || e.message); process.exit(1); });

