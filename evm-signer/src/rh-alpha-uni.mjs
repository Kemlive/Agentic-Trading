// rh-alpha-uni.mjs — EXACT Uniswap V3 pool data handler (native ethers JSON-RPC).
//
// Grounding: on-chain data is the single source of truth (BIS unified-ledger &
// on-chain market-microstructure literature); price comes from the pool itself,
// never an aggregator. Microstructure (swap logs) is used for peak/drawdown.
//
//   price(token0 in token1) = (sqrtPriceX96 / 2^96)^2 * 10^(dec0 - dec1)
//
// Reads slot0/token0/token1/decimals/liquidity via provider.call() (eth_call),
// plus a bounded Swap-log window for observed peak price + drawdown margin.
// Upserts results into data/live/feed/rh_alpha.json.
//
// Usage:
//   node src/rh-alpha-uni.mjs 0x<POOL> [--window 20000] [--selftest]
import fs from "fs";
import path from "path";
import { ethers } from "ethers";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", "..");
const RPC = process.env.RPC_URL || "https://rpc.mainnet.chain.robinhood.com";
const CHAIN_ID = process.env.CHAIN_ID ? Number(process.env.CHAIN_ID) : 4663;
const DB = path.join(ROOT, "data", "live", "feed", "rh_alpha.json");
const provider = new ethers.JsonRpcProvider(RPC, CHAIN_ID, { staticNetwork: true });

// Minimal ABI surfaces (kept exact, nothing loose)
const poolIface = new ethers.Interface([
  "function slot0() view returns (uint160 sqrtPriceX96, int24 tick, uint16 observationIndex, uint16 observationCardinality, uint16 observationCardinalityNext, uint8 feeProtocol, bool unlocked)",
  "function token0() view returns (address)",
  "function token1() view returns (address)",
  "function liquidity() view returns (uint128)",
  "function fee() view returns (uint24)",
]);
const erc20 = new ethers.Interface([
  "function decimals() view returns (uint8)",
  "function symbol() view returns (string)",
  "function name() view returns (string)",
]);
const SWAP = ethers.id("Swap(address,address,int256,int256,uint160,uint128,int24)");
const Q96 = 2n ** 96n;

async function view(iface, fn, args, at) {
  const data = iface.encodeFunctionData(fn, args || []);
  const hex = await provider.call({ to: at, data });
  return iface.decodeFunctionResult(fn, hex);
}

function priceFromSqrt(sqrt, d0, d1) {
  const base = Number(sqrt) / Number(Q96); // sqrtPriceX96 / 2^96
  const r = base * base;                   // (price ratio)^2, float-safe
  return r * Math.pow(10, Number(d0) - Number(d1));
}

async function fetchUniswapV3PoolData(pool, windowBlocks = 20000) {
  const out = { pool, ts: new Date().toISOString(), ok: false };
  try {
    const s0 = await view(poolIface, "slot0", [], pool);
    const t0 = (await view(poolIface, "token0", [], pool))[0];
    const t1 = (await view(poolIface, "token1", [], pool))[0];
    const [d0, d1] = await Promise.all([
      (await view(erc20, "decimals", [], t0))[0],
      (await view(erc20, "decimals", [], t1))[0],
    ]);
    let sym0 = null, sym1 = null;
    try { sym0 = (await view(erc20, "symbol", [], t0))[0]; } catch {}
    try { sym1 = (await view(erc20, "symbol", [], t1))[0]; } catch {}
    let liq = null, fee = null;
    try { liq = (await view(poolIface, "liquidity", [], pool))[0].toString(); } catch {}
    try { fee = (await view(poolIface, "fee", [], pool))[0]; } catch {}
    const sqrt = s0[0];
    const tick = s0[1];
    const px = priceFromSqrt(sqrt, d0, d1);
    Object.assign(out, { ok: true, token0: t0, token1: t1, symbol0: sym0, symbol1: sym1,
      dec0: d0, dec1: d1, sqrtPriceX96: sqrt.toString(), tick: Number(tick),
      liquidity: liq, fee: fee ? Number(fee) : null,
      priceToken0PerToken1: px, priceToken1PerToken0: px ? 1 / px : null });
    // microstructure: bounded Swap-log window -> observed max price + drawdown
    try {
      const head = await provider.getBlockNumber();
      const logs = await provider.getLogs({ address: pool, topics: [SWAP],
        fromBlock: Math.max(head - windowBlocks, 0), toBlock: head });
      let maxPx = px, maxSqrt = sqrt;
      for (const l of logs.slice(-500)) {
        const sq = BigInt("0x" + l.data.slice(0, 66).slice(2));
        const p = priceFromSqrt(sq, d0, d1);
        if (p > maxPx) { maxPx = p; maxSqrt = sq; }
      }
      out.swapsInWindow = logs.length;
      out.maxPriceWindow = maxPx;
      out.maxSqrtWindow = maxSqrt.toString();
      out.drawdownFromWindowMaxPct = maxPx > 0 ? ((px / maxPx - 1) * 100) : null;
    } catch (e) { out.historyErr = String(e.message).slice(0, 120); }
  } catch (e) { out.error = String(e.message).slice(0, 120); out.stack = String(e.stack || "").split("\n").slice(0, 4).join(" | "); }
  return out;
}

function upsertDb(rec) {
  let db = { pools: {}, updatedAt: null };
  try { db = JSON.parse(fs.readFileSync(DB, "utf8")); } catch {}
  db.pools = db.pools || {};
  db.pools[rec.pool.toLowerCase()] = rec;
  db.updatedAt = new Date().toISOString();
  const t = DB + ".tmp";
  fs.writeFileSync(t, JSON.stringify(db, null, 2));
  fs.renameSync(t, DB);
  return db;
}

async function selftest() {
  // sqrt=2^96, dec0=dec1=6 => price must be 1.0
  const r = priceFromSqrt(Q96, 6, 6);
  console.log("SELFTEST sqrt=2^96 d0=d1=6 ->", r, r.toFixed(6) === "1.000000" ? "PASS" : "FAIL");
  // USDC(6)/WETH(18): sqrt=2^96 => 10^(6-18) = 1e-12 ETH per USDC
  console.log("SELFTEST usdc/weth pair ->", priceFromSqrt(Q96, 6, 18).toExponential(3));
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--selftest")) { await selftest(); return; }
  const w = args.includes("--window") ? Number(args[args.indexOf("--window") + 1]) : 20000;
  const pools = args.filter((a) => a.startsWith("0x"));
  console.log("🔬 UniV3 handler @", new Date().toISOString(), "| factory(es) scanned: univ3 0x1F98431c8aD98523631AE4a59f267346ea31F984");
  for (const p of pools) {
    console.log("   fetching pool", p);
    const rec = await fetchUniswapV3PoolData(p, w);
    console.log("   ->", rec.ok
      ? `price0in1=${rec.priceToken0PerToken1} tick=${rec.tick} dec=${rec.dec0}/${rec.dec1} swaps=${rec.swapsInWindow ?? 0}`
      : ("ERR " + (rec.error || "") + (rec.stack ? " | " + rec.stack : "")));
    if (CHAIN_ID === 4663 && rec.ok) {
      const db = upsertDb(rec);
      console.log("   db pools now:", Object.keys(db.pools).length);
    } else {
      console.log(CHAIN_ID === 4663 ? "   (rec invalid - DB not written)" : "   (validation run on chain " + CHAIN_ID + " - DB not written)");
    }
  }
}

main().catch((e) => { console.error("handler error:", e); process.exit(1); });
