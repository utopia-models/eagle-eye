-- The SEND step (DOMAINS.md domain 2, Q8 + BACKENDS card 11-21): after Tyler records, the one-shot reaches the target
-- the same day (email + LinkedIn + call); our own viewer page reports watches; replies are answered by the hunt's
-- backend agent. Changes, each with its reason:
--   * viewers: one public page per one-shot (utopiamodels.ai/v/<slug>). The slug carries a random suffix so pages are
--     not enumerable; the public watch beacon resolves the slug to its workspace here (it carries no token).
--   * touches.watch_pct + touches.thread_id: the furthest milestone watched (0/25/50/75/100) for "call if they
--     watched", and the provider thread a reply is matched to (Gmail threadId).
--   * touches.status: queued (a channel waiting on novaserver: LinkedIn desk, dialer, Upwork desk) | sent | failed.
--     sent_at stays NOT NULL: for a queued touch it is the time the send was decided.
--   * touches.channel gains 'web' is NOT added: a watch is a property of the touch whose link was opened (?c=<channel>).
--   * workspace 'dryrun': the dry-run pipeline writes here, never to tyler's feed (Tyler 11-21: "I hate seeing mock
--     data"). Same hunt types, so a dry-run exercises the real write paths.

create table viewers (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  slug          text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{3,80}$'),
  item_id       uuid not null references hunt_items(id),
  one_shot_id   uuid references one_shots(id),
  recording_id  uuid references recordings(id),
  title         text not null,
  sender_name   text not null,
  video_url     text,
  page_url      text not null,
  published     jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create index viewers_item_idx on viewers (item_id);
create trigger viewers_updated before update on viewers for each row execute function touch_updated_at();

alter table touches add column status text not null default 'sent' check (status in ('queued','sent','failed'));
alter table touches add column watch_pct smallint check (watch_pct in (0,25,50,75,100));
alter table touches add column thread_id text;
alter table touches add column details jsonb not null default '{}';
create index touches_thread_idx on touches (workspace_id, thread_id) where thread_id is not null;

alter table viewers enable row level security;
alter table viewers force row level security;
create policy ws_isolation on viewers to eagle_app
  using (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
  with check (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid);
create policy owner_all on viewers to eagleeye_owner using (true) with check (true);
grant select, insert, update on viewers to eagle_app;

insert into workspaces (slug, name) values ('dryrun', 'Send-step dry runs');
insert into hunt_types (workspace_id, key, label, icon, version, extension_table, roost_rules)
select d.id, t.key, t.label, t.icon, t.version, t.extension_table, t.roost_rules
from hunt_types t join workspaces w on w.id = t.workspace_id and w.slug = 'tyler', workspaces d
where d.slug = 'dryrun' and t.deleted_at is null;
