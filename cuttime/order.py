"""Order the features of a part before cutting. The outer profile always goes last (the part is held by it)."""
import itertools
import math

import numpy as np

from . import path

STRATEGIES = ["CAD tree order", "group by tool", "group by tool + nearest next feature", "best tool order (all permutations) + nearest next feature"]


def make_part(rng, held):
    W, Lh = float(rng.uniform(70, 120)), float(rng.uniform(55, 90))
    feats = []
    for _ in range(int(rng.integers(1, 4 if not held else 5))):
        small = held and rng.random() < 0.6
        w, l = (rng.uniform(8, 18), rng.uniform(8, 18)) if small else (rng.uniform(15, 35), rng.uniform(15, 30))
        feats.append({"kind": "pocket", "x": float(rng.uniform(4, W - w - 4)), "y": float(rng.uniform(4, Lh - l - 4)), "w": float(w), "l": float(l),
                      "depth": float(rng.uniform(3, 12)), "r": float(rng.uniform(1.6, 2.9) if small else rng.uniform(3, 6)), "d": 0})
    for _ in range(int(rng.integers(0, 4 if not held else 5))):
        feats.append({"kind": "slot", "x": float(rng.uniform(4, W - 30)), "y": float(rng.uniform(4, Lh - 10)), "w": float(rng.choice([3.0, 4.0, 5.0])),
                      "l": float(rng.uniform(10, 25)), "depth": float(rng.uniform(2, 6)), "r": 0, "d": 0})
    for _ in range(int(rng.integers(2, 10 if not held else 16))):
        feats.append({"kind": "hole", "x": float(rng.uniform(4, W - 4)), "y": float(rng.uniform(4, Lh - 4)), "w": 0, "l": 0, "depth": float(rng.uniform(4, 16)),
                      "r": 0, "d": float(rng.choice([2.0, 3.0, 4.0, 6.0] if not held else [2.0, 2.5, 3.0, 4.0, 5.0, 6.0]))})
    perm = rng.permutation(len(feats))
    feats = [feats[i] for i in perm]                                   # the order a CAD feature tree might list them
    profile = {"kind": "profile", "x": 0.0, "y": 0.0, "w": W, "l": Lh, "depth": 6.0, "r": float(rng.uniform(2, 8)), "d": 0}
    return feats, profile


def pos(f):
    return (f["x"], f["y"])


def nearest_chain(feats, start):
    left, out, cur = list(feats), [], start
    while left:
        j = min(range(len(left)), key=lambda i: math.dist(cur, pos(left[i])))
        out.append(left.pop(j))
        cur = pos(out[-1])
    return out


def groups(feats):
    g = {}
    for f in feats:
        g.setdefault(path.tool_of(f), []).append(f)
    return g


def chain_groups(order, g, start):
    out, cur = [], start
    for t in order:
        c = nearest_chain(g[t], cur)
        out += c
        cur = pos(c[-1])
    return out


def sequence(strategy, feats, profile, tool_change, feeds):
    if strategy == "CAD tree order":
        seq = list(feats)
    else:
        g = groups(feats)
        if strategy == "group by tool":
            seq = [f for t in g for f in g[t]]
        elif strategy == "group by tool + nearest next feature":
            seq = chain_groups(list(g), g, (0.0, 0.0))
        else:
            best = None
            for order in itertools.permutations(g):
                s = chain_groups(order, g, (0.0, 0.0))
                t = path.fixed_time(path.plan({"features": s + [profile]}, *feeds), tool_change)
                if best is None or t < best[0]:
                    best = (t, s)
            seq = best[1]
    return seq + [profile]


def job_time(strategy, feats, profile, tool_change=path.TOOL_CHANGE_S, feeds=(25.0, 12.0), accel=500.0):
    seq = sequence(strategy, feats, profile, tool_change, feeds)
    ops = path.plan({"features": seq}, *feeds)
    changes = sum(o["kind"] == "toolchange" for o in ops)
    return path.fixed_time(ops, tool_change) + path.cut_time_true(ops, accel), changes
