-- Fails if the most recent pool snapshot has too few rows (< 50).
-- Catches an ingest that ran but returned almost no data.
with latest as (
    select max(snapshot_date) as snapshot_date from {{ ref('stg_dex_pools') }}
)

select count(*) as row_count
from {{ ref('stg_dex_pools') }}
where snapshot_date = (select snapshot_date from latest)
having count(*) < 50
