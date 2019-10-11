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

namespace OCA\IDA\Model;

use OCA\IDA\Util\Access;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\Mapper;
use OCP\AppFramework\Db\Entity;
use OCP\IDBConnection;
use OCP\Util;

/**
 * Interact with the ida_frozen_file database table
 */
class FileMapper extends Mapper
{
    /**
     * Create the ida_frozen_file database mapper
     *
     * @param IDBConnection $db the database connection to use
     */
    public function __construct(IDBConnection $db) {
        parent::__construct(
            $db,
            'ida_frozen_file',
            '\OCA\IDA\Model\File'
        );
    }
    
    /**
     * Retrieve all file records associated with the specified action, based on the provided action PID,
     * optionally restricted to one or more projects.
     *
     * @param string $pid      the PID of an action
     * @param string $projects one or more comma separated project names, with no whitespace
     * @param int    $limit    limit total to optionally specified maximum
     *
     * @return File[]
     */
    public function findFiles($pid = null, $projects = null, $limit = null) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_frozen_file';
        
        // Add action pid restriction if defined
        
        if ($pid != null) {
            $sql = $sql . ' WHERE action = \'' . $pid . '\'';
        }
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                if ($pid == null) {
                    $sql = $sql . ' WHERE';
                }
                else {
                    $sql = $sql . ' AND';
                }
                $sql = $sql . ' project IN (' . $projectList . ')';
            }
        }
        
        // Sort results according to pathname
        
        $sql = $sql . ' ORDER BY pathname ASC';
        
        // If limit specified, restrict query to limit
        
        if ($limit != null && is_integer($limit)) {
            $sql = $sql . ' LIMIT ' . $limit;
        }
        
        Util::writeLog('ida', 'findFiles: sql=' . $sql, \OCP\Util::DEBUG);
        
        return $this->findEntities($sql);
    }
    
    /**
     * Count the total file records associated with the specified action, based on the provided action PID,
     * optionally restricted to one or more projects.
     *
     * @param string  $pid             the PID of an action
     * @param string  $projects        one or more comma separated project names, with no whitespace
     * @param boolean $includeInactive include removed and cleared file records
     *
     * @return File[]
     */
    public function countFiles($pid = null, $projects = null, $includeInactive = true) {
        
        $sql = 'SELECT COUNT(*) FROM *PREFIX*ida_frozen_file';
        
        // Add action pid restriction if defined
        
        if ($pid != null) {
            $sql = $sql . ' WHERE action = \'' . $pid . '\'';
        }
        
        if ($includeInactive == false) {
            
            if ($pid == null) {
                $sql = $sql . ' WHERE';
            }
            else {
                $sql = $sql . ' AND';
            }
            
            $sql = $sql . ' removed IS NULL AND cleared IS NULL';
        }
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                if (($pid == null) && ($includeInactive == true)) {
                    $sql = $sql . ' WHERE';
                }
                else {
                    $sql = $sql . ' AND';
                }
                $sql = $sql . ' project IN (' . $projectList . ')';
            }
        }
        
        Util::writeLog('ida', 'countFiles: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        
        return $stmt->fetch()['count'];
    }
    
    /**
     * Return the most recently created frozen file record with the specified PID, or null if not
     * found, optionally limited to one or more projects.
     *
     * @param string  $pid             the PID of the frozen file
     * @param string  $projects        one or more comma separated project names, with no whitespace
     * @param boolean $includeInactive include removed and cleared file records
     *
     * @return Entity
     */
    function findFile($pid, $projects = null, $includeInactive = false) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_frozen_file WHERE pid = \'' . $pid . '\'';
        
        if ($includeInactive == false) {
            $sql = $sql . ' AND removed IS NULL AND cleared IS NULL';
        }
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                $sql = $sql . ' AND project IN (' . $projectList . ')';
            }
        }
        
        $sql = $sql . ' ORDER BY id DESC LIMIT 1';
        
        Util::writeLog('ida', 'findFile: sql=' . $sql, \OCP\Util::DEBUG);
        
        try {
            return $this->findEntity($sql);
        }
        catch (DoesNotExistException $e) {
            return null;
        }
    }
    
    /**
     * Return the most recently created active frozen file record with the specified Nextcloud node ID, or null if no
     * file record has the specified node ID, optionally limited to one or more projects.
     *
     * @param integer $node            the Nextcloud node ID of the frozen file
     * @param string  $projects        one or more comma separated project names, with no whitespace
     * @param boolean $includeInactive include removed and cleared file records
     *
     * @return Entity
     */
    function findByNextcloudNodeId($node, $projects = null, $includeInactive = false) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_frozen_file WHERE node = ' . $node;
        
        if ($includeInactive == false) {
            $sql = $sql . ' AND removed IS NULL AND cleared IS NULL';
        }
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                $sql = $sql . ' AND project IN (' . $projectList . ')';
            }
        }
        
        $sql = $sql . ' ORDER BY id DESC LIMIT 1';
        
        Util::writeLog('ida', 'findByNextcloudNodeId: sql=' . $sql, \OCP\Util::DEBUG);
        
        try {
            return $this->findEntity($sql);
        }
        catch (DoesNotExistException $e) {
            return null;
        }
    }
    
    /**
     * Retrieve the most recently created active frozen file record with the specified project and pathname, or null if
     * not found, optionally restricted to one or more projects.
     *
     * @param string  $project         the project to which the file belongs
     * @param string  $pathname        the full relative pathname of the file to retrieve, rooted in the project's frozen directory
     * @param string  $projects        one or more comma separated project names, with no whitespace
     * @param boolean $includeInactive include removed and cleared file records
     *
     * @return Entity
     */
    public function findByProjectPathname($project, $pathname, $projects = null, $includeInactive = false) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_frozen_file WHERE project = \'' . $project . '\' AND pathname = \'' . $pathname . '\'';
        
        if ($includeInactive == false) {
            $sql = $sql . ' AND removed IS NULL AND cleared IS NULL';
        }
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                $sql = $sql . ' AND project IN (' . $projectList . ')';
            }
        }
        
        $sql = $sql . ' ORDER BY id DESC LIMIT 1';
        
        Util::writeLog('ida', 'findByProjectPathname: sql=' . $sql, \OCP\Util::DEBUG);
        
        try {
            return $this->findEntity($sql);
        }
        catch (DoesNotExistException $e) {
            return null;
        }
    }
    
    /**
     * Retrieve all frozen file records associated with the specified project.
     *
     * @param string  $project         the project name
     * @param boolean $includeInactive include removed and cleared file records
     *
     * @return File[]
     */
    public function findFrozenFiles($project, $includeInactive = false) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_frozen_file WHERE project = \'' . $project . '\'';
        
        if ($includeInactive == false) {
            $sql = $sql . ' AND removed IS NULL AND cleared IS NULL';
        }
        
        Util::writeLog('ida', 'findFrozenFiles: sql=' . $sql, \OCP\Util::DEBUG);
        
        return $this->findEntities($sql);
    }
    
    /**
     * Delete all file records associated with the specified action, based on the provided action PID,
     * optionally restricted to one or more projects..
     *
     * This function is only used when rolling back / cleaning up if something goes amiss while registering
     * all files associated with an action, and should not be used otherwise.
     *
     * @param string $pid      the PID of an action
     * @param string $projects one or more comma separated project names, with no whitespace
     */
    public function deleteFiles($pid, $projects = null) {
        
        $sql = 'DELETE FROM *PREFIX*ida_frozen_file WHERE action = \'' . $pid . '\'';
        
        // Add project restrictions if defined
        
        if ($projects != null) {
            
            $projects = Access::cleanProjectList($projects);
            
            $projectList = null;
            $first = true;
            
            foreach (explode(',', $projects) as $project) {
                if ($first) {
                    $projectList = '\'' . $project . '\'';
                    $first = false;
                }
                else {
                    $projectList = $projectList . ' ,\'' . $project . '\'';
                }
            }
            
            if ($projectList != null) {
                $sql = $sql . ' AND project IN (' . $projectList . ')';
            }
        }
        
        Util::writeLog('ida', 'deleteFiles: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }
    
    /**
     * Delete all frozen file records with the specified PID from the database
     */
    function deleteFile($pid) {
        
        $sql = 'DELETE FROM *PREFIX*ida_frozen_file WHERE pid = \'' . $pid . '\'';
        
        Util::writeLog('ida', 'deleteFile: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }
    
    /**
     * Delete all file records in the database for the specified project, or for all projects if 'all' specified
     */
    function deleteAllFiles($project = null) {
        
        $sql = 'DELETE FROM *PREFIX*ida_frozen_file';
        
        if ($project != 'all') {
            $sql = $sql . ' WHERE project =\'' . $project . '\'';
        }
        
        Util::writeLog('ida', 'deleteAllFiles: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }
}

