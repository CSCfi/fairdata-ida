<?php
/**
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2023 Ministry of Education and Culture, Finland
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
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Generate;
use OCA\IDA\Model\DataChange;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\Mapper;
use OCP\AppFramework\Db\Entity;
use OCP\IDBConnection;
use OCP\Util;
use Exception;

/**
 * Interact with the ida_frozen_file database table
 */
class DataChangeMapper extends Mapper
{
    /**
     * Create the ida_frozen_file database mapper
     *
     * @param IDBConnection $db the database connection to use
     */
    public function __construct(IDBConnection $db) {
        parent::__construct(
            $db,
            'ida_data_change',
            '\OCA\IDA\Model\DataChange'
        );
    }

    /**
     * Retrieve the detauls of when the project was added to IDA, defaulting to the IDA migration epoch.
     */
    public function getInitializationDetails($project)
    {
        Util::writeLog('ida', 'getInitializationDetails: project=' . $project, \OCP\Util::DEBUG);

        $sql = 'SELECT * FROM *PREFIX*ida_data_change ' .
               'WHERE project = \'' . Access::escapeQueryStringComponent($project) . '\' ' .
               'AND change = \'init\' ' .
               'ORDER BY timestamp ASC LIMIT 1';

        Util::writeLog('ida', 'getInitializationDetails: sql=' . $sql , \OCP\Util::DEBUG);

        try {
            $changes = $this->findEntities($sql);
        }
        catch (DoesNotExistException $e) {
            $changes = null;
        }

        if ($changes === null || count($changes) < 1) {
            $change = null;
        }
        else {
            $change = $changes[0];
        }

        Util::writeLog('ida', 'getInitializationDetails: change=' . json_encode($change), \OCP\Util::DEBUG);

        return $change;
    }

