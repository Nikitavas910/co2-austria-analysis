"""CO2 emissions of Austria compared with its neighbours: SQL + Python analysis.

Pipeline: CSV -> SQLite -> SQL queries (window functions) -> pandas -> charts + linear-algebra regression.
Run:  python src/download_data.py && python src/analysis.py
"""
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "owid-co2-data.csv"
DB = ROOT / "data" / "co2.sqlite"
SQL = ROOT / "sql" / "queries.sql"
OUT = ROOT / "results"

PEERS = ["Austria", "Germany", "Switzerland", "Czechia", "Hungary", "Italy", "Slovenia", "Slovakia"]
REGRESSION_YEAR = 2022  # latest year with GDP data


def load_database() -> sqlite3.Connection:
    df = pd.read_csv(DATA)
    con = sqlite3.connect(DB)
    df.to_sql("co2", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS idx_country_year ON co2(country, year)")
    return con


def load_queries() -> dict[str, str]:
    queries, name, buf = {}, None, []
    for line in SQL.read_text().splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf).strip()
            name, buf = line.split(":", 1)[1].strip(), []
        elif name and not (line.startswith("--") and not buf):
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf).strip()
    return queries


def run(con, queries, name, **fmt) -> pd.DataFrame:
    peers = ", ".join("'" + p + "'" for p in PEERS)
    return pd.read_sql_query(queries[name].format(peers=peers, **fmt), con)


def fit_log_linear(x: np.ndarray, y: np.ndarray):
    """Least squares for y = a + b*ln(x), solved with the normal equations (X^T X) beta = X^T y."""
    X = np.column_stack([np.ones_like(x), np.log(x)])
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    resid = y - X @ beta
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return beta, r2


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = load_database()
    q = load_queries()

    ranking = run(con, q, "latest_per_capita_ranking")
    yoy = run(con, q, "austria_yoy")
    peaks = run(con, q, "peak_and_reduction")
    rolling = run(con, q, "rolling_5y")
    gdp = run(con, q, "gdp_vs_emissions", year=REGRESSION_YEAR)

    ranking.to_csv(OUT / "ranking_latest.csv", index=False)
    peaks.to_csv(OUT / "peak_and_reduction.csv", index=False)

    # Chart 1: rolling per-capita emissions, Austria highlighted
    fig, ax = plt.subplots(figsize=(9, 5))
    for country, g in rolling.groupby("country"):
        if country == "Austria":
            ax.plot(g.year, g.pc_rolling5, color="#c8102e", lw=3, label="Austria")
        else:
            ax.plot(g.year, g.pc_rolling5, color="#9aa0a6", lw=1, alpha=0.8)
            ax.annotate(country, (g.year.iloc[-1], g.pc_rolling5.iloc[-1]), fontsize=7, color="#5f6368", xytext=(3, 0), textcoords="offset points")
    ax.set_title("CO2 per person, 5-year rolling mean (tonnes)")
    ax.set_xlabel("Year")
    ax.set_ylabel("t CO2 per person")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "per_capita_rolling.png", dpi=150)
    plt.close(fig)

    # Chart 2: Austria's emissions by source
    src = pd.read_sql_query(
        "SELECT year, coal_co2, oil_co2, gas_co2, cement_co2 FROM co2 WHERE country='Austria' AND year >= 1950", con
    ).set_index("year")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.stackplot(src.index, src.T.values, labels=["Coal", "Oil", "Gas", "Cement"], colors=["#3c4043", "#c8102e", "#f9ab00", "#9aa0a6"])
    ax.set_title("Austria: CO2 emissions by source (million tonnes)")
    ax.set_xlabel("Year")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "austria_by_source.png", dpi=150)
    plt.close(fig)

    # Chart 3 + regression: GDP per capita vs CO2 per capita
    x = gdp.gdp_per_capita.to_numpy(float)
    y = gdp.co2_per_capita.to_numpy(float)
    beta, r2 = fit_log_linear(x, y)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x, y, s=14, color="#9aa0a6")
    at = gdp[gdp.country == "Austria"]
    ax.scatter(at.gdp_per_capita, at.co2_per_capita, s=60, color="#c8102e", zorder=3, label="Austria")
    xs = np.linspace(x.min(), x.max(), 200)
    ax.plot(xs, beta[0] + beta[1] * np.log(xs), color="#1a73e8", lw=2, label=f"y = {beta[0]:.1f} + {beta[1]:.2f}*ln(x)  (R2 = {r2:.2f})")
    ax.set_xscale("log")
    ax.set_title(f"GDP vs CO2 per person, {REGRESSION_YEAR} (countries > 1M people)")
    ax.set_xlabel("GDP per person (international $, log scale)")
    ax.set_ylabel("t CO2 per person")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "gdp_vs_co2.png", dpi=150)
    plt.close(fig)

    pred_at = beta[0] + beta[1] * np.log(float(at.gdp_per_capita.iloc[0]))
    summary = {
        "latest_year": int(ranking.year.iloc[0]),
        "austria_rank": int(ranking.loc[ranking.country == "Austria", "rank_high_to_low"].iloc[0]),
        "n_peers": len(ranking),
        "regression_n": len(gdp),
        "beta0": beta[0],
        "beta1": beta[1],
        "r2": r2,
        "austria_actual": float(at.co2_per_capita.iloc[0]),
        "austria_predicted": float(pred_at),
    }
    lines = [
        "# Results (generated by src/analysis.py)",
        "",
        f"## CO2 per person, {summary['latest_year']}",
        ranking.to_markdown(index=False),
        "",
        "## Peak per-capita emissions and change since the peak (since 1950)",
        peaks.to_markdown(index=False),
        "",
        f"## Regression, {REGRESSION_YEAR}: co2_per_capita = a + b * ln(gdp_per_capita)",
        f"- countries: {summary['regression_n']}",
        f"- a = {summary['beta0']:.2f}, b = {summary['beta1']:.2f}, R2 = {summary['r2']:.2f}",
        f"- Austria: actual {summary['austria_actual']:.2f} t, model {summary['austria_predicted']:.2f} t",
    ]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nlargest YoY drops in Austria since 1990:")
    print(yoy.nsmallest(3, "change_pct").to_string(index=False))


if __name__ == "__main__":
    main()
