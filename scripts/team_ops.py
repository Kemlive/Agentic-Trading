#!/usr/bin/env python3
"""
team-ops.py - Agentic Trading TEAM HQ: group channel + task router for subagents.

In-repo ops mesh. Subagents "talk" by appending to an append-only channel log and
by claiming/resolving board tickets, so they never collide or redo work:

  ROLES: chief scanner risk execution portfolio monitoring guard

  python3 scripts/team-ops.py assign --kind rebalance --title "..." --body "..."
  python3 scripts/team-ops.py list [--status open|claimed|needs-boss|done]
  python3 scripts/team-ops.py claim T-3 --as execution
  python3 scripts/team-ops.py done T-3 --as execution --note "..."
  python3 scripts/team-ops.py post --from scanner --to risk --msg "..."
  python3 scripts/team-ops.py report          # boss digest of the whole team

ROUTING (who to ask/assign when a task arrives):
  scan/research/regime       -> scanner
  trade/execution/fill       -> execution  (needs boss GO first)
  risk/killswitch/review     -> risk
  portfolio/rebalance/sizing/allocation/exposure/profit -> portfolio
  sla/health/monitor/feed    -> monitoring
  fix/bug/code/config        -> guard      (proposes ONLY; boss approves)
  anything else / money moves / policy -> chief -> boss approval

The FINANCIAL source of truth stays data/ + logs/trades.jsonl. This board is task
coordination + reporting only.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = os.path.join(ROOT, "data", "live", "team")
BOARD = os.path.join(TEAM, "board.json")
CHAT = os.path.join(TEAM, "chat.jsonl")

ROLES = ("chief", "scanner", "risk", "execution", "portfolio", "monitoring", "guard")
ROUTER = {
    "scan": "scanner", "research": "scanner", "regime": "scanner", "discovery": "scanner",
    "trade": "execution", "execution": "execution", "fill": "execution",
    "risk": "risk", "killswitch": "risk", "review": "risk",
    "portfolio": "portfolio", "rebalance": "portfolio", "sizing": "portfolio",
    "allocation": "portfolio", "exposure": "portfolio", "profit": "portfolio",
    "sla": "monitoring", "health": "monitoring", "monitor": "monitoring", "feed": "monitoring",
    "fix": "guard", "bug": "guard", "code": "guard", "config": "guard", "proposal": "guard",
}
DEFAULT_OWNER = "chief"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _read_board():
    try:
        return json.load(open(BOARD))
    except Exception:
        return {"next": 1, "items": []}


def _write_board(b):
    json.dump(b, open(BOARD, "w"), indent=2)


def _chat(line):
    with open(CHAT, "a") as f:
        f.write(json.dumps(line) + "\n")


def resolve_owner(kind):
    return ROUTER.get((kind or "").lower(), DEFAULT_OWNER)


def assign(kind, title, body="", to=None, priority="P2", needs_boss=False):
    b = _read_board()
    tid = "T-%d" % b["next"]
    b["next"] += 1
    owner = to or resolve_owner(kind)
    status = "needs-boss" if needs_boss or owner == "chief" else "open"
    item = {"id": tid, "ts": now(), "kind": kind.lower(), "from": "chief",
            "to": owner, "owner": owner, "status": status, "priority": priority,
            "title": title, "body": body, "note": "", "reportTo": "boss"}
    b["items"].insert(0, item)
    _write_board(b)
    _chat({"ts": now(), "from": "chief", "to": owner,
           "msg": "assigned %s: %s (%s)" % (tid, title, status), "ticket": tid})
    return item


def claim(tid, as_role):
    b = _read_board()
    for it in b["items"]:
        if it["id"] == tid:
            if it["owner"] != as_role and as_role != "chief":
                return None, "not owner (%s)" % it["owner"]
            it["status"] = "claimed"
            it["from"] = as_role
            _write_board(b)
            _chat({"ts": now(), "from": as_role, "to": "chief",
                   "msg": "claimed %s: %s" % (tid, it["title"]), "ticket": tid})
            return it, None
    return None, "no such ticket"


def done(tid, as_role, note=""):
    b = _read_board()
    for it in b["items"]:
        if it["id"] == tid:
            it["status"] = "done"
            it["from"] = as_role
            it["note"] = note
            _write_board(b)
            _chat({"ts": now(), "from": as_role, "to": "boss",
                   "msg": "done %s: %s | %s" % (tid, it["title"], note), "ticket": tid})
            return it, None
    return None, "no such ticket"


def post(frm, to, msg, ticket=None):
    _chat({"ts": now(), "from": frm, "to": to, "msg": msg, "ticket": ticket})
    return True


def report():
    b = _read_board()
    chats = []
    try:
        chats = [json.loads(l) for l in open(CHAT) if l.strip()]
    except Exception:
        pass
    out = []
    out.append("TEAM HQ REPORT  %s" % now())
    out.append("Active by owner:")
    for role in ROLES:
        mine = [i for i in b["items"] if i["owner"] == role and i["status"] in ("open", "claimed", "needs-boss")]
        if mine:
            out.append("  [%s] %s" % (role, ", ".join("%s(%s:%s)" % (i["id"], i["kind"], i["status"]) for i in mine[:6])))
    nb = [i for i in b["items"] if i["status"] == "needs-boss"]
    if nb:
        out.append("NEEDS BOSS APPROVAL:")
        for i in nb[:10]:
            out.append("  - %s [%s] %s :: %s" % (i["id"], i["kind"], i["title"], i["body"]))
    out.append("Recent channel activity:")
    for c in chats[-12:]:
        out.append("  %s -> %s: %s" % (c.get("from"), c.get("to"), c.get("msg", "")))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assign")
    a.add_argument("--kind", required=True); a.add_argument("--title", required=True)
    a.add_argument("--body", default=""); a.add_argument("--to", default=None)
    a.add_argument("--priority", default="P2"); a.add_argument("--needs-boss", action="store_true")
    c = sub.add_parser("claim"); c.add_argument("id"); c.add_argument("--as", dest="as_role", required=True)
    d = sub.add_parser("done"); d.add_argument("id"); d.add_argument("--as", dest="as_role", required=True); d.add_argument("--note", default="")
    p = sub.add_parser("post"); p.add_argument("--from", dest="frm", required=True); p.add_argument("--to", required=True); p.add_argument("--msg", required=True); p.add_argument("--ticket", default=None)
    l = sub.add_parser("list"); l.add_argument("--status", default=None)
    sub.add_parser("report")
    args = ap.parse_args()
    if args.cmd == "assign":
        it = assign(args.kind, args.title, args.body, args.to, args.priority, args.needs_boss)
        print("ASSIGNED %s -> %s [%s]" % (it["id"], it["owner"], it["status"]))
    elif args.cmd == "claim":
        it, err = claim(args.id, args.as_role)
        print(err or ("CLAIMED " + args.id))
    elif args.cmd == "done":
        it, err = done(args.id, args.as_role, args.note)
        print(err or ("DONE " + args.id))
    elif args.cmd == "post":
        post(args.frm, args.to, args.msg)
        print("POSTED")
    elif args.cmd == "list":
        b = _read_board()
        for i in b["items"]:
            if args.status and i["status"] != args.status:
                continue
            print("%s [%s/%s/%s] %s" % (i["id"], i["owner"], i["kind"], i["status"], i["title"]))
    elif args.cmd == "report":
        print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
