select
    -- surrogate keys (hashed IDs used to join to dimension tables)
    {{ dbt_utils.generate_surrogate_key(['pool_address', 'snapshot_date']) }} as pool_snapshot_key,
    {{ dbt_utils.generate_surrogate_key(['pool_address'])                  }} as pool_key,
    {{ dbt_utils.generate_surrogate_key(['base_token_address'])            }} as base_token_key,
    {{ dbt_utils.generate_surrogate_key(['quote_token_address'])           }} as quote_token_key,

    -- time
    snapshot_date,
    snapshot_at,

    -- identifiers
    dex_name,
    pool_address,
    base_token_symbol,
    base_token_address,
    quote_token_symbol,
    quote_token_address,

    -- raw volume / fee / liquidity metrics
    trailing_24h_volume_usd,
    trailing_24h_fees_usd,
    tvl_usd,

    -- derived metrics from intermediate layer
    dex_total_24h_volume,
    market_total_24h_volume,
    pool_share_of_dex_pct,
    pool_share_of_market_pct,
    fee_rate_pct,
    volume_to_tvl_ratio,
    volume_7d_avg,
    volume_wow_pct_change,

    source_file

from {{ ref('int_pool_metrics') }}
