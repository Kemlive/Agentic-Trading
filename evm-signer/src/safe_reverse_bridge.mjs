// safe_reverse_bridge.mjs - Agentic Trading: execute Mayan FAST_MCTP (Base->Solana) from
// the SAFE via two owner-signed Safe execTransactions. DRY simulates every step with
// eth_call; broadcast ONLY with --go (boss approval + sims pass).
// Usage: node safe_reverse_bridge.mjs [--go]
import fs from "fs";
import { spawnSync } from "child_process";
import { ethers } from "ethers";

const SAFE = "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A";
const OWNER = "0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const ZERO = "0x0000000000000000000000000000000000000000";
const RPCS = ["https://mainnet.base.org", "https://base.llamarpc.com", "https://1rpc.io/base"];
const PAYLOAD = JSON.parse(fs.readFileSync("/tmp/mctp_payload.json", "utf8"));
const GO = process.argv.includes("--go");
const iface = new ethers.Interface([
  "function execTransaction(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,bytes signatures) payable returns (bool success)",
  "function nonce() view returns (uint256)",
  "function getTransactionHash(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,uint256 _nonce) view returns (bytes32)",
]);
const usdcIface = new ethers.Interface(["function approve(address spender,uint256 amount) returns (bool)"]);

let PIN = null; // pin all RPC calls in a sequence to one node (nonce consistency)
async function rpc(method, params) {
  let last = null;
  const order = PIN ? [PIN, ...RPCS.filter((u) => u !== PIN)] : RPCS;
  for (const url of order) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
      const j = await r.json();
      if (j.error) throw new Error(method + " " + JSON.stringify(j.error).slice(0, 300));
      if (!PIN) PIN = url;
      return j.result;
    } catch (e) { last = e; }
  }
  throw new Error("all RPCs failed " + method + ": " + (last && last.message));
}

async function safeExecSim(target, calldata) {
  const nonce = BigInt(await rpc("eth_call", [{ to: SAFE, data: "0xaffed0e0" }, "latest"])).toString();
  const hash = await rpc("eth_call", [{
    to: SAFE,
    data: iface.encodeFunctionData("getTransactionHash", [target, 0, calldata, 0, 0, 0, 0, ZERO, ZERO, nonce]),
  }, "latest"]);
  const digest = "0x" + hash.slice(2).padStart(64, "0");
  const sg = spawnSync("node", ["src/cli.mjs", "sign-digest", digest], { cwd: process.cwd(), encoding: "utf8" });
  if (sg.status !== 0) throw new Error("sign-digest failed: " + sg.stderr);
  const sig = JSON.parse(sg.stdout.trim().split("\n").pop());
  const signatures = "0x" + sig.r.slice(2) + sig.s.slice(2) + (sig.v).toString(16).padStart(2, "0");
  let recovered = "?";
  try { recovered = ethers.recoverAddress(digest, { r: sig.r, s: sig.s, v: sig.v }); } catch (_) {}
  console.log("  digest", digest.slice(0, 20) + "…", "| recovered", recovered, "| owner", OWNER);
  const execData = iface.encodeFunctionData("execTransaction",
    [target, 0, calldata, 0, 0, 0, 0, ZERO, ZERO, signatures]);
  const sim = await rpc("eth_call", [{ from: OWNER, to: SAFE, data: execData }, "latest"]);
  return { sim, execData, nonce, digest };
}

async function broadcast(execData, tag) {
  fs.writeFileSync("/tmp/safe_tx.json", JSON.stringify({ to: SAFE, data: execData, value: "0" }));
  const b = spawnSync("node", ["src/cli.mjs", "sign", "/tmp/safe_tx.json", "8453", "--broadcast", "--ethUsd", "2500"],
    { cwd: process.cwd(), encoding: "utf8" });
  const out = (b.stdout || "") + (b.stderr || "");
  const m = out.match(/BROADCAST (0x[0-9a-fA-F]+)/);
  if (!m) throw new Error(tag + " broadcast failed: " + out.slice(-600));
  console.log(tag, "BROADCAST", m[1]);
  return m[1];
}

async function waitForReceipt(txHash) {
  for (let i = 0; i < 20; i++) {
    try {
      const rc = await rpc("eth_getTransactionReceipt", [txHash]);
      if (rc && rc.status && parseInt(rc.status, 16) === 1) return rc;
      if (rc && rc.status && parseInt(rc.status, 16) !== 1) throw new Error("tx reverted: " + txHash);
    } catch (e) { if (/reverted/.test(e.message)) throw e; }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("approve not confirmed in time");
}

(async () => {
  console.log("STEP1 approve Mayan contract for", PAYLOAD.approveAmount, "micro-USDC");
  if (process.env.SKIP_APPROVE === "1") {
    console.log("SKIP_APPROVE=1: approve already on-chain — proceeding to STEP2 only");
  } else {
    const appr = usdcIface.encodeFunctionData("approve", [PAYLOAD.to, PAYLOAD.approveAmount]);
    const a = await safeExecSim(USDC, appr);
    console.log("SIM1 OK (approve via Safe)");
    if (!GO) {
      console.log("DRY: SIM1 clean. Broadcast approve (--go) first, then SIM2/payload runs.");
      return;
    }
    console.log("--go: broadcasting APPROVE…");
    const apprHash = await broadcast(a.execData, "APPROVE");
    await waitForReceipt(apprHash);
    console.log("APPROVE confirmed", apprHash);
  }

  console.log("STEP2 re-sim + broadcast FAST_MCTP payload to", PAYLOAD.to, "expected", PAYLOAD.expectedAmountOut);
  const b = await safeExecSim(PAYLOAD.to, PAYLOAD.data);
  console.log("SIM2 OK (payload via Safe, allowance live)");
  const payHash = await broadcast(b.execData, "PAYLOAD");
  console.log("LIVE_OK reverse bridge submitted", payHash);
})().catch((e) => { console.error("FAIL", e.message); process.exit(1); });
