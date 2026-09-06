// pons_curve_fill.cjs - Pons v2 pre-graduation fill sim (zero funds).
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");
const fs = require("fs");
const RPC = "https://rpc.mainnet.chain.robinhood.com";
const FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e";
const USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168";
const WETH = "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73";
const TEST = "0x1111111111111111111111111111111111111111";
const provider = new ethers.JsonRpcProvider(RPC, 4663, { staticNetwork: true });
async function rpc(m, p) { const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) }); return r.json(); }
async function ec(tx, ov) {
  const r = await rpc("eth_call", ov ? [tx, "latest", ov] : [tx, "latest"]);
  if ("result" in r) return { ok: true, out: r.result };
  let re = ((r.error || {}).message || "").slice(0, 120);
  const d = (r.error || {}).data || "";
  if (typeof d === "string" && d.startsWith("0x08c379a0")) { const n = parseInt(d.slice(10, 74), 16) * 2; re = Buffer.from(d.slice(74, 74 + n), "hex").toString().slice(0, 120); }
  return { ok: false, reason: re };
}
const a40 = (w) => "0x" + w.toString(16).padStart(64, "0").slice(24);
async function code(a) { const r = await rpc("eth_getCode", [a, "latest"]); return (r.result || "0x").length > 2; }
async function view(to, sig, args) { const i = new ethers.Interface([sig]); return ec({ to, data: i.encodeFunctionData(sig.match(/function\s+(\w+)/)[1], args || []) }); }
function decb(n, d) { const ip = n / d; let rr = n % d, s = ip.toString() + "."; for (let k = 0; k < 12; k++) { rr *= 10n; s += (rr / d).toString(); rr %= d; } return s; }
async function ethUsd() {
  const i = new ethers.Interface(["function getPool(address,address,uint24) view returns (address)"]);
  const s0 = new ethers.Interface(["function slot0() view returns (uint160 sqrtPriceX96,int24 tick,uint16,uint16,uint16,uint8,bool)"]);
  const t0 = new ethers.Interface(["function token0() view returns (address)"]);
  for (const fee of [3000, 500, 100, 10000]) {
    const pr = await ec({ to: "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA", data: i.encodeFunctionData("getPool", [WETH, USDG, fee]) });
    if (!pr.ok || !pr.out) continue;
    const pool = a40(BigInt(pr.out)); if (BigInt(pool) === 0n) continue;
    const s = await ec({ to: pool, data: "0x3850c7bd" });
    if (s.ok && s.out) {
      let sp; try { sp = s0.decodeFunctionResult("slot0", s.out)[0]; } catch (e) { continue; }
      const tr = await ec({ to: pool, data: "0x0dfe1681" });
      let p = 0; try {
        const sq = Number(sp) / Math.pow(2, 96); const prr = sq * sq; // token1/token0 in raw units
        if (tr.ok && tr.out) { const tok0 = a40(BigInt(tr.out)); p = (tok0.toLowerCase() === WETH.toLowerCase()) ? prr * Math.pow(10, -12) : (prr * Math.pow(10, 12)); }
        else p = prr * Math.pow(10, -12);
      } catch (e) { continue; }
      if (p > 1) return p;
    }
  }
  // Fallback: Uniswap v2 WETH/USDG pair reserves.
  try {
    const i2 = new ethers.Interface(["function getPair(address,address) view returns (address)"]);
    const rr = await ec({ to: "0x8bcEaA40B9AcdfAedF85AdF4FF01F5Ad6517937f", data: i2.encodeFunctionData("getPair", [WETH, USDG]) });
    if (rr.ok && rr.out) {
      const pair = a40(BigInt(rr.out));
      if (BigInt(pair) !== 0n) {
        const t0 = await ec({ to: pair, data: "0x0dfe1681" });
        const gr = await ec({ to: pair, data: "0x0902f1ac" });
        if (gr.ok && gr.out && t0.ok && t0.out) {
          const dec = new ethers.AbiCoder().decode(["uint112", "uint112", "uint32"], gr.out);
          const t0a = a40(BigInt(t0.out));
          let p = 0;
          const raw = Number(dec[0]) / Number(dec[1]); // res0/res1
          if (t0a.toLowerCase() === WETH.toLowerCase()) p = (Number(dec[1]) / Number(dec[0])) * Math.pow(10, 12);
          else p = (Number(dec[0]) / Number(dec[1])) * Math.pow(10, 12);
          if (p > 1) return p;
        }
      }
    }
  } catch (e) { /* no v2 price */ }
  return null;
}
async function main() {
  const toks = fs.readFileSync(process.env.TFILE, "utf8").trim().split(/\s+/).filter(Boolean);
  let eth=null; try { eth = await ethUsd(); } catch(e){ console.log("ETHUSD_ERR", e.stack.split(String.fromCharCode(10)).slice(0,3).join(" | ")); }
  const rows = [];
  const fi = new ethers.Interface(["function getLaunchedToken(address) view returns (bytes)"]);
  const bi = new ethers.Interface(["function buy(uint256,uint256,address) payable returns (uint256)"]);
  for (const tok of toks) { try {
    const gt = await ec({ to: FACTORY, data: fi.encodeFunctionData("getLaunchedToken", [tok]) });
    if (!gt.ok) { rows.push({ token: tok, status: "factory-revert" }); continue; }
    let h = gt.out.slice(2); h = h.length % 64 ? h.slice(0, h.length - (h.length % 64)) : h; const words = [];
    for (let i = 0; i + 64 <= h.length; i += 64) words.push(BigInt("0x" + h.slice(i, i + 64)));
    if (words[words.length - 1] === 0n) { rows.push({ token: tok, status: "not-on-pons" }); continue; }
    let curve = null, isNat = null;
    for (const w of words) {
      if (!w) continue; const a = a40(w);
      if (!/^0x[0-9a-fA-F]{40}$/.test(a) || !(await code(a))) continue;
      const nq = await view(a, "function isNativeQuote() view returns (bool)");
      if (nq.ok && (nq.out === "0x" + "0".repeat(63) + "1" || nq.out === "0x" + "0".repeat(64))) { curve = a; isNat = BigInt(nq.out) === 1n; break; }
    }
    if (!curve) { rows.push({ token: tok, status: "curve-not-decoded" }); continue; }
    const pairR = await view(curve, "function pairToken() view returns (address)");
    const pair = pairR.ok ? a40(BigInt(pairR.out)) : "?";
    let sim = { ok: false, reason: "" };
    if (isNat && eth) {
      const wei = BigInt(Math.floor((5 / eth) * 1e18));
      const data = bi.encodeFunctionData("buy", [wei, 0n, TEST]);
      const ov = { [TEST]: { balance: "0x" + (wei + 1000000000000000n).toString(16) } };
      sim = await ec({ from: TEST, to: curve, data, value: "0x" + wei.toString(16) }, ov);
    } else if (!isNat && pair.toLowerCase() === USDG.toLowerCase()) {
      const amt = 5n * 10n ** 6n; const enc = (types, vals) => ethers.AbiCoder.defaultAbiCoder().encode(types, vals);
      // Probe USDG balance-slot index using a holder with a known balance (the USDG/WETH pool).
      let bSlot = 0;
      try {
        const pool = "0xa9188730fe85be88ad499d7d52b099e800fb0334";
        for (let b = 0; b < 10; b++) {
          const k = ethers.keccak256(enc(["address", "uint256"], [pool, b])).slice(2);
          const g = await rpc("eth_getStorageAt", [USDG, "0x" + k, "latest"]);
          let sv = 0n; try { sv = BigInt(g.result); } catch (e) { sv = 0n; }
          if (sv > 0n) { bSlot = b; break; }
        }
      } catch (e) { bSlot = 0; }
      const balK = ethers.keccak256(enc(["address", "uint256"], [TEST, bSlot])).slice(2);
      const outer = ethers.keccak256(enc(["address", "uint256"], [TEST, bSlot + 1]));
      const allK = ethers.keccak256(enc(["address", "uint256"], [curve, outer])).slice(2);
      const storage = { [balK]: "0x" + amt.toString(16).padStart(64, "0"), [allK]: "0x" + amt.toString(16).padStart(64, "0") };
      const data = bi.encodeFunctionData("buy", [amt, 0n, TEST]);
      sim = await ec({ from: TEST, to: curve, data }, { [USDG]: { storage } });
    } else { sim.reason = isNat ? "eth-price-unavailable" : "custom-pair-sim-unsupported"; }
    const ok = sim.ok && sim.out && BigInt(sim.out) > 0n;
    rows.push({ token: tok, curve, isNative: isNat, pair, status: ok ? "PASS" : "no-fill", tokensOut: ok ? BigInt(sim.out).toString() : null, reason: ok ? null : sim.reason }); } catch (e) { rows.push({ token: tok, status: "ERR", err: String(e.message).slice(0,100) }); }
    console.log(JSON.stringify(rows[rows.length - 1]));
  }
  fs.writeFileSync(process.env.OUT || "/tmp/pons.json", JSON.stringify(rows, null, 1));
}
main().catch((e) => { console.error("ERR", (e && e.stack) ? e.stack.split("\n").slice(0, 6).join(" || ") : String(e)); process.exit(1); });
