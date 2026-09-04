/**
 * Central configuration for the trading application.
 *
 * Values are read from environment variables so secrets and deployment
 * settings stay outside the source code.
 */
const config = {
  network: process.env.TRADING_NETWORK || "ethereum",
  rpcUrl: process.env.RPC_URL || "",
  walletAddress: process.env.WALLET_ADDRESS || "",
  dryRun: process.env.DRY_RUN !== "false",
};

module.exports = config;
