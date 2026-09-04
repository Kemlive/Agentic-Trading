/**
 * Small Rabby-compatible wallet helper.
 *
 * Rabby provides an EIP-1193 provider as window.ethereum in a browser.
 * This module does not store private keys or sign anything automatically.
 */
function getProvider() {
  if (typeof window === "undefined" || !window.ethereum) {
    throw new Error("No browser wallet provider found. Install or unlock Rabby.");
  }

  return window.ethereum;
}

async function connectWallet() {
  const provider = getProvider();
  const accounts = await provider.request({ method: "eth_requestAccounts" });

  if (!Array.isArray(accounts) || accounts.length === 0) {
    throw new Error("Rabby did not return a connected account.");
  }

  return accounts[0];
}

async function getChainId() {
  const provider = getProvider();
  return provider.request({ method: "eth_chainId" });
}

module.exports = {
  connectWallet,
  getChainId,
  getProvider,
};
