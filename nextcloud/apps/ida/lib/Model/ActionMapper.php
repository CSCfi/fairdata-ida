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
use OCA\IDA\Util\Generate;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\Mapper;
use OCP\AppFramework\Db\Entity;
use OCP\IDBConnection;
use OCP\Util;
use Exception;

/**
 * Interact with the ida_action database table
 */
class ActionMapper extends Mapper
{
    /**
     * Create the ida_action database mapper
     *
     * @param IDBConnection $db the database connection to use
     */
    public function __construct(IDBConnection $db) {
        parent::__construct(
            $db,
            'ida_action',
            '\OCA\IDA\Model\Action'
        );
    }
    
    /**
     * Return true if any actions, possibly of a specified status, exist for one or more projects; else return false.
     *
     * pending:     there are ongoing background operations
     * completed:   action completed successfully
     * failed:      background operations have stopped due to some unrecoverable error
     * cleared:     failed action was cleared, possibly retried
     * incomplete:  action is either pending or failed (but not cleared); used to check for action conflicts
     * initiating:  action has not finished updating storage yet
     *
     * @param string $status   one of 'pending', 'failed', 'completed', 'cleared', 'incomplete', or 'initiating'
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity[]
     */
    function hasActions($status = null, $projects = null) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_action';
        
        // Add status restriction if defined
        
