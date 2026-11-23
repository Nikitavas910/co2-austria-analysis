import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import analysis  # noqa: E402


def test_fit_log_linear_recovers_known_coefficients():
    x = np.linspace(500, 80000, 200)
    y = 2.0 + 3.0 * np.log(x)
    beta, r2 = analysis.fit_log_linear(x, y)
    assert np.allclose(beta, [2.0, 3.0])
    assert r2 > 0.999999


def test_load_queries_finds_all_blocks():
    q = analysis.load_queries()
    assert set(q) == {
        "latest_per_capita_ranking",
        "austria_yoy",
        "peak_and_reduction",
        "rolling_5y",
        "gdp_vs_emissions",
    }
    assert all(sql.rstrip().endswith(";") for sql in q.values())
