-- Client roster fields on roosts (CRM Deals: _infra/occ-feeds/clients.json). Records only; their old events are not imported.
alter table roosts add column stage text;          -- deal stage word: contract | hourly | direct | prospect: <status>
alter table roosts add column origin text;         -- where the relationship came from: upwork | consulting | direct
alter table roosts add column paid_cents bigint;   -- paid to date
alter table roosts add column pending_cents bigint; -- pending + funded, not yet paid
create or replace view roost_rows with (security_invoker = true) as
select r.id, r.workspace_id, r.kind, r.status, r.roosted_at, r.value_cents,
       p.full_name, c.name as company,
       (select array_agg(distinct i.hunt_type) from hunt_items i where i.roost_id = r.id) as came_from,
       (select max(x.at) from (
          select e.at from events e where e.roost_id = r.id
          union all select e.at from events e join hunt_items i on i.id = e.item_id where i.roost_id = r.id
          union all select rp.received_at from replies rp where rp.roost_id = r.id) x) as last_activity,
       r.stage, r.origin, r.paid_cents, r.pending_cents
from roosts r
left join people p on p.id = r.person_id
left join companies c on c.id = r.company_id
where r.deleted_at is null;
