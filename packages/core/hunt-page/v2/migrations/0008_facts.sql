-- Push at the source (knowledge#16868 follow-up, Tyler 11-22 ~2 AM MT: "This should be automatic"): every outward-send
-- fact (proposal sent, video attached, email sent, reply, render done, watched) arrives as POST /rest/events and is
-- applied in one transaction. Its event row (type fact.applied) carries the fact's key; this index makes a replay of the
-- same fact a no-op at the database, whatever the caller does.
create unique index events_fact_key on events (workspace_id, (data->>'key')) where type = 'fact.applied';
