-- Tyler's cards 11-21 ~8:50 PM (DOMAINS.md "CARDS 11-21 ~8:50 PM"). Changes, each with its reason:
--   * follow-ups = 3 per prospect with no reply, days 3/7/14 after the first send, each adding something NEW (copied from
--     lemlist's "added value" sequence: lemlist.com/blog/cold-email-follow-up). They are touches step fu_1|fu_2|fu_3,
--     scheduled by pg-boss (src/followups.ts). The older day-7 bump / day-14 break-up / investor "last" email steps are
--     superseded: queued ones are cancelled here, the sequences no longer create them.
--   * replies.outcome gains 'bounce' (a bounce is not a reply: it stops follow-ups but never makes a roost row).
--   * next_steps: the roost row leads with next step + when + owner (Tyler or an agent name). One open row per thing to
--     do; done_at closes it. source_key makes an import idempotent (crm:<task id>, clients:<slug>:next, ...).
--   * Upwork 5-minute reply (send/upwork_reply.py): a reply drafted for a client message is a touch on channel upwork;
--     touches.status gains 'drafted' (gated, waiting for the desk seat to type it; dry-run never leaves this state).

alter table replies drop constraint replies_outcome_check;
alter table replies add constraint replies_outcome_check
  check (outcome in ('positive','neutral','negative','booked','hired','unsubscribe','bounce'));

alter table touches drop constraint touches_status_check;
alter table touches add constraint touches_status_check check (status in ('queued','drafted','sent','failed','cancelled'));

update touches set status = 'cancelled',
       details = details || '{"reason":"superseded: follow-ups are fu_1/fu_2/fu_3 on days 3/7/14 (card 11-21 ~8:50 PM)"}'::jsonb
where status = 'queued' and channel = 'email' and step in ('bump','breakup','last');

create table next_steps (
  id            uuid primary key default uuidv7(),
  workspace_id  uuid not null references workspaces(id),
  item_id       uuid references hunt_items(id),
  roost_id      uuid references roosts(id),
  what          text not null,               -- short: "Call", "Send proposal", "M2 due"
  due_at        timestamptz,
  owner         text not null,               -- tyler | an agent name
  done_at       timestamptz,
  source_key    text,                        -- idempotent import key
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  check (item_id is not null or roost_id is not null),
  unique (workspace_id, source_key)
);
create index next_steps_open on next_steps (workspace_id, due_at) where done_at is null;
create trigger next_steps_updated before update on next_steps for each row execute function touch_updated_at();

alter table next_steps enable row level security;
alter table next_steps force row level security;
create policy ws_isolation on next_steps to eagle_app
  using (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
  with check (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid);
create policy owner_all on next_steps to eagleeye_owner using (true) with check (true);
grant select, insert, update on next_steps to eagle_app;
