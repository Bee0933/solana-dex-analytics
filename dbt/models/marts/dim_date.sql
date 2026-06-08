/*
  A standard calendar/date dimension.
  Spans from the first possible snapshot date through one year in the future,
  so fact tables always have a matching date row to join against.
*/

with date_spine as (

    {{ dbt_utils.date_spine(
        datepart   = "day",
        start_date = "cast('2026-06-01' as date)",
        end_date   = "date_add(current_date(), interval 365 day)"
    ) }}

)

select
    {{ dbt_utils.generate_surrogate_key(['date_day']) }} as date_key,

    date_day                                                    as calendar_date,
    extract(dayofweek from date_day)                            as day_of_week,       -- 1=Sun, 7=Sat in BigQuery
    extract(week      from date_day)                            as week_number,
    extract(month     from date_day)                            as month_number,
    extract(quarter   from date_day)                            as quarter,
    extract(year      from date_day)                            as year,
    extract(dayofweek from date_day) in (1, 7)                  as is_weekend,
    date_day = date_trunc(date_day, month)                      as is_month_start,
    date_day = last_day(date_day)                               as is_month_end

from date_spine
