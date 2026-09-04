# Agentic Trading — Team HQ (agents work together, report to boss)

**Own brand, in-repo, no external tool.** Subagents coordinate through an append-only
channel + a structured board under `data/live/team/`. No agent edits another's code or
moves money without Chief/boss approval.

## Roles & who handles what
| Role | Owns (routed by kind) | Behavior |
|---|---|---|
| **chief** | everything else, policy, boss approvals | routes tasks, keeps the boss report |
| **scanner** | scan / research / regime / discovery | finds candidates & regime shifts |
| **risk** | risk / killswitch / review | gates entries, stops the desk |
| **execution** | trade / execution / fill | fills ONLY after boss GO; books to logs/ |
| **portfolio** | portfolio / rebalance / sizing / allocation / exposure / profit | runs portfolio_manager, proposes rebalances |
| **monitoring** | sla / health / monitor / feed | watches heartbeat + feeds, flags SLA |
| **guard (coder/fix)** | fix / bug / code / config / proposal | watches code 24/7, PROPOSES fixes, NEVER changes code without approval |

## How they "talk" (no collisions)
- **Channel log** `data/live/team/chat.jsonl` — every handoff/claim/done appended (like a group chat).
- **Board** `data/live/team/board.json` — tickets with owner/status; an agent claims its own ticket,
  so two agents never do the same job.
- **Router:** when a task arrives, Chief runs
  `python3 scripts/team_ops.py assign --kind <type> --title "..." --body "..."` and the router
  picks the owner. Guard proposals land as `needs-boss`; Chief/boss approves before any code change.
- **Boss digest:** `python3 scripts/team_ops.py report` (or Chief posts it after each session).

## Money boundaries (unchanged)
Financial truth stays in `data/` + `logs/trades.jsonl`. The team board NEVER holds balances,
prices, or fills as source. Guard NEVER edits code or touches funds — it only proposes.
