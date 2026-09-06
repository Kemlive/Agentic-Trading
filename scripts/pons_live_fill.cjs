// pons_live_fill.cjs - live Pons v2 discovery + $5 pre-graduation fill scan (zero funds).
// Discovery = official factory TokenLaunched logs. Phase/curve/pair decoded from the official
// LaunchedToken struct layout. Sim = real eth_call + state overrides only.
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");
const fs = require("fs");
const RPC = "https://rpc.mainnet.chain.robinhood.com";
const FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e";
const USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168";
const TEST = "0x1111111111111111111111111111111111111111";
const USDG_HOLDER_POOL = "0xa9188730fe85be88ad499d7d52b099e800fb0334";
const TS = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19).replace("T", "-").replace(/-/g, "").slice(0, 14);
const PREFIX = process.env.PREFIX || ("research/pons-live-fillability-" + TS);
async function rpc(m, p) { const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) }); return r.json(); }
async function ec(tx, ov) {
  const r = await rpc("eth_call", ov ? [tx, "latest", ov] : [tx, "latest"]);
  if ("result" in r) return { ok: true, out: r.result };
  let re = ((r.error || {}).message || "").slice(0, 140);
  const d = (r.error || {}).data || "";
  if (typeof d === "string" && d.startsWith("0x08c379a0")) { const n = parseInt(d.slice(10, 74), 16) * 2; re = "revert: " + Buffer.from(d.slice(74, 74 + n), "hex").toString().slice(0, 140); }
  else if (d && d !== "0x") re = re + " [" + String(d).slice(0, 40) + "]";
  return { ok: false, reason: re };
}
const a40 = (w) => "0x" + w.toString(16).padStart(64, "0").slice(24);
async function ethUsdUsd() {
  try {
    const j = await (await fetch("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", { headers: { accept: "application/json" } })).json();
    const p = Number(((j || {}).ethereum || {}).usd);
    if (p > 50) return { price: p, src: "coingecko-simple-price" };
  } catch (e) { /* fallthrough */ }
  return null;
}
async function discover(maxTokens, maxBlocks) {
  const bn = await rpc("eth_blockNumber", []);
  const latest = parseInt(bn.result, 16);
  const t0 = ethers.id("TokenLaunched(address,address,address,address,uint256,uint256)");
  const found = new Map(); let to = latest; const out = [];
  while (found.size < maxTokens && to > latest - maxBlocks) {
    const from = Math.max(latest - maxBlocks, to - 20000);
    const gl = await rpc("eth_getLogs", [{ address: FACTORY, topics: [t0], fromBlock: "0x" + from.toString(16), toBlock: "0x" + to.toString(16) }]);
    const logs = gl.result || [];
    for (let i = logs.length - 1; i >= 0 && found.size < maxTokens; i--) {
      const tk = "0x" + logs[i].topics[1].slice(26).toLowerCase();
      if (!found.has(tk)) { found.set(tk, true); out.push(tk); }
    }
    to = from - 1;
    if (!logs.length && from === latest - maxBlocks) break;
  }
  return { tokens: out, latest, scannedTo: to, scannedFrom: latest - maxBlocks };
}
(async () => {
  const eth = await ethUsdUsd();
  // USDG balance-slot probe (once): balances mapping slot index on USDG.
  let bSlot = 0;
  const enc = (t, v) => ethers.AbiCoder.defaultAbiCoder().encode(t, v);
  for (let b = 0; b < 12; b++) {
    const k = ethers.keccak256(enc(["address", "uint256"], [USDG_HOLDER_POOL, b])).slice(2);
    const g = await rpc("eth_getStorageAt", [USDG, "0x" + k, "latest"]);
    let sv = 0n; try { sv = BigInt(g.result); } catch (e) { sv = 0n; }
    if (sv > 0n) { bSlot = b; break; }
  }
  const D = await discover(process.env.MAX || 350, process.env.BLOCKS || 400000);
  const rows = [];
  for (const tok of D.tokens) {
    const gt = await ec({ to: FACTORY, data: "0x3cf28b5a" + tok.slice(2).toLowerCase().padStart(64, "0") }); // getLaunchedToken(address)
    if (!gt.ok) { rows.push({ token: tok, status: "factory-revert", reason: gt.reason }); continue; }
    let h = gt.out.slice(2); h = h.length % 64 ? h.slice(0, h.length - (h.length % 64)) : h;
    if (h.length < 64 * 15) { rows.push({ token: tok, status: "struct-short" }); continue; }
    const w = []; for (let i = 0; i + 64 <= h.length && w.length < 15; i += 64) w.push(BigInt("0x" + h.slice(i, i + 64)));
    const exists = w[14] !== 0n, phase = Number(w[10]);
    const curve = a40(w[1]), pair = a40(w[4]);
    if (!exists) { rows.push({ token: tok, curve, status: "not-on-pons" }); continue; }
    if (phase !== 0) { rows.push({ token: tok, curve, pair, status: "not-phase0", phase }); continue; }
    const native = BigInt(pair) === 0n;
    const usdgPair = pair.toLowerCase() === USDG.toLowerCase();
    if (!native && !usdgPair) { rows.push({ token: tok, curve, pair, status: "custom-pair-skipped" }); continue; }
    const bi = new ethers.Interface(["function buy(uint256,uint256,address) payable returns (uint256)"]);
    let sim;
    if (native) {
      if (!eth) { rows.push({ token: tok, curve, pair, status: "no-fill", reason: "eth-price-unavailable" }); continue; }
      const wei = BigInt(Math.floor((5 / eth.price) * 1e18));
      const data = bi.encodeFunctionData("buy", [wei, 0n, TEST]);
      const ov = { [TEST]: { balance: "0x" + (wei + 1000000000000000n).toString(16) } };
      sim = await ec({ from: TEST, to: curve, data, value: "0x" + wei.toString(16) }, ov);
    } else {
      const amt = 5n * 10n ** 6n;
      const balK = ethers.keccak256(enc(["address", "uint256"], [TEST, bSlot])).slice(2);
      const outer = ethers.keccak256(enc(["address", "uint256"], [TEST, bSlot + 1]));
      const allK = ethers.keccak256(enc(["address", "uint256"], [curve, outer])).slice(2);
      const data = bi.encodeFunctionData("buy", [amt, 0n, TEST]);
      sim = await ec({ from: TEST, to: curve, data }, { [USDG]: { storage: { [balK]: "0x" + amt.toString(16).padStart(64, "0"), [allK]: "0x" + amt.toString(16).padStart(64, "0") } } });
    }
    const ok = sim.ok && sim.out && BigInt(sim.out) > 0n;
    rows.push({ token: tok, curve, pair, native, status: ok ? "PASS" : "no-fill", tokensOut: ok ? BigInt(sim.out).toString() : null, reason: ok ? null : (sim.reason || "execution reverted") });
    console.log(JSON.stringify(rows[rows.length - 1]));
  }
  const json = { asOf: new Date().toISOString(), quote: "USDG/ETH(native)", method: "official factory TokenLaunched logs + LaunchedToken struct decode; real eth_call + state overrides", ethUsdSource: eth ? eth.src : "unavailable", scannedTokens: D.tokens.length, latestBlock: D.latest, scannedBackTo: D.scannedTo, rows };
  fs.writeFileSync(PREFIX + ".json", JSON.stringify(json, null, 1));
  const sum = (s) => rows.filter((r) => r.status === s).length;
  const md = ["# Pons Live Discovery + Fill Scan (" + TS + " UTC)", "",
    "Source: official Pons v2 factory 0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e TokenLaunched logs.",
    "Filter: exists && phase=0 (NotGraduated); native-ETH or USDG pair only. $5 sim = real non-revert eth_call (state-override funded test EOA).",
    "ETH price for $5 sizing: " + (eth ? eth.src : "unavailable") + ".",
    "",
    "Discovered " + D.tokens.length + " unique launches (back to block " + D.scannedTo + "). PASS=" + sum("PASS") + " no-fill=" + sum("no-fill") + " not-phase0=" + sum("not-phase0") + " custom-pair-skipped=" + sum("custom-pair-skipped"),
    "", "| token | phase | curve | pair | status |" + (sum("PASS") ? " tokensOut" : ""), "|---|---|---|---|---|"];
  for (const r of rows) md.push("| `" + r.token.slice(0, 10) + "` | " + (r.phase ?? "0") + " | `" + (r.curve || "-").slice(0, 10) + "` | " + (r.native ? "ETH" : r.pair || "-") + " | " + r.status + (r.tokensOut ? " " + r.tokensOut : "") + (r.reason && r.status !== "PASS" ? " (" + r.reason.slice(0, 60) + ")" : "") + " |");
  md.push("", "Result in " + PREFIX + ".json. PASS requires real non-revert eth_call returning tokensOut>0 at $5.");
  fs.writeFileSync(PREFIX + ".md", md.join("\n"));
  console.log("DONE tokens=" + D.tokens.length + " PASS=" + sum("PASS") + " files=" + PREFIX + ".{json,md}");
})().catch((e) => { console.error("ERR", e.stack || e.message); process.exit(1); });

