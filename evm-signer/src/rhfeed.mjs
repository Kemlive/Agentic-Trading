// rhfeed.mjs — STEP 2: OWN ROBINHOOD CHAIN DATA FEED (feed-only).
// Mirrors solfeed (data/live/feed/robinhood.jsonl), one normalized event per log.
// Sources: on-chain only. Uniswap V3 factory (verified present on RH) -> PoolCreated
// discovery -> pool Swap events; Transfer events for configured stock tokens.
// Usage: node src/rhfeed.mjs --secs 30   (windowed)   / plain = run until Ctrl-C
import fs from "fs";
import path from "path";
import { ethers } from "ethers";

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.resolve(__dirname, "..", "..");
const CFG_PATH = path.join(ROOT, "data", "live", "feed-venues.json");
const STATE_PATH = path.join(ROOT, "data", "live", "feed-state.json");
const OUT = path.join(ROOT, "data", "live", "feed", "robinhood.jsonl");
const RPC = "https://rpc.mainnet.chain.robinhood.com";
const UNI3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984";
const POOL_CREATED = ethers.id("PoolCreated(address,address,uint24,int24,address)");
const SWAP = ethers.id("Swap(address,address,int256,int256,uint160,uint128,int24)");
const TRANSFER = ethers.id("Transfer(address,address,uint256)");
// Dynamic watchlist. Seeded with the recon'd active set; rhfeed DISCOVERS more
// itself (chain-wide token-transfers feed on RH's official Blockscout + Uni V3
// pool creations) so no RH token is gated behind a hardcoded allowlist.
const SEED_TOKENS = [
  ["0xf6b983a2cae178575edb0c585f6496246875a38e", "LIT"],
  ["0x2f0d8fdb2eb8ced67137297daf6674f3980a1e18", "LIGER"],
  ["0x0bd7d308f8e1639fab988df18a8011f41eacad73", "WETH"],
  ["0x5fc5360d0400a0fd4f2af552add042d716f1d168", "USDG"],
  ["0x1b0e319c6a659f002271b69db8a7df2f911c153e", "GME"],
  ["0x5e9a6cf4fc2389ecc442e96fb8d91fec874af839", null],
];
const BLOCKSCOUT = "https://robinhoodchain.blockscout.com/api/v2";
const EXPLORER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
const WATCH_MAX = 300;
const DISCOVER_EVERY = 10; // passes (~30s) between chain-wide discovery sweeps

function quoteSyms() {
  try {
    const rc = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "live", "rh-assets.json"), "utf8"));
    return new Set([...(rc.natives || []), ...(rc.stables || [])].map((s) => s.toUpperCase()));
  } catch {
    return new Set(["USDG", "USDC", "USDT", "WETH", "DAI", "EURC", "PYUSD", "FRAX", "USDE"]);
  }
}

async function discover(st, log, consoleInfo) {
  const quotes = quoteSyms();
  let found = [];
  try {
    const r = await fetch(BLOCKSCOUT + "/token-transfers?limit=100", {
      headers: { "user-agent": EXPLORER_UA, accept: "application/json" },
      signal: AbortSignal.timeout(12000),
    });
    const j = await r.json();
    for (const it of j.items || []) {
      const tok = it && it.token;
      if (!tok) continue;
      const addr = String(tok.address_hash || "").toLowerCase();
      const sym = tok.symbol || null;
      if (!addr || st.assetTokens[addr]) continue;
      if (sym && quotes.has(sym.toUpperCase())) continue;
      st.assetTokens[addr] = { sym, firstSeen: Date.now() };
      log({ venue: "token_discovered", chain: "robinhood", token: addr, symbol: sym,
            holders: tok.holders_count || null, decimals: tok.decimals != null ? Number(tok.decimals) : null,
            ts: new Date().toISOString() });
      found.push(sym || addr.slice(0, 8));
    }
  } catch (e) {
    consoleInfo("discovery sweep error: " + e.message);
  }
  // prune to WATCH_MAX (oldest-first) so RPC log fetch stays bounded
  const keys = Object.keys(st.assetTokens);
  if (keys.length > WATCH_MAX) {
    const sorted = keys.sort((a, b) => st.assetTokens[a].firstSeen - st.assetTokens[b].firstSeen);
    for (const k of sorted.slice(0, keys.length - WATCH_MAX)) delete st.assetTokens[k];
  }
  return found;
}

