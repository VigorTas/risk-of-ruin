"""Position sizing and risk of ruin, by Monte Carlo.

Part 1  Kelly criterion: how bet size changes growth and drawdowns for a strategy with a known edge.
Part 2  Prop-firm evaluation: chance of hitting a profit target before a trailing drawdown, by risk per trade.

Usage: python ruin.py [--paths 20000] [--seed 1]
"""
import argparse
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def kelly(p, b):
    """Kelly fraction for win probability p and win/loss ratio b (loss = 1 unit of risk)."""
    return p - (1 - p) / b


def outcomes(p, b, n_trades, n_paths, rng):
    """Matrix of trade results in R-multiples: +b with probability p, else -1."""
    return np.where(rng.random((n_paths, n_trades)) < p, b, -1.0)


def fractional_paths(R, f):
    """Equity paths (start 1.0) when risking fraction f of current equity on every trade."""
    return np.cumprod(1 + f * R, axis=1)


def kelly_table(p, b, n_trades, n_paths, rng):
    R = outcomes(p, b, n_trades, n_paths, rng)
    k = kelly(p, b)
    rows = []
    for mult in (0.25, 0.5, 1.0, 2.0, 3.0):
        eq = np.clip(fractional_paths(R, k * mult), 1e-12, None)
        dd = (eq / np.maximum.accumulate(eq, axis=1) - 1).min(axis=1)
        rows.append({
            "mult": mult, "f": k * mult,
            "median_final": np.median(eq[:, -1]),
            "growth_per_trade": np.median(np.log(eq[:, -1])) / n_trades,
            "p_dd50": (dd <= -0.5).mean(),
            "p_below_start": (eq[:, -1] < 1).mean(),
        })
    return rows


def evaluation(pnl, target, max_loss, trailing=True):
    """pnl: matrix (paths, trades) of dollar results. Pass = equity reaches +target. Fail = equity falls max_loss
    below its peak (trailing until the floor reaches the starting balance, then fixed), or below -max_loss if not
    trailing. Returns (pass rate, fail rate); the rest is undecided when the trades run out."""
    n_paths, n_trades = pnl.shape
    eq = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(pnl, axis=1)], axis=1)
    if trailing:
        floor = np.minimum(np.maximum.accumulate(eq, axis=1) - max_loss, 0.0)
    else:
        floor = np.full_like(eq, -max_loss)
    never = n_trades + 1
    hit_t = np.where((eq >= target).any(1), (eq >= target).argmax(1), never)
    hit_f = np.where((eq <= floor).any(1), (eq <= floor).argmax(1), never)
    return (hit_t < hit_f).mean(), (hit_f < hit_t).mean()


def daily_pnl(edge, risk, n_days, n_paths, rng):
    """Daily P&L ~ Normal(edge * risk, risk): `risk` is one standard deviation of a day's result."""
    return rng.normal(edge * risk, risk, size=(n_paths, n_days))


def pass_svg(curves, risks, path):
    W, H, pad = 720, 340, 55
    X = lambda v: pad + (v - risks[0]) / (risks[-1] - risks[0]) * (W - 2 * pad)
    Y = lambda v: H - pad - v * (H - 2 * pad)
    colors = ["#6b7280", "#2563eb", "#16a34a"]
    lines, legend = "", ""
    for i, (label, ys) in enumerate(curves):
        pts = " ".join("{:.1f},{:.1f}".format(X(r), Y(y)) for r, y in zip(risks, ys))
        lines += '<polyline points="{}" fill="none" stroke="{}" stroke-width="2"/>'.format(pts, colors[i])
        legend += '<text x="{}" y="{}" font-size="11" fill="{}">{}</text>'.format(W - pad - 210, 50 + 16 * i, colors[i], label)
    xt = "".join('<text x="{:.0f}" y="{}" font-size="11" text-anchor="middle">${}</text>'.format(X(r), H - pad + 16, r)
                 for r in risks[::2])
    yt = "".join('<text x="{}" y="{:.0f}" font-size="11" text-anchor="end">{:.0%}</text>'.format(pad - 6, Y(v) + 4, v)
                 for v in (0, 0.25, 0.5, 0.75, 1))
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif">
<rect width="{W}" height="{H}" fill="white"/>
<text x="{pad}" y="24" font-size="14" font-weight="bold">Chance to pass a $3,000-target / $2,000-trailing-drawdown evaluation</text>
<line x1="{pad}" y1="{b}" x2="{r}" y2="{b}" stroke="#9ca3af"/>
{lines}{legend}{xt}{yt}
<text x="{cx}" y="{bl}" font-size="11" text-anchor="middle">daily risk (one standard deviation of daily P&amp;L), one year of trading days</text>
</svg>""".format(W=W, H=H, pad=pad, b=H - pad, r=W - pad, lines=lines, legend=legend, xt=xt, yt=yt, cx=W / 2, bl=H - 12)
    with open(path, "w") as f:
        f.write(svg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    p, b, n = 0.45, 1.5, 250
    print("Part 1: strategy that wins {:.0%} of trades at {}:1. Edge {:+.3f}R per trade, Kelly fraction {:.1%}. {} trades.\n".format(
        p, b, p * b - (1 - p), kelly(p, b), n))
    print("{:>8} {:>8} {:>13} {:>16} {:>17} {:>14}".format("x Kelly", "risk", "median final", "growth/trade", "P(drawdown>50%)", "P(end < start)"))
    for r in kelly_table(p, b, n, a.paths, np.random.default_rng(a.seed)):
        print("{:>8} {:>8.1%} {:>13.2f} {:>+16.4f} {:>17.1%} {:>14.1%}".format(
            r["mult"], r["f"], r["median_final"], r["growth_per_trade"], r["p_dd50"], r["p_below_start"]))

    print("\nPart 2: evaluation with $3,000 target and $2,000 trailing drawdown, max 250 trading days.")
    print("Daily P&L is normal with standard deviation = risk and mean = edge x risk.\n")
    risks = list(range(100, 1601, 100))
    edges = (("no edge", 0.0), ("edge 0.05 sd/day", 0.05), ("edge 0.10 sd/day", 0.10))
    curves, table = [], {r: [] for r in risks}
    for label, e in edges:
        ys = []
        for r in risks:
            pr, _ = evaluation(daily_pnl(e, r, 250, a.paths, np.random.default_rng(a.seed)), 3000, 2000)
            ys.append(pr)
            table[r].append(pr)
        curves.append((label, ys))
    print("{:>6}".format("risk") + "".join("{:>18}".format(l) for l, _ in edges))
    for r in risks:
        print("{:>6}".format("$" + str(r)) + "".join("{:>18.1%}".format(x) for x in table[r]))
    pass_svg(curves, risks, os.path.join(HERE, "docs", "pass_rate.svg"))


if __name__ == "__main__":
    main()
