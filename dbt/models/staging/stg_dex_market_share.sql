with source as (

    select * from {{ source('solana_raw', 'raw_dex_market_share') }}

),

normalized as (

    select
        cast(snapshot_date as date)      as snapshot_date,
        cast(snapshot_at   as timestamp) as snapshot_at,

        -- DefiLlama returns protocol-level names (e.g. "meteora dlmm",
        -- "orca dex", "raydium amm"). Roll them up to the canonical DEX so
        -- market share is measured per DEX, not per individual protocol.
        case
            when lower(dex_name) like '%raydium%' then 'raydium'
            when lower(dex_name) like '%orca%'    then 'orca'
            when lower(dex_name) like '%meteora%' then 'meteora'
            else lower(dex_name)
        end as dex_name,

        cast(trailing_24h_volume_usd as numeric) as trailing_24h_volume_usd,
        cast(trailing_7d_volume_usd  as numeric) as trailing_7d_volume_usd,
        cast(total_volume_usd        as numeric) as total_volume_usd,
        cast(source_file             as string)  as source_file
    from source

)

-- sum the protocol rows into one row per DEX per day
select
    snapshot_date,
    dex_name,
    max(snapshot_at)             as snapshot_at,
    sum(trailing_24h_volume_usd) as trailing_24h_volume_usd,
    sum(trailing_7d_volume_usd)  as trailing_7d_volume_usd,
    sum(total_volume_usd)        as total_volume_usd,
    max(source_file)             as source_file
from normalized
group by snapshot_date, dex_name
