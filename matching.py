"""Event fingerprint and Déjà View matching.

Rules are in docs/CORPUS_PLAN.md. A fingerprint has four features, all known one
hour after the launch moment (T0). Matching standardizes them with the corpus
mean and standard deviation and lists the nearest past launches by Euclidean
distance. It shows observed outcomes, never a probability.
"""

import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS_FILE = ROOT / "data" / "corpus.json"
FEATURES = ("actor_quality", "entry_speed", "persistence", "concentration")
FEATURE_NAMES = {"actor_quality": "Actor quality", "entry_speed": "Entry speed",
                 "persistence": "Persistence", "concentration": "Concentration"}
MIN_SCOREABLE = 3
STRONG_REFLEX = 50
K = 3


def fingerprint(all_buyers, top):
    """Four features from every filtered buyer and the scored top buyers.

    Returns (features, None), or (None, reason) when too few buyers are scoreable.
    """
    ok = [r for r in top if r.get("scoreable")]
    if len(ok) < MIN_SCOREABLE:
        return None, "Too few known buyers to find similar launches."
    weight = sum(r["usd"] for r in ok)
    quality = sum(r["reflex"] * r["usd"] for r in ok) / weight
    strong = [min(60.0, max(0.0, r["entry_delay_s"] / 60)) for r in ok if r["reflex"] >= STRONG_REFLEX]
    speed = statistics.median(strong) if strong else 60.0
    later = 0.0
    for r in top:
        w = r["window_usd"]
        first = next(i for i, v in enumerate(w) if v > 0)
        later += sum(w[first + 1:])
    persistence = later / sum(r["usd"] for r in top)
    sizes = sorted((b["usd"] for b in all_buyers), reverse=True)
    concentration = sum(sizes[:3]) / sum(sizes)
    return {"actor_quality": quality, "entry_speed": speed,
            "persistence": persistence, "concentration": concentration}, None


def describe_feature(name, value):
    if name == "actor_quality":
        return f"buyer Reflex {value:.0f}"
    if name == "entry_speed":
        return "no strong buyer in the first hour" if value >= 60 else f"strong buyers by {value:.0f} min"
    if name == "persistence":
        return f"{value:.0%} of buying came later"
    return f"top 3 buyers {value:.0%} of volume"


def load_corpus():
    return json.loads(CORPUS_FILE.read_text()) if CORPUS_FILE.exists() else None


def scale(events):
    """Mean and standard deviation per feature."""
    out = {}
    for f in FEATURES:
        vals = [e["features"][f] for e in events]
        out[f] = {"mean": statistics.mean(vals), "sd": statistics.pstdev(vals) or 1.0}
    return out


def z(features, stats, only=FEATURES):
    return [(features[f] - stats[f]["mean"]) / stats[f]["sd"] for f in only]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def neighbours(target, events, stats, k=K, skip=lambda e: False, only=FEATURES):
    """The k nearest events to target features, nearest first, as (distance, event)."""
    tz = z(target, stats, only)
    ranked = sorted(((distance(tz, z(e["features"], stats, only)), e) for e in events if not skip(e)),
                    key=lambda p: p[0])
    return ranked[:k]


def closeness(d, corpus):
    t1, t2 = corpus["distance_terciles"]
    return "close" if d <= t1 else "moderate" if d <= t2 else "distant"


def card(d, event, target, corpus, counter=False):
    stats = corpus["scale"]
    gaps = sorted(FEATURES, key=lambda f: abs(z(target, stats, (f,))[0] - z(event["features"], stats, (f,))[0]))
    return {"token": event["token"], "symbol": event["symbol"], "date": event["date"],
            "distance": round(d, 2), "closeness": closeness(d, corpus), "counter_example": counter,
            "matched_on": [{"feature": FEATURE_NAMES[f], "this": describe_feature(f, target[f]),
                            "then": describe_feature(f, event["features"][f])} for f in gaps[:2]],
            "features": event["features"], "outcomes": event["outcomes"],
            "winner": event["outcomes"]["ret24h_pct"] > 0}


def analogues(target, token, corpus):
    """Three nearest past launches, plus the nearest counter-example when all three agree."""
    events = corpus["events"]
    stats = corpus["scale"]
    skip = lambda e: e["token"] == token  # noqa: E731
    near = neighbours(target, events, stats, skip=skip)
    cards = [card(d, e, target, corpus) for d, e in near]
    results = {c["winner"] for c in cards}
    if len(results) == 1:
        want = not results.pop()
        other = neighbours(target, events, stats, k=1,
                           skip=lambda e: skip(e) or (e["outcomes"]["ret24h_pct"] > 0) != want)
        if other:
            cards.append(card(other[0][0], other[0][1], target, corpus, counter=True))
    return cards
