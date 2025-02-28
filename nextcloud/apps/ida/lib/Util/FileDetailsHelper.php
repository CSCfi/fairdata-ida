<?php
/**
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2025 Ministry of Education and Culture, Finland
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

namespace OCA\IDA\Util;

use Exception;
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Access;
use OCP\IDBConnection;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Util;
use OC\Files\FileInfo;
use OC\Files\View;

/**
 * Retrieve all essential details from the database to populate FileInfo instances efficiently
 */
class FileDetailsHelper
{
    private IDBConnection $db;
    private View $fsView;

    public function __construct($fsView) {
        $this->db = \OC::$server->getDatabaseConnection();
        $this->fsView = $fsView;
    }

    /**
     * Fetch all files for a user, optionally filtering by path prefix and limit.
     * 
     * @param string $project      the project to which the files should belong
     * @param string $fullPathname the full pathname of a node starting from the frozen or staging area root folder
     * @param int    $limit        the maximum total number of files allowed (zero = no limit)
     * 
     * @return array ['count' => (int)total, 'files' => FileInfo[]]
     */
    public function getFileDetails(string $project, string $fullPathname, int $limit): array {

        Util::writeLog('ida', 'getFileDetails:' . 'project=' . $project . ' fullPathname=' . $fullPathname . ' limit=' . $limit , \OCP\Util::DEBUG);

        $psoUserId = 'home::' . Constants::PROJECT_USER_PREFIX . $project;

        Util::writeLog('ida', 'getFileDetails: psoUserId=' . $psoUserId, \OCP\Util::DEBUG);

        // Get user's storage numeric ID

        try {
            $qb = $this->db->getQueryBuilder();

            $qb->select('numeric_id')
               ->from('storages')
               ->where($qb->expr()->eq('id', $qb->createNamedParameter($psoUserId, IQueryBuilder::PARAM_STR)));

            //Util::writeLog('ida', 'getFileDetails: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

            // $storageId = $qb->executeQuery()->fetchOne(); // NC30
            $storageId = $qb->execute()->fetchOne();         // NC21

        } catch (Exception $e) {
            Util::writeLog('ida', 'getFileDetails: Error retrieving storage id for user ' . $psoUserId . ': ' . $e, \OCP\Util::WARN);
            $storageId = null;
        }

        Util::writeLog('ida', 'getFileDetails: storageId=' . $storageId, \OCP\Util::DEBUG);

        // If project user doesn't exist, return empty results rather than throw exception

        if (is_null($storageId) || !isset($storageId) || !is_int($storageId)) {
            return ['count' => 0, 'files' => []];
        }

        // Query filecache to check if pathname corresponds to single file

        $qb = $this->db->getQueryBuilder();

        $qb->select('path')
            ->from('filecache')
            ->where($qb->expr()->eq('storage', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->neq('mimetype', $qb->createNamedParameter(2, IQueryBuilder::PARAM_INT))) // 2 = folder, i.e. not a folder, i.e. a file
            ->andWhere($qb->expr()->eq('path', $qb->createNamedParameter('files' . $fullPathname, IQueryBuilder::PARAM_STR)))
            ->orderBy('fileid', 'DESC')
            ->setMaxResults(1);

        //Util::writeLog('ida', 'getFileDetails: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

        $cache_files = $qb->execute()->fetchAll();

        if (empty($cache_files)) {

            // Since no file matches pathname, assume pathname corresponds to folder, verify folder at that pathname exists

            $qb = $this->db->getQueryBuilder();

            $qb->select('path')
                ->from('filecache')
                ->where($qb->expr()->eq('storage', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)))
                ->andWhere($qb->expr()->eq('mimetype', $qb->createNamedParameter(2, IQueryBuilder::PARAM_INT))) // 2 = folder, i.e. a folder
                ->andWhere($qb->expr()->eq('path', $qb->createNamedParameter('files' . $fullPathname, IQueryBuilder::PARAM_STR)))
                ->orderBy('fileid', 'DESC')
                ->setMaxResults(1);

            //Util::writeLog('ida', 'getFileDetails: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

            $cache_files = $qb->execute()->fetchAll();

            if (!empty($cache_files)) {

                // If pathname matches folder, query filecache for all matching file paths, excluding folders, that
                // have the pathname as a prefix (exist within the folder as a descendant)

                $qb = $this->db->getQueryBuilder();
 
                $qb->select('path')
                    ->from('filecache')
                    ->where($qb->expr()->eq('storage', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)))
                    ->andWhere($qb->expr()->neq('mimetype', $qb->createNamedParameter(2, IQueryBuilder::PARAM_INT))) // 2 = folder, i.e. not a folder, i.e. a file
                    ->andWhere($qb->expr()->like('path', $qb->createNamedParameter('files' . $fullPathname . '/%', IQueryBuilder::PARAM_STR)))
                    ->orderBy('path', 'ASC');
  
                // Apply limit if defined (we add 1 to the limit to be able to check if we went over)
   
                if ($limit > 0) {
                    $qb->setMaxResults($limit + 1);
                }
    
                //Util::writeLog('ida', 'getFileDetails: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

                $cache_files = $qb->execute()->fetchAll();
            }
        }
    
        $files = [];
        $i = 0;

        foreach ($cache_files as $cache_file) {
            try {
                $path = $cache_file['path'];
                $fullPathname = substr($path, 5); // remove prefix substring 'files', starts then with frozen or staging folder
                $fileInfo = $this->fsView->getFileInfo($fullPathname);

                if ($fileInfo) {
                    $files[] = $fileInfo;
                    Util::writeLog('ida', 'getFileDetails: (' . $i . ') fullPathname=' . $fullPathname, \OCP\Util::DEBUG);
                    $i++;
                }
            } catch (Exception $e) { 
                // Ignore any failures to construct FileInfo instances, which may be due to issues being repaired
                // based on the details returned by this function
                Util::writeLog('ida', 'getFileDetails: Error retrieving file info for ' . $fullPathname . ': ' . $e, \OCP\Util::DEBUG);
            }
        }

