"""2.5D toolpaths for simple machined parts (pockets, slots, holes, outer profile) and a motion-planner time model.

The motion model is a GRBL-style look-ahead planner: junction speed from the corner angle, trapezoid velocity per segment. Parameters are invented."""
import math

import numpy as np

TOL = 0.01              # arc chord tolerance, mm
JUNCTION_DEV = 0.02     # mm
RAPID = 5000 / 60       # mm/s
TOOL_CHANGE_S = 12.0   # varies by machine; see the what-if in README


def arc(cx, cy, r, a0, a1):
    n = max(2, int(math.ceil(abs(a1 - a0) / (2 * math.acos(max(0.0, 1 - TOL / max(r, 0.05)))))))
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def rounded_rect(x, y, w, l, r):
    r = min(r, w / 2, l / 2)
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -math.pi / 2), (x + w - r, y + l - r, 0), (x + r, y + l - r, math.pi / 2), (x + r, y + r, math.pi)):
        pts += arc(cx, cy, r, a0, a0 + math.pi / 2) if r > 0.01 else [(cx, cy)]
    return pts + [pts[0]]


def zigzag(x, y, w, l, step):
    pts, yy, d = [], y, 1
    while yy <= y + l + 1e-9:
        xs = (x, x + w)[::d]
        pts += [(xs[0], yy), (xs[1], yy)]
        yy += step
        d = -d
    return pts


def tool_of(f):
    return {"pocket": "em6" if f["r"] >= 3 else "em3", "slot": "em3", "hole": f"drill{f['d']:.1f}", "profile": "em6"}[f["kind"]]


def plan(part, rough_feed, finish_feed):
    """-> list of ops: {'kind': 'cut', 'poly': [(x, y), ...], 'feed': mm/s} / {'kind': 'drill', 'time': s} / {'kind': 'toolchange'}"""
    ops, tool = [], None
    for f in part["features"]:
        need = tool_of(f)
        if need != tool:
            ops.append({"kind": "toolchange"})
            tool = need
        if f["kind"] == "hole":
            pecks = max(1, math.ceil(f["depth"] / (2 * f["d"])))
            ops.append({"kind": "drill", "time": f["depth"] / 4.0 + pecks * 1.5, "at": (f["x"], f["y"])})
            continue
        dia = 6.0 if tool == "em6" else 3.0
        if f["kind"] == "pocket":
            passes = math.ceil(f["depth"] / 2.0)
            inner = (f["x"] + dia / 2, f["y"] + dia / 2, f["w"] - dia, f["l"] - dia)
            for _ in range(passes):
                ops.append({"kind": "cut", "poly": zigzag(*inner, step=0.4 * dia), "feed": rough_feed})
            for _ in range(math.ceil(f["depth"] / 6.0)):
                ops.append({"kind": "cut", "poly": rounded_rect(f["x"] + dia / 2, f["y"] + dia / 2, f["w"] - dia, f["l"] - dia, max(f["r"] - dia / 2, 0.0)), "feed": finish_feed})
        elif f["kind"] == "slot":
            for _ in range(math.ceil(f["depth"] / 2.0)):
                ops.append({"kind": "cut", "poly": rounded_rect(f["x"], f["y"], f["w"], f["l"], f["w"] / 2) + [], "feed": rough_feed})
        else:
            for _ in range(math.ceil(f["depth"] / 3.0)):
                ops.append({"kind": "cut", "poly": rounded_rect(f["x"], f["y"], f["w"], f["l"], f["r"]), "feed": finish_feed})
    return ops


def segments(poly):
    p = np.asarray(poly, float)
    d = np.diff(p, axis=0)
    L = np.hypot(d[:, 0], d[:, 1])
    keep = L > 1e-9
    return d[keep], L[keep]


def polyline_time(poly, feed, accel):
    """Look-ahead trapezoid time for one continuous polyline (starts and ends at rest)."""
    d, L = segments(poly)
    n = len(L)
    if n == 0:
        return 0.0
    u = d / L[:, None]
    vj = np.zeros(n + 1)
    for i in range(1, n):
        cos_t = -float(u[i - 1] @ u[i])
        s = math.sqrt(max(0.0, 0.5 * (1 - cos_t)))
        vj[i] = feed if s >= 0.999 else min(feed, math.sqrt(max(accel * JUNCTION_DEV * s / (1 - s), 0.0)))
    for i in range(n - 1, -1, -1):                      # backward: must be able to stop in time
        vj[i] = min(vj[i], math.sqrt(vj[i + 1] ** 2 + 2 * accel * L[i]))
    for i in range(n):                                  # forward: cannot exceed what acceleration reaches
        vj[i + 1] = min(vj[i + 1], math.sqrt(vj[i] ** 2 + 2 * accel * L[i]))
    t = 0.0
    for i in range(n):
        v0, v1, l = vj[i], vj[i + 1], L[i]
        vpk2 = (2 * accel * l + v0 ** 2 + v1 ** 2) / 2
        vpk = min(feed, math.sqrt(max(vpk2, 0.0)))
        da, dd = (vpk ** 2 - v0 ** 2) / (2 * accel), (vpk ** 2 - v1 ** 2) / (2 * accel)
        cruise = max(0.0, l - da - dd)
        t += (vpk - v0) / accel + (vpk - v1) / accel + (cruise / vpk if vpk > 0 else 0.0)
    return t


def fixed_time(ops, tool_change=TOOL_CHANGE_S):
    """Everything that is not feed-limited cutting: rapids between polylines, drilling cycles, tool changes (same for every estimator)."""
    t, last = 0.0, None
    for op in ops:
        if op["kind"] == "toolchange":
            t += tool_change
        elif op["kind"] == "drill":
            t += op["time"] + 1.0 + (math.dist(last, op["at"]) / RAPID if last else 0.0)
            last = op["at"]
        else:
            p0 = op["poly"][0]
            t += (math.dist(last, p0) / RAPID if last else 1.0) + 0.6
            last = op["poly"][-1]
    return t


def cut_time_true(ops, accel):
    return sum(polyline_time(o["poly"], o["feed"], accel) for o in ops if o["kind"] == "cut")


def cut_length_over_feed(ops):
    return sum(float(segments(o["poly"])[1].sum()) / o["feed"] for o in ops if o["kind"] == "cut")


def block_stats(ops):
    n = short = 0
    for o in ops:
        if o["kind"] == "cut":
            _, L = segments(o["poly"])
            n += len(L)
            short += int((L < 1.0).sum())
    return n, short
