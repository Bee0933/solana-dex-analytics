-- Fails if any snapshot_date is in the future.
-- The pipeline captures yesterday's 24h window — future dates mean
-- the snapshot_date calculation in the ingest task is broken.
select *
from {{ ref('stg_dex_pools') }}
where snapshot_date > current_date()
