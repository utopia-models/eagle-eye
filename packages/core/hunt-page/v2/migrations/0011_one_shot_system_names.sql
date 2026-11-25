-- Final one-shot system NAMES (Tyler 11-22 ~5:00 AM MT, on the live detail page): the channel is part of the system's name,
-- shown as "One-shot system: Upwork Intro VSL" on the row and the detail page. The hunt type stays its own chip.
update one_shot_systems s set label = v.label from (values
  ('upwork-intro-vsl',    'Upwork Intro VSL'),
  ('upwork-entire-vsl',   'Upwork Entire VSL'),
  ('funding-walkthrough', 'Funding Founder Walkthrough'),
  ('jobs-video-demo',     'Job Post Video + Demo'),
  ('investor-fleet-demo', 'Investor Fleet Demo')
) as v(key, label) where s.key = v.key;