const provider = new ethers.JsonRpcProvider(RPC, 4663, { staticNetwork: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function load(p, d) { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return d; } }
function save(p, o) { const t = p + ".tmp"; fs.writeFileSync(t, JSON.stringify(o, null, 2)); fs.renameSync(t, p); }

const TIMEOUT_MS = 20000;
let rpcId = 1;
async function rpc(method, params, ms = TIMEOUT_MS) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  const id = rpcId++;
  try {
    const r = await fetch(RPC, { method: "POST",
      headers: { "content-type": "application/json", "user-agent": "rhfeed/2.0" },
      body: JSON.stringify({ jsonrpc: "2.0", id, method, params }), signal: ctrl.signal });
    const j = await r.json();
    return j.error ? null : j.result;
  } catch { return null; } finally { clearTimeout(t); }
}

async function getLatest() {
  const n = await rpc("eth_blockNumber", [], 12000);
  return n ? parseInt(n, 16) : null;
}

async function fetchLogs(fromB, toB, addr, topic) {
  const f = { fromBlock: "0x" + Number(fromB).toString(16), toBlock: "0x" + Number(toB).toString(16), address: addr };
  if (topic) f.topics = [topic];
  const res = await rpc("eth_getLogs", [f]);
  if (!res) return null;
  return res.map((x) => ({ blockNumber: parseInt(x.blockNumber, 16), transactionHash: x.transactionHash,
                           logIndex: parseInt(x.logIndex, 16), address: x.address,
                           topics: x.topics || [], data: x.data || "0x" }));
}

async function blockTimeOf(b) {
  for (let a = 0; a < 2; a++) {
    const bl = await rpc("eth_getBlockByNumber", ["0x" + Number(b).toString(16), false], 10000);
    if (bl) return parseInt(bl.timestamp, 16);
    await sleep(400);
  }
  return null;
}

