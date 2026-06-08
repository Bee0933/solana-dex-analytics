with source as (

    select * from {{ source('solana_raw', 'raw_dex_market_share') }}

)

select
    cast(snapshot_date           as date)      as snapshot_date,
    cast(snapshot_at             as timestamp) as snapshot_at,
    cast(dex_name                as string)    as dex_name,
    cast(trailing_24h_volume_usd as numeric)   as trailing_24h_volume_usd,
    cast(trailing_7d_volume_usd  as numeric)   as trailing_7d_volume_usd,
    cast(total_volume_usd        as numeric)   as total_volume_usd,
    cast(source_file             as string)    as source_file
from source
