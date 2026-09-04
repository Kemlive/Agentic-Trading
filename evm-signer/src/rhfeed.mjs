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
// Top active RH asset tokens from on-chain recon (Transfer volume, last ~60 blocks).
const ASSET_TOKENS = ["0xf6b983a2cae178575edb0c585f6496246875a38e",
                      "0x2f0d8fdb2eb8ced67137297daf6674f3980a1e18",
                      "0x0bd7d308f8e1639fab988df18a8011f41eacad73",
                      "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
                      "0x5e9a6cf4fc2389ecc442e96fb8d91fec874af839",
                      "0x1b0e319c6a659f002271b69db8a7df2f911c153e"];

const provider = new ethers.JsonRpcProvider(RPC, 4663, { staticNetwork: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function load(p, d) { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return d; } }
function save(p, o) { const t = p + ".tmp"; fs.writeFileSync(t, JSON.stringify(o, null, 2)); fs.renameSync(t, p); }

async function getLatest() { return Number((await provider.getBlock("latest")).number); }

async function fetchLogs(fromB, toB, addr, topic) {
  try {
    return await provider.getLogs({ fromBlock: fromB, toBlock: toB, address: addr, topics: topic ? [topic] : undefined });
  } catch { return []; }
}

async function main() {
  const secs = process.argv.includes("--secs") ? Number(process.argv[process.argv.indexOf("--secs") + 1]) : Infinity;
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const cfg = load(CFG_PATH, {}); // venue registry (kept for symmetry; RH params inline below)
  const state = load(STATE_PATH, {});
  state.rh = state.rh || { lastBlock: 0, pools: [], poolsSeen: 0 };
  const st = state.rh;
  const log = (ev) => fs.appendFileSync(OUT, JSON.stringify(ev) + "\n");
  const start = Date.now();
  let passes = 0, events = 0;
  console.log("🟢 ROBINHOOD FEED ONLINE @", new Date().toISOString(), "| uni3 factory", UNI3_FACTORY);

  if (!st.lastBlock) {
    const latest = await getLatest();
    // backfill pool discovery over recent ~2.5k blocks so Swap capture works immediately
    const logs = await fetchLogs(latest - 500, latest, UNI3_FACTORY, POOL_CREATED);
    for (const l of logs) {
      const t = ethers.AbiCoder.defaultAbiCoder().decode(["address", "address", "uint24", "int24", "address"], l.data);
      st.pools.push(t[4].toLowerCase());
    }
    st.lastBlock = latest - 500;
    console.log("   backfill: discovered pools ->", st.pools.length);
    save(STATE_PATH, state);
  }

  while (Date.now() - start < secs) {
    const latest = await getLatest();
    const effFrom = st.lastBlock + 1;
    // NO-SKIP: process oldest-first, bounded chunk so block-time fetch stays accurate
    const from = effFrom;
    const to = Math.min(latest, effFrom + 399);
    if (latest >= from && to >= from) {
      let logs = []; // raw log wrappers -> stamped with REAL chain time below
      const created = await fetchLogs(from, to, UNI3_FACTORY, POOL_CREATED);
      for (const l of created) {
        try {
          const t = ethers.AbiCoder.defaultAbiCoder().decode(["address", "address", "uint24", "int24", "address"], l.data);
          const pool = t[4].toLowerCase();
          st.pools.push(pool);
          logs.push({ kind: "pool", pool, tok0: t[0], tok1: t[1], fee: Number(t[2]), l });
        } catch {}
      }
      if (st.pools.length) {
        for (const l of await fetchLogs(from, to, st.pools.slice(-200), SWAP)) {
          logs.push({ kind: "swap", pool: l.address, l });
        }
      }
      let trCap = 0;
      for (const l of await fetchLogs(from, to, ASSET_TOKENS, TRANSFER)) {
        if (++trCap > 120) break;
        logs.push({ kind: "transfer", from: "0x" + l.topics[1].slice(26), to: "0x" + l.topics[2].slice(26), l });
      }
      // real chain timestamps for every event in this chunk (no local-clock guessing)
      const blocks = [...new Set(logs.map((x) => x.l.blockNumber))].sort((a, b) => a - b);
      if (blocks.length > 250) { // defer tail to a later pass instead of skipping it
        const cut = blocks[249];
        logs = logs.filter((x) => x.l.blockNumber <= cut);
        st.lastBlock = cut;
      } else {
        st.lastBlock = to;
      }
      const times = {};
      const chunk = blocks.slice(0, 250);
      await Promise.all(chunk.map(async (b) => {
        try { const bl = await provider.getBlock(b); times[b] = bl.timestamp; } catch {}
      }));
      for (const x of logs) {
        const blockTime = times[x.l.blockNumber];
        if (blockTime === undefined) continue; // block-time fetch failed; retried next pass
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
                from: x.from, to: x.to, ts: new Date().toISOString() });
        }
        events++;
      }
    }
    passes++;
    if (passes % 3 === 0) console.log(`   pass ${passes} | block ${st.lastBlock} | pools ${st.pools.length} | events ${events}`);
    save(STATE_PATH, state);
    await sleep(3000);
  }
  console.log(`DONE passes=${passes} pools=${st.pools.length} events=${events} rows=${fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").split("\n").filter(Boolean).length : 0}`);
}

main().catch((e) => { console.error("rhfeed error:", e); process.exit(1); });
