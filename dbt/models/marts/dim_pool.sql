/*
  One row per unique pool_address.
  Metadata (token symbols, DEX name) comes from the most recent snapshot.
  Lifetime stats are aggregated across all snapshots we have ever observed.
*/

with latest_meta as (

    select
        pool_address,
        dex_name,
        base_token_symbol,
        base_token_address,
        quote_token_symbol,
        quote_token_address,
        row_number() over (
            partition by pool_address
            order by snapshot_date desc
        ) as rn
    from {{ ref('stg_dex_pools') }}

),

aggregates as (

    select
        pool_address,
        min(snapshot_date)                  as first_seen_date,
        max(snapshot_date)                  as last_seen_date,
        sum(trailing_24h_volume_usd)        as lifetime_observed_volume_usd,
        sum(trailing_24h_fees_usd)          as lifetime_observed_fees_usd,
        count(distinct snapshot_date)       as snapshot_days_count
    from {{ ref('stg_dex_pools') }}
    group by pool_address

),

final as (

    select
        m.pool_address,
        m.dex_name,
        m.base_token_symbol,
        m.base_token_address,
        m.quote_token_symbol,
        m.quote_token_address,
        a.first_seen_date,
        a.last_seen_date,
        a.lifetime_observed_volume_usd,
        a.lifetime_observed_fees_usd,
        a.snapshot_days_count
    from latest_meta m
    inner join aggregates a on m.pool_address = a.pool_address
    where m.rn = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['pool_address']) }} as pool_key,
    pool_address,
    dex_name,
    base_token_symbol,
    base_token_address,
    quote_token_symbol,
    quote_token_address,
    first_seen_date,
    last_seen_date,
    lifetime_observed_volume_usd,
    lifetime_observed_fees_usd,
    snapshot_days_count
from final
