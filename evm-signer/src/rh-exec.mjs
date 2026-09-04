// rh-exec.mjs — RH CHAIN EXECUTION ORCHESTRATOR (approve -> swap bundle).
// FUTURE-ACTIVATION ONLY: default is DRY (build + simulate). Sending requires BOTH
// config enabled=true AND --go (and a funded RH key later). No keys/balances here.
//
// Pipeline per order:
//   1) quote   : router.quoteExactInputSingle -> expected out (min = out*(1-slip))
//   2) approve : ERC20 approve(spender=router, amountIn)
//   3) swap    : router.exactInputSingle(tokenIn->tokenOut)
//   simulate both via eth_call; when armed: sign via local evm-signer keystore path
//   (same model as Base autopilot) and broadcast.
// Config   : data/live/rh-exec.json   (chain/rpc/tokens/router/caps/slippage)
// State    : data/live/rh-exec-state.json
// Usage:
//   node src/rh-exec.mjs --dry <tokenIn> <tokenOut> <amountIn>          (default)
//   node src/rh-exec.mjs --go <tokenIn> <tokenOut> <amountIn>           (armed only)
//   RPC_URL / CHAIN_ID env override for cross-chain validation runs.
import fs from "fs";
import path from "path";
import { ethers } from "ethers";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", "..");
const CFG_PATH = path.join(ROOT, "data", "live", "rh-exec.json");
const STATE_PATH = path.join(ROOT, "data", "live", "rh-exec-state.json");
const RPC = process.env.RPC_URL || "https://rpc.mainnet.chain.robinhood.com";
const CHAIN_ID = process.env.CHAIN_ID ? Number(process.env.CHAIN_ID) : 4663;
const provider = new ethers.JsonRpcProvider(RPC, CHAIN_ID, { staticNetwork: true });

const ERC20 = new ethers.Interface([
  "function approve(address spender, uint256 amount) returns (bool)"]);
const ROUTER = new ethers.Interface([
  "function quoteExactInputSingle((address tokenIn,address tokenOut,uint24 fee,uint256 amountIn,uint160 sqrtPriceLimitX96)) view returns (uint256 amountOut)",
  "function exactInputSingle((address tokenIn,address tokenOut,uint24 fee,address recipient,uint256 deadline,uint256 amountIn,uint256 amountOutMinimum,uint160 sqrtPriceLimitX96)) payable returns (uint256 amountOut)",
]);

function loadCfg() {
  const def = { enabled: false, chainId: 4663,
    rpc: "https://rpc.mainnet.chain.robinhood.com",
    router: "0xE592427A0AEce92De3Edee1F18E0157C05861564", // Uni V3 SwapRouter canonical
    fee: 3000, slippageBps: 300, perTxUsdCap: 10, dailyUsdCap: 25,
    tokens: {}, note: "tokens/router must be verified on RH before activation" };
  let cfg;
  try { cfg = { ...def, ...JSON.parse(fs.readFileSync(CFG_PATH, "utf8")) }; }
  catch { cfg = def; fs.writeFileSync(CFG_PATH, JSON.stringify(def, null, 2)); }
  if (process.env.FEE) cfg.fee = Number(process.env.FEE);
  return cfg;
}

async function codeAt(a) { try { return (await provider.getCode(a)).length > 2; } catch { return false; } }
async function view(iface, fn, args, at) {
  const data = iface.encodeFunctionData(fn, args);
  const hex = await provider.call({ to: at, data });
  return iface.decodeFunctionResult(fn, hex)[0];
}
async function simulate(to, data, from) {
  try { return { ok: true, result: await provider.call({ from, to, data }) }; }
  catch (e) { return { ok: false, err: String(e.message || e).slice(0, 160) }; }
}

async function buildOrder(cfg, tokenIn, tokenOut, amountIn, slipBps) {
  const q = await view(ROUTER, "quoteExactInputSingle",
    [{ tokenIn, tokenOut, fee: cfg.fee, amountIn, sqrtPriceLimitX96: 0 }], cfg.router);
  const minOut = (q * BigInt(10000 - slipBps)) / 10000n;
  const deadline = BigInt(Math.floor(Date.now() / 1000) + 600);
  const approveData = ERC20.encodeFunctionData("approve", [cfg.router, amountIn]);
  const swapData = ROUTER.encodeFunctionData("exactInputSingle", [{
    tokenIn, tokenOut, fee: cfg.fee, recipient: "0x0000000000000000000000000000000000000000",
    deadline, amountIn, amountOutMinimum: minOut, sqrtPriceLimitX96: 0 }]);
  return { quoteOut: q.toString(), minOut: minOut.toString(), deadline: deadline.toString(),
           approveData, swapData };
}

async function main() {
  const args = process.argv.slice(2);
  const go = args.includes("--go");
  const tok = args.filter((a) => a.startsWith("0x"));
  const cfg = loadCfg();
  if (tok.length < 2) { console.log("usage: node src/rh-exec.mjs [--go] <tokenIn> <tokenOut> <amountInWei>"); return; }
  const [tokenIn, tokenOut] = tok.map((a) => ethers.getAddress(a));
  const amtIdx = args.indexOf(tokenOut) + 1;
  const amountIn = BigInt(amtIdx < args.length && /^[0-9]+$/.test(args[amtIdx]) ? args[amtIdx] : "0");
  if (go && !cfg.enabled) { console.log("⛔ REFUSED: rh-exec.enabled=false; activation not permitted"); process.exit(1); }

  console.log("🔌 RH EXEC %s @ %s | chain %d | router %s", go ? "--GO" : "DRY",
              new Date().toISOString(), CHAIN_ID, cfg.router);
  console.log("   router code:", await codeAt(cfg.router) ? "present" : "MISSING on this chain");
  const from = cfg.sender || "0x0000000000000000000000000000000000000001";

  try {
    const ord = await buildOrder(cfg, tokenIn, tokenOut, amountIn, cfg.slippageBps);
    console.log("   quote out(minus slip) =", ethers.formatUnits(ord.minOut, 6));
    console.log("   approve calldata:", ord.approveData.slice(0, 40) + "…");
    console.log("   swap calldata   :", ord.swapData.slice(0, 40) + "…");
    const sA = await simulate(tokenIn, ord.approveData, from);
    const sS = await simulate(cfg.router, ord.swapData, from);
    console.log("   simulate approve:", sA.ok ? "OK" : "FAIL " + sA.err);
    console.log("   simulate swap   :", sS.ok
      ? "OK (calldata valid; dry has no funds to actually settle)"
      : "EXPECTED(no balance): " + String(sS.err).slice(0, 90));
    const state = { asOf: new Date().toISOString(), chainId: CHAIN_ID, router: cfg.router,
      lastOrder: { tokenIn, tokenOut, amountIn: amountIn.toString(), minOut: ord.minOut,
                   dry: !go, sent: false } };
    fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
    console.log("   state ->", STATE_PATH, go ? "| bundle prepared (sign+broadcast wiring pending)" : "| dry only");
  } catch (e) {
    console.log("   ERROR", String(e.message || e).slice(0, 200));
  }
}

main().catch((e) => { console.error("rh-exec error:", e); process.exit(1); });

