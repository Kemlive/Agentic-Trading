const config = require("../config");

/**
 * Trading service placeholder.
 *
 * Keep strategy decisions and transaction preparation here. In production,
 * validate every amount, token, recipient, and chain before asking Rabby to
 * sign a transaction.
 */
function createTradingService(options = {}) {
  const serviceConfig = { ...config, ...options };

  return {
    getStatus() {
      return {
        network: serviceConfig.network,
        dryRun: serviceConfig.dryRun,
        ready: Boolean(serviceConfig.rpcUrl),
      };
    },

    async executeSignal(signal) {
      if (!signal || typeof signal !== "object") {
        throw new TypeError("A trading signal object is required.");
      }

      if (serviceConfig.dryRun) {
        return {
          simulated: true,
          signal,
        };
      }

      throw new Error("Live trading is not implemented yet.");
    },
  };
}

module.exports = {
  createTradingService,
};

if (require.main === module) {
  console.log(createTradingService().getStatus());
}
