<?php
/**
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2018 Ministry of Education and Culture, Finland
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License,
 * or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 * PHP Version 7
 *
 * @category  Owncloud
 * @package   IDA
 * @author    CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @license   GNU Affero General Public License, version 3
 * @link      https://research.csc.fi/
 */

namespace OCA\IDA\AppInfo;

return [
    'routes' => [
        
        // Action Listing Views
        
        [
            // List all pending actions for the projects of the current user
            'name' => 'View#getActionTable',
            'url'  => '/actions/{status}',
            'verb' => 'GET'
            // Restricted to UI
            // Required parameters:
            //     status = one of 'pending' (default), 'failed', 'completed', or 'cleared'
        ],
        [
            // Show specific action details
            'name' => 'View#getActionDetails',
            'url'  => '/action/{pid}',
            'verb' => 'GET'
            // Restricted to UI
            // Required parameters:
            //     pid = the PID of the action
        ],
        [
            // Retry a specific action and show updated details
            'name' => 'View#retryAction',
            'url'  => '/retry/{pid}',
            'verb' => 'GET'
            // Restricted to UI
            // Required parameters:
            //     pid = the PID of the action
        ],
        [
            // Clear a specific action and show updated details
            'name' => 'View#clearAction',
            'url'  => '/clear/{pid}',
            'verb' => 'GET'
            // Restricted to UI
            // Required parameters:
            //     pid = the PID of the action
        ],
        
        // Locking Operations
        
        [
            // Check if project is locked. Returns 200 OK if lock exists for project, else returns 404 Not found
            'name' => 'Freezing#projectIsLocked',
            'url'  => '/api/lock/{project}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = the name of the project ('all' = service lock)
        ],
        
        [
            // Lock a project. Returns 200 OK on success, else returns 409 Conflict
            'name' => 'Freezing#lockProject',
            'url'  => '/api/lock/{project}',
            'verb' => 'POST'
            // Restricted to PSO user of specified project, or admin if 'all' is specified
            // Required parameters:
            //     project = the name of the project ('all' = service lock)
        ],
        
        [
            // Unlock a project. Returns 200 OK on success, else returns 409 Conflict
            'name' => 'Freezing#unlockProject',
            'url'  => '/api/lock/{project}',
            'verb' => 'DELETE'
            // Restricted to PSO user of specified project, or admin if 'all' is specified
            // Required parameters:
            //     project = the name of the project ('all' = service lock)
        ],
        
        // Freezing Operations
        
        [
            // Freeze all staged files within a specific scope
            'name' => 'Freezing#freezeFiles',
            'url'  => '/api/freeze',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = the name of the project to which the files belongs
            //     pathname = pathname of the root node of the scope, within the staging
            // Optional parameters:
            //     node = the Nextcloud node ID for the root node of the scope to be frozen, derived from pathname if not specified
            //     token = batch action token (only relevant if PSO user)
        ],
        [
            // Unfreeze all frozen files within a specific scope
            'name' => 'Freezing#unfreezeFiles',
            'url'  => '/api/unfreeze',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = the name of the project to which the files belongs
            //     pathname = pathname of the root node of the scope, within frozen shared project folder
            // Optional parameters:
            //     node = the Nextcloud node ID for the root node of the scope to be frozen, derived from pathname if not specified
            //     token = batch action token (only relevant if PSO user)
        ],
        [
            // Delete all frozen files within a specific scope
            'name' => 'Freezing#deleteFiles',
            'url'  => '/api/delete',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = the name of the project to which the files belongs
            //     pathname = pathname of the root node of the scope, within frozen shared project folder
            // Optional parameters:
            //     node = the Nextcloud node ID for the root node of the scope to be frozen, derived from pathname if not specified
            //     token = batch action token (only relevant if PSO user)
        ],
        
        // Retry Operations
        
        [
            // Retry a specific failed action
            'name' => 'Freezing#retryAction',
            'url'  => '/api/retry/{pid}',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Required parameters:
            //     pid = the PID of the action
            // Optional parameters:
            //     token = batch action token (only relevant if PSO user)
        ],
        [
            // Clear a specific failed action
            'name' => 'Freezing#clearAction',
            'url'  => '/api/clear/{pid}',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Allowed parameters:
            //     pid = the PID of the action
        ],
        [
            // Retry all failed actions, optionally restricted to one or more projects
            'name' => 'Freezing#retryActions',
            'url'  => '/api/retryall',
            'verb' => 'POST'
            // Restricted to admin
            // Allowed parameters:
            //     projects = one or more projects, comma separated, with no whitespace
        ],
    
        // Housekeeping Operations
    
        [
            // Clear all failed and/or pending actions, optionally restricted to one or more projects
            'name' => 'Freezing#clearActions',
            'url'  => '/api/clearall',
            'verb' => 'POST'
            // Restricted to admin
            // Allowed parameters:
            //     status = one of 'pending' or 'failed' (default)
            //     projects = one or more projects, comma separated, with no whitespace
        ],
        [
            // Delete all action and frozen node data from the specified project, or from all projects if 'all' specified
            'name' => 'Freezing#flushDatabase',
            'url'  => '/api/flush',
            'verb' => 'POST'
            // Restricted to admin or PSO user of specified project
            // Allowed parameters:
            //     project = the project to flush (required, may be 'all' for admin user)
        ],
    
        // Database Performance Testing Operations
        
        [
            // Flush and/or generate database records for adding load to query execution and indices
            'name' => 'Freezing#dbLoad',
            'url'  => '/api/dbload',
            'verb' => 'POST'
            // Restricted to admin
            // Allowed parameters:
            //     flush = one of 'true' or 'false' (default)
            //     actions = integer, the number of action records to generate (required if flush=false)
            //     filesPerAction = integer, the number of file records to generate per action (required if action defined)
        ],
        [
            // Return a summary of all existing db load records
            'name' => 'Freezing#dbLoadSummary',
            'url'  => '/api/dbload',
            'verb' => 'GET'
            // Restricted to admin
        ],
        
        // Migration / Import Operations
        
        [
            // Create action and frozen node entities in database for all files of a newly imported project
            'name' => 'Freezing#bootstrapProject',
            'url'  => '/api/bootstrap',
            'verb' => 'POST'
            // Restricted to PSO user. Project name is derived from PSO username
        ],
        
        // Project Repair Operations
        
        [
            // Repair frozen file details for all files actually physically stored in frozen area of project
            'name' => 'Freezing#repairProject',
            'url'  => '/api/repair',
            'verb' => 'POST'
            // Restricted to PSO user. Project name is derived from PSO username
        ],
        
        // Scope Intersection Tests
        
        [
            // Check for instersection of scope with ongoing action
            'name' => 'Freezing#checkScope',
            'url'  => '/api/checkScope',
            'verb' => 'POST'
            // Restricted to project access scope of user
            // Required parameters:
            //    project = the name of the project to check
            //    pathname = the pathname of the scope to check
        ],
        
        // File Inventory
        
        [
            // Return an inventory of all project files stored in the IDA service, both in staging
            // and frozen areas, with all technical metadata about each file.
            'name' => 'Freezing#getFileInventory',
            'url'  => '/api/inventory/{project}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = the name of the project
        ],
        
        // Actions
        
        [
            // Retrieve set of actions
            'name' => 'Action#getActions',
            'url'  => '/api/actions',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Optional parameters:
            //     status = one of 'pending' (default), 'failed', 'completed', or 'cleared'
            //     projects = comma separated list of project names with no whitespace
        ],
        [
            // Retrieve action details
            'name' => 'Action#getAction',
            'url'  => '/api/actions/{pid}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     pid = the PID of the action
            //     projects = comma separated list of project names with no whitespace
        ],
        [
            // Update action
            'name' => 'Action#updateAction',
            'url'  => '/api/actions/{pid}',
            'verb' => 'POST'
            // Restricted to admin or PSO user of project specified for action
            // Required parameters:
            //     pid = the PID of the action
            // Allowed parameters:
            //     checksums = timestamp
            //     metadata = timestamp
            //     replication = timestamp
            //     completed = timestamp
            //     failed = timestamp
            //     error = error message string
            //     cleared = timestamp
        ],
        [
            // Create new action
            'name' => 'Action#createAction',
            'url'  => '/api/actions',
            'verb' => 'POST'
            // Used by tests and special admin tasks only, not by any regular processes
            // Restricted to admin or PSO user of specified project
            // Required parameters:
            //     action = one of 'freeze', 'unfreeze', or 'delete'
            //     project = project name
            //     pathname = pathname of root node of action
            // Allowed parameters:
            //     node = the Nextcloud node ID of the root node of action
        ],
        [
            // Delete action
            'name' => 'Action#deleteAction',
            'url'  => '/api/actions/{pid}',
            'verb' => 'DELETE'
            // Used by tests and special admin tasks only, not by any regular processes
            // Restricted to admin or PSO user of project specified for action
            // Required parameters:
            //     pid = the PID of the action
        ],
        [
            // Return a status summary about the project, whether it is suspended, or has pending and/or failed actions
            'name' => 'Action#getStatus',
            'url' => '/api/status',
            'verb' => 'GET'
            // Allowed parameters:
            //     project = project name (defaults to project of authenticated user, required for admin user)
        ],
        
        // Frozen Files
    
        [
            // Retrieve frozen file details by local Nextcloud node ID
            // (this path pattern is ugly, but it's only used by the UI and it works, so...)
            'name' => 'File#getFileByNextcloudNodeId',
            'url'  => '/api/files/byNextcloudNodeId/{node}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     node = Nextcloud node ID of file
        ],
        [
            // Retrieve frozen file details by local Nextcloud ID
            // (this path pattern is ugly, but it's only used by the UI and it works, so...)
            'name' => 'File#getFileByProjectPathname',
            'url'  => '/api/files/byProjectPathname/{project}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     project = project name
            //     pathname = pathname of file
        ],
        [
            // Retrieve frozen files associated with a specific action
            'name' => 'File#getFiles',
            'url'  => '/api/files/action/{pid}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     pid = the PID of the action
            // Allowed parameters:
            //     projects = comma separated list of project names with no whitespace
        ],
        [
            // Retrieve frozen file details by PID
            'name' => 'File#getFile',
            'url'  => '/api/files/{pid}',
            'verb' => 'GET'
            // Restricted to project access scope of user
            // Required parameters:
            //     pid = the PID of the file
        ],
        [
            // Update frozen file record
            'name' => 'File#updateFile',
            'url'  => '/api/files/{pid}',
            'verb' => 'POST'
            // Restricted to admin or PSO user of project specified for file
            // Required parameters:
            //     pid = the PID of the file
            // Allowed parameters:
            //     checksum = checksum string
            //     metadata = timestamp
            //     replicated = timestamp
            //     removed = timestamp
            //     cleared = timestamp
        ],
        [
            // Create new frozen file
            'name' => 'File#createFile',
            'url'  => '/api/files',
            'verb' => 'POST'
            // Used by tests and special admin tasks only, not by any regular processes
            // Restricted to admin or PSO user of specified project
            // Required parameters:
            //     action = the PID of the action with which the file is associated
            //     project = project name
            //     pathname = pathname of file
            // Allowed parameters:
            //     node = the Nextcloud node ID of the file
            //     checksum = checksum string
            //     frozen = timestamp (defaults to current time if not specified)
            //     metadata = timestamp
            //     replicated = timestamp
            //     removed = timestamp
            //     cleared = timestamp
        ],
        [
            // Delete frozen file record (used by tests only)
            'name' => 'File#deleteFile',
            'url'  => '/api/files/{pid}',
            'verb' => 'DELETE'
            // Used by tests and special admin tasks only, not by any regular processes
            // Restricted to admin or PSO user of specified project
            // Required parameters:
            //     pid = the PID of the file
        ],
    ]
];