        $count = count($files);

        Util::writeLog('ida', 'getFileDetails: count=' . $count, \OCP\Util::DEBUG);

        return [ 'count' => $count, 'files' => $files ];
    }

    /**
     * Fetch the latest pathname, timestamp pairs from the data changes table for the specified
     * project and scope, corresponding to when files were added to staging.
     * 
     * @param string $project  the project to which the files should belong
     * @param string $scope    the scope that pathnames should begin with
     * 
     * @return array [ pathname => timestamp, ... ]
     */
    public function getDataChangeLastAddTimestamps(string $project, string $scope): array {

        Util::writeLog('ida', 'getDataChangeLastAddTimestamps:' . 'project=' . $project . ' scope=' . $scope, \OCP\Util::DEBUG);

        // Get QueryBuilder instance from Nextcloud's DB connection
        $qb = $this->db->getQueryBuilder();

        // Define the pathname prefix
        $stagingPathnamePrefix = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $scope . '%';

        // Build the query
        $qb->select([
                'ida.pathname',
                'ida.timestamp'
            ])
            ->from('ida_data_change', 'ida')
            ->where($qb->expr()->eq('ida.project', $qb->createNamedParameter($project, IQueryBuilder::PARAM_STR)))
            ->andWhere($qb->expr()->eq('ida.change', $qb->createNamedParameter('add', IQueryBuilder::PARAM_STR)))
            ->andWhere($qb->expr()->like('ida.pathname', $qb->createNamedParameter($stagingPathnamePrefix, IQueryBuilder::PARAM_STR)))
            ->orderBy('ida.pathname', 'ASC') // Order by pathname
            ->orderBy('ida.timestamp', 'DESC'); // Then order by timestamp

        //Util::writeLog('ida', 'getDataChangeLastAddTimestamps: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

        // Get results
        $results = $qb->execute()->fetchAll();

        // Use array_unique to keep only the latest timestamp for each pathname
        $finalResults = [];
        foreach ($results as $row) {
            $fullPathname = $row['pathname'];
            // Store only the latest timestamp for each pathname
            if (!isset($finalResults[$fullPathname])) {
                $finalResults[$fullPathname] = $row['timestamp'];
            }
        }

        Util::writeLog('ida', 'getDataChangeLastAddTimestamps:' . 'results=' . count($finalResults), \OCP\Util::DEBUG);

        if (!empty($finalResults)) {
            reset($finalResults);
            $firstPathname = key($finalResults);
            $firstTimestamp = current($finalResults);
            Util::writeLog('ida', 'getDataChangeLastAddTimestamp:' . 'result1: pathname=' . $firstPathname . ' timestamp=' . $firstTimestamp, \OCP\Util::DEBUG);
        }

        return $finalResults;
    }

    /**
     * Fetch all IDA frozen file records belonging to the specified project and
     * with pathnames within the specified scope, returning a dict with the full
     * frozen folder pathname as key and the record as an array of values.
     * 
     * @param string $project  the project to which the files should belong
     * @param string $scope    the scope that pathnames should begin with
     * 
     * @return array [ pathname => array, ... ]
     */
    public function getIdaFrozenFileDetails(string $project, string $scope): array {

        Util::writeLog('ida', 'getIdaFrozenFileDetails:' . 'project=' . $project . ' scope=' . $scope, \OCP\Util::DEBUG);

        // Get QueryBuilder instance from Nextcloud's DB connection
        $qb = $this->db->getQueryBuilder();

        // Define the pathname prefix
        $pathnamePrefix = $scope . '%';

        // Build the query
        $qb->select('*')
            ->from('ida_frozen_file', 'ida')
            ->where($qb->expr()->eq('ida.project', $qb->createNamedParameter($project, IQueryBuilder::PARAM_STR)))
            ->andWhere($qb->expr()->isNull('ida.removed'))
            ->andWhere($qb->expr()->isNull('ida.cleared'))
            ->andWhere($qb->expr()->like('ida.pathname', $qb->createNamedParameter($pathnamePrefix, IQueryBuilder::PARAM_STR)))
            ->orderBy('ida.id', 'DESC');

        //Util::writeLog('ida', 'getIdaFrozenFileDetails: sql=' . Access::getRawSQL($qb), \OCP\Util::DEBUG);

        // Get results
        $results = $qb->execute()->fetchAll();

        // Use array_unique to keep only the latest timestamp for each pathname
        $finalResults = [];
        foreach ($results as $row) {
            $frozenPathname = '/' . $project . $row['pathname'];
            if (!isset($finalResults[$frozenPathname])) {
                $finalResults[$frozenPathname] = $row;
                //Util::writeLog('ida', 'getIdaFrozenFileDetails: frozenPathname=' . $frozenPathname . ' row=' . json_encode($row), \OCP\Util::DEBUG);
            }
        }

        Util::writeLog('ida', 'getIdaFrozenFileDetails:' . 'results=' . count($finalResults), \OCP\Util::DEBUG);

        if (!empty($finalResults)) {
            reset($finalResults);
            $firstPathname = key($finalResults);
            $firstDetails = current($finalResults);
            Util::writeLog('ida', 'getIdaFrozenFileDetails:' . 'result1: pathname=' . $firstPathname . ' details=' . json_encode($firstDetails), \OCP\Util::DEBUG);
        }

        return $finalResults;
    }

}