        if ($status != null) {
            if ($status == 'pending') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL AND failed IS NULL AND action != \'suspend\'';
            }
            elseif ($status == 'completed') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NOT NULL';
            }
            elseif ($status == 'failed') {
                $sql = $sql . ' WHERE cleared IS NULL AND failed IS NOT NULL';
            }
            elseif ($status == 'cleared') {
                $sql = $sql . ' WHERE cleared IS NOT NULL';
            }
            elseif ($status == 'incomplete') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL AND action != \'suspend\'';
            }
            elseif ($status == 'initiating') {
                $sql = $sql . ' WHERE cleared IS NULL AND storage IS NULL AND action != \'suspend\'';
            }
            else {
                throw new Exception('Invalid action status: "' . $status . '"');
            }
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
                if ($status == null) {
                    $sql = $sql . ' WHERE';
                }
                else {
                    $sql = $sql . ' AND';
                }
                $sql = $sql . ' project IN (' . $projectList . ')';
            }
        }
        
        // Limit results to single action
        
        $sql = $sql . ' LIMIT 1';
        
        Util::writeLog('ida', 'hasActions: sql=' . $sql, \OCP\Util::DEBUG);
        
        $entities = $this->findEntities($sql);

        return (count($entities) > 0);
    }

    /**
     * Return true if any pending suspend action exists for one or more projects; else return false.
     *
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity[]
     */
    function isSuspended($projects = null) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_action WHERE action = \'suspend\' AND cleared IS NULL AND completed IS NULL AND failed IS NULL';

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
        
        // Limit results to single action
        
        $sql = $sql . ' LIMIT 1';
        
        Util::writeLog('ida', 'isSuspended: sql=' . $sql, \OCP\Util::DEBUG);
        
        $entities = $this->findEntities($sql);

        return (count($entities) > 0);
    }

    /**
     * Return all actions, optionally constrained by status and to one or more projects.
     *
     * pending:     there are ongoing background operations
     * completed:   action completed successfully
     * failed:      background operations have stopped due to some unrecoverable error
     * cleared:     failed action was cleared, possibly retried
     * incomplete:  action is either pending or failed (but not cleared); used to check for action conflicts
     * initiating:  action has not finished updating storage yet
     *
     * @param string $status   one of 'pending', 'failed', 'completed', 'cleared', 'incomplete', or 'initiating'
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity[]
     */
    function findActions($status = null, $projects = null) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_action';
        
        // Add status restriction if defined
        
        if ($status != null) {
            if ($status == 'pending') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL AND failed IS NULL';
            }
            elseif ($status == 'completed') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NOT NULL';
            }
            elseif ($status == 'failed') {
                $sql = $sql . ' WHERE cleared IS NULL AND failed IS NOT NULL';
            }
            elseif ($status == 'cleared') {
                $sql = $sql . ' WHERE cleared IS NOT NULL';
            }
            elseif ($status == 'incomplete') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL';
            }
            elseif ($status == 'initiating') {
                $sql = $sql . ' WHERE cleared IS NULL AND storage IS NULL';
            }
            else {
                throw new Exception('Invalid action status: "' . $status . '"');
            }
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
                if ($status == null) {
                    $sql = $sql . ' WHERE';
                }
                else {
                    $sql = $sql . ' AND';
                }
                $sql = $sql . ' project IN (' . $projectList . ')';
            }
        }
        
        // Sort results according to appropriate timestamp for status
        
        if ($status == 'completed') {
            $sql = $sql . ' ORDER BY completed DESC';
        }
        elseif ($status == 'failed') {
            $sql = $sql . ' ORDER BY failed DESC';
        }
        elseif ($status == 'cleared') {
            $sql = $sql . ' ORDER BY cleared DESC';
        }
        else {
            $sql = $sql . ' ORDER BY initiated DESC';
        }
        
        Util::writeLog('ida', 'findActions: sql=' . $sql, \OCP\Util::DEBUG);
        
        return $this->findEntities($sql);
    }
    
    /**
     * Return count of all actions, optionally constrained by status and to one or more projects.
     *
     * pending:     there are ongoing background operations
     * completed:   action completed successfully
     * failed:      background operations have stopped due to some unrecoverable error
     * cleared:     failed action was cleared, possibly retried
     * incomplete:  action is either pending or failed (but not cleared); used to check for action conflicts
     * initiating:  action has not finished updating storage yet
     *
     * @param string $status   one of 'pending', 'failed', 'completed', 'cleared', 'incomplete', or 'initiating'
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity[]
     */
    function countActions($status = null, $projects = null) {
        
        $sql = 'SELECT COUNT(*) FROM *PREFIX*ida_action';
        
        // Add status restriction if defined
        
        if ($status != null) {
            if ($status == 'pending') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL AND failed IS NULL';
            }
            elseif ($status == 'completed') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NOT NULL';
            }
            elseif ($status == 'failed') {
                $sql = $sql . ' WHERE cleared IS NULL AND failed IS NOT NULL';
            }
            elseif ($status == 'cleared') {
                $sql = $sql . ' WHERE cleared IS NOT NULL';
            }
            elseif ($status == 'incomplete') {
                $sql = $sql . ' WHERE cleared IS NULL AND completed IS NULL';
            }
            elseif ($status == 'initiating') {
                $sql = $sql . ' WHERE cleared IS NULL AND storage IS NULL';
            }
            else {
                throw new Exception('Invalid action status: "' . $status . '"');
            }
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
                if ($status == null) {
                    $sql = $sql . ' WHERE';
                }
                else {
                    $sql = $sql . ' AND';
                }
                $sql = $sql . ' project IN (' . $projectList . ')';
            }
        }
        
        Util::writeLog('ida', 'countActions: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        
        return $stmt->fetch()['count'];
    }
    
    /**
     * Return an action based on a PID, or null if no action has the specified PID, optionally limited to one or more projects
     *
     * @param string $pid      the PID of the action
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity
     */
    function findAction($pid, $projects = null) {
        
        $sql = 'SELECT * FROM *PREFIX*ida_action WHERE pid = \'' . $pid . '\'';
        
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
        
        Util::writeLog('ida', 'findAction: sql=' . $sql, \OCP\Util::DEBUG);
        
        try {
            return $this->findEntity($sql);
        }
        catch (DoesNotExistException $e) {
            return null;
        }
    }
    
    /**
     * Clear a failed action
     *
     * @param string $pid the PID of the action
     *
     * @return Entity
     * @throws Exception
     */
    function clearAction($pid) {
        
        $actionEntity = $this->findAction($pid);
        
        if ($actionEntity) {
            if ($actionEntity->getFailed() == null) {
                throw new Exception('The action with PID "' . $pid . '" is not failed. Only failed actions may be cleared.');
            }
            $actionEntity->setCleared(Generate::newTimestamp());
        }
        else {
            throw new Exception('No action found with specified PID "' . $pid . '"');
        }
        
        return $this->update($actionEntity);
    }
    
    /**
     * Clear all actions, by default limited to failed actions, optionally restricted to one or more projects
     *
     * @param string $projects one or more comma separated project names, with no whitespace
     *
     * @return Entity[]
     */
    function clearActions($status = 'failed', $projects = null) {
        
        $actionEntities = $this->findActions($status, $projects);
        
        foreach ($actionEntities as $actionEntity) {
            $this->clearAction($actionEntity->getPid());
        }
        
        return $actionEntities;
    }
    
    /**
     * Delete a specific action record from the database
     */
    function deleteAction($pid) {
        
        $sql = 'DELETE FROM *PREFIX*ida_action WHERE pid = \'' . $pid . '\'';
        
        Util::writeLog('ida', 'deleteAction: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }
    
    /**
     * Delete all action records in the database for the specified project, or for all projects if 'all' specfied
     */
    function deleteAllActions($project = null) {
        
        $sql = 'DELETE FROM *PREFIX*ida_action';
        
        if ($project != 'all') {
            $sql = $sql . ' WHERE project =\'' . $project . '\'';
        }
        
        Util::writeLog('ida', 'deleteAllActions: sql=' . $sql, \OCP\Util::DEBUG);
        
        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }
}

