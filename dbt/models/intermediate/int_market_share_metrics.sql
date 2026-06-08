with base as (

    select * from {{ ref('stg_dex_market_share') }}

),

-- total the market across all DEXs on each date
with_totals as (

    select
        *,
        sum(trailing_24h_volume_usd) over (
            partition by snapshot_date
        ) as total_market_24h_volume
    from base

),

-- each DEX's share of that total
with_share as (

    select
        *,
        case
            when total_market_24h_volume > 0
            then trailing_24h_volume_usd / total_market_24h_volume * 100
            else 0
        end as dex_market_share_pct
    from with_totals

),

-- 7-day rolling average of that share for each DEX
with_avg as (

    select
        *,
        avg(dex_market_share_pct) over (
            partition by dex_name
            order by snapshot_date
            rows between 6 preceding and current row
        ) as share_7d_avg
    from with_share

)

select
    snapshot_date,
    snapshot_at,
    dex_name,
    trailing_24h_volume_usd,
    trailing_7d_volume_usd,
    total_volume_usd,
    source_file,
    total_market_24h_volume,
    dex_market_share_pct,
    share_7d_avg,
    dex_market_share_pct - share_7d_avg as share_change_vs_7d_avg_pct
from with_avg
