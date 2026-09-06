// v4resolve2.cjs — Uniswap v4 RH PoolKey resolver v2 (verified hooks only).
// poolId = keccak256(160-byte PoolKey). Existence PROVEN via PoolManager.getSlot0.
// Hooks: ZERO (vanilla), PONS_MEME + TWOFOLD_DUALPOOL (verified 2026-09-05, see research/rh-hooks-20260905.md).
// bankr hook: NOT verified -> never used here.
// Usage: node v4resolve2.cjs <token> [token...]
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");

const RPC = process.env.RPC_URL || "https://rpc.mainnet.chain.robinhood.com";
const POOLMGR = "0x8366a39CC670B4001A1121B8F6A443A643e40951";
const QUOTER = "0x8Dc178eFB8111BB0973Dd9d722ebeFF267c98F94";
const USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168";
const ZERO = "0x0000000000000000000000000000000000000000";
const PONS = "0xE5e702641Ea86F4ae6cC3cDaeD2B886f976Be044";
const TWO_FOLD = "0x127B3f3b7769f659C5eDBfF8b4005443f19FAAc0";
const STATIC_FEES = [100, 500, 1000, 3000, 10000];
const DYNAMIC_FEE = 0x800000;
const SPACINGS = [1, 2, 5, 10, 20, 40, 60, 100, 120, 200, 500, 1000];
const SIZES = [5, 25, 50];
const USDG_DEC = 6n;

const provider = new ethers.JsonRpcProvider(RPC, 4663, { staticNetwork: true });
const pm = new ethers.Contract(POOLMGR, [
  "function getSlot0(bytes32) view returns (uint160, int24, uint16, uint24)",
], provider);
const quoter = new ethers.Contract(QUOTER, [
  "function quoteExactInputSingle((address currency0,address currency1,uint24 fee,int24 tickSpacing,address hooks,bool zeroForOne,uint128 exactAmount,bytes hookData)) view returns (uint256, uint256)",
], provider);

function poolId(c0, c1, fee, spacing, hook) {
  const enc = ethers.AbiCoder.defaultAbiCoder().encode(
    ["address", "address", "uint24", "int24", "address"], [c0, c1, fee, spacing, hook]);
  return ethers.keccak256(enc);
}

function decDiv(n, d) { // string decimal of n/d (18 places)
  if (n === 0n) return "0";
  const neg = n < 0n; if (neg) n = -n;
  const ip = n / d; let r = n % d; let s = ip.toString() + ".";
  for (let k = 0; k < 18; k++) { r *= 10n; s += (r / d).toString(); r %= d; }
  return (neg ? "-" : "") + s;
}

async function exists(key) {
  try {
    const s = await pm.getSlot0(poolId(key.c0, key.c1, key.fee, key.spacing, key.hook));
    return s[0] > 0n ? s[0] : null;
  } catch { return null; }
}

async function decimalsOf(a) {
  const ifc = new ethers.Interface(["function decimals() view returns (uint8)"]);
  try {
    const r = await provider.call({ to: a, data: ifc.encodeFunctionData("decimals", []) });
    return BigInt(Number(ifc.decodeFunctionResult("decimals", r)[0]));
  } catch { return 18n; }
}

async function main() {
  const tokens = process.argv.slice(2);
  const out = [];
  for (const token of tokens) {
    const t = token.toLowerCase();
    const dt = await decimalsOf(t);
    const res = { token: t, decOut: Number(dt), found: [] };
    const hooks = t === TWO_FOLD.toLowerCase()
      ? [[ZERO, STATIC_FEES], [TWO_FOLD, [DYNAMIC_FEE]]]
      : [[ZERO, STATIC_FEES], [PONS, [0, DYNAMIC_FEE]]];
    for (const [hook, fees] of hooks) {
      for (const order of [[t, USDG], [USDG, t]]) {
        const [c0, c1] = order;
        for (const fee of fees) {
          for (const spacing of SPACINGS) {
            const key = { c0, c1, fee, spacing, hook };
            const sp = await exists(key);
            if (!sp) continue;
            // mid USDG per token from sqrtPrice
            const two192 = 1n << 192n;
            const rawNum = sp * sp; // token1/token0 raw ratio * 2^192
            const raw = parseFloat(decDiv(rawNum, two192));
            let mid;
            if (c0.toLowerCase() === USDG) mid = (1 / raw) * Math.pow(10, Number(dt - USDG_DEC));
            else mid = raw * Math.pow(10, Number(USDG_DEC - dt));
            const zeroForOne = c0.toLowerCase() === USDG;
            const quotes = {};
            let maxOk = 0;
            for (const usd of SIZES) {
              const amt = BigInt(Math.round(usd * 1e6));
              try {
                const r = await quoter.quoteExactInputSingle({
                  currency0: c0, currency1: c1, fee, tickSpacing: spacing, hooks: hook,
                  zeroForOne, exactAmount: amt, hookData: "0x",
                });
                const outUi = Number(r[0]) / Math.pow(10, Number(dt));
                const fillPx = usd / outUi;
                const imp = mid ? (fillPx / mid - 1) : null;
                quotes["$" + usd] = { out, imp: imp == null ? null : Number((imp * 100).toFixed(2)) };
                if (imp == null || Math.abs(imp) <= 0.05) maxOk = usd;
              } catch { quotes["$" + usd] = { out: null, imp: null }; }
            }
            const pass = maxOk >= 5;
            res.found.push({ c0, c1, fee, tickSpacing: spacing, hook, mid, maxOk,
              status: pass ? "PASS" : "no-fill", quotes });
          }
        }
      }
    }
    out.push(res);
    console.log(JSON.stringify(res));
  }
  require("fs").writeFileSync(process.env.OUT || "/tmp/v4results.json", JSON.stringify(out));
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
