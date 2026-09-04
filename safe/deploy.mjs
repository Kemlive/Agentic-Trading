// deploy.mjs - deploy the lane Safe (1/1, EOA owner) on Base via ProxyFactory.createProxyWithNonce.
// DRY-RUN by default (prints the tx). Add --go to actually sign + broadcast.
// Predicted address (saltNonce=0): 0x3Be09FD2F0655C096eD364338561dACCF507Ce8d
import { ethers } from 'ethers';
import { getSafeSingletonDeployment, getProxyFactoryDeployment, getFallbackHandlerDeployment } from '@safe-global/safe-deployments';
import { loadKeystore, decryptPrivateKey, loadPassphrase } from '../evm-signer/src/keystore.mjs';

const GO = process.argv.includes('--go');
function a(dep, net = '8453') { return dep.networkAddresses?.[net] ?? dep.address ?? dep.defaultAddress; }

const provider = new ethers.JsonRpcProvider('https://base-rpc.publicnode.com');
const singleton = a(getSafeSingletonDeployment({ network: '8453', version: '1.4.1' }));
const factory = a(getProxyFactoryDeployment({ network: '8453', version: '1.4.1' }));
const fallback = a(getFallbackHandlerDeployment({ network: '8453', version: '1.4.1' }));
const saltNonce = '0x' + '00'.repeat(32);

async function main() {
  const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase()).connect(provider);
  const iface = new ethers.Interface([
    'function setup(address[] _owners, uint256 _threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)'
  ]);
  const setupCalldata = iface.encodeFunctionData('setup', [
    [wallet.address], 1, ethers.ZeroAddress, '0x', fallback, ethers.ZeroAddress, 0, ethers.ZeroAddress,
  ]);
  const factoryIface = new ethers.Interface(['function createProxyWithNonce(address _singleton, bytes initializer, uint256 saltNonce)']);
  const deployData = factoryIface.encodeFunctionData('createProxyWithNonce', [singleton, setupCalldata, saltNonce]);

  const tx = { from: wallet.address, to: factory, data: deployData };
  const gas = await provider.estimateGas(tx);
  const fee = await provider.getFeeData();
  const costEth = Number(gas) * Number(fee.maxFeePerGas) / 1e18;
  console.log('owner EOA:', wallet.address);
  console.log('singleton:', singleton, '| factory:', factory, '| fallback:', fallback);
  console.log('deploy gas:', gas.toString(), '| approx cost ETH:', costEth.toFixed(8));

  if (!GO) {
    console.log('DRY-RUN. To deploy, run: node deploy.mjs --go');
    return;
  }
  const resp = await wallet.sendTransaction(tx);
  console.log('BROADCAST', resp.hash);
  const rec = await resp.wait();
  console.log('status', rec.status, '| block', rec.blockNumber, '| gasUsed', rec.gasUsed.toString());
  // verify deployed proxy code at predicted address
  const pred = ethers.getCreate2Address(factory, saltNonce, ethers.keccak256(await provider.call({ to: factory, data: '0x53e5d935' })));
  const code = await provider.getCode(pred);
  console.log('predicted Safe:', pred, '| code deployed:', code !== '0x' ? 'YES' : 'NO');
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 500)); process.exit(1); });
