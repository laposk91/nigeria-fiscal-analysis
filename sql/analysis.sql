-- Nigeria public finance analysis queries (SQLite).
-- Each query starts with a "-- name:" line so the notebook can load it by name.
-- Run them directly with:  sqlite3 data/processed/fiscal.db < sql/analysis.sql


-- name: nigeria_fiscal_panel
-- One row per year with every Nigeria indicator side by side (pivot via conditional aggregation),
-- plus the headline ratio of this project: interest payments as a share of revenue.
WITH wide AS (
    SELECT
        year,
        MAX(CASE WHEN indicator = 'GGXWDG_NGDP' THEN value END) AS debt_pct_gdp,
        MAX(CASE WHEN indicator = 'GGXCNL_NGDP' THEN value END) AS balance_pct_gdp,
        MAX(CASE WHEN indicator = 'rev'         THEN value END) AS revenue_pct_gdp,
        MAX(CASE WHEN indicator = 'exp'         THEN value END) AS expenditure_pct_gdp,
        MAX(CASE WHEN indicator = 'ie'          THEN value END) AS interest_pct_gdp,
        MAX(CASE WHEN indicator = 'pb'          THEN value END) AS primary_balance_pct_gdp,
        MAX(CASE WHEN indicator = 'NGDP_RPCH'   THEN value END) AS real_gdp_growth,
        MAX(CASE WHEN indicator = 'PCPIPCH'     THEN value END) AS inflation,
        MAX(CASE WHEN indicator = 'NGDPD'       THEN value END) AS gdp_usd_bn,
        MAX(CASE WHEN indicator = 'LP'          THEN value END) AS population_m,
        MAX(is_projection)                                      AS is_projection
    FROM observations
    WHERE iso3 = 'NGA'
    GROUP BY year
)
SELECT
    *,
    ROUND(100.0 * interest_pct_gdp / NULLIF(revenue_pct_gdp, 0), 1) AS interest_pct_revenue,
    ROUND(1000.0 * gdp_usd_bn / population_m, 0)                    AS gdp_per_capita_usd
FROM wide
ORDER BY year;


-- name: debt_turning_points
-- Year-on-year change in the debt ratio (LAG window function) and the biggest jumps since 2010.
WITH debt AS (
    SELECT
        year,
        value AS debt_pct_gdp,
        value - LAG(value) OVER (ORDER BY year) AS change_pp
    FROM observations
    WHERE iso3 = 'NGA' AND indicator = 'GGXWDG_NGDP' AND is_projection = 0
)
SELECT year, debt_pct_gdp, ROUND(change_pp, 1) AS change_pp
FROM debt
WHERE year >= 2010
ORDER BY change_pp DESC
LIMIT 5;


-- name: era_averages
-- Average fiscal position by era. Eras are defined by the main structural breaks in the data:
-- debt relief (2005-06), the oil-price crash (2014-15) and the 2023 FX and subsidy reforms.
WITH tagged AS (
    SELECT
        o.*,
        CASE
            WHEN year BETWEEN 2006 AND 2014 THEN '1) 2006-2014 post debt relief'
            WHEN year BETWEEN 2015 AND 2022 THEN '2) 2015-2022 after oil crash'
            WHEN year BETWEEN 2023 AND 2024 THEN '3) 2023-2024 reform years'
        END AS era
    FROM observations o
    WHERE iso3 = 'NGA' AND is_projection = 0
)
SELECT
    era,
    ROUND(AVG(CASE WHEN indicator = 'GGXWDG_NGDP' THEN value END), 1) AS avg_debt_pct_gdp,
    ROUND(AVG(CASE WHEN indicator = 'rev'         THEN value END), 1) AS avg_revenue_pct_gdp,
    ROUND(AVG(CASE WHEN indicator = 'ie'          THEN value END), 2) AS avg_interest_pct_gdp,
    ROUND(AVG(CASE WHEN indicator = 'NGDP_RPCH'   THEN value END), 1) AS avg_real_growth,
    ROUND(AVG(CASE WHEN indicator = 'PCPIPCH'     THEN value END), 1) AS avg_inflation
FROM tagged
WHERE era IS NOT NULL
GROUP BY era
ORDER BY era;


-- name: peer_comparison
-- Debt, revenue and interest burden for Nigeria and seven African peers,
-- ranked within each year (RANK window function). Egypt is excluded from
-- revenue and interest ranks because the source has no data for it.
WITH wide AS (
    SELECT
        o.iso3,
        c.name AS country,
        o.year,
        MAX(CASE WHEN indicator = 'GGXWDG_NGDP' THEN value END) AS debt_pct_gdp,
        MAX(CASE WHEN indicator = 'rev'         THEN value END) AS revenue_pct_gdp,
        MAX(CASE WHEN indicator = 'ie'          THEN value END) AS interest_pct_gdp
    FROM observations o
    JOIN countries c USING (iso3)
    WHERE o.year BETWEEN 2010 AND 2024
    GROUP BY o.iso3, c.name, o.year
),
ratios AS (
    SELECT *, ROUND(100.0 * interest_pct_gdp / revenue_pct_gdp, 1) AS interest_pct_revenue
    FROM wide
)
SELECT
    *,
    RANK() OVER (PARTITION BY year ORDER BY debt_pct_gdp DESC)  AS debt_rank_high_to_low,
    CASE WHEN revenue_pct_gdp IS NOT NULL
         THEN RANK() OVER (PARTITION BY year, revenue_pct_gdp IS NULL ORDER BY revenue_pct_gdp ASC) END
                                                                AS revenue_rank_low_to_high,
    CASE WHEN interest_pct_revenue IS NOT NULL
         THEN RANK() OVER (PARTITION BY year, interest_pct_revenue IS NULL ORDER BY interest_pct_revenue DESC) END
                                                                AS interest_burden_rank_high_to_low
FROM ratios
ORDER BY year, iso3;


-- name: revenue_gap_vs_peers
-- How far Nigeria's revenue ratio sits below the peer average each year,
-- and what that gap is worth in US dollars.
WITH peer_avg AS (
    SELECT year, AVG(value) AS peer_avg_revenue
    FROM observations
    WHERE indicator = 'rev' AND iso3 <> 'NGA' AND year BETWEEN 2010 AND 2024
    GROUP BY year
),
nga AS (
    SELECT
        year,
        MAX(CASE WHEN indicator = 'rev'   THEN value END) AS nga_revenue,
        MAX(CASE WHEN indicator = 'NGDPD' THEN value END) AS gdp_usd_bn
    FROM observations
    WHERE iso3 = 'NGA' AND year BETWEEN 2010 AND 2024
    GROUP BY year
)
SELECT
    n.year,
    ROUND(n.nga_revenue, 1)                                          AS nga_revenue_pct_gdp,
    ROUND(p.peer_avg_revenue, 1)                                     AS peer_avg_revenue_pct_gdp,
    ROUND(p.peer_avg_revenue - n.nga_revenue, 1)                     AS gap_pp,
    ROUND((p.peer_avg_revenue - n.nga_revenue) / 100 * n.gdp_usd_bn, 1) AS gap_usd_bn
FROM nga n
JOIN peer_avg p USING (year)
ORDER BY n.year;
