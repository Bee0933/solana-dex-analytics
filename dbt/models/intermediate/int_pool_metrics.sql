with base as (

    select * from {{ ref('stg_dex_pools') }}

),


-- window aggregations 
with_window_aggs as (

    select
        *,

        -- total volume traded across all pools in this DEX on this date
        sum(trailing_24h_volume_usd) over (
            partition by dex_name, snapshot_date
        ) as dex_total_24h_volume,

        -- total volume traded across ALL DEXs on this date
        sum(trailing_24h_volume_usd) over (
            partition by snapshot_date
        ) as market_total_24h_volume,

        -- rolling 7-day average volume for this specific pool
        avg(trailing_24h_volume_usd) over (
            partition by pool_address
            order by snapshot_date
            rows between 6 preceding and current row
        ) as volume_7d_avg,

        -- volume from exactly 7 days ago (used for week-over-week calc)
        lag(trailing_24h_volume_usd, 7) over (
            partition by pool_address
            order by snapshot_date
        ) as volume_7d_ago

    from base

)

/*
  derive the percentage and ratio columns now that the
  window aggregation results are available as regular columns.
*/
select
    snapshot_date,
    snapshot_at,
    dex_name,
    pool_address,
    base_token_symbol,
    base_token_address,
    quote_token_symbol,
    quote_token_address,
    trailing_24h_volume_usd,
    trailing_24h_fees_usd,
    tvl_usd,
    source_file,
    dex_total_24h_volume,
    market_total_24h_volume,

    case
        when dex_total_24h_volume > 0
        then trailing_24h_volume_usd / dex_total_24h_volume * 100
        else 0
    end as pool_share_of_dex_pct,

    case
        when market_total_24h_volume > 0
        then trailing_24h_volume_usd / market_total_24h_volume * 100
        else 0
    end as pool_share_of_market_pct,

    case
        when trailing_24h_volume_usd > 0
        then trailing_24h_fees_usd / trailing_24h_volume_usd * 100
        else 0
    end as fee_rate_pct,

    case
        when tvl_usd > 0
        then trailing_24h_volume_usd / tvl_usd
        else 0
    end as volume_to_tvl_ratio,

    volume_7d_avg,

    -- (today - 7 days ago) / 7 days ago * 100; null when no data 7 days back yet
    (trailing_24h_volume_usd - volume_7d_ago)
        / nullif(volume_7d_ago, 0) * 100    as volume_wow_pct_change

from with_window_aggs
