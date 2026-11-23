-- Queries used by src/analysis.py. Each block starts with "-- name: <id>".
-- Database: SQLite, table "co2" loaded from the Our World in Data CO2 dataset.

-- name: latest_per_capita_ranking
-- CO2 emissions per person in the latest year with data, for the peer group.
SELECT country,
       year,
       ROUND(co2_per_capita, 2) AS co2_per_capita_t,
       RANK() OVER (ORDER BY co2_per_capita DESC) AS rank_high_to_low
FROM co2
WHERE country IN ({peers})
  AND year = (SELECT MAX(year) FROM co2 WHERE country = 'Austria' AND co2_per_capita IS NOT NULL)
ORDER BY rank_high_to_low;

-- name: austria_yoy
-- Year-over-year change of Austria's total CO2 (million tonnes) using LAG().
SELECT year,
       ROUND(co2, 2) AS co2_mt,
       ROUND(co2 - LAG(co2) OVER (ORDER BY year), 2) AS change_mt,
       ROUND(100.0 * (co2 - LAG(co2) OVER (ORDER BY year)) / LAG(co2) OVER (ORDER BY year), 2) AS change_pct
FROM co2
WHERE country = 'Austria' AND year >= 1990
ORDER BY year;

-- name: peak_and_reduction
-- For every peer: year of peak per-capita emissions (since 1950) and the change since then.
WITH ranked AS (
    SELECT country, year, co2_per_capita,
           ROW_NUMBER() OVER (PARTITION BY country ORDER BY co2_per_capita DESC) AS rn
    FROM co2
    WHERE country IN ({peers}) AND year >= 1950 AND co2_per_capita IS NOT NULL
),
latest AS (
    SELECT country, co2_per_capita AS latest_pc
    FROM co2
    WHERE country IN ({peers}) AND year = (SELECT MAX(year) FROM co2 WHERE country = 'Austria' AND co2_per_capita IS NOT NULL)
)
SELECT r.country,
       r.year AS peak_year,
       ROUND(r.co2_per_capita, 2) AS peak_pc_t,
       ROUND(l.latest_pc, 2) AS latest_pc_t,
       ROUND(100.0 * (l.latest_pc - r.co2_per_capita) / r.co2_per_capita, 1) AS change_since_peak_pct
FROM ranked r JOIN latest l USING (country)
WHERE r.rn = 1
ORDER BY change_since_peak_pct;

-- name: rolling_5y
-- 5-year rolling mean of per-capita emissions for the peer group (window function).
SELECT country, year,
       ROUND(AVG(co2_per_capita) OVER (PARTITION BY country ORDER BY year ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 3) AS pc_rolling5
FROM co2
WHERE country IN ({peers}) AND year >= 1990 AND co2_per_capita IS NOT NULL
ORDER BY country, year;

-- name: gdp_vs_emissions
-- Countries (no aggregates) with complete GDP, population and CO2 in the chosen year.
SELECT country,
       gdp / population AS gdp_per_capita,
       co2_per_capita
FROM co2
WHERE year = {year}
  AND iso_code IS NOT NULL
  AND gdp IS NOT NULL AND population > 1000000 AND co2_per_capita IS NOT NULL;
