-- One-shot SYSTEM per hunt item (Tyler 11-22 ~2:50 AM MT, voice, looking at Eagle Eye: "it is not clear which one-shot system we
-- are using, it just says Upwork ... the one-shot system we're using should be within the row ... we should have several one-shots
-- within Upwork: one of the one-shots should be me doing the entire VSL for a specific niche ... it is also different if I only want
-- to do the intro versus the entire VSL").
--
-- The hunt type is the CHANNEL (Upwork | Funding | Job post | Investor). The one-shot system is WHAT is made and sent inside it:
--   * one_shot_systems: the catalog, one row per system, per workspace (like hunt_types). A new one-shot is a new row
--     (POST /rest/oneShotSystems), never a code change: forward-compatible.
--       take     = what Tyler records: intro (his live intro hands off to the voice agent) | entire (he does the whole VSL)
--                  | none (no video)
--       template = the takeflow VSL script template (takeflow/templates/<template>.yaml) that builds its takes
--       is_default = the system a lane's one-shot gets when the builder names none (one per hunt type)
--   * hunt_items.one_shot_system: the item's system (null = no one-shot started). FK to the catalog, so an unknown slug is refused.
--     Set explicitly by the system that makes the take (takeflow vsl-make --take intro|entire -> render_done fact) or derived
--     here by trigger the moment a one-shot exists (stage one_shot, a VSL stage past none, or a one_shots row): no agent has to
--     remember to set it.
create table one_shot_systems (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  key           text not null check (key ~ '^[a-z0-9][a-z0-9-]{1,60}$'),
  label         text not null,
  hunt_type     text not null,
  take          text not null default 'intro' check (take in ('intro', 'entire', 'none')),
  template      text,
  status        text not null default 'active' check (status in ('active', 'placeholder', 'retired')),
  is_default    boolean not null default false,
  description   text,
  sort          smallint not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz,
  unique (workspace_id, key)
);
create unique index one_shot_systems_one_default on one_shot_systems (workspace_id, hunt_type) where is_default and deleted_at is null;
create trigger one_shot_systems_updated before update on one_shot_systems for each row execute function touch_updated_at();

alter table one_shot_systems enable row level security;
alter table one_shot_systems force row level security;
create policy ws_isolation on one_shot_systems to eagle_app
  using (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
  with check (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid);
create policy owner_all on one_shot_systems to eagleeye_owner using (true) with check (true);
grant select, insert, update on one_shot_systems to eagle_app;

-- the systems that exist today (DOMAINS.md domain 1 "ONE-SHOT SYSTEMS WITHIN UPWORK" + "VSL SYSTEMS = ONE PER ONE-SHOT SYSTEM";
-- takeflow/templates/*.yaml status), seeded into every workspace
insert into one_shot_systems (workspace_id, key, label, hunt_type, take, template, status, is_default, description, sort)
select w.id, s.key, s.label, s.hunt_type, s.take, s.template, s.status, s.is_default, s.description, s.sort
from workspaces w, (values
  ('upwork-intro-vsl',    'Intro VSL',           'upwork',   'intro',  'upwork',    'active',      true,
   'Tyler''s short live intro hands off to the voice agent: diagram + MVP of their post', 10),
  ('upwork-entire-vsl',   'Entire VSL',          'upwork',   'entire', 'upwork',    'active',      false,
   'Tyler records the whole VSL himself, for one niche', 20),
  ('funding-walkthrough', 'Founder walkthrough', 'funding',  'intro',  'funding',   'active',      true,
   'Offer first; on a yes, Tyler''s live intro + the voice agent''s walkthrough of their product (3 findings, diagram, MVP)', 30),
  ('jobs-video-demo',     'Video + demo',        'job_post', 'intro',  'jobs',      'placeholder', true,
   'Video + small demo of the posted need, to the hiring manager (template not written yet)', 40),
  ('investor-fleet-demo', 'Fleet demo',          'investor', 'intro',  'investors', 'placeholder', true,
   '60-90 s live fleet demo opening on their latest similar bet (template not written yet; sends held)', 50)
) as s(key, label, hunt_type, take, template, status, is_default, description, sort);

alter table hunt_items add column one_shot_system text;
alter table hunt_items add constraint hunt_items_one_shot_system_fk
  foreign key (workspace_id, one_shot_system) references one_shot_systems (workspace_id, key);

-- the default the moment a one-shot exists, whoever wrote the row (upsert, PATCH, fact): never overwrites a system already set
create function default_one_shot_system(p_ws uuid, p_hunt_type text) returns text language sql stable as $$
  select key from one_shot_systems where workspace_id = p_ws and hunt_type = p_hunt_type and is_default and deleted_at is null limit 1
$$;
create function hunt_items_one_shot_system() returns trigger language plpgsql as $$
begin
  if new.one_shot_system is null and (new.stage = 'one_shot' or new.vsl_stage <> 'none') then
    new.one_shot_system := default_one_shot_system(new.workspace_id, new.hunt_type);
  end if;
  return new;
end $$;
create trigger hunt_items_one_shot_system before insert or update on hunt_items
  for each row execute function hunt_items_one_shot_system();

create function one_shots_set_system() returns trigger language plpgsql as $$
begin
  update hunt_items i set one_shot_system = default_one_shot_system(i.workspace_id, i.hunt_type)
   where i.id = new.item_id and i.one_shot_system is null;
  return null;
end $$;
create trigger one_shots_set_system after insert on one_shots for each row execute function one_shots_set_system();

-- backfill: every item with a one-shot today gets its lane's system (Workflow Solutions = Upwork Intro VSL, B2 was his 15 s
-- intro + the voice agent; River / MouseCat / Touchmark / Luwian = the funding walkthrough offer). Everything else stays null.
update hunt_items i set one_shot_system = default_one_shot_system(i.workspace_id, i.hunt_type)
 where i.one_shot_system is null and i.deleted_at is null
   and (i.stage = 'one_shot' or i.vsl_stage <> 'none' or exists (select 1 from one_shots o where o.item_id = i.id and o.deleted_at is null));

-- the feed view carries it (0006's columns, plus one_shot_system at the end)
create or replace view feed_rows with (security_invoker = true) as
select i.id, i.workspace_id, i.hunt_type, t.icon as hunt_icon, i.target, i.signal,
       i.signal_at, i.found_at, ft.first_sent_at,
       round(extract(epoch from (i.found_at - i.signal_at)) / 60.0, 1)     as find_lag_minutes,
       round(extract(epoch from (ft.first_sent_at - i.signal_at)) / 60.0, 1) as speed_to_lead_minutes,
       os.status as one_shot_status, i.stage, i.vsl_stage, i.reply_status, i.fit,
       i.backend_agent, i.frontend_agent, i.details, i.updated_at, i.subtype, t.label as hunt_label, i.one_shot_system
from hunt_items i
join hunt_types t on t.id = i.hunt_type_id
left join lateral (select min(x.sent_at) as first_sent_at from touches x where x.item_id = i.id and x.status = 'sent') ft on true
left join lateral (select status from one_shots o where o.item_id = i.id and o.deleted_at is null
                   order by o.id desc limit 1) os on true
where i.deleted_at is null and i.stage not in ('roosted','passed');
