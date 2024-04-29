-- noinspection SqlNoDataSourceInspectionForFile
DROP INDEX IF EXISTS oc_ida_frozen_file_node_idx;
DROP INDEX IF EXISTS oc_ida_frozen_file_pid_idx;
DROP INDEX IF EXISTS oc_ida_frozen_file_action_idx;
DROP INDEX IF EXISTS oc_ida_frozen_file_project_idx;
DROP INDEX IF EXISTS oc_ida_frozen_file_removed_idx;
DROP INDEX IF EXISTS oc_ida_action_pid_idx;
DROP INDEX IF EXISTS oc_ida_action_project_idx;
DROP INDEX IF EXISTS oc_ida_action_storage_idx;
DROP INDEX IF EXISTS oc_ida_action_completed_idx;
DROP INDEX IF EXISTS oc_ida_action_failed_idx;
DROP INDEX IF EXISTS oc_ida_action_cleared_idx;
DROP INDEX IF EXISTS oc_ida_frozen_file_action_pid_idx;
DROP INDEX IF EXISTS oc_ida_data_change_last_idx;
DROP INDEX IF EXISTS oc_ida_data_change_init_idx;
DROP INDEX IF EXISTS oc_filecache_missing_checksums_idx;
DROP INDEX IF EXISTS oc_filecache_old_data_idx;
DROP INDEX IF EXISTS oc_filecache_extended_old_data_idx;