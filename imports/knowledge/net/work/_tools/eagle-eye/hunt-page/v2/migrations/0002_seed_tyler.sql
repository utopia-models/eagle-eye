-- Configuration, not data: the one workspace in use (Tyler 11-21 "I'm only focused on me") and the three
-- first-party hunt types (DOMAINS.md domain 2, PER-HUNT cards 11-21 ~7:05 PM). No hunt rows are seeded.
insert into workspaces (slug, name) values ('tyler', 'Tyler Youk');
insert into workspace_members (workspace_id, email, name, role)
  select id, 'tyler@utopiamodels.ai', 'Tyler Youk', 'owner' from workspaces where slug = 'tyler';

insert into hunt_types (workspace_id, key, label, icon, version, extension_table, roost_rules)
select w.id, t.key, t.label, t.icon, '0.1.0', t.ext, t.rules::jsonb
from workspaces w,
  (values
    ('funding', 'Funding',  'funding', 'funding_signals', '{"fit":"technical founders, AI product, $500K-$5M pre-seed/seed, US, raised in the last 48 h","roost_when":{"reply_status":"won"},"kind":"client"}'),
    ('job_post','Job post', 'job',     'job_posts',       '{"fit":"AI / ML engineer roles, contract and full-time, answered with video + demo","roost_when":{"reply_status":"won"},"kind":"client"}'),
    ('upwork',  'Upwork',   'upwork',  'upwork_jobs',     '{"roost_when":{"reply_status":"won"},"kind":"client"}')
  ) as t(key, label, icon, ext, rules)
where w.slug = 'tyler';
