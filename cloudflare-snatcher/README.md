# Agentic Snatcher — Cloudflare Worker (24/7, no laptop)

Serverless cron worker that runs the trading loop every 15 minutes on Cloudflare's edge.
Mirrors the local autopilot rails exactly (1 position max, $1.50, USDC-leg, reserve $15,
daily -10% kill, snatcher exits, Telegram alerts on every action).

## Files
- `wrangler.toml` — worker config + cron (`*/15`) + KV binding (fill in KV id)
- `src/index.js` — the whole loop (scan -> buy -> snatcher-manage -> sell -> notify)
- `package.json` — deps (`@solana/web3.js`, `bs58`, `wrangler`)

## Deploy steps (one-time, ~5 min)
```
cd /Users/earn/Agentic-Trading/cloudflare-snatcher
npm install
npx wrangler login                 # opens browser -> Cloudflare account
npx wrangler kv namespace create STATE     # copy the returned id
# paste that id into wrangler.toml -> [[kv_namespaces]] id = "..."
npx wrangler secret put SOLANA_PRIVATE_KEY   # paste agent hot-wallet base58 key (GHojAX... keypair)
npx wrangler secret put HELIUS_KEY
npx wrangler secret put TG_TOKEN
npx wrangler secret put TG_CHAT
npx wrangler deploy
```
Verify:
- `curl https://<your-worker>.workers.dev/alive` → `alive`
- `curl https://<your-worker>.workers.dev/run` → triggers one loop immediately (Telegram will ping)

## State & kill switch
- Holdings/peaks/tried live in KV (`STATE`), not on disk.
- Pause: set KV key `state` = `{"off":true}` (or delete the worker / rotate secrets).
- Secrets are Cloudflare-encrypted; the repo contains none.

## Notes
- Cron = every 15 min (change in `wrangler.toml` -> `[triggers] crons`).
- Free tier: cron triggers supported; keep per-run fetches low (8-token enrichment cap).
- This replaces the laptop daemon for real 24/7; local watchdog can keep running as backup.
