import json

import numpy as np

from . import order


def score(seeds, held, tool_change=12.0):
    acc = {s: {"t": [], "ch": []} for s in order.STRATEGIES}
    for sd in seeds:
        feats, prof = order.make_part(np.random.default_rng(sd), held)
        for s in order.STRATEGIES:
            t, ch = order.job_time(s, feats, prof, tool_change)
            acc[s]["t"].append(t)
            acc[s]["ch"].append(ch)
    base = np.array(acc[order.STRATEGIES[0]]["t"])
    out = {}
    for s, a in acc.items():
        t = np.array(a["t"])
        out[s] = {"mean_job_minutes": round(float(t.mean()) / 60, 2), "tool_changes": round(float(np.mean(a["ch"])), 1), "time_saved_vs_CAD_order_pct": round(100 * float(1 - t.sum() / base.sum()), 1),
                  "jobs_slower_than_CAD_order": int((t > base + 1e-9).sum())}
    return out


def main():
    res = {"dev": score(range(0, 100), False), "held_out": score(range(1000, 1200), True)}
    res["held_out_tool_change_what_if"] = {f"{tc} s": score(range(1000, 1100), True, tc) for tc in (3.0, 12.0, 30.0)}
    json.dump(res, open("out/result.json", "w"), indent=1)
    for k, v in res.items():
        print(k)
        for m, d in v.items():
            print("  ", m, d)


if __name__ == "__main__":
    main()