    /**
     * Retrieve the details of the last recorded 'add' change event for a particular relative pathname for a project, in staging, if any.
     */
    public function getLastAddChangeDetails($project, $pathname)
    {
        Util::writeLog('ida', 'getLastAddChangeDetails:' . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        $stagingPathname = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $pathname;

        Util::writeLog('ida', 'getLastAddChangeDetails: stagingPathname=' . $stagingPathname, \OCP\Util::DEBUG);

        $sql = 'SELECT * FROM *PREFIX*ida_data_change '
               . ' WHERE project = \'' . Access::escapeQueryStringComponent($project) . '\''
               . ' AND change = \'add\''
               . ' AND pathname = \'' . Access::escapeQueryStringComponent($stagingPathname) . '\''
               . ' ORDER BY timestamp DESC'
               . ' LIMIT 1;';

        Util::writeLog('ida', 'getLastAddChangeDetails: sql=' . $sql, \OCP\Util::DEBUG);

        try {
            $changes = $this->findEntities($sql);
        }
        catch (DoesNotExistException $e) {
            $changes = null;
        }

        if ($changes === null || count($changes) < 1) {
            $change = null;
        }
        else {
            $change = $changes[0];
        }

        Util::writeLog('ida', 'getLastAddChangeDetails: change=' . json_encode($change), \OCP\Util::DEBUG);

        return $change;
    }

    /**
     * Retrieve the details of the last recorded data change event for a project, if any, else return details
     * from original legacy data migration event.
     */
    public function getLastDataChangeDetails($project, $user = null, $change = null, $mode = null)
    {
        Util::writeLog('ida', 'getLastDataChangeDetails:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' mode=' . $mode
            , \OCP\Util::DEBUG);

        $changes = $this->getDataChangeDetails($project, $user, $change, $mode, 1);

        if ($changes === null || count($changes) < 1) {
            $change = null;
        }
        else {
            $change = $changes[0];
        }

        Util::writeLog('ida', 'getLastDataChangeDetails: change=' . json_encode($change), \OCP\Util::DEBUG);

        return $change;
    }

    /**
     * Retrieve the details of the specified number of last recorded data change events for a project, if any,
     * else return details from original legacy data migration event; optionally limited to a particular
     * user and/or change.
     */
    public function getDataChangeDetails($project, $user = null, $change = null, $mode = null, $limit = null)
    {
        Util::writeLog('ida', 'getDataChangeDetails:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' mode=' . $mode
            . ' limit=' . $limit
            , \OCP\Util::DEBUG);


        if ($limit === null || trim($limit) === '') {
            $limit = 0;
        }
        else {
            $limit = (int)$limit;
        }

        $sql = 'SELECT * FROM *PREFIX*ida_data_change WHERE project = \'' . Access::escapeQueryStringComponent($project) . '\'';

        if ($user != null) {
            $sql = $sql . ' AND "user" = \'' . Access::escapeQueryStringComponent($user) . '\'';
        }

        if ($change != null) {
            $sql = $sql . ' AND change = \'' . Access::escapeQueryStringComponent($change) . '\'';
        }

        if ($mode != null) {
            $sql = $sql . ' AND mode" = \'' . Access::escapeQueryStringComponent($mode) . '\'';
        }

        $sql = $sql . ' ORDER BY timestamp DESC';

        if ($limit > 0) {
            $sql = $sql . ' LIMIT ' . $limit;
        }

        $sql = $sql . ';';

        Util::writeLog('ida', 'getDataChangeDetails: sql=' . $sql , \OCP\Util::DEBUG);

        try {
            $dataChanges = $this->findEntities($sql);
        }
        catch (DoesNotExistException $e) {
            $dataChanges = null;
        }

        Util::writeLog('ida', 'getDataChangeDetails:' . ' found=' . count($dataChanges), \OCP\Util::DEBUG);

        if ( ($dataChanges === null || count($dataChanges) === 0)
             &&
             ($user === null   || $user === 'service')
             &&
             ($change === null || $change === 'init')
             &&
             ($mode === null || $mode === 'system')
           ) {
            $dataChange = new DataChange();
            $dataChange->setTimestamp(Constants::IDA_MIGRATION);
            $dataChange->setProject($project);
            $dataChange->setUser('service');
            $dataChange->setChange('init');
            $dataChange->setPathname('/');
            $dataChange->setMode('system');
            $dataChanges = array($dataChange);
        }

        if ($dataChanges === null) {
            $dataChanges = array();
        }

        Util::writeLog('ida', 'getDataChangeDetails:' . ' returned=' . count($dataChanges), \OCP\Util::DEBUG);

        return $dataChanges;
    }

    /**
     * Record the details of a data change event for a project.
     */
    public function recordDataChangeDetails($project, $user, $change, $pathname, $target = null, $timestamp = null, $mode = null)
    {
        Util::writeLog('ida', 'recordDataChangeDetails:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' pathname=' . $pathname
            . ' target=' . $target
            . ' timestamp=' . $timestamp
            . ' mode=' . $mode
            , \OCP\Util::DEBUG);

        if ($project === null || $project === '') { throw new Exception('Project cannot be null'); }
        if ($user === null || $user === '') { throw new Exception('User cannot be null'); }
        if ($change === null || $change === '') { throw new Exception('Change cannot be null'); }
        if ($pathname === null || $pathname === '') { throw new Exception('Pathname cannot be null'); }

        if (! in_array($change, DataChange::CHANGES)) {
            throw new Exception('Invalid change: ' . $change);
        }

        if (in_array($change, DataChange::TARGET_CHANGES) && $target === null) {
            throw new Exception('Target must be specified for ' . $change . ' change');
        }

        // If admin or PSO user, record user as 'service', e.g. for a batch action, repair, etc.

        $user = trim($user);

        if ($user === null || $user === '' || $user === '--' || $user === 'admin' || strpos($user, Constants::PROJECT_USER_PREFIX) === 0) {
            $user = 'service';
        }

        if ($timestamp === null) {
            $timestamp = Generate::newTimestamp();
        }

        if ($mode === null || $mode === '') {
            $mode = 'api';
        }

        $dataChange = new DataChange();
        $dataChange->setTimestamp($timestamp);
        $dataChange->setProject($project);
        $dataChange->setUser($user);
        $dataChange->setChange($change);
        $dataChange->setPathname($pathname);
        $dataChange->setTarget($target);
        $dataChange->setMode($mode);

        $this->insert($dataChange);

        return $dataChange;
    }

    /**
     * Delete all data change records in the database for the specified project, or for all projects if 'all' specfied
     */
    public function deleteAllDataChanges($project = null) {

        $sql = 'DELETE FROM *PREFIX*ida_data_change';

        if ($project != 'all') {
            $sql = $sql . ' WHERE project =\'' . Access::escapeQueryStringComponent($project) . '\'';
        }

        Util::writeLog('ida', 'deleteAllDataChanges: sql=' . $sql, \OCP\Util::DEBUG);

        $stmt = $this->execute($sql);
        $stmt->closeCursor();
    }

}
