-- speed-to-lead counts only a touch that left (a queued LinkedIn/dialer/Upwork step is not a send)
create or replace view feed_rows with (security_invoker = true) as
select i.id, i.workspace_id, i.hunt_type, t.icon as hunt_icon, i.target, i.signal,
       i.signal_at, i.found_at, ft.first_sent_at,
       round(extract(epoch from (i.found_at - i.signal_at)) / 60.0, 1)     as find_lag_minutes,
       round(extract(epoch from (ft.first_sent_at - i.signal_at)) / 60.0, 1) as speed_to_lead_minutes,
       os.status as one_shot_status, i.stage, i.vsl_stage, i.reply_status, i.fit,
       i.backend_agent, i.frontend_agent, i.details, i.updated_at
from hunt_items i
join hunt_types t on t.id = i.hunt_type_id
left join lateral (select min(x.sent_at) as first_sent_at from touches x where x.item_id = i.id and x.status = 'sent') ft on true
left join lateral (select status from one_shots o where o.item_id = i.id and o.deleted_at is null
                   order by o.id desc limit 1) os on true
where i.deleted_at is null and i.stage not in ('roosted','passed');
