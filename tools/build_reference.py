#!/usr/bin/env python3
"""Build data/reflex_reference.json from the D3 retest (spike_out/d3/).

The reference holds derived numbers only: no wallet addresses, no raw Nansen rows.
Launch Reflex percentiles are measured against it.
"""

import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D3 = ROOT / "spike_out" / "d3"
LN10 = math.log(10)
K = 4  # shrinkage strength, in entries


def capped_log(a, b):
    return max(-LN10, min(LN10, math.log(a / b))) if a and b else None


entries = json.loads((D3 / "entries.json").read_text())
actors = []
for es in entries.values():
    usable = [e for e in es if e.get("p0") and e.get("pmax")]
    if len(usable) >= 16:
        actors.append(usable)

pooled = [capped_log(e["pmax"], e["p0"]) for es in actors for e in es]
prior = statistics.mean(pooled)
shrunk = sorted(
    (sum(capped_log(e["pmax"], e["p0"]) for e in es) + K * prior) / (len(es) + K) for es in actors
)
ref = {
    "source": "Test D3 wide retest, spike_results.md",
    "actors": len(actors),
    "entries": len(pooled),
    "shrinkage_k": K,
    "prior_mean_mfe60": round(prior, 4),
    "pooled_runner_rate": round(statistics.mean(float(e["pmax"] >= 2 * e["p0"]) for es in actors for e in es), 4),
    "pooled_failed_launch_rate": round(statistics.mean(float(e["failed_launch"]) for es in actors for e in es), 4),
    "shrunk_mean_mfe60": [round(x, 4) for x in shrunk],
}
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data" / "reflex_reference.json").write_text(json.dumps(ref, indent=2))
print(json.dumps({k: v for k, v in ref.items() if k != "shrunk_mean_mfe60"}, indent=2))
print("range", shrunk[0], shrunk[-1])
