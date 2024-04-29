-- noinspection SqlNoDataSourceInspectionForFile
CREATE INDEX oc_ida_frozen_file_node_idx ON oc_ida_frozen_file USING btree (node) WITH (fillfactor = 80);
CREATE INDEX oc_ida_frozen_file_pid_idx ON oc_ida_frozen_file USING btree (pid) WITH (fillfactor = 80);
CREATE INDEX oc_ida_frozen_file_action_idx ON oc_ida_frozen_file USING btree (action) WITH (fillfactor = 80);
CREATE INDEX oc_ida_frozen_file_project_idx ON oc_ida_frozen_file USING btree (project) WITH (fillfactor = 80);
CREATE INDEX oc_ida_frozen_file_removed_idx ON oc_ida_frozen_file USING btree (removed) WITH (fillfactor = 80) WHERE removed IS NULL;
CREATE INDEX oc_ida_action_pid_idx ON oc_ida_action USING btree (pid) WITH (fillfactor = 80);
CREATE INDEX oc_ida_action_project_idx ON oc_ida_action USING btree (project) WITH (fillfactor = 80);
CREATE INDEX oc_ida_action_storage_idx ON oc_ida_action USING btree (storage) WITH (fillfactor = 80) WHERE storage IS NULL;
CREATE INDEX oc_ida_action_completed_idx ON oc_ida_action USING btree (completed) WITH (fillfactor = 80) WHERE completed IS NULL;
CREATE INDEX oc_ida_action_failed_idx ON oc_ida_action USING btree (failed) WITH (fillfactor = 80) WHERE failed IS NULL;
CREATE INDEX oc_ida_action_cleared_idx ON oc_ida_action USING btree (cleared) WITH (fillfactor = 80) WHERE cleared IS NULL;
CREATE INDEX oc_ida_data_change_init_idx ON oc_ida_data_change USING btree (project, change, timestamp ASC) WITH (fillfactor = 80);
CREATE INDEX oc_ida_data_change_last_idx ON oc_ida_data_change USING btree (project, timestamp DESC) WITH (fillfactor = 80);
CREATE INDEX oc_filecache_missing_checksums_idx ON oc_filecache USING btree (storage, mimetype, checksum) WITH (fillfactor = 80);
CREATE INDEX oc_filecache_old_data_idx ON oc_filecache USING btree (storage, mimetype, path, mtime, fileid) WITH (fillfactor = 80);
CREATE INDEX oc_filecache_extended_old_data_idx ON oc_filecache_extended USING btree (fileid, upload_time) WITH (fillfactor = 80);