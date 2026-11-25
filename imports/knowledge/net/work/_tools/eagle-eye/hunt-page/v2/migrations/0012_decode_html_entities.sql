-- Titles arrived HTML-escaped from Upwork alert mail ("Software, AI &amp; Business"); the UI escapes once more, so Tyler saw
-- "&amp;" literally (11-22). The write path now decodes once at ingest (hunts.ts decodeEntities); this decodes what is stored.
create function pg_temp.unent(s text) returns text language sql immutable as $$
  select replace(replace(replace(replace(replace(replace(replace(s, '&amp;amp;', '&'), '&amp;', '&'), '&lt;', '<'), '&gt;', '>'),
         '&quot;', '"'), '&#39;', ''''), '&#x27;', '''')
$$;
update hunt_items set target = pg_temp.unent(target), signal = pg_temp.unent(signal)
 where target ~ '&(amp|lt|gt|quot|#39|#x27);' or signal ~ '&(amp|lt|gt|quot|#39|#x27);';
update upwork_jobs set title = pg_temp.unent(title) where title ~ '&(amp|lt|gt|quot|#39|#x27);';
update job_posts set title = pg_temp.unent(title) where title ~ '&(amp|lt|gt|quot|#39|#x27);';