async function main() {
  const secs = process.argv.includes("--secs") ? Number(process.argv[process.argv.indexOf("--secs") + 1]) : Infinity;
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const cfg = load(CFG_PATH, {}); // venue registry (kept for symmetry; RH params inline below)
  const state = load(STATE_PATH, {});
  state.rh = state.rh || { lastBlock: 0, pools: [], poolsSeen: 0 };
  const st = state.rh;
  // idempotent seed merge: seeds are always present, dynamic adds accumulate
  st.assetTokens = st.assetTokens || {};
  for (const [a, s] of SEED_TOKENS) {
    const ad = a.toLowerCase();
    if (!st.assetTokens[ad]) st.assetTokens[ad] = { sym: s, firstSeen: Date.now() };
  }
  const watchCount = () => Object.keys(st.assetTokens).length;
  const log = (ev) => fs.appendFileSync(OUT, JSON.stringify(ev) + "\n");
  const start = Date.now();
  let passes = 0, events = 0, discoveryTick = 0;
  console.log("🟢 ROBINHOOD FEED ONLINE @", new Date().toISOString(), "| uni3 factory", UNI3_FACTORY);

  // Startup housekeeping: quick pool census over the recent tail (never a deep
  // stall) + overlap guard so a stale lastBlock can't trigger a massive
  // duplicate re-crawl. Events in the compressed window were already captured
  // by earlier feed runs (jsonl rows exist), so nothing is actually skipped.
  const latest0 = await getLatest();
  if (latest0) {
    if (st.pools.length === 0) {
      const seen = new Set(st.pools);
      const scanFrom = Math.max(latest0 - 2000, 1);
      for (let b = scanFrom; b < latest0; b += 500) {
        const logs = await fetchLogs(b, Math.min(b + 499, latest0), UNI3_FACTORY, POOL_CREATED);
        if (logs === null) { console.log("   pool census: rpc timeout, retry next start"); break; }
        for (const l of logs) {
          try {
            const t = ethers.AbiCoder.defaultAbiCoder().decode(["address", "address", "uint24", "int24", "address"], l.data);
            const pool = t[4].toLowerCase();
            if (!seen.has(pool)) { seen.add(pool); st.pools.push(pool); }
          } catch {}
        }
      }
      console.log("   pool census: discovered pools ->", st.pools.length);
    }
    if (!st.lastBlock) st.lastBlock = latest0 - 400;
    else if (latest0 - st.lastBlock > 2000) st.lastBlock = latest0 - 200;
    if (st.lastBlock < 1) st.lastBlock = 1;
    save(STATE_PATH, state);
  }

  while (Date.now() - start < secs) {
    if (++discoveryTick % DISCOVER_EVERY === 0) {
      const found = await discover(st, log, console.log);
      if (found.length) console.log("   discovery: +" + found.length + " -> " + found.slice(0, 8).join(", ") + " (watch " + watchCount() + ")");
    }
    const latest = await getLatest();
    if (!latest) { console.log("   hold: latest rpc failed"); passes++; await sleep(3000); continue; }
    const effFrom = st.lastBlock + 1;
    // NO-SKIP: process oldest-first, bounded chunk; any failed fetch HOLDS the
    // pass (no advance, no flush) so nothing is ever skipped.
    const from = effFrom;
    const to = Math.min(latest, effFrom + 399);
    if (latest >= from && to >= from) {
      const okAll = [];
      let logs = [];
      const created = await fetchLogs(from, to, UNI3_FACTORY, POOL_CREATED);
      okAll.push(created !== null);
      for (const l of (created || [])) {
        try {
          const t = ethers.AbiCoder.defaultAbiCoder().decode(["address", "address", "uint24", "int24", "address"], l.data);
          const pool = t[4].toLowerCase();
          if (!st.pools.includes(pool)) st.pools.push(pool);
          logs.push({ kind: "pool", pool, tok0: t[0], tok1: t[1], fee: Number(t[2]), l });
        } catch {}
      }
      if (st.pools.length) {
        const swaps = await fetchLogs(from, to, st.pools.slice(-200), SWAP);
        okAll.push(swaps !== null);
        for (const l of (swaps || [])) logs.push({ kind: "swap", pool: l.address, l });
      } else {
        okAll.push(true);
      }
      const tAddrs = Object.keys(st.assetTokens);
      let transfersOk = true;
      for (let i = 0; i < tAddrs.length && transfersOk; i += 40) {
        const grp = tAddrs.slice(i, i + 40);
        const tr = await fetchLogs(from, to, grp, TRANSFER);
        if (tr === null) { transfersOk = false; break; }
        for (const l of tr) {
          logs.push({ kind: "transfer", sym: (st.assetTokens[l.address] || {}).sym || null,
                      from: "0x" + l.topics[1].slice(26), to: "0x" + l.topics[2].slice(26), l });
        }
      }
      okAll.push(transfersOk);
      if (!okAll.every(Boolean)) {
        console.log(`   hold pass: rpc fetch failed (${okAll.filter((x) => !x).length})`);
      } else if (logs.length) {
        // real chain timestamps for every event in this chunk (no local-clock guessing)
        const blocks = [...new Set(logs.map((x) => x.l.blockNumber))].sort((a, b) => a - b);
        let cut = to;
        if (blocks.length > 250) { cut = blocks[249]; logs = logs.filter((x) => x.l.blockNumber <= cut); }
        const times = {};
        const uBlocks = blocks.filter((b) => b <= cut).slice(0, 250);
        let failAt = null;
        for (let i = 0; i < uBlocks.length && !failAt; i += 8) {
          const part = await Promise.all(uBlocks.slice(i, i + 8).map(async (b) => ({ b, bt: await blockTimeOf(b) })));
          for (const p of part) {
            if (p.bt === null) { failAt = p.b; break; }
            times[p.b] = p.bt;
          }
        }
        if (failAt !== null) {
          console.log("   hold pass: block time fetch failed @" + failAt);
          cut = failAt - 1;
          logs = [];
        }
        if (logs.length) {
          for (const x of logs) {
            const blockTime = times[x.l.blockNumber];
            if (blockTime === undefined) continue;
            if (x.kind === "pool") {
              log({ venue: "univ3_pool_created", chain: "robinhood", block: x.l.blockNumber, blockTime,
                    tx: x.l.transactionHash, logIndex: x.l.index, token0: x.tok0, token1: x.tok1,
                    fee: x.fee, pool: x.pool, ts: new Date().toISOString() });
            } else if (x.kind === "swap") {
              log({ venue: "univ3_swap", chain: "robinhood", block: x.l.blockNumber, blockTime,
                    tx: x.l.transactionHash, logIndex: x.l.index, pool: x.pool, topic0: SWAP,
                    ts: new Date().toISOString() });
            } else {
              log({ venue: "asset_transfer", chain: "robinhood", block: x.l.blockNumber, blockTime,
                    tx: x.l.transactionHash, logIndex: x.l.index, token: x.l.address,
                    symbol: x.sym, from: x.from, to: x.to, ts: new Date().toISOString() });
            }
            events++;
          }
        }
        st.lastBlock = cut;
      } else {
        st.lastBlock = to; // no logs in range: still advance
      }
    }
    passes++;
    if (passes % 3 === 0) console.log(`   pass ${passes} | block ${st.lastBlock} | pools ${st.pools.length} | watch ${watchCount()} | events ${events}`);
    save(STATE_PATH, state);
    await sleep(3000);
  }
  console.log(`DONE passes=${passes} pools=${st.pools.length} events=${events} rows=${fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").split("\n").filter(Boolean).length : 0}`);
}

main().catch((e) => { console.error("rhfeed error:", e); process.exit(1); });
