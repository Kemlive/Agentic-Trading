// networks.mjs - resolve the chain registry (reuse data/live/evm-networks.json).
import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const NETWORKS_PATH = path.join(__dirname, '..', '..', 'data', 'live', 'evm-networks.json');
