-- Eagle Eye core schema v0 (Postgres 18: native uuidv7()).
-- Source: _shots/stream-vsl/research_notes/Offers and hunts rehaul/eagle_eye_backend.md section 5 (approved 11-21).
-- Changes from that DDL, each with its reason:
--   * hunt_items.found_at (ingest time) + feed_rows.speed_to_lead_minutes (first touch.sent_at - signal_at): Tyler 11-21 "hit signals ASAP".
--   * upwork_jobs.job_url nullable: Upwork alert mail carries the title only, never the job URL; null beats an invented URL.
--   * funding_signals.kind: launch | form_d | news, the source kind the feed chip shows.
--   * Ask role, ask_workspace_id() and ask_isolation policies dropped: Tyler 11-21 "no Ask bar".
--   * owner_all policy for eagleeye_owner (migrations, key minting, nightly purge); request traffic runs as eagle_app.
--   * touches_item_idx for the speed-to-lead subquery.

create extension if not exists pg_trgm;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'eagle_app') then create role eagle_app nologin; end if;
end $$;

-- ---------- tenancy ----------
create table workspaces (
  id          uuid primary key default uuidv7(),
  slug        text not null unique,
  name        text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

create table workspace_members (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  email         text not null,
  name          text not null,
  role          text not null default 'owner' check (role in ('owner','member','viewer')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz,
  unique (workspace_id, email)
);

create table api_keys (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  name          text not null,
  actor_kind    text not null check (actor_kind in ('agent_backend','agent_frontend','integration','member')),
  token_sha256  bytea not null unique,
  scopes        text[] not null default '{}',
  expires_at    timestamptz not null,
  revoked_at    timestamptz,
  last_used_at  timestamptz,
  created_at    timestamptz not null default now()
);

-- ---------- hunt types ----------
create table hunt_types (
  id              uuid primary key default uuidv7(),
  workspace_id    uuid not null references workspaces(id),
  key             text not null,
  label           text not null,
  icon            text not null,
  version         text not null,
  extension_table text,
  fields_schema   jsonb not null default '{}',
  roost_rules     jsonb not null default '{}',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  unique (workspace_id, key)
);

-- ---------- who is hunted ----------
create table companies (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  name          text not null,
  domain        text,
  linkedin_url  text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create unique index companies_domain_uq on companies (workspace_id, lower(domain)) where domain is not null and deleted_at is null;
create index companies_name_idx on companies (workspace_id, lower(name)) where deleted_at is null;

create table people (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  company_id    uuid references companies(id),
  full_name     text not null,
  title         text,
  email         text,
  linkedin_url  text,
  handles       jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create unique index people_email_uq on people (workspace_id, lower(email)) where email is not null and deleted_at is null;
create index people_name_trgm on people using gin (full_name gin_trgm_ops);

-- ---------- roosts ----------
create table roosts (
  id              uuid primary key default uuidv7(),
  workspace_id    uuid not null references workspaces(id),
  person_id       uuid references people(id),
  company_id      uuid references companies(id),
  kind            text not null check (kind in ('client','partner','network','investor')),
  status          text not null default 'active' check (status in ('active','paused','churned')),
  source_item_id  uuid,
  roosted_at      timestamptz not null default now(),
  value_cents     bigint,
  notes           text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  check (person_id is not null or company_id is not null)
);
create unique index roosts_person_uq on roosts (workspace_id, person_id) where person_id is not null and deleted_at is null;

-- ---------- the core hunt row ----------
create table hunt_items (
  id              uuid primary key default uuidv7(),
  workspace_id    uuid not null references workspaces(id),
  hunt_type_id    uuid not null references hunt_types(id),
  hunt_type       text not null,
  external_id     text not null,
  person_id       uuid references people(id),
  company_id      uuid references companies(id),
  target          text not null,
  signal          text not null,
  signal_at       timestamptz not null,               -- source publish time (the signal)
  found_at        timestamptz not null default now(), -- ingest time (first write; never moved by a re-find)
  fit             smallint check (fit between 0 and 100),
  stage           text not null default 'new'
                  check (stage in ('new','qualified','one_shot','sent','replied','roosted','passed')),
  vsl_stage       text not null default 'none'
                  check (vsl_stage in ('none','scripted','recorded','rendered','sent','watched')),
  reply_status    text not null default 'none'
                  check (reply_status in ('none','opened','watched','replied','booked','won','lost')),
  backend_agent   text,
  frontend_agent  text,
  roost_id        uuid references roosts(id),
  details         jsonb not null default '{}',
  created_by      jsonb not null default '{"source":"MANUAL"}',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  unique (workspace_id, hunt_type, external_id),
  check ((stage = 'roosted') = (roost_id is not null))
);
alter table roosts add constraint roosts_source_item_fk foreign key (source_item_id) references hunt_items(id);

create index hunt_items_feed_idx on hunt_items (workspace_id, signal_at desc, id desc)
  where deleted_at is null and stage not in ('roosted','passed');
create index hunt_items_roost_idx on hunt_items (roost_id) where roost_id is not null;
create index hunt_items_details_gin on hunt_items using gin (details jsonb_path_ops);

-- ---------- per-type extension tables ----------
create table funding_signals (
  item_id        uuid primary key references hunt_items(id) on delete cascade,
  workspace_id   uuid not null references workspaces(id),
  kind           text not null check (kind in ('launch','form_d','news')),
  round          text not null,
  amount_usd     bigint,
  announced_on   date not null,
  lead_investor  text,
  source_url     text not null
);

create table job_posts (
  item_id        uuid primary key references hunt_items(id) on delete cascade,
  workspace_id   uuid not null references workspaces(id),
  title          text not null,
  board          text not null,
  posted_at      timestamptz not null,
  location       text,
  salary_range   text,
  source_url     text not null
);

create table upwork_jobs (
  item_id          uuid primary key references hunt_items(id) on delete cascade,
  workspace_id     uuid not null references workspaces(id),
  title            text not null,
  budget_type      text check (budget_type in ('fixed','hourly')),
  budget_min_usd   numeric(10,2),
  budget_max_usd   numeric(10,2),
  client_country   text,
  client_spend_usd numeric(12,2),
  client_hire_rate numeric(5,2),
  proposals_band   text,
  posted_at        timestamptz not null,
  job_url          text
);

-- ---------- one-shots and recordings ----------
create table one_shots (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  item_id       uuid not null references hunt_items(id),
  kind          text not null check (kind in ('demo','vsl','loom','mockup','audit')),
  status        text not null default 'draft' check (status in ('draft','building','ready','sent','failed')),
  demo_url      text,
  script        text,
  assets        jsonb not null default '[]',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create index one_shots_item_idx on one_shots (item_id);

create table recordings (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  one_shot_id   uuid not null references one_shots(id),
  take_path     text not null,
  duration_s    numeric(8,2),
  is_final      boolean not null default false,
  recorded_at   timestamptz not null default now(),
  created_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create unique index recordings_one_final on recordings (one_shot_id) where is_final and deleted_at is null;

-- ---------- outreach ----------
create table touches (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  item_id       uuid references hunt_items(id),
  roost_id      uuid references roosts(id),
  one_shot_id   uuid references one_shots(id),
  channel       text not null check (channel in ('email','linkedin','upwork','x','sms','call')),
  sent_at       timestamptz not null,
  opened_at     timestamptz,
  watched_s     numeric(8,2),
  provider_id   text,
  created_at    timestamptz not null default now(),
  check (item_id is not null or roost_id is not null),
  unique (workspace_id, channel, provider_id)
);
create index touches_item_idx on touches (item_id, sent_at) where item_id is not null;

create table replies (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  item_id       uuid references hunt_items(id),
  roost_id      uuid references roosts(id),
  touch_id      uuid references touches(id),
  channel       text not null,
  body          text not null,
  received_at   timestamptz not null,
  outcome       text check (outcome in ('positive','neutral','negative','booked','hired','unsubscribe')),
  provider_id   text,
  created_at    timestamptz not null default now(),
  check (item_id is not null or roost_id is not null),
  unique (workspace_id, channel, provider_id)
);

-- ---------- the event log (append-only) ----------
create table events (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  item_id       uuid references hunt_items(id),
  roost_id      uuid references roosts(id),
  type          text not null,
  actor         jsonb not null,
  data          jsonb not null default '{}',
  at            timestamptz not null default now()
);
create index events_ws_cursor on events (workspace_id, id);
create index events_item on events (item_id, id) where item_id is not null;
create index events_roost on events (roost_id, id) where roost_id is not null;

create table idempotency_keys (
  workspace_id   uuid not null references workspaces(id),
  key            text not null,
  request_sha256 bytea not null,
  status_code    smallint,
  response       jsonb,
  created_at     timestamptz not null default now(),
  primary key (workspace_id, key)
);

-- ---------- triggers ----------
create function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

do $$ declare t text; begin
  foreach t in array array['workspaces','workspace_members','hunt_types','companies','people','roosts','hunt_items','one_shots'] loop
    execute format('create trigger %I_updated before update on %I for each row execute function touch_updated_at()', t, t);
  end loop;
end $$;

create function forbid_mutation() returns trigger language plpgsql as $$
begin raise exception 'events is append-only'; end $$;
create trigger events_append_only before update or delete on events for each row execute function forbid_mutation();

create function notify_event() returns trigger language plpgsql as $$
begin
  perform pg_notify('eagle_events', json_build_object('w', new.workspace_id, 'id', new.id)::text);
  return null;
end $$;
create trigger events_notify after insert on events for each row execute function notify_event();

create function roost_item(p_item uuid, p_kind text, p_actor jsonb) returns uuid language plpgsql as $$
declare v_item hunt_items; v_roost uuid;
begin
  select * into v_item from hunt_items where id = p_item for update;
  if v_item.id is null then raise exception 'hunt item % not found', p_item; end if;
  select id into v_roost from roosts
    where workspace_id = v_item.workspace_id and person_id = v_item.person_id and deleted_at is null;
  if v_roost is null then
    insert into roosts (workspace_id, person_id, company_id, kind, source_item_id)
    values (v_item.workspace_id, v_item.person_id, v_item.company_id, p_kind, v_item.id)
    returning id into v_roost;
  end if;
  update hunt_items set stage = 'roosted', roost_id = v_roost where id = p_item;
  insert into events (workspace_id, item_id, roost_id, type, actor, data)
  values (v_item.workspace_id, p_item, v_roost, 'item.roosted', p_actor,
          jsonb_build_object('kind', p_kind, 'hunt_type', v_item.hunt_type, 'target', v_item.target));
  return v_roost;
end $$;

-- ---------- views ----------
create view feed_rows with (security_invoker = true) as
select i.id, i.workspace_id, i.hunt_type, t.icon as hunt_icon, i.target, i.signal,
       i.signal_at, i.found_at, ft.first_sent_at,
       round(extract(epoch from (i.found_at - i.signal_at)) / 60.0, 1)     as find_lag_minutes,
       round(extract(epoch from (ft.first_sent_at - i.signal_at)) / 60.0, 1) as speed_to_lead_minutes,
       os.status as one_shot_status, i.stage, i.vsl_stage, i.reply_status, i.fit,
       i.backend_agent, i.frontend_agent, i.details, i.updated_at
from hunt_items i
join hunt_types t on t.id = i.hunt_type_id
left join lateral (select min(x.sent_at) as first_sent_at from touches x where x.item_id = i.id) ft on true
left join lateral (select status from one_shots o where o.item_id = i.id and o.deleted_at is null
                   order by o.id desc limit 1) os on true
where i.deleted_at is null and i.stage not in ('roosted','passed');

create view roost_rows with (security_invoker = true) as
select r.id, r.workspace_id, r.kind, r.status, r.roosted_at, r.value_cents,
       p.full_name, c.name as company,
       (select array_agg(distinct i.hunt_type) from hunt_items i where i.roost_id = r.id) as came_from,
       (select max(x.at) from (
          select e.at from events e where e.roost_id = r.id
          union all select e.at from events e join hunt_items i on i.id = e.item_id where i.roost_id = r.id
          union all select rp.received_at from replies rp where rp.roost_id = r.id) x) as last_activity
from roosts r
left join people p on p.id = r.person_id
left join companies c on c.id = r.company_id
where r.deleted_at is null;

create view roost_timeline with (security_invoker = true) as
select coalesce(e.roost_id, i.roost_id) as roost_id,
       e.id, e.workspace_id, e.item_id, e.type, e.actor, e.data, e.at, i.hunt_type
from events e left join hunt_items i on i.id = e.item_id
where coalesce(e.roost_id, i.roost_id) is not null;

-- ---------- Row-Level Security ----------
-- Each API request: BEGIN; SET LOCAL ROLE eagle_app; set_config('app.workspace_id', <uuid>, true).
-- current_setting(..., true) returns null when unset, so a request that forgot the setting sees nothing.
do $$ declare t text; begin
  foreach t in array array['workspace_members','api_keys','hunt_types','companies','people','roosts','hunt_items',
                           'funding_signals','job_posts','upwork_jobs','one_shots','recordings','touches','replies',
                           'events','idempotency_keys'] loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force row level security', t);
    execute format($p$create policy ws_isolation on %I to eagle_app
                    using (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
                    with check (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)$p$, t);
    execute format('create policy owner_all on %I to eagleeye_owner using (true) with check (true)', t);
  end loop;
end $$;

alter table workspaces enable row level security;
alter table workspaces force row level security;
create policy ws_isolation on workspaces to eagle_app using (id = nullif(current_setting('app.workspace_id', true), '')::uuid);
create policy owner_all on workspaces to eagleeye_owner using (true) with check (true);

-- ---------- grants ----------
grant usage on schema public to eagle_app;
grant select on workspaces to eagle_app;
grant select, insert, update on workspace_members, api_keys, hunt_types, companies, people, roosts, hunt_items,
  funding_signals, job_posts, upwork_jobs, one_shots, recordings, touches, replies, idempotency_keys to eagle_app;
grant select, insert on events to eagle_app;
grant select on feed_rows, roost_rows, roost_timeline to eagle_app;
grant execute on function roost_item(uuid, text, jsonb) to eagle_app;
