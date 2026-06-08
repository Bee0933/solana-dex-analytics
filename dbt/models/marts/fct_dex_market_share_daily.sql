select
    -- surrogate key
    {{ dbt_utils.generate_surrogate_key(['dex_name', 'snapshot_date']) }} as market_share_snapshot_key,

    -- time
    snapshot_date,
    snapshot_at,

    -- identifier
    dex_name,

    -- raw volume from DefiLlama
    trailing_24h_volume_usd,
    trailing_7d_volume_usd,
    total_volume_usd,

    -- derived market share metrics
    total_market_24h_volume,
    dex_market_share_pct,
    share_7d_avg,
    share_change_vs_7d_avg_pct,

    source_file

from {{ ref('int_market_share_metrics') }}
