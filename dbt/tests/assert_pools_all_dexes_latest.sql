-- Fails if the most recent pool snapshot is missing any of the 3 DEXs.
-- Catches a partial run where one DEX ingest silently dropped out.
with latest as (
    select max(snapshot_date) as snapshot_date from {{ ref('stg_dex_pools') }}
)

select count(distinct dex_name) as dex_count
from {{ ref('stg_dex_pools') }}
where snapshot_date = (select snapshot_date from latest)
having count(distinct dex_name) < 3
