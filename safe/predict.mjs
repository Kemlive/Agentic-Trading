// predict.mjs - READ-ONLY: predict the Safe address + estimate deployment gas on Base.
// Uses official Safe deployments + AllowanceModule address. Never broadcasts.
import { ethers } from 'ethers';
import { getSafeSingletonDeployment, getProxyFactoryDeployment, getFallbackHandlerDeployment } from '@safe-global/safe-deployments';
import { getAllowanceModuleDeployment } from '@safe-global/safe-modules-deployments';
import { loadKeystore, decryptPrivateKey, loadPassphrase } from '../evm-signer/src/keystore.mjs';

const LANE = '0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8';
const provider = new ethers.JsonRpcProvider('https://mainnet.base.org');

function addr(dep, network = '8453') {
  if (!dep) return null;
  return dep.networkAddresses?.[network] ?? dep.address ?? dep.defaultAddress ?? null;
}

async function rpc(method, params) {
  return provider.send(method, params);
}

async function main() {
  const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());
  console.log('signer (EOA):', wallet.address, '| matches lane:', wallet.address.toLowerCase() === LANE.toLowerCase());

  const singleton = addr(getSafeSingletonDeployment({ network: '8453', version: '1.4.1' }));
  const factory = addr(getProxyFactoryDeployment({ network: '8453', version: '1.4.1' }));
  const fallback = addr(getFallbackHandlerDeployment({ network: '8453', version: '1.4.1' }));
  const allowance = addr(getAllowanceModuleDeployment({ network: '8453' }));
  console.log('Safe singleton 1.4.1 (Base):', singleton);
  console.log('ProxyFactory 1.4.1 (Base):', factory);
  console.log('FallbackHandler 1.4.1 (Base):', fallback);
  console.log('AllowanceModule (Base):', allowance);

  // predicted Safe address = create2(factory, saltNonce, keccak256(proxyCreationCode))
  const proxyCreationCodeRaw = await rpc('eth_call', [{ to: factory, data: '0x53e5d935' }, 'latest']); // proxyCreationCode()
  const proxyCreationCode = ethers.AbiCoder.defaultAbiCoder().decode(['bytes'], proxyCreationCodeRaw)[0];
  const saltNonce = '0x' + '00'.repeat(32); // 0
  const initCodeHash = ethers.keccak256(proxyCreationCode);
  const predicted = ethers.getCreate2Address(factory, saltNonce, initCodeHash);
  console.log('predicted Safe address (saltNonce=0):', predicted);

  // setup calldata: setup(owners=[EOA], threshold=1, to=0, data=0x, fallbackHandler, paymentToken=0, payment=0, paymentReceiver=0)
  const iface = new ethers.Interface([
    'function setup(address[] _owners, uint256 _threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)'
  ]);
  const setupCalldata = iface.encodeFunctionData('setup', [
    [wallet.address], 1, ethers.ZeroAddress, '0x', fallback, ethers.ZeroAddress, 0, ethers.ZeroAddress,
  ]);
  const factoryIface = new ethers.Interface(['function createProxyWithNonce(address _singleton, bytes initializer, uint256 saltNonce)']);
  const deployData = factoryIface.encodeFunctionData('createProxyWithNonce', [singleton, setupCalldata, saltNonce]);

  // gas estimate for the createProxyWithNonce (deployment)
  let deployGas = null;
  try {
    deployGas = parseInt(await rpc('eth_estimateGas', [{ from: wallet.address, to: factory, data: deployData }]), 16);
  } catch (e) {
    deployGas = 'estimateGas reverted: ' + (e.message || String(e)).slice(0, 120);
  }
  const gp = await provider.getFeeData();
  const ethPriceUsd = 2415;
  const deployCostEth = typeof deployGas === 'number' ? deployGas * Number(gp.maxFeePerGas) / 1e18 : null;
  console.log('deploy gas estimate:', deployGas);
  console.log('approx deploy cost ETH:', deployCostEth?.toFixed(8), '=> USD', deployCostEth != null ? (deployCostEth * ethPriceUsd).toFixed(3) : 'n/a');

  // which of our 6 chains have Safe deployed (same address achievable)
  const chainMap = { '1': 'Ethereum', '56': 'BNB', '8453': 'Base', '42161': 'Arbitrum', '137': 'Polygon', '10': 'Optimism', '999': 'HyperEVM', '4663': 'Robinhood' };
  console.log('\nSafe singleton presence across target chains:');
  for (const [id, name] of Object.entries(chainMap)) {
    const s = addr(getSafeSingletonDeployment({ network: id, version: '1.4.1' }));
    console.log(' ', name.padEnd(11), id.padEnd(6), s ? 'deployed ' + s : 'NOT in safe-deployments (needs manual deploy)');
  }
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 600)); process.exit(1); });
