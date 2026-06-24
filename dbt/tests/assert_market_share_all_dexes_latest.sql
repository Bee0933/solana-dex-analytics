-- Fails if the most recent market-share snapshot doesn't cover all 3 canonical DEXs
-- (raydium/orca/meteora) after the staging rollup of DefiLlama protocols.
with latest as (
    select max(snapshot_date) as snapshot_date from {{ ref('fct_dex_market_share_daily') }}
)

select count(distinct dex_name) as dex_count
from {{ ref('fct_dex_market_share_daily') }}
where snapshot_date = (select snapshot_date from latest)
having count(distinct dex_name) < 3
