-- Fails if any staging row has a negative 24h volume.
-- A negative volume means the API returned bad data or the cast went wrong.
select *
from {{ ref('stg_dex_pools') }}
where trailing_24h_volume_usd < 0
