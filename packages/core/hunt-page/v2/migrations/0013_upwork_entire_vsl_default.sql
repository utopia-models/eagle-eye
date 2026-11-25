-- Every new Upwork hunt is an Entire VSL hunt from the moment it is found (Eagle 11-23, fleetmail 18021: job 2046 arrived at
-- 8:47 AM ET reading "No one-shot yet"; Tyler records the whole VSL himself, one per job). Three moves, Upwork only (funding,
-- job posts and investors keep "no system until a one-shot exists"):
--   1. the Upwork lane's default system is Entire VSL (was Intro VSL), in every workspace;
--   2. the hunt_items trigger stamps the lane default on INSERT of an Upwork item, whoever writes it (ingest, upsert, REST);
--      a system the writer names wins, and it never overwrites a system already set (the 0010 rule, unchanged);
--   3. backfill: every live Upwork item with no system gets the default. Items Eagle set by hand keep theirs.
update one_shot_systems set is_default = false where hunt_type = 'upwork' and key <> 'upwork-entire-vsl' and is_default;
update one_shot_systems set is_default = true where hunt_type = 'upwork' and key = 'upwork-entire-vsl' and deleted_at is null;
create or replace function hunt_items_one_shot_system() returns trigger language plpgsql as $$
begin
  if new.one_shot_system is null and ((tg_op = 'INSERT' and new.hunt_type = 'upwork')
      or new.stage = 'one_shot' or new.vsl_stage <> 'none' or new.details->'oneshot'->>'status' = 'ready') then
    new.one_shot_system := default_one_shot_system(new.workspace_id, new.hunt_type);
  end if;
  return new;
end $$;
update hunt_items i set one_shot_system = default_one_shot_system(i.workspace_id, i.hunt_type)
 where i.hunt_type = 'upwork' and i.one_shot_system is null and i.deleted_at is null;
