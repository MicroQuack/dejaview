"""Event fingerprint and Déjà View matching.

Rules are in docs/CORPUS_PLAN.md. A fingerprint has four features, all known one
hour after the launch moment (T0). Matching standardizes them with the corpus
mean and standard deviation and lists the nearest past launches by Euclidean
distance. It shows observed outcomes, never a probability.
"""

import bisect
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS_FILE = ROOT / "data" / "corpus.json"
REFERENCE = json.loads((ROOT / "data" / "reflex_reference.json").read_text())
# Priority order: when two features are redundant, the later one is dropped.
FEATURES = ("actor_quality", "entry_speed", "concentration", "persistence")
FEATURE_NAMES = {"actor_quality": "Actor quality", "entry_speed": "Entry speed",
                 "persistence": "Persistence", "concentration": "Concentration"}
MIN_SCOREABLE = 3
STRONG_REFLEX_RAW = statistics.median(REFERENCE["shrunk_mean_mfe60"])  # the median reference buyer
REDUNDANT_RHO = 0.80
K = 3


def percentile(shrunk):
    """Launch Reflex for display: rank of a shrunk mean mfe60 among the D3 reference buyers."""
    ref = REFERENCE["shrunk_mean_mfe60"]
    return round(100 * bisect.bisect_left(ref, shrunk) / len(ref))


def fingerprint(all_buyers, top):
    """Four features from every filtered buyer and the scored top buyers.

    Returns (features, None), or (None, reason) when too few buyers are scoreable.
    Matching uses the underlying shrunk Reflex; the percentile is for display only.
    """
    ok = [r for r in top if r.get("scoreable")]
    if len(ok) < MIN_SCOREABLE:
        return None, "Too few known buyers to find similar launches."
    weights = [math.sqrt(r["usd"]) for r in ok]
    quality = sum(w * r["reflex_raw"] for w, r in zip(weights, ok)) / sum(weights)
    strong = [min(60.0, max(0.0, r["entry_delay_s"] / 60)) for r in ok if r["reflex_raw"] > STRONG_REFLEX_RAW]
    speed = statistics.median(strong) if strong else 60.0
    later = 0.0
    for r in top:
        w = r["window_usd"]
        first = next(i for i, v in enumerate(w) if v > 0)
        later += sum(w[first + 1:])
    persistence = later / sum(r["usd"] for r in top)
    sizes = sorted((b["usd"] for b in all_buyers), reverse=True)
    concentration = sum(sizes[:3]) / sum(sizes)
    return {"actor_quality": quality, "entry_speed": speed, "persistence": persistence,
            "concentration": concentration, "actor_quality_pct": percentile(quality),
            "scoreable_buyers": len(ok), "top_buyers": len(top)}, None


def describe_feature(name, features):
    value = features[name]
    if name == "actor_quality":
        return f"buyer Reflex {percentile(value)}"
    if name == "entry_speed":
        return "no strong buyer in the first hour" if value >= 60 else f"strong buyers by {value:.0f} min"
    if name == "persistence":
        return f"{value:.0%} of buying came later"
    return f"top 3 buyers {value:.0%} of volume"


def spearman(x, y):
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r, i = [0.0] * len(xs), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy) if sx and sy else 0.0


def select_features(feature_rows):
    """Keep features in priority order, dropping any with |Spearman rho| > 0.80 against a kept one."""
    rho = {}
    for i, a in enumerate(FEATURES):
        for b in FEATURES[i + 1:]:
            rho[f"{a}|{b}"] = round(spearman([f[a] for f in feature_rows], [f[b] for f in feature_rows]), 3)
    kept = []
    for f in FEATURES:
        if all(abs(rho[f"{k}|{f}"]) <= REDUNDANT_RHO for k in kept):
            kept.append(f)
    return kept, rho


def load_corpus():
    return json.loads(CORPUS_FILE.read_text()) if CORPUS_FILE.exists() else None


def scale(events, only):
    """Mean and standard deviation per feature."""
    out = {}
    for f in only:
        vals = [e["features"][f] for e in events]
        out[f] = {"mean": statistics.mean(vals), "sd": statistics.pstdev(vals) or 1.0}
    return out


def z(features, stats, only):
    return [(features[f] - stats[f]["mean"]) / stats[f]["sd"] for f in only]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def neighbours(target, events, stats, only, k=K, skip=lambda e: False):
    """The k nearest events to target features, nearest first, as (distance, event)."""
    tz = z(target, stats, only)
    ranked = sorted(((distance(tz, z(e["features"], stats, only)), e) for e in events if not skip(e)),
                    key=lambda p: p[0])
    return ranked[:k]


def loo_nearest_distances(events, only):
    """Each event's distance to its nearest other event, with the scale learned without it."""
    out = []
    for e in events:
        rest = [x for x in events if x is not e]
        out.append(neighbours(e["features"], rest, scale(rest, only), only, k=1)[0][0])
    return out


def closeness(d, corpus):
    t = corpus["distance_thresholds"]
    return "close" if d <= t["median"] else "moderate" if d <= t["p95"] else "distant"


def card(d, event, target, corpus, counter=False):
    stats, only = corpus["scale"], corpus["features_used"]
    gaps = sorted(only, key=lambda f: abs(z(target, stats, (f,))[0] - z(event["features"], stats, (f,))[0]))
    return {"token": event["token"], "symbol": event["symbol"], "date": event["date"],
            "distance": round(d, 2), "closeness": closeness(d, corpus), "counter_example": counter,
            "matched_on": [{"feature": FEATURE_NAMES[f], "this": describe_feature(f, target),
                            "then": describe_feature(f, event["features"])} for f in gaps[:2]],
            "scoreable_buyers": event["scoreable_buyers"], "top_buyers": event["top_buyers"],
            "outcomes": event["outcomes"], "winner": event["outcomes"]["ret24h_pct"] > 0}


def analogues(target, token, corpus):
    """Three nearest past launches, plus the nearest counter-example when all three agree.

    seen_before is False when even the nearest launch is farther than the 95th percentile
    of the corpus's own nearest-neighbour distances.
    """
    events, stats, only = corpus["events"], corpus["scale"], corpus["features_used"]
    skip = lambda e: e["token"] == token  # noqa: E731
    near = neighbours(target, events, stats, only, skip=skip)
    cards = [card(d, e, target, corpus) for d, e in near]
    results = {c["winner"] for c in cards}
    if len(results) == 1:
        want = not results.pop()
        other = neighbours(target, events, stats, only, k=1,
                           skip=lambda e: skip(e) or (e["outcomes"]["ret24h_pct"] > 0) != want)
        if other:
            cards.append(card(other[0][0], other[0][1], target, corpus, counter=True))
    seen = bool(near) and near[0][0] <= corpus["distance_thresholds"]["p95"]
    return {"seen_before": seen, "cards": cards}
