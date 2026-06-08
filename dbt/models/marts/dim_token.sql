/*
  One row per unique token_address.
  Unions base tokens and quote tokens from pool snapshots to build a full token universe.
  Symbol comes from the most recent snapshot where the token appeared.
*/

with base_tokens as (

    select
        base_token_address  as token_address,
        base_token_symbol   as token_symbol,
        snapshot_date,
        1                   as is_base,
        0                   as is_quote
    from {{ ref('stg_dex_pools') }}
    where base_token_address is not null

),

quote_tokens as (

    select
        quote_token_address as token_address,
        quote_token_symbol  as token_symbol,
        snapshot_date,
        0                   as is_base,
        1                   as is_quote
    from {{ ref('stg_dex_pools') }}
    where quote_token_address is not null

),

all_appearances as (
    select * from base_tokens
    union all
    select * from quote_tokens
),

latest_symbol as (

    select
        token_address,
        token_symbol,
        row_number() over (
            partition by token_address
            order by snapshot_date desc
        ) as rn
    from all_appearances

),

aggregates as (

    select
        token_address,
        min(snapshot_date)          as first_seen_date,
        max(snapshot_date)          as last_seen_date,
        sum(is_base)                as appears_as_base_count,
        sum(is_quote)               as appears_as_quote_count
    from all_appearances
    group by token_address

),

final as (

    select
        l.token_address,
        l.token_symbol,
        a.first_seen_date,
        a.last_seen_date,
        a.appears_as_base_count,
        a.appears_as_quote_count
    from latest_symbol l
    inner join aggregates a on l.token_address = a.token_address
    where l.rn = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['token_address']) }} as token_key,
    token_address,
    token_symbol,
    first_seen_date,
    last_seen_date,
    appears_as_base_count,
    appears_as_quote_count
from final
