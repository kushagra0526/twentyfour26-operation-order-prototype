import math

import numpy as np

from cuttime import order, path


def part(seed=1, held=False):
    return order.make_part(np.random.default_rng(seed), held)


def test_polyline_time_matches_trapezoid_for_one_straight_segment():
    # 100 mm at feed 20 mm/s, accel 500: accelerate and decelerate 0.4 mm each, cruise the rest
    t = path.polyline_time([(0, 0), (100, 0)], 20.0, 500.0)
    assert math.isclose(t, 99.2 / 20 + 2 * 20 / 500, rel_tol=1e-6)


def test_sharp_corner_costs_more_than_a_straight_line_of_same_length():
    straight = path.polyline_time([(0, 0), (10, 0), (20, 0)], 25.0, 300.0)
    corner = path.polyline_time([(0, 0), (10, 0), (10, 10)], 25.0, 300.0)
    assert corner > straight


def test_every_strategy_puts_the_profile_last_and_keeps_all_features():
    feats, prof = part(3)
    for s in order.STRATEGIES:
        seq = order.sequence(s, feats, prof, 12.0, (25.0, 12.0))
        assert seq[-1] is prof and len(seq) == len(feats) + 1 and all(f in seq for f in feats)


def test_grouping_never_adds_tool_changes_and_best_order_is_not_slower():
    for sd in range(5):
        feats, prof = part(sd)
        t = {s: order.job_time(s, feats, prof) for s in order.STRATEGIES}
        assert t["group by tool"][1] <= t["CAD tree order"][1]
        assert t[order.STRATEGIES[3]][0] <= t["group by tool + nearest next feature"][0] + 1e-9


def test_cut_time_is_independent_of_order():
    feats, prof = part(2)
    a = path.cut_time_true(path.plan({"features": feats + [prof]}, 25.0, 12.0), 500.0)
    b = path.cut_time_true(path.plan({"features": feats[::-1] + [prof]}, 25.0, 12.0), 500.0)
    assert math.isclose(a, b, rel_tol=1e-9)
