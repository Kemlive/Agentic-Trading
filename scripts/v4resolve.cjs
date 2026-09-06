// v4resolve3.cjs — full-shortlist v4 fill scan (vanilla + verified hooks), concurrent.
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");
const fs = require("fs");
const RPC = "https://rpc.mainnet.chain.robinhood.com";
const POOLMGR = "0x8366a39CC670B4001A1121B8F6A443A643e40951";
const QUOTER = "0x8Dc178eFB8111BB0973Dd9d722ebeFF267c98F94";
const USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168";
const ZERO = "0x0000000000000000000000000000000000000000";
const PONS = "0xE5e702641Ea86F4ae6cC3cDaeD2B886f976Be044";
const TWO = "0x127B3f3b7769f659C5eDBfF8b4005443f19FAAc0";
const STATIC = [100, 500, 1000, 3000, 10000];
const SPAC = [1, 2, 5, 10, 20, 40, 60, 100, 120, 200, 500, 1000];
const SIZES = [5, 25, 50];
const provider = new ethers.JsonRpcProvider(RPC, 4663, { staticNetwork: true });
const pm = new ethers.Contract(POOLMGR, ["function getSlot0(bytes32) view returns (uint160,int24,uint16,uint24)"], provider);
const quoter = new ethers.Contract(QUOTER, [
  "function quoteExactInputSingle((address currency0,address currency1,uint24 fee,int24 tickSpacing,address hooks,bool zeroForOne,uint128 exactAmount,bytes hookData)) view returns (uint256,uint256)",
], provider);

const id = (c0, c1, fee, sp, hk) => ethers.keccak256(ethers.AbiCoder.defaultAbiCoder().encode(
  ["address", "address", "uint24", "int24", "address"], [c0, c1, fee, sp, hk]));
const dec = (s) => { if (s === 0n) return "0"; let n = s < 0n ? -s : s; const ip = n / 1000000000000000000n; return Number(ip) / 1e0; };
async function decimalsOf(a) {
  const ifc = new ethers.Interface(["function decimals() view returns (uint8)"]);
  try { const r = await provider.call({ to: a, data: ifc.encodeFunctionData("decimals", []) }); return BigInt(Number(ifc.decodeFunctionResult("decimals", r)[0])); }
  catch { return 18n; }
}
async function pool(maxC, items, fn) {
  const out = []; let i = 0;
  const worker = async () => { while (i < items.length) { const j = i++; out[j] = await fn(items[j]); } };
  await Promise.all(Array.from({ length: maxC }, worker)); return out;
}

async function main() {
  const src = process.env.TFILE ? fs.readFileSync(process.env.TFILE, "utf8") : process.argv.slice(2).join(" ");
  const tokens = src.trim().split(/\s+/).filter(Boolean);
  const all = [];
  for (const raw of tokens) {
    const t = raw.toLowerCase();
    const dt = await decimalsOf(t);
    const cands = [];
    const push = (c0, c1, fee, sp, hk) => cands.push({ c0, c1, fee, sp, hk, pid: id(c0, c1, fee, sp, hk) });
    for (const o of [[t, USDG], [USDG, t]]) for (const f of STATIC) for (const sp of SPAC) push(o[0], o[1], f, sp, ZERO);
    for (const o of [[t, USDG], [USDG, t]]) for (const f of [0, 0x800000]) for (const sp of SPAC) push(o[0], o[1], f, sp, PONS);
    if (t === "0x2a4a33a2163d005d8e7f1d9ac08d14c98db288d5")
      for (const o of [[t, USDG], [USDG, t]]) for (const f of [0, 0x800000]) for (const sp of SPAC) push(o[0], o[1], f, sp, TWO);
    const checks = await pool(12, cands, async (k) => {
      try { const s = await pm.getSlot0(k.pid); return s[0] > 0n ? { k, sp: s[0] } : null; } catch { return null; }
    });
    const found = checks.filter(Boolean);
    const rows = [];
    for (const { k, sp } of found) {
      const two192 = 1n << 192n;
      const raw = parseFloat((function div(n, d) { const ip = n / d; let r = n % d; let s = ip.toString() + "."; for (let j = 0; j < 15; j++) { r *= 10n; s += (r / d).toString(); r %= d; } return s; })(sp * sp, two192));
      const mid = k.c0.toLowerCase() === USDG ? (1 / raw) * Math.pow(10, Number(dt - 6n)) : raw * Math.pow(10, Number(6n - dt));
      const zero = k.c0.toLowerCase() === USDG;
      const quotes = {}; let maxOk = 0;
      for (const usd of SIZES) {
        try {
          const r = await quoter.quoteExactInputSingle({ currency0: k.c0, currency1: k.c1, fee: k.fee, tickSpacing: k.sp, hooks: k.hk, zeroForOne: zero, exactAmount: BigInt(Math.round(usd * 1e6)), hookData: "0x" });
          const ui = Number(r[0]) / Math.pow(10, Number(dt)); const fp = usd / ui; const imp = mid ? (fp / mid - 1) : null;
          quotes["$" + usd] = { ok: true, imp: imp == null ? null : Number((imp * 100).toFixed(2)) };
          if (imp == null || Math.abs(imp) <= 0.05) maxOk = usd;
        } catch { quotes["$" + usd] = { ok: false, imp: null }; }
      }
      rows.push({ c0: k.c0, c1: k.c1, fee: k.fee, tickSpacing: k.sp, hook: k.hk, mid, maxOk, status: maxOk >= 5 ? "PASS" : "no-fill", quotes });
    }
    const rec = { token: t, decOut: Number(dt), found: rows.length, status: rows.some(r => r.status === "PASS") ? "PASS" : (rows.length ? "no-fill" : "no-v4-pool"), rows };
    all.push(rec); console.log(JSON.stringify(rec));
  }
  fs.writeFileSync(process.env.OUT || "/tmp/v4full.json", JSON.stringify(all, null, 1));
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
