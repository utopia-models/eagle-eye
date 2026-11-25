-- A built package is a one-shot (verified live 11-22 in WebKit: 24 Upwork + 18 job rows showed "Not started" next to their
-- "Record" pill and a ready Vizier talk-script). The one-shot builders (hunts/oneshots, the funding agent) record the package on
-- the hunter's copy, details.oneshot.status = 'ready', not on stage/vsl_stage, so 0009's trigger missed them. Same rule, one more
-- signal: the lane default lands when the package is ready, whoever wrote it. Never overwrites a system already set.
create or replace function hunt_items_one_shot_system() returns trigger language plpgsql as $$
begin
  if new.one_shot_system is null and (new.stage = 'one_shot' or new.vsl_stage <> 'none'
      or new.details->'oneshot'->>'status' = 'ready') then
    new.one_shot_system := default_one_shot_system(new.workspace_id, new.hunt_type);
  end if;
  return new;
end $$;

update hunt_items i set one_shot_system = default_one_shot_system(i.workspace_id, i.hunt_type)
 where i.one_shot_system is null and i.deleted_at is null and i.details->'oneshot'->>'status' = 'ready';
