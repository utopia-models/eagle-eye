-- Tyler's cards 11-21 (DOMAINS.md "CARDS 11-21 ~6:55 PM" + "INVESTOR HUNT"), research: investor_hunt.md §2/§5 and
-- campaign_channels_all_hunts.md §2/§3/§5. Changes, each with its reason:
--   * hunt type `investor` + investor_signals (1:1 extension of hunt_items, the fields investor_hunt.md §2 names, plus
--     the rubric parts so a score is explainable, `verified` so an [unverified] row stays flagged and never gets a one-shot,
--     and `lane` cold|warm|program|mena: the MENA funds open 2027-01-04).
--   * hunt_items.subtype: the row's kind inside its hunt type (investor: fund | angel | program), the feed's subtype chip.
--   * touches.step + touches.due_at: every campaign is a sequence of dated touches (funding day 0 offer -> day 14 break-up;
--     jobs ATS + HM email + referral + connect; investor email + X). due_at is when the step runs; sent_at keeps its meaning
--     (time decided, then time sent). status gains 'cancelled' (a reply stops the rest of the sequence).
--   * touches.channel gains 'ats': the job application form is a touch of its own (queued with exact steps for a desk).

alter table hunt_items add column subtype text;

alter table touches add column step text;
alter table touches add column due_at timestamptz;
alter table touches drop constraint touches_status_check;
alter table touches add constraint touches_status_check check (status in ('queued','sent','failed','cancelled'));
alter table touches drop constraint touches_channel_check;
alter table touches add constraint touches_channel_check check (channel in ('email','linkedin','upwork','x','sms','call','ats'));
create index touches_due_idx on touches (workspace_id, due_at) where status = 'queued';

create table investor_signals (
  item_id        uuid primary key references hunt_items(id) on delete cascade,
  workspace_id   uuid not null references workspaces(id),
  investor       text not null,                 -- the person or the program/fund name the email goes to
  firm           text,
  investor_kind  text not null check (investor_kind in ('fund','angel','program')),
  lane           text not null default 'cold' check (lane in ('cold','warm','program','mena','skip')),
  verified       boolean not null default false, -- checked against a primary page (investor_hunt.md §1); false = [unverified]
  deal_company   text,
  deal_round     text,
  deal_amount    text,
  deal_date      date,
  deal_url       text,
  similarity     smallint check (similarity between 0 and 100),
  check_min      bigint,
  check_max      bigint,
  cold_route     text,
  thesis_quote   text,
  x_handle       text,
  portfolio_url  text,
  score          smallint check (score between 0 and 100),
  score_parts    jsonb not null default '{}',   -- {similarity:0-40, check_stage:0-20, oss_history:0-20, cold_route:0-10, warm_path:0-10}
  source_url     text not null
);

alter table investor_signals enable row level security;
alter table investor_signals force row level security;
create policy ws_isolation on investor_signals to eagle_app
  using (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
  with check (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid);
create policy owner_all on investor_signals to eagleeye_owner using (true) with check (true);
grant select, insert, update on investor_signals to eagle_app;

insert into hunt_types (workspace_id, key, label, icon, version, extension_table, roost_rules)
select w.id, 'investor', 'Investor', 'investor', '0.1.0', 'investor_signals',
       '{"fit":"writes pre-seed / first checks <= $500K or a program for solo founders; backed OSS, dev-tools, agent or infra in 24 months; has a cold route; allows a US C-corp founder abroad","ask":"$250-500K SAFE at $8M post-money","roost_when":{"reply_status":"replied"},"kind":"investor"}'::jsonb
from workspaces w where w.slug in ('tyler', 'dryrun')
on conflict (workspace_id, key) do nothing;

-- feed rows carry the subtype (the chip next to the type badge)
create or replace view feed_rows with (security_invoker = true) as
select i.id, i.workspace_id, i.hunt_type, t.icon as hunt_icon, i.target, i.signal,
       i.signal_at, i.found_at, ft.first_sent_at,
       round(extract(epoch from (i.found_at - i.signal_at)) / 60.0, 1)     as find_lag_minutes,
       round(extract(epoch from (ft.first_sent_at - i.signal_at)) / 60.0, 1) as speed_to_lead_minutes,
       os.status as one_shot_status, i.stage, i.vsl_stage, i.reply_status, i.fit,
       i.backend_agent, i.frontend_agent, i.details, i.updated_at, i.subtype, t.label as hunt_label
from hunt_items i
join hunt_types t on t.id = i.hunt_type_id
left join lateral (select min(x.sent_at) as first_sent_at from touches x where x.item_id = i.id and x.status = 'sent') ft on true
left join lateral (select status from one_shots o where o.item_id = i.id and o.deleted_at is null
                   order by o.id desc limit 1) os on true
where i.deleted_at is null and i.stage not in ('roosted','passed');
