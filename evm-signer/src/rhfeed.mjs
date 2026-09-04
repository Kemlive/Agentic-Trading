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
    const from = Math.min(st.lastBlock + 1, latest);
    if (latest >= from) {
      const range = [from, latest];
      const created = await fetchLogs(from, latest, UNI3_FACTORY, POOL_CREATED);
      for (const l of created) {
        try {
          const t = ethers.AbiCoder.defaultAbiCoder().decode(["address", "address", "uint24", "int24", "address"], l.data);
          const pool = t[4].toLowerCase();
          st.pools.push(pool);
          log({ venue: "univ3_pool_created", chain: "robinhood", block: l.blockNumber, tx: l.transactionHash,
                logIndex: l.index, token0: t[0], token1: t[1], fee: Number(t[2]), pool, ts: new Date().toISOString() });
          events++;
        } catch {}
      }
      // pool swaps (bounded to discovered pools)
      if (st.pools.length) {
        const swaps = await fetchLogs(from, latest, st.pools.slice(-200), SWAP);
        for (const l of swaps) {
          log({ venue: "univ3_swap", chain: "robinhood", block: l.blockNumber, tx: l.transactionHash,
                logIndex: l.index, pool: l.address, topic0: SWAP, ts: new Date().toISOString() });
          events++;
        }
      }
      // asset-layer transfers (stock tokens / RWAs) for the recon'd active tokens
      let trCap = 0;
      const transfers = await fetchLogs(from, latest, ASSET_TOKENS, TRANSFER);
      for (const l of transfers) {
        if (++trCap > 120) break;
        const fromAddr = "0x" + l.topics[1].slice(26);
        const toAddr = "0x" + l.topics[2].slice(26);
        log({ venue: "asset_transfer", chain: "robinhood", block: l.blockNumber, tx: l.transactionHash,
              logIndex: l.index, token: l.address, from: fromAddr, to: toAddr, ts: new Date().toISOString() });
        events++;
      }
      st.lastBlock = latest;
    }
    passes++;
    if (passes % 3 === 0) console.log(`   pass ${passes} | block ${st.lastBlock} | pools ${st.pools.length} | events ${events}`);
    save(STATE_PATH, state);
    await sleep(3000);
  }
  console.log(`DONE passes=${passes} pools=${st.pools.length} events=${events} rows=${fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").split("\n").filter(Boolean).length : 0}`);
}

main().catch((e) => { console.error("rhfeed error:", e); process.exit(1); });
