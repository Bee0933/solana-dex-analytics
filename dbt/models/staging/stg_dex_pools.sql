with source as (

    select *
    from {{ source('solana_raw', 'raw_dex_pools') }}
    where snapshot_date >= '2026-06-01'
      and trailing_24h_volume_usd is not null

)

select
    cast(snapshot_date            as date)      as snapshot_date,
    cast(snapshot_at              as timestamp) as snapshot_at,
    cast(dex_name                 as string)    as dex_name,
    cast(pool_address             as string)    as pool_address,
    cast(base_token_symbol        as string)    as base_token_symbol,
    cast(base_token_address       as string)    as base_token_address,
    cast(quote_token_symbol       as string)    as quote_token_symbol,
    cast(quote_token_address      as string)    as quote_token_address,
    cast(trailing_24h_volume_usd  as numeric)   as trailing_24h_volume_usd,
    cast(trailing_24h_fees_usd    as numeric)   as trailing_24h_fees_usd,
    cast(tvl_usd                  as numeric)   as tvl_usd,
    cast(source_file              as string)    as source_file
from source
