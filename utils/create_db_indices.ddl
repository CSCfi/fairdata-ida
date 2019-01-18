-- noinspection SqlNoDataSourceInspectionForFile

CREATE INDEX oc_ida_frozen_file_node_idx
ON oc_ida_frozen_file USING btree (node)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_frozen_file_pid_idx
ON oc_ida_frozen_file USING btree (pid)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_frozen_file_action_idx
ON oc_ida_frozen_file USING btree (action)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_frozen_file_project_idx
ON oc_ida_frozen_file USING btree (project)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_frozen_file_removed_idx
ON oc_ida_frozen_file USING btree (removed)
WITH (fillfactor = 50)
WHERE removed IS NULL;

CREATE INDEX oc_ida_action_pid_idx
ON oc_ida_action USING btree (pid)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_action_project_idx
ON oc_ida_action USING btree (project)
WITH (fillfactor = 50);

CREATE INDEX oc_ida_action_storage_idx
ON oc_ida_action USING btree (storage)
WITH (fillfactor = 50)
WHERE storage IS NULL;

CREATE INDEX oc_ida_action_completed_idx
ON oc_ida_action USING btree (completed)
WITH (fillfactor = 50)
WHERE completed IS NULL;

CREATE INDEX oc_ida_action_failed_idx
ON oc_ida_action USING btree (failed)
WITH (fillfactor = 50)
WHERE failed IS NULL;

CREATE INDEX oc_ida_action_cleared_idx
ON oc_ida_action USING btree (cleared)
WITH (fillfactor = 50)
WHERE cleared IS NULL;

