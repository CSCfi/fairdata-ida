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

namespace OCA\IDA\Controller;

use Exception;
use OCA\IDA\Model\Action;
use OCA\IDA\Model\ActionMapper;
use OCA\IDA\Model\File;
use OCA\IDA\Model\FileMapper;
use OCA\IDA\Model\DataChange;
use OCA\IDA\Model\DataChangeMapper;
use OCA\IDA\Util\Access;
use OCA\IDA\Util\API;
use OCA\IDA\Util\FileDetailsHelper;
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Generate;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Db\Entity;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\IConfig;
use OCP\IRequest;
use OCP\Util;
use OC\Files\FileInfo;
use OC\Files\Filesystem;
use OC;
use PhpAmqpLib\Connection\AMQPStreamConnection;
use PhpAmqpLib\Message\AMQPMessage;

/**
 * Class MaximumAllowedFilesExceeded
 *
 * Exception class to signal when maximum number of files allowed per action is exceeded.
 */
class MaximumAllowedFilesExceeded extends Exception
{
    public function __construct($message = null)
    {
        if ($message === null) {
            $this->message = 'Maximum allowed file count for a single action was exceeded.';
        } else {
            $this->message = $message;
        }
    }
}

/**
 * Class PathConflict
 *
 * Exception class to signal when a node of the same relative path already exists in either the staging or frozen space
 */
class PathConflict extends Exception
{
    public function __construct($message = null)
    {
        if ($message === null) {
            $this->message = 'A node already exists with the target pathname.';
        } else {
            $this->message = $message;
        }
    }
}

/**
 * Frozen File State Controller
 */
class FreezingController extends Controller
{
    protected $actionMapper;
    protected $fileMapper;
    protected $fileDetailsHelper;
    protected $dataChangeMapper;
    protected $userId;
    protected $fsView;
    protected $config;

    /**
     * Creates the AppFramwork Controller
     *
     * @param string             $appName            name of the app
     * @param IRequest           $request            request object
     * @param ActionMapper       $actionMapper       action mapper
     * @param FileMapper         $fileMapper         file mapper
     * @param DataChangeMapper   $dataChangeMapper   data change event mapper
     * @param string             $userId             current user
     * @param IConfig            $config             global configuration
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function __construct(
        $appName,
        IRequest $request,
        ActionMapper $actionMapper,
        FileMapper $fileMapper,
        DataChangeMapper $dataChangeMapper,
        $userId,
        IConfig $config
    ) {
        parent::__construct($appName, $request);
        $this->actionMapper = $actionMapper;
        $this->fileMapper = $fileMapper;
        $this->dataChangeMapper = $dataChangeMapper;
        $this->userId = $userId;
        Filesystem::init($userId, '/' . $userId . '/files');
        $this->fsView = Filesystem::getView();
        $this->fileDetailsHelper = new FileDetailsHelper($this->fsView);
        $this->config = $config->getSystemValue('ida');
        if (strpos($this->config['METAX_API'], '/rest/') !== false) {
            $this->config['METAX_API_VERSION'] = 1;
        }
        else {
            $this->config['METAX_API_VERSION'] = 3;
        }
        $this->config['MIGRATION_TIMESTAMP'] = "2018-11-01T00:00:00Z";
    }

    /**
     * Get the upload timestamp for the specified node
     *
     * @param string   $project  the project to which the file belongs
     * @param FileInfo $nodeInfo the nextcloud node info object
     *
     * @return string
     *
     */
    protected function getUploadedTimestamp($project, $nodeInfo)
    {
        Util::writeLog('ida', 'getUploadedTimestamp', \OCP\Util::DEBUG);

        # For files added via other means than the WebUI or command line tools (e.g. vanilla
        # WebDAV, originally migrated files, files added locally and recorded using the
        # occ files:scan command, etc.) no upload timestamp will be recorded in the Nextcloud
        # file cache tables and a zero value will be returned by the Nextcloud NodeInfo method
        # getUploadTime().
        #
        # If there is no explicit upload timestamp recorded in the Nextcloud file cache, we will
        # check if we have recorded an 'add' change event in the project data changes table for
        # the file pathname in staging and if so we will use the latest such 'add' event timestamp.
        #
        # If no upload timestamp can be found from either of those sources, null is returned.

        $uploaded = $nodeInfo->getUploadTime();

        if ($uploaded && $uploaded > 0) {
            $timestamp = Generate::newTimestamp($uploaded);
        }
        else {
            $timestamp = $this->getLastAddChangeTimestamp($project, $nodeInfo);
        }

        Util::writeLog('ida', 'getUploadedTimestamp: timestamp=' . $timestamp, \OCP\Util::DEBUG);

        return $timestamp;
    }

    /**
     * Get the last 'add' change timestamp recorded for the specified file, if any
     *
     * @param string   $project  the project to which the file belongs
     * @param FileInfo $nodeInfo the nextcloud node info object
     *
     * @return string
     *
     */
    protected function getLastAddChangeTimestamp($project, $nodeInfo)
    {
        Util::writeLog('ida', 'getLastAddChangeTimestamp', \OCP\Util::DEBUG);

        $timestamp = null;

        $pathname = $this->stripRootProjectFolder($project, $nodeInfo->getPath());

        $addChangeDetails = $this->dataChangeMapper->getLastAddChangeDetails($project, $pathname);

        if ($addChangeDetails != null) {
            $timestamp = $addChangeDetails->getTimestamp();
        }

        Util::writeLog('ida', 'getLastAddChangeTimestamp: timestamp=' . $timestamp, \OCP\Util::DEBUG);

        return $timestamp;
    }

    /**
     * Return an inventory of all project files stored in the IDA service, with all technical metadata about each file.
     * 
     * By default, the inventory will include files stored both in staging and frozen areas; however, if the optional
     * parameter $area is specified as either 'frozen' or 'staging', only files in the specified area will be incuded.
     * Furthermore, if the additional optional parameter $pathname is specified with a value corresponding to the relative
     * pathname of a file or folder (the $scope parametr is ignored if $area is null) then files will only be included
     * from the specified area and matching the scope of the specified pathname.
     *
     * NOTE: If a file has no recorded upload time, it will be included in the inventory regardless whether an uploadedBefore
     * timestamp is specified. Consider whether to utilize modified and project creation timestamps in determination.
     *
     * @param string $project         the project to which the files belong
     * @param string $area            either 'frozen', or 'staging' (default null) limiting inventory to the specified area
     * @param string $scope           relative pathname limiting the scope of the inventory ($area must be either 'frozen' or 'staging')
     * @param string $uploadedBefore  ISO datetime string excluding files uploaded after the specified datetime
     * @param string $unpublishedOnly if "true" exclude files which are part of one or more published datasets
     * @param string $testing         if "true" includes additional information needed by automated tests
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFileInventory($project, $area = null, $scope = null, $uploadedBefore = null, $unpublishedOnly = 'false', $testing = 'false')
    {
        try {

            // If user is not admin, nor PSO user, verify user belongs to project

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                Access::verifyIsAllowedProject($project);
            }

            if (empty(trim($area))) {
                $area = null;
            }

            if (empty(trim($scope))) {
                $scope = null;
            }

            if (empty(trim($uploadedBefore))) {
                $uploadedBefore = null;
            }

            if ($unpublishedOnly === null) {
                $unpublishedOnly = 'false';
            }

            Util::writeLog('ida', 'getFileInventory:'
                . ' project=' . $project
                . ' area=' . $area
                . ' scope=' . $scope
                . ' uploadedBefore=' . $uploadedBefore
                . ' unpublishedOnly=' . $unpublishedOnly
                , \OCP\Util::INFO);

            $scope = ($area && $scope) ? $scope : '/';

            $stagedFiles = array();
            $frozenFiles = array();

            $lastChange = $this->dataChangeMapper->getLastDataChangeDetails($project);

            if ($lastChange !== null) {
                $change = array(
                    'timestamp' => $lastChange->getTimestamp(),
                    'user' => $lastChange->getUser(),
                    'change' => $lastChange->getChange(),
                    'pathname' => $lastChange->getPathname(),
                    'target' => $lastChange->getTarget(),
                    'mode' => $lastChange->getMode()
                );
                if ($change['target'] === null) {
                    unset($change['target']);
                }
                $lastChange = $change;
            }

            $dataChangeLastAddTimestamps = $this->fileDetailsHelper->getDataChangeLastAddTimestamps($project, $scope);

            if ($area === null || $area === 'staging') {

                # Aggregate files from staging area

                Util::writeLog('ida', 'getFileInventory: aggregating nodes from staging area ...', \OCP\Util::DEBUG);

                $nextcloudNodes = $this->getNextcloudNodes('freeze', $project, $scope, 0);

                $i = 0;

                foreach ($nextcloudNodes as $nodeInfo) {

                    // This test should be unnecessary as all nodes should already only be file nodes
                    // but it is retained just to be absolutely certain we only output file details
                    if ($nodeInfo->getType() === FileInfo::TYPE_FILE) {

                        $rootPathname = $nodeInfo->getPath(); // pathname from IDA storage root
                        $relativePathname = $this->stripRootProjectFolder($project, $rootPathname); 
                        $stagingPathname = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $relativePathname;

                        //Util::writeLog('ida', 'getFileInventory: frozen: nodeInfo: stagingPathname=' . $stagingPathname, \OCP\Util::DEBUG);

                        $uploaded = $nodeInfo->getUploadTime();
                        $uploaded = ($uploaded && $uploaded > 0) ? Generate::newTimestamp($uploaded) : null;

                        //Util::writeLog('ida', 'getFileInventory: cache uploaded=' . $uploaded, \OCP\Util::DEBUG);

                        // If no uploaded timestamp defined for node, use data change add timestamp, if any
                        if ($uploaded === null) {
                            $uploaded = $dataChangeLastAddTimestamps[$stagingPathname] ?? null;
                            //Util::writeLog('ida', 'getFileInventory: tableLastAdd uploaded=' . $uploaded, \OCP\Util::DEBUG);
                        }

                        if ($uploadedBefore === null || $uploaded === null || $uploaded < $uploadedBefore) {

                            $checksum = $nodeInfo->getChecksum();

                            $fileInfo = array(
                                'uploaded' => $uploaded,
                                'modified' => Generate::newTimestamp($nodeInfo->getMTime()),
                                'size'     => $nodeInfo->getSize(),
                                'checksum' => (empty(trim($checksum))) ? null : $checksum
                            );

                            $stagedFiles[$relativePathname] = $fileInfo;
                            Util::writeLog('ida', 'getFileInventory: staging: (' . $i . ') pathname=' . $relativePathname, \OCP\Util::DEBUG);
                            $i++;
                        }
                    }
                }

                // Free up memory
                $nextcloudNodes = null;
                gc_collect_cycles();
            }

            if ($area === null || $area === 'frozen') {

                # Aggregate files from frozen area

                Util::writeLog('ida', 'getFileInventory: aggregating nodes from frozen area ...', \OCP\Util::DEBUG);

                $idaFrozenFiles = $this->fileDetailsHelper->getIdaFrozenFileDetails($project, $scope);
                $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, $scope, 0);

                $filePIDs = array();

                $i = 0;

                foreach ($nextcloudNodes as $nodeInfo) {

                    // This test should be unnecessary as all nodes should already only be file nodes
                    // but it is retained just to be absolutely certain we only output file details
                    if ($nodeInfo->getType() === FileInfo::TYPE_FILE) {

                        $rootPathname = $nodeInfo->getPath(); // pathname from IDA storage root
                        $relativePathname = $this->stripRootProjectFolder($project, $rootPathname); 
                        $stagingPathname = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $relativePathname;
                        $frozenPathname = '/' . $project . $relativePathname;

                        //Util::writeLog('ida', 'getFileInventory: frozen: nodeInfo: stagingPathname=' . $stagingPathname, \OCP\Util::DEBUG);
                        //Util::writeLog('ida', 'getFileInventory: frozen: nodeInfo: frozenPathname=' . $frozenPathname, \OCP\Util::DEBUG);

                        $uploaded = $nodeInfo->getUploadTime();
                        $uploaded = ($uploaded && $uploaded > 0) ? Generate::newTimestamp($uploaded) : null;

                        //Util::writeLog('ida', 'getFileInventory: cache uploaded=' . $uploaded, \OCP\Util::DEBUG);

                        // If no uploaded timestamp defined for node, use data change add timestamp, if any
                        if ($uploaded === null) {
                            $uploaded = $dataChangeLastAddTimestamps[$stagingPathname] ?? null;
                            //Util::writeLog('ida', 'getFileInventory: tableLastAdd uploaded=' . $uploaded, \OCP\Util::DEBUG);
                        }

                        if ($uploadedBefore === null || $uploaded === null || $uploaded < $uploadedBefore) {

                            $fileInfo = array(
                                'uploaded' => $uploaded
                            );

                            $frozenFile = $idaFrozenFiles[$frozenPathname] ?? null;

                            //Util::writeLog('ida', 'getFileInventory: idaFrozenFileTable frozenFile=' . json_encode($frozenFile), \OCP\Util::DEBUG);

                            if ($frozenFile != null) {

                                $filePID = $frozenFile['pid'];
                                $fileInfo['modified'] = $frozenFile['modified'];
                                $fileInfo['frozen'] = $frozenFile['frozen'];
                                $fileInfo['metadata'] = $frozenFile['metadata'];
                                $fileInfo['replicated'] = $frozenFile['replicated'];
                                $fileInfo['pid'] = $filePID;
                                $fileInfo['size'] = $frozenFile['size'];

                                $cacheChecksum = $nodeInfo->getChecksum();
                                $checksum = $frozenFile['checksum'];

                                if ($checksum === null) {
                                    $checksum = (empty(trim($cacheChecksum))) ? null : $cacheChecksum;
                                }

                                // Ensure the checksum is returned as an sha256: checksum URI

                                if ($checksum != null) {
                                    if (substr($checksum, 0, 7) === 'sha256:') {
                                        $fileInfo['checksum'] = $checksum;
                                    } else {
                                        $fileInfo["checksum"] = 'sha256:' . $checksum;
                                    }
                                }

                                if ($testing === 'true') {
                                    $fileInfo['cacheSize'] = $nodeInfo->getSize();
                                    $fileInfo["cacheChecksum"] = $cacheChecksum;
                                    $fileInfo["cacheModified"] = Generate::newTimestamp($nodeInfo->getMTime());
                                }
                            }

                            $filePIDs[] = $filePID;
                            $frozenFiles[$relativePathname] = $fileInfo;
                            Util::writeLog('ida', 'getFileInventory: frozen: (' . $i . ') pathname=' . $relativePathname, \OCP\Util::DEBUG);
                            $i++;
                        }
                    }
                }

                // Free up memory
                $nextcloudNodes = null;
                $idaFrozenFiles = null;
                gc_collect_cycles();

                // Get datasets based on frozen file pids, then iterate over frozen files and add datasets to each file
                // details accordingly, and then filter out files which are part of published datasets if unpublishedOnly
                // is true

                $datasetFiles = $this->getDatasetFilesByPIDList($filePIDs);

                if (count($datasetFiles) > 0) {

                    $i = 0;

                    foreach ($frozenFiles as $relativePathname => $fileInfo) {

                        $filePID = $fileInfo['pid'];
                        $datasets = null;

                        if ($filePID != null) {
                            if (isset($datasetFiles[$filePID])) {
                                $datasets = $datasetFiles[$filePID];
                            }
                            if ($unpublishedOnly === 'false' || ($unpublishedOnly === 'true' && $datasets === null)) {
                                // Either we want all frozen files or we only only want unpublished files and it's inpublished so include it
                                Util::writeLog('ida', 'getFileInventory: datasets: (' . $i . ') pathname=' . $relativePathname, \OCP\Util::DEBUG);
                                // If there are datasets, add them to the frozen file info
                                if ($datasets != null) {
                                    $fileInfo['datasets'] = $datasets;
                                    $frozenFiles[$relativePathname] = $fileInfo;
                                    Util::writeLog('ida', 'getFileInventory: datasets: (' . $i . ') pid=' . $filePID . ' datasets=' . json_encode($datasets) , \OCP\Util::DEBUG);
                                }
                            } else {
                                // We're excluding published frozen files so remove from the list
                                unset($frozenFiles[$relativePathname]);
                            }
                        }
                        $i++;
                    }
                }

                // Free up memory
                $filePIDs = null;
                $datasetFiles = null;
            }

            // Free up memory
            $dataChangeLastAddTimestamps = null;
            gc_collect_cycles();

            $totalStagedFiles = count($stagedFiles);
            $totalFrozenFiles = count($frozenFiles);
            $totalFiles = $totalStagedFiles + $totalFrozenFiles;

            Util::writeLog(
                'ida',
                'getInventory:'
                    . ' totalFiles=' . $totalFiles
                    . ' totalStagedFiles=' . $totalStagedFiles
                    . ' totalFrozenFiles=' . $totalFrozenFiles,
                \OCP\Util::INFO
            );

            if (empty($stagedFiles)) {
                $stagedFiles = (object) null; // Coercing to object ensures that an empty dict is output in the JSON response
            }

            if (empty($frozenFiles)) {
                $frozenFiles = (object) null;
            }

            $inventory = array(
                'project' => $project,
                'created' => Generate::newTimestamp(),
                'area' => $area,
                'scope' => $scope,
                'uploadedBefore' => $uploadedBefore,
                'unpublishedOnly' => ($unpublishedOnly === 'true'),
                'totalFiles' => $totalFiles,
                'lastChange' => $change,
                'totalStagedFiles' => $totalStagedFiles,
                'totalFrozenFiles' => $totalFrozenFiles,
                'staging' => $stagedFiles,
                'frozen' => $frozenFiles
            );

            Util::writeLog('ida', 'getFileInventory: writing inventory as JSON to memory buffer', \OCP\Util::DEBUG);

            $file = fopen('php://memory', 'w+');
            API::outputArrayAsJSON($file, $inventory);
            rewind($file);

            Util::writeLog('ida', 'getFileInventory: write complete', \OCP\Util::DEBUG);

            // Free up memory
            $inventory = null;
            gc_collect_cycles();

            Util::writeLog('ida', 'getFileInventory: creating streaming response', \OCP\Util::DEBUG);

            $response = new StreamResponse($file);

            Util::writeLog('ida', 'getFileInventory: returning streaming response', \OCP\Util::DEBUG);

            return $response;

        } catch (Exception $e) {
            return API::serverErrorResponse('getFileInventory: ' . $e->getMessage());
        }
    }

    /**
     * Return a list of PIDs for all frozen project files stored in the IDA service.
     *
     * @param string $project the project to which the files belong
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFrozenFilePids($project)
    {
        try {

            // If user is not admin, nor PSO user, verify user belongs to project

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                Access::verifyIsAllowedProject($project);
            }

            Util::writeLog('ida', 'getFrozenFilePids:' . ' project=' . $project, \OCP\Util::DEBUG);

            $frozenFilePids = $this->fileMapper->getFrozenFilePids($project);

            Util::writeLog('ida', 'getFrozenFilePids:' . ' project=' . $project . ' count=' . count($frozenFilePids), \OCP\Util::DEBUG);

            return new DataResponse($frozenFilePids);

        } catch (Exception $e) {
            return API::serverErrorResponse('getFrozenFilePids: ' . $e->getMessage());
        }
    }

    /**
     * Check if a project is locked
     *
     * @param string $project project to check
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function projectIsLocked($project)
    {
        try {

            //Util::writeLog('ida', 'projectIsLocked:' . ' project=' . $project . ' user=' . $this->userId, \OCP\Util::DEBUG);

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            if ($this->userId !== 'admin' && $project !== 'all') {
                try {
                    Access::verifyIsAllowedProject($project);
                } catch (Exception $e) {
                    return API::forbiddenErrorResponse($e->getMessage());
                }
            }

            // Check if project is locked

            if (Access::projectIsLocked($project)) {
                if ($project === 'all') {
                    return API::successResponse('The service is locked.');
                }

                return API::successResponse('The specified project is locked.');
            }

            if ($project === 'all') {
                return API::notFoundErrorResponse('No lock exists for the service.');
            }

            return API::notFoundErrorResponse('No lock exists for the specified project.');
        } catch (Exception $e) {
            return API::serverErrorResponse('projectIsLocked: ' . $e->getMessage());
        }
    }

    /**
     * Lock a project
     *
     * Restricted to admin or PSO user of specified project
     *
     * @param string $project project to be locked
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function lockProject($project)
    {
        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user is either admin or PSO user

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                return API::forbiddenErrorResponse();
            }

            // Admin is limited only to setting service lock

            if ($this->userId === 'admin' && $project !== 'all') {
                return API::forbiddenErrorResponse();
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            if ($this->userId !== 'admin') {
                try {
                    Access::verifyIsAllowedProject($project);
                } catch (Exception $e) {
                    return API::forbiddenErrorResponse($e->getMessage());
                }
            }

            // Lock the project

            if (Access::lockProject($project)) {

                Util::writeLog('ida', 'lockProject: project=' . $project . ' user=' . $this->userId, \OCP\Util::INFO);

                if ($project === 'all') {
                    return API::successResponse('The service is locked.');
                }

                return API::successResponse('The specified project is locked.');
            }

            if ($project === 'all') {
                return API::conflictErrorResponse('Unable to lock the service.');
            }

            return API::conflictErrorResponse('Unable to lock the specified project.');
        } catch (Exception $e) {
            return API::serverErrorResponse('lockProject: ' . $e->getMessage());
        }
    }

    /**
     * Unlock a project
     *
     * Restricted to admin or PSO user of specified project
     *
     * @param string $project project to be unlocked
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function unlockProject($project)
    {
        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user is either admin or PSO user

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                return API::forbiddenErrorResponse();
            }

            // Admin is limited only to clearing service lock

            if ($this->userId === 'admin' && $project !== 'all') {
                return API::forbiddenErrorResponse();
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            if ($this->userId !== 'admin') {
                try {
                    Access::verifyIsAllowedProject($project);
                } catch (Exception $e) {
                    return API::forbiddenErrorResponse($e->getMessage());
                }
            }

            // Unlock the project

            if (Access::unlockProject($project)) {

                Util::writeLog('ida', 'unlockProject: project=' . $project . ' user=' . $this->userId, \OCP\Util::INFO);

                if ($project === 'all') {
                    return API::successResponse('The service is unlocked.');
                }

                return API::successResponse('The specified project is unlocked.');
            }

            if ($project === 'all') {
                return API::conflictErrorResponse('Unable to unlock the service.');
            }

            return API::conflictErrorResponse('Unable to unlock the specified project.');
        } catch (Exception $e) {
            return API::serverErrorResponse('unlockProject: ' . $e->getMessage());
        }
    }

    /**
     * Put the service into offline mode
     *
     * Restricted to admin
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function serviceOffline()
    {
        try {

            // Verify that current user is admin

            if ($this->userId !== 'admin') {
                return API::forbiddenErrorResponse();
            }

            // Create the offline sentinel file

            if (Access::setOfflineMode()) {

                Util::writeLog('ida', 'serviceOffline', \OCP\Util::INFO);

                return API::successResponse('The service is offline.');
            }

            return API::conflictErrorResponse('Unable to put the service into offline mode.');

        } catch (Exception $e) {
            return API::serverErrorResponse('serviceOffline: ' . $e->getMessage());
        }
    }

    /**
     * Put the service into online mode
     *
     * Restricted to admin
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function serviceOnline()
    {
        try {

            // Verify that current user is admin

            if ($this->userId !== 'admin') {
                return API::forbiddenErrorResponse();
            }

            // Remove the offline sentinel file

            if (Access::setOnlineMode()) {

                Util::writeLog('ida', 'serviceOnline', \OCP\Util::INFO);

                return API::successResponse('The service is online.');
            }

            return API::conflictErrorResponse('Unable to put the service into online mode.');

        } catch (Exception $e) {
            return API::serverErrorResponse('serviceOnline: ' . $e->getMessage());
        }
    }

    /**
     * Freeze staged files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
     *
     * This function uses either the 'actions' or the 'batch-actions' RabbitMQ exchange
     *
     * @param int    $nextcloudNodeId Nextcloud node ID of the root node specifying the scope
     * @param string $project         project to which the files belong
     * @param string $pathname        relative pathname of the root node of the scope to be frozen, within the root staging folder
     * @param string $token           batch action token (optional)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function freezeFiles($nextcloudNodeId, $project, $pathname, $token = null)
    {
        $actionEntity = null;

        try {

            Util::writeLog(
                'ida',
                'freezeFiles:'
                    . ' nextcloudNodeId=' . $nextcloudNodeId
                    . ' project=' . $project
                    . ' pathname=' . $pathname
                    . ' user=' . $this->userId
                    . ' token=' . $token,
                \OCP\Util::INFO
            );

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
                API::validateIntegerParameter('nextcloudNodeId', $nextcloudNodeId);
                API::validateStringParameter('token', $token);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify Nextcloud node ID per specified pathname

            try {
                $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, 'freeze', $project, $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify RabbitMQ is accepting connections, if not, abandon action and inform the user to try again later...

            if (!$this->verifyRabbitMQConnectionOK()) {
                Util::writeLog('ida', 'freezeFiles: ERROR: Unable to open connection to RabbitMQ!', \OCP\Util::ERROR);
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('Failed to lock project when initiating requested action.');
            }

            // If $token is defined, it means that this is a batch action, and $batch should be true
            if (($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
            ($token === $this->config['BATCH_ACTION_TOKEN'])
            ) {
                $batch = true;
                Util::writeLog('ida', '$token is set, proceeding with batch action', \OCP\Util::INFO);
            } else {
                $batch = false;
                Util::writeLog('ida', '$token is not set, proceeding with normal action', \OCP\Util::INFO);
            }

            // Store freeze action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'freeze', $project, $this->userId, $pathname, $batch);

            // Ensure specified pathname identifies a node in the staging area

            $fullPathname = $this->buildFullPathname('freeze', $project, $pathname);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo === false) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::notFoundErrorResponse('The specified scope could not be found in the staging area of the project: ' . $fullPathname);
            }

            // If node is folder, ensure folder is not empty (has at least one descendant file)

            if ($this->isEmptyFolder('freeze', $project, $pathname)) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::badRequestErrorResponse('The specified folder contains no files which can be frozen.');
            }

            // Collect all nodes in scope of root action pathname, signalling error if maximum file count is exceeded

            try {

                // If PSO user and batch action token valid, impose no file limit, else use default limit

                if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                    ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                    ($token === $this->config['BATCH_ACTION_TOKEN'])
                ) {
                    Util::writeLog(
                        'ida',
                        'freezeFiles: Batch Action Execution:'
                            . ' project=' . $project
                            . ' pathname=' . $pathname,
                        \OCP\Util::INFO
                    );
                    $nextcloudNodes = $this->getNextcloudNodes('freeze', $project, $pathname, 0);
                } else {
                    $nextcloudNodes = $this->getNextcloudNodes('freeze', $project, $pathname);
                }
            } catch (Exception $e) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure that the requested action pathname does not conflict with any ongoing action(s)

            if ($this->checkIntersectionWithIncompleteActions($project, $pathname, $nextcloudNodes, $actionEntity->getPid())) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::conflictErrorResponse('The requested action conflicts with an ongoing action in the specified project.');
            }

            // Ensure no files in the scope of the action intersect with any existing file(s) in the target space

            if ($this->checkIntersectionWithExistingFiles('freeze', $project, $nextcloudNodes)) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::conflictErrorResponse('The requested action conflicts with an existing file in the frozen area.');
            }

            // Ensure that the size on disk of all files in scope match what is recorded in Nextcloud cache as reported
            // by the client when each file was uploaded (detects incomplete uploads)
            //
            // NOTE: auditing will also detect size mismatches, but a user may freeze a file before the project is
            // audited, so this is an additional check to prevent freezing of files that did not upload completely

            try {

                $this->checkFileSizes('freeze', $project, $nextcloudNodes);

            } catch (Exception $e) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::serverErrorResponse('freezeFiles: ' . $e->getMessage());

            }

            // Record details of files within scope of action

            $this->registerFiles('freeze', $project, $nextcloudNodes, $actionEntity->getPid(), $actionEntity->getInitiated());

            // Record completion of PID generation (and registration) for all files within scope of action

            $actionEntity->setPids(Generate::newTimestamp());
            $this->actionMapper->update($actionEntity);

            // Move all files in scope from staging to frozen space

            $this->moveNextcloudNode('freeze', $project, $pathname);

            $actionEntity->setStorage(Generate::newTimestamp());
            $this->actionMapper->update($actionEntity);

            // Publish new action message to RabbitMQ

            $this->publishActionMessage($actionEntity, $batch);

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($actionEntity);
        } catch (Exception $e) {
            try {
                if ($actionEntity != null) {
                    $actionEntity->setFailed(Generate::newTimestamp());
                    $actionEntity->setError($e->getMessage());
                    $this->actionMapper->update($actionEntity);
                }
            } catch (Exception $e) {
                Util::writeLog('ida', 'freezeFiles: Failed to mark freeze action as failed: ' . $e->getMessage(), \OCP\Util::ERROR);
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('freezeFiles: ' . $e->getMessage());
        }
    }

    /**
     * Unfreeze frozen files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
     *
     * This function uses either the 'actions' or the 'batch-actions' RabbitMQ exchange
     *
     * @param int    $nextcloudNodeId Nextcloud node ID of the root node specifying the scope
     * @param string $project         project to which the files belong
     * @param string $pathname        relative pathname of the root node of the scope to be frozen, within the root frozen folder
     * @param string $token           batch action token (optional)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function unfreezeFiles($nextcloudNodeId, $project, $pathname, $token = null)
    {
        $actionEntity = null;

        try {

            Util::writeLog(
                'ida',
                'unfreezeFiles:'
                    . ' nextcloudNodeId=' . $nextcloudNodeId
                    . ' project=' . $project
                    . ' pathname=' . $pathname
                    . ' user=' . $this->userId
                    . ' token=' . $token,
                \OCP\Util::INFO
            );

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
                API::validateIntegerParameter('nextcloudNodeId', $nextcloudNodeId);
                API::validateStringParameter('token', $token);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify Nextcloud node ID per specified pathname

            try {
                $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, 'unfreeze', $project, $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify RabbitMQ is accepting connections, if not, abandon action and inform the user to try again later...

            if (!$this->verifyRabbitMQConnectionOK()) {
                Util::writeLog('ida', 'unfreezeFiles: ERROR: Unable to open connection to RabbitMQ!', \OCP\Util::ERROR);
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // If $token is defined, it means that this is a batch action, and $batch should be true
            if (($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
            ($token === $this->config['BATCH_ACTION_TOKEN'])
            ) {
                $batch = true;
                Util::writeLog('ida', '$token is set, proceeding with batch action', \OCP\Util::INFO);
            } else {
                $batch = false;
                Util::writeLog('ida', '$token is not set, proceeding with normal action', \OCP\Util::INFO);
            }

            // Store unfreeze action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'unfreeze', $project, $this->userId, $pathname, $batch);

            // Ensure specified pathname identifies a node in the frozen area

            $fullPathname = $this->buildFullPathname('unfreeze', $project, $pathname);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo === false) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::notFoundErrorResponse('The specified scope could not be found in the frozen area of the project: ' . $fullPathname);
            }

            // If node is folder, ensure folder is not empty (has at least one descendant file)

            if ($this->isEmptyFolder('unfreeze', $project, $pathname)) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::badRequestErrorResponse('The specified folder contains no files which can be unfrozen.');
            }

            // Collect all nodes in scope of root action pathname, signalling error if maximum file count is exceeded

            try {

                // If PSO user and batch action token valid, impose no file limit, else use default limit

                if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                    ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                    ($token === $this->config['BATCH_ACTION_TOKEN'])
                ) {
                    Util::writeLog(
                        'ida',
                        'unfreezeFiles: Batch Action Execution:'
                            . ' project=' . $project
                            . ' pathname=' . $pathname,
                        \OCP\Util::INFO
                    );
                    $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, $pathname, 0);
                } else {
                    $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, $pathname);
                }
            } catch (Exception $e) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure that the requested action pathname does not conflict with any incomplete action(s)

            if ($this->checkIntersectionWithIncompleteActions($project, $pathname, $nextcloudNodes, $actionEntity->getPid())) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::conflictErrorResponse('The requested action conflicts with an ongoing action in the specified project.');
            }

            // Ensure no files in the scope of the action intersect with any existing file(s) in the target space

            if ($this->checkIntersectionWithExistingFiles('unfreeze', $project, $nextcloudNodes)) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::conflictErrorResponse('The requested action conflicts with an existing file in the staging area.');
            }

            // Record file details within scope of action

            $this->registerFiles('unfreeze', $project, $nextcloudNodes, $actionEntity->getPid(), $actionEntity->getInitiated());

            // Move all files in scope from frozen to staging space

            $this->moveNextcloudNode('unfreeze', $project, $pathname);

            $actionEntity->setStorage(Generate::newTimestamp());
            $this->actionMapper->update($actionEntity);

            // Publish new action message to RabbitMQ

            $this->publishActionMessage($actionEntity, $batch);

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($actionEntity);
        } catch (Exception $e) {
            try {
                if ($actionEntity != null) {
                    $actionEntity->setFailed(Generate::newTimestamp());
                    $actionEntity->setError($e->getMessage());
                    $this->actionMapper->update($actionEntity);
                }
            } catch (Exception $e) {
                Util::writeLog('ida', 'unfreezeFiles: Failed to mark unfreeze action as failed: ' . $e->getMessage(), \OCP\Util::ERROR);
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('unfreezeFiles: ' . $e->getMessage());
        }
    }

    /**
     * Delete frozen files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
     *
     * This function uses either the 'actions' or the 'batch-actions' RabbitMQ exchange
     *
     * @param int    $nextcloudNodeId Nextcloud node ID of the root node specifying the scope
     * @param string $project         project to which the files belong
     * @param string $pathname        relative pathname of the root node of the scope to be frozen, within the root frozen folder
     * @param string $token           batch action token (optional)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function deleteFiles($nextcloudNodeId, $project, $pathname, $token = null)
    {
        $actionEntity = null;
        $isEmptyFolder = false;

        try {

            Util::writeLog(
                'ida',
                'deleteFiles:'
                    . ' nextcloudNodeId=' . $nextcloudNodeId
                    . ' project=' . $project
                    . ' pathname=' . $pathname
                    . ' user=' . $this->userId
                    . ' token=' . $token,
                \OCP\Util::INFO
            );

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
                API::validateIntegerParameter('nextcloudNodeId', $nextcloudNodeId);
                API::validateStringParameter('token', $token);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify Nextcloud node ID per specified pathname

            try {
                $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, 'delete', $project, $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify RabbitMQ is accepting connections, if not, abandon action and inform the user to try again later...

            if (!$this->verifyRabbitMQConnectionOK()) {
                Util::writeLog('ida', 'deleteFiles: ERROR: Unable to open connection to RabbitMQ!', \OCP\Util::ERROR);
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // If $token is defined, it means that this is a batch action, and $batch should be true
            if (($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
            ($token === $this->config['BATCH_ACTION_TOKEN'])
            ) {
                $batch = true;
                Util::writeLog('ida', '$token is set, proceeding with batch action', \OCP\Util::INFO);
            } else {
                $batch = false;
                Util::writeLog('ida', '$token is not set, proceeding with normal action', \OCP\Util::INFO);
            }

            // Store delete action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'delete', $project, $this->userId, $pathname, $batch);

            // Ensure specified pathname identifies a node in the frozen area

            $fullPathname = $this->buildFullPathname('delete', $project, $pathname);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo === false) {

                $this->actionMapper->deleteAction($actionEntity->getPid());
                Access::unlockProject($project);

                return API::notFoundErrorResponse('The specified scope could not be found in the frozen area of the project: ' . $fullPathname);
            }

            // If the target node is an empty folder (has zero descendant files), take note of the fact, which will result in skipping file
            // related steps and publication to RabbitMQ

            if ($this->isEmptyFolder('delete', $project, $pathname)) {

                $isEmptyFolder = true;
            } else {

                // Collect all nodes within scope of action, signalling error if maximum file count is exceeded

                try {

                    // If PSO user and batch action token valid, impose no file limit, else use default limit

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token === $this->config['BATCH_ACTION_TOKEN'])
                    ) {
                        Util::writeLog(
                            'ida',
                            'deleteFiles: Batch Action Execution:'
                                . ' project=' . $project
                                . ' pathname=' . $pathname,
                            \OCP\Util::INFO
                        );
                        $nextcloudNodes = $this->getNextcloudNodes('delete', $project, $pathname, 0);
                    } else {
                        $nextcloudNodes = $this->getNextcloudNodes('delete', $project, $pathname);
                    }
                } catch (Exception $e) {

                    $this->actionMapper->deleteAction($actionEntity->getPid());
                    Access::unlockProject($project);

                    return API::badRequestErrorResponse($e->getMessage());
                }

                // Ensure that the requested action pathname does not conflict with any incomplete action(s)

                if ($this->checkIntersectionWithIncompleteActions($project, $pathname, $nextcloudNodes, $actionEntity->getPid())) {

                    $this->actionMapper->deleteAction($actionEntity->getPid());
                    Access::unlockProject($project);

                    return API::conflictErrorResponse('The requested action conflicts with an ongoing action in the specified project.');
                }

                // Record details of files within scope of action

                $this->registerFiles('delete', $project, $nextcloudNodes, $actionEntity->getPid(), $actionEntity->getInitiated());
            }

            // Delete target node from frozen space

            $this->deleteNextcloudNode($project, $pathname);

            $actionEntity->setStorage(Generate::newTimestamp());
            $this->actionMapper->update($actionEntity);

            // If the target node was an empty folder, record the action as completed,
            // else publish the new action message to RabbitMQ for postprocessing

            if ($isEmptyFolder) {

                $actionEntity->setCompleted(Generate::newTimestamp());
                $this->actionMapper->update($actionEntity);
            } else {

                $this->publishActionMessage($actionEntity, $batch);
            }

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($actionEntity);
        } catch (Exception $e) {
            try {
                if ($actionEntity != null) {
                    $actionEntity->setFailed(Generate::newTimestamp());
                    $actionEntity->setError($e->getMessage());
                    $this->actionMapper->update($actionEntity);
                }
            } catch (Exception $e) {
                Util::writeLog('ida', 'deleteFiles: Failed to mark delete action as failed: ' . $e->getMessage(), \OCP\Util::ERROR);
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('deleteFiles: ' . $e->getMessage());
        }
    }

    /**
     * Retry failed action
     *
     * @param string $pid    PID of the failed action to retry
     * @param string $token  batch action token (optional)
     *
     * @return DataResponse the new retry action
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function retryAction($pid, $token = null)
    {
        $retryActionEntity = null;
        $project = null;

        try {

            Util::writeLog('ida', 'retryAction: pid=' . $pid . ' user=' . $this->userId . ' token=' . $token, \OCP\Util::INFO);

            try {
                API::verifyRequiredStringParameter('pid', $pid);
                API::validateStringParameter('token', $token);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Retrieve failed action details

            $failedActionEntity = $this->actionMapper->findAction($pid);

            if ($failedActionEntity === null) {
                return API::notFoundErrorResponse('The specified action does not exist.');
            }

            $project = $failedActionEntity->getProject();

            // Verify that current user has rights to the action project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify that the action actually is failed action

            if ($failedActionEntity->getFailed() === null) {
                return API::badRequestErrorResponse('Specified action is not a failed action.');
            }

            // Verify RabbitMQ is accepting connections, if not, abandon action and inform the user to try again later...

            if (!$this->verifyRabbitMQConnectionOK()) {
                Util::writeLog('ida', 'retryAction: ERROR: Unable to open connection to RabbitMQ!', \OCP\Util::ERROR);
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // If $token is defined, it means that this is a batch action, and $batch should be true
            if (($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
            ($token === $this->config['BATCH_ACTION_TOKEN'])
            ) {
                $batch = true;
                Util::writeLog('ida', '$token is set, proceeding with batch action', \OCP\Util::INFO);
            } else {
                $batch = false;
                Util::writeLog('ida', '$token is not set, proceeding with normal action', \OCP\Util::INFO);
            }

            // Store retry action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked. Create new retry action with failed action details.

            $retryActionEntity = $this->registerAction(
                $failedActionEntity->getNode(),
                $failedActionEntity->getAction(),
                $failedActionEntity->getProject(),
                $failedActionEntity->getUser(),
                $failedActionEntity->getPathname(),
                $batch
            );

            // Set reference to failed action being retried

            $retryActionEntity->setRetrying($failedActionEntity->getPid());

            // Copy any timestamps for completed steps

            $retryActionEntity->setStorage($failedActionEntity->getStorage());
            $retryActionEntity->setPids($failedActionEntity->getPids());
            $retryActionEntity->setChecksums($failedActionEntity->getChecksums());
            $retryActionEntity->setMetadata($failedActionEntity->getMetadata());
            $retryActionEntity->setReplication($failedActionEntity->getReplication());

            $this->actionMapper->update($retryActionEntity);

            // Determine if any initial steps are required locally, prior to publishing message to RabbitMQ...

            // Ensure that PIDs are generated and stored for all nodes

            if ($retryActionEntity->getPids() === null && $retryActionEntity->getAction() === 'freeze') {

                // Collect all nodes within scope of action, signalling error if maximum file count is exceeded

                $action   = $retryActionEntity->getAction();
                $pathname = $retryActionEntity->getPathname();

                try {

                    // If PSO user and batch action token valid, impose no file limit, else use default limit

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token === $this->config['BATCH_ACTION_TOKEN'])
                    ) {
                        Util::writeLog('ida', 'retryAction: Batch Action Execution: action=' . $action . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::INFO);
                        $nextcloudNodes = $this->getNextcloudNodes($action, $project, $pathname, 0);
                    } else {
                        $nextcloudNodes = $this->getNextcloudNodes($action, $project, $pathname);
                    }
                } catch (Exception $e) {

                    $this->actionMapper->deleteAction($retryActionEntity->getPid());
                    Access::unlockProject($project);

                    return API::badRequestErrorResponse($e->getMessage());
                }

                // Ensure that the retried copy of the failed action does not conflict with an incomplete action
                // (no change to failed action or associated files up to this point, so OK to bail, deleting new retry action)

                if ($this->checkIntersectionWithIncompleteActions($failedActionEntity->getProject(), $failedActionEntity->getPathname(), $nextcloudNodes)) {
                    $this->actionMapper->deleteAction($retryActionEntity->getPid());
                    Access::unlockProject($project);

                    return API::conflictErrorResponse('The requested action conflicts with an ongoing action in the specified project.');
                }

                // Migrate files from failed action to retry action (zero or more files, depending on when registration process failed)

                $this->cloneFiles($failedActionEntity, $retryActionEntity);

                // Record details of files within scope of action (filling in all files in scope not previously registered with failed action)
                // (if a file record already exists, it will be reused, else a new file record will be created)

                $this->registerFiles(
                    $retryActionEntity->getAction(),
                    $retryActionEntity->getProject(),
                    $nextcloudNodes,
                    $retryActionEntity->getPid(),
                    $retryActionEntity->getInitiated()
                );

                // Record completion of PID generation (and registration) for all nodes within scope of action

                $retryActionEntity->setPids(Generate::newTimestamp());
                $this->actionMapper->update($retryActionEntity);
            } else {
                // Get files associated with failed action

                $nextcloudNodes = $this->fileMapper->findFiles($failedActionEntity->getPid());

                // Ensure that the files associated with the failed action do not conflict with an incomplete action
                // (no change to failed action or associated files up to this point, so OK to bail, deleting new retry action)

                if ($this->checkIntersectionWithIncompleteActions($failedActionEntity->getProject(), $failedActionEntity->getPathname(), $nextcloudNodes)) {
                    $this->actionMapper->deleteAction($retryActionEntity->getPid());
                    Access::unlockProject($project);

                    return API::conflictErrorResponse('The requested action conflicts with an ongoing action in the specified project.');
                }

                // Migrate files from failed action to retry action

                $this->cloneFiles($failedActionEntity, $retryActionEntity);
            }

            // Record failed action as retried and clear it

            $failedActionEntity->setRetry($retryActionEntity->getPid());
            $failedActionEntity->setCleared(Generate::newTimestamp());
            $this->actionMapper->update($failedActionEntity);

            // Ensure that the Nextcloud storage is correctly updated

            if ($retryActionEntity->getStorage() === null) {

                // Determine how storage needs to be modified

                if ($retryActionEntity->getAction() === 'delete') {

                    $this->deleteNextcloudNode($retryActionEntity->getProject(), $retryActionEntity->getPathname());
                } else { // action === 'freeze' or 'unfreeze'

                    // Move node from staging to frozen space, or frozen space to staging, depending on action

                    $this->moveNextcloudNode(
                        $retryActionEntity->getAction(),
                        $retryActionEntity->getProject(),
                        $retryActionEntity->getPathname()
                    );
                }

                $retryActionEntity->setStorage(Generate::newTimestamp());
            }

            // Publish new action message to RabbitMQ

            $this->publishActionMessage($retryActionEntity, $batch);

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($retryActionEntity);

        } catch (Exception $e) {
            try {
                if ($retryActionEntity != null) {
                    $retryActionEntity->setFailed(Generate::newTimestamp());
                    $retryActionEntity->setError($e->getMessage());
                    $this->actionMapper->update($retryActionEntity);
                }
            } catch (Exception $e) {
                Util::writeLog('ida', 'retryAction: Failed to mark retry action as failed: ' . $e->getMessage(), \OCP\Util::ERROR);
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('retryAction: ' . $e->getMessage());
        }
    }

    /**
     * Clear pending or failed action
     *
     * @param string $pid PID of the action to clear
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function clearAction($pid)
    {
        Util::writeLog('ida', 'clearAction: pid=' . $pid . ' user=' . $this->userId, \OCP\Util::INFO);

        $project = null;

        try {
            try {
                API::verifyRequiredStringParameter('pid', $pid);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Retrieve action details

            $actionEntity = $this->actionMapper->findAction($pid);

            if (!$actionEntity) {
                return API::notFoundErrorResponse('The specified action does not exist.');
            }

            $project = $actionEntity->getProject();

            // Verify that current user has rights to the action project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify that action is either failed or pending

            if ($actionEntity->getFailed() != null && $actionEntity->getCompleted() != null && $actionEntity->getCleared() != null) {
                return API::badRequestErrorResponse('Specified action is neither failed nor pending.');
            }

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // Clear action

            $actionEntity->setCleared(Generate::newTimestamp());
            $this->actionMapper->update($actionEntity);

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($actionEntity);
        } catch (Exception $e) {

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('clearAction: ' . $e->getMessage());
        }
    }

    /**
     * Register the specified action in the database
     *
     * @param int    $nextcloudNodeId the Nextcloud node ID
     * @param string $action          the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project         the project to which the node belongs
     * @param string $user            the username of the user initiating the action
     * @param string $pathname        the relative pathname of the node within the shared project staging or frozen folder
     * @param bool   $batch           specifies whether the action in question is a batch action or a normal action
     *
     * @return Entity
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function registerAction($nextcloudNodeId, $action, $project, $user, $pathname, $batch = false)
    {
        // Convert boolean to string for logging
        $batch_string = var_export($batch, true);

        Util::writeLog(
            'ida',
            'registerAction:'
                . ' nextcloudNodeId=' . $nextcloudNodeId
                . ' action=' . $action
                . ' project=' . $project
                . ' user=' . $user
                . ' pathname=' . $pathname
                . ' batch=' . $batch_string,
            \OCP\Util::INFO
        );

        // Verify Nextcloud node ID per specified pathname

        try {
            $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, $action, $project, $pathname);
        } catch (Exception $e) {
            return API::badRequestErrorResponse($e->getMessage());
        }

        // If the user is the admin or PSO user, record the user as 'service'

        if ($user === 'admin' || $user === Constants::PROJECT_USER_PREFIX . $project) {
            $user = 'service';
        }

        $actionEntity = new Action();
        $actionEntity->setPid(Generate::newPid('a' . $nextcloudNodeId));
        $actionEntity->setAction($action);
        $actionEntity->setUser($user);
        $actionEntity->setProject($project);
        $actionEntity->setNode($nextcloudNodeId);
        $actionEntity->setPathname($pathname);
        $actionEntity->setInitiated(Generate::newTimestamp());

        $actionEntity = $this->actionMapper->insert($actionEntity);

        Util::writeLog('ida', 'registerAction: id=' . $actionEntity->getId(), \OCP\Util::INFO);

        return $actionEntity;
    }

    /**
     * Retrieve any datasets from Metax which contain frozen files within the scope of a particular node
     *
     * @param int    $nextcloudNodeId Nextcloud node ID of the root node specifying the scope
     * @param string $project         project to which the files belong
     * @param string $pathname        relative pathname of the root node of the scope to be checked, within the root frozen folder
     * @param string $token           batch action token (optional)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getDatasets($nextcloudNodeId, $project, $pathname, $token = null)
    {
        try {

            Util::writeLog(
                'ida',
                'getDatasets:'
                    . ' nextcloudNodeId=' . $nextcloudNodeId
                    . ' project=' . $project
                    . ' pathname=' . $pathname
                    . ' user=' . $this->userId
                    . ' token=' . $token,
                \OCP\Util::INFO
            );

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
                API::validateIntegerParameter('nextcloudNodeId', $nextcloudNodeId);
                API::validateStringParameter('token', $token);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Verify Nextcloud node ID per specified pathname

            try {
                $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, 'delete', $project, $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure specified pathname identifies a node in the frozen area

            $fullPathname = $this->buildFullPathname('delete', $project, $pathname);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo === false) {
                return API::notFoundErrorResponse('The specified scope could not be found in the frozen area of the project: ' . $fullPathname);
            }

            // If the target node is an empty folder (has zero descendant files), return empty array

            if ($this->isEmptyFolder('delete', $project, $pathname)) {

                return new DataResponse(array());

            } else {

                // Collect all nodes within scope of action, signalling error if maximum file count is exceeded

                try {

                    // If PSO user and batch action token valid, impose no file limit, else use default limit

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token === $this->config['BATCH_ACTION_TOKEN'])
                    ) {
                        Util::writeLog(
                            'ida',
                            'deleteFiles: Batch Action Execution:'
                                . ' project=' . $project
                                . ' pathname=' . $pathname,
                            \OCP\Util::INFO
                        );
                        $nextcloudNodes = $this->getNextcloudNodes('delete', $project, $pathname, 0);
                    } else {
                        $nextcloudNodes = $this->getNextcloudNodes('delete', $project, $pathname);
                    }
                } catch (Exception $e) {
                    return API::badRequestErrorResponse($e->getMessage());
                }

                // Query Metax for any datasets containing any of the frozen files in scope

                $datasets = $this->checkDatasets($nextcloudNodes);
            }

            return new DataResponse($datasets);

        } catch (Exception $e) {
            return API::serverErrorResponse('getDatasets: ' . $e->getMessage());
        }
    }

    /**
     * Retrieve an array of Dataset instances for all datasets in Metax which contain one or more
     * specified frozen files, providing the PID and title of each dataset, and a boolean flag indicating
     * whether the dataset has entered the PAS longterm preservation process.
     *
     * @param Array $nextcloudNodes an array of Nextcloud FileInfo objects
     *
     * @return Dataset[]
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function checkDatasets($nextcloudNodes)
    {
        Util::writeLog('ida', 'checkDatasets: nodeCount=' . count($nextcloudNodes), \OCP\Util::DEBUG);

        $datasets = array();
        $metax_datasets = array();

        // Query Metax for intersecting datasets

        $filePIDs = array();

        foreach ($nextcloudNodes as $fileInfo) {
            $file = $this->fileMapper->findByNextcloudNodeId($fileInfo->getId());
            $filePIDs[] = $file->getPid();
        }

        if ($this->config['METAX_API_VERSION'] >= 3) {
            $queryURL = $this->config['METAX_API'] . '/files/datasets?storage_service=ida';
        }
        else {
            $queryURL = $this->config['METAX_API'] . '/files/datasets';
        }
        $username = $this->config['METAX_USER'];
        $password = $this->config['METAX_PASS'];
        $postbody = json_encode($filePIDs);

        $ch = curl_init($queryURL);

        $headers = array(
            'Accept: application/json',
            'Content-Type: application/json',
            'Content-Length: ' . strlen($postbody)
        );

        if ($this->config['METAX_API_VERSION'] >= 3) {
            $headers[] = 'Authorization: Token ' . $password;
        }
        else {
            curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
        }

        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postbody);
        curl_setopt($ch, CURLOPT_HEADER, false);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
        curl_setopt($ch, CURLOPT_FAILONERROR, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);

        Util::writeLog('ida', 'checkDatasets: queryURL=' . $queryURL
                       . ' headers=' . json_encode($headers)
                       . ' username=' . $username
                       . ' password=' . $password
                       . ' postbody=' . $postbody
                       , \OCP\Util::DEBUG);

        $response = curl_exec($ch);

        if ($response === false) {
            Util::writeLog('ida', 'checkDatasets:'
                . ' curl_errno=' . curl_errno($ch)
                . ' response=' . $response, \OCP\Util::ERROR);
            curl_close($ch);
            throw new Exception('Failed to check Metax for intersecting datasets');
        }

        $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        curl_close($ch);

        Util::writeLog('ida', 'checkDatasets: httpcode' . $httpcode . ' datasets_response=' . $response, \OCP\Util::DEBUG);

        if ($httpcode === 200) {

            $intersecting_dataset_ids = json_decode($response, true);

            if (! is_array($intersecting_dataset_ids)) {
                list($ignore, $keep) = explode("200 OK", $response, 2);
                list($ignore, $body) = explode("\r\n\r\n", $keep, 2);
                Util::writeLog('ida', 'checkDatasets: body=' . $body, \OCP\Util::DEBUG);
                $intersecting_dataset_ids = json_decode($body, true);
            }

            if (! is_array($intersecting_dataset_ids)) {
                $intersecting_dataset_ids = array();
            }

            Util::writeLog('ida', 'checkDatasets: ids=' . json_encode($intersecting_dataset_ids), \OCP\Util::DEBUG);

            foreach ($intersecting_dataset_ids as $intersecting_dataset_id) {

                // Query Metax for dataset details

                $queryURL = $this->config['METAX_API'] . '/datasets/' . $intersecting_dataset_id;

                $ch = curl_init($queryURL);

                curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "GET");
                curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                curl_setopt($ch, CURLOPT_FAILONERROR, false);
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);

                if ($this->config['METAX_API_VERSION'] >= 3) {
                    curl_setopt($ch, CURLOPT_HTTPHEADER, array('Authorization: Token ' . $password));
                }
                else {
                    curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                }

                $response = curl_exec($ch);

                Util::writeLog('ida', 'checkDatasets: dataset_response=' . $response, \OCP\Util::DEBUG);

                if ($response === false) {
                    Util::writeLog('ida', 'checkDatasets:'
                        . ' curl_errno=' . curl_errno($ch)
                        . ' response=' . $response, \OCP\Util::ERROR);
                    curl_close($ch);
                    throw new Exception('Failed to retrieve dataset by id');
                }

                $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

                curl_close($ch);

                if ($httpcode === 200) {
                    Util::writeLog('ida', 'checkDatasets: id=' . $intersecting_dataset_id, \OCP\Util::DEBUG);
                    $metax_datasets[] = json_decode($response, true);
                }
                else {
                    Util::writeLog('ida', 'checkDatasets: ' . $response, \OCP\Util::WARN);
                    if ($this->config['METAX_API_VERSION'] >= 3) {
                        $metax_datasets[] = [ 'id' => $intersecting_dataset_id ];
                    }
                    else {
                        $metax_datasets[] = [ 'identifier' => $intersecting_dataset_id ];
                    }
                }
            }
        }

        foreach ($metax_datasets as $metax_dataset) {

            $dataset = array();
            $dataset['pas'] = false;

            if ($this->config['METAX_API_VERSION'] >= 3) {

                $dataset['pid'] = $metax_dataset['id'];

                $dataset['title'] = $metax_dataset['title']['en']
                                 ?? $metax_dataset['title']['fi']
                                 ?? $metax_dataset['title']['sv']
                                 ?? $metax_dataset['persistent_identifier']
                                 ?? $metax_dataset['id'];

                // Any dataset for which the PAS ingestion process is ongoing, indicated by having a
                // preservation state greater than zero but less than 120
                if (array_key_exists('preservation', $metax_dataset)) {
                    $preservation = $metax_dataset['preservation'];
                    if ($preservation != null && array_key_exists('state', $preservation)
                            &&
                            $preservation['state'] > 0
                            &&
                            $preservation['state'] < 120) {
                        $dataset['pas'] = true;
                    }
                }
            }
            else {

                $dataset['pid'] = $metax_dataset['identifier'];

                $dataset['title'] = $metax_dataset['research_dataset']['title']['en']
                    ?? $metax_dataset['research_dataset']['title']['fi']
                    ?? $metax_dataset['research_dataset']['title']['sv']
                    ?? $metax_dataset['research_dataset']['preferred_identifier']
                    ?? $metax_dataset['identifier'];

                // Any dataset for which the PAS ingestion process is ongoing, indicated by having a
                // preservation state greater than zero but less than 120
                if (array_key_exists('preservation_state', $metax_dataset)
                        &&
                        $metax_dataset['preservation_state'] > 0
                        &&
                        $metax_dataset['preservation_state'] < 120) {
                    $dataset['pas'] = true;
                }
            }

            $datasets[] = $dataset;
        }

        Util::writeLog('ida', 'checkDatasets: datasetCount=' . count($datasets), \OCP\Util::DEBUG);

        return ($datasets);
    }

    /**
     * Retrieve an associative array containing entries for all frozen files which belong to one or more
     * Datasets in Metax, for all of the specified frozen file nodes. Keys will be frozen file PIDs and
     * values will be an array of dataset persistent identifiers.
     *
     * @param array $nextcloudNodes an array of Nextcloud FileInfo objects
     *
     * @return array
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function getDatasetFiles($nextcloudNodes)
    {
        Util::writeLog('ida', 'getDatasetFiles: nodeCount=' . count($nextcloudNodes), \OCP\Util::DEBUG);

        // Query Metax for intersecting datasets

        $filePIDs = array();

        foreach ($nextcloudNodes as $fileInfo) {
            Util::writeLog('ida', 'getDatasetFiles: fileId=' . $fileInfo->getId(), \OCP\Util::DEBUG);
            $file = $this->fileMapper->findByNextcloudNodeId($fileInfo->getId());
            if ($file) {
                Util::writeLog('ida', 'getDatasetFiles: filePID=' . $file->getPid(), \OCP\Util::DEBUG);
                $filePIDs[] = $file->getPid();
            }
        }

        Util::writeLog('ida', 'getDatasetFiles: filePIDs=' . json_encode($filePIDs), \OCP\Util::DEBUG);

        return $this->getDatasetFilesByPIDList($filePIDs);
    }

    /**
     * Retrieve an associative array containing entries for all frozen files which belong to one or more
     * Datasets in Metax, for all of the specified frozen file pids.
     *
     * @param array $filePIDs an array of Nextcloud frozen file PIDs
     *
     * @return array
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function getDatasetFilesByPIDList($filePIDs)
    {
        Util::writeLog('ida', 'getDatasetFilesByPIDList: filePIDs=' . count($filePIDs), \OCP\Util::DEBUG);

        if ($this->config['METAX_API_VERSION'] >= 3) {
            $queryURL = $this->config['METAX_API'] . '/files/datasets?storage_service=ida&relations=true';
        }
        else {
            $queryURL = $this->config['METAX_API'] . '/files/datasets?keys=files';
        }
        $username = $this->config['METAX_USER'];
        $password = $this->config['METAX_PASS'];
        $postbody = json_encode($filePIDs);

        //Util::writeLog('ida', 'getDatasetFilesByPIDList: queryURL=' . $queryURL
        //               . ' username=' . $username
        //               . ' password=' . $password
        //               . ' postbody=' . $postbody
        //               , \OCP\Util::DEBUG);

        $ch = curl_init($queryURL);

        $headers = array(
            'Accept: application/json',
            'Content-Type: application/json',
            'Content-Length: ' . strlen($postbody)
        );

        if ($this->config['METAX_API_VERSION'] >= 3) {
            $headers[] = 'Authorization: Token ' . $password;
        }
        else {
            curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
        }

        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postbody);
        curl_setopt($ch, CURLOPT_HEADER, false);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
        curl_setopt($ch, CURLOPT_FAILONERROR, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);

        $response = curl_exec($ch);

        if ($response === false) {
            Util::writeLog('ida', 'getDatasetFilesByPIDList:'
                . ' curl_errno=' . curl_errno($ch)
                . ' response=' . $response, \OCP\Util::ERROR);
            curl_close($ch);
            throw new Exception('Failed to check Metax for intersecting datasets');
        }

        $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        curl_close($ch);

        //Util::writeLog('ida', 'getDatasetFilesByPIDList: datasets_response=' . $response, \OCP\Util::DEBUG);

        if ($httpcode === 200) {

            $datasetFiles = json_decode($response, true);

            if (! is_array($datasetFiles)) {
                list($ignore, $keep) = explode("200 OK", $response, 2);
                list($ignore, $body) = explode("\r\n\r\n", $keep, 2);
                Util::writeLog('ida', 'getDatasetFilesByPIDList: body=' . $body, \OCP\Util::DEBUG);
                $datasetFiles = json_decode($body, true);
            }

            Util::writeLog('ida', 'getDatasetFilesByPIDList: fileCount=' . count($datasetFiles), \OCP\Util::DEBUG);

            return ($datasetFiles);
        }

        return (array());
    }

    /**
     * Registers the file in the database, associating it with the specified action
     *
     * @param FileInfo $fileInfo  the Nextcloud node
     * @param string   $action    the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string   $project   the project to which the file belongs
     * @param string   $pathname  the relative pathname of the file within the frozen project frozen folder
     * @param string   $actionPid the PID of the action with which the file is associated
     * @param string   $timestamp the timestamp of when the action was initiated
     *
     * @return Entity
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function registerFile($fileInfo, $action, $project, $pathname, $actionPid, $timestamp)
    {
        if (empty($pathname)) {
            throw new Exception('Empty pathname.');
        }

        if ($timestamp != null) {
            $timestamp = Generate::newTimestamp();
        }

        $fileEntity = new File();
        $fileEntity->setAction($actionPid);
        $fileEntity->setNode($fileInfo->getId());
        $fileEntity->setPid(Generate::newPid('f' . $fileInfo->getId()));
        if ($action === 'freeze') {
            $fileEntity->setFrozen($timestamp);
        }
        $fileEntity->setProject($project);
        $fileEntity->setPathname($pathname);
        $fileEntity->setSize(0 + $fileInfo->getSize());

        $fileEntity->setModified(Generate::newTimestamp($fileInfo->getMTime()));
        if ($action != 'freeze') {
            $fileEntity->setRemoved($timestamp);
        }
        $fileEntity = $this->fileMapper->insert($fileEntity);

        Util::writeLog(
            'ida',
            'registerFile:'
                . ' nextcloudNodeId=' . $fileInfo->getId()
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname
                . ' actionPid=' . $actionPid,
            \OCP\Util::INFO
        );

        return $fileEntity;
    }

    /**
     * Check that file size on disk matches what is recorded in Nextcloud cache, for all files. Throws exception
     * if any size differs, or if the file does not exist on disk.
     *
     * @param string     $action         the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string     $project        the project to which the files belong
     * @param FileInfo[] $nextcloudNodes one or more FileInfo instances
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function checkFileSizes($action, $project, $nextcloudNodes)
    {
        Util::writeLog(
            'ida',
            'checkFileSizes:'
                . ' project=' . $project
                . ' nextcloudNodes=' . count($nextcloudNodes),
            \OCP\Util::DEBUG
        );

        foreach ($nextcloudNodes as $fileInfo) {

            // Node should only ever be file, but we check anyway, just to be sure...

            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {

                $relativePathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());
                $fullPathname = $this->buildFullPathname($action, $project, $relativePathname);
                $filesystemPathname = $this->buildFilesystemPathname($action, $project, $relativePathname);

                // If file does not exist on disk, throw exception

                if (!file_exists($filesystemPathname)) {
                    throw new Exception('File not found on disk: '
                                            . $fullPathname
                                            //. '; filesystem pathname '
                                            //. $filesystemPathname
                                        );
                }

                $fileSizeInCache = $fileInfo->getSize();
                $fileSizeOnDisk = filesize($filesystemPathname);

                // if sizes don't match, throw exception

                if ($fileSizeOnDisk != $fileSizeInCache) {
                    throw new Exception('File size on disk ('
                                            . $fileSizeOnDisk
                                            . ') does not match the originally reported upload file size ('
                                            . $fileSizeInCache
                                            . ') for file '
                                            . $fullPathname
                                            //. '; filesystem pathname '
                                            //. $filesystemPathname
                                        );
                }
            }
        }
    }

    /**
     * Register one or more files, within the scope of a specified node, associating them with the specified action PID.
     *
     * If the action is 'freeze', then entirely new file records will be created; otherwise, the existing file
     * records will be cloned and updated, associating the cloned record with the new action and marking the existing
     * record as removed.
     *
     * @param string     $action         the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string     $project        the project to which the files belongs
     * @param FileInfo[] $nextcloudNodes one or more FileInfo instances within the scope of the action
     * @param string     $pid            the PID of the action with which the files should be associated
     * @param string     $timestamp      the timestamp of when the action was initiated
     *
     * @return Entity[]
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function registerFiles($action, $project, $nextcloudNodes, $pid, $timestamp)
    {
        Util::writeLog(
            'ida',
            'registerFiles:'
                . ' action=' . $action
                . ' project=' . $project
                . ' nextcloudNodes=' . count($nextcloudNodes)
                . ' pid=' . $pid
                . ' timestamp=' . $timestamp,
            \OCP\Util::DEBUG
        );

        $fileEntities = array();

        foreach ($nextcloudNodes as $fileInfo) {

            // Node should only ever be file, but we check anyway, just to be sure...

            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {

                $pathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());

                if ($action === 'freeze') {

                    // Register new frozen file

                    $fileEntities[] = $this->registerFile($fileInfo, $action, $project, $pathname, $pid, $timestamp);
                } else {

                    // Retrieve existing frozen file

                    $fileEntity = $this->fileMapper->findByNextcloudNodeId($fileInfo->getId());

                    // Clone existing, or create new, frozen file record

                    if ($fileEntity !== null) {

                        // Mark existing file record as removed from frozen space

                        $fileEntity->setRemoved($timestamp);
                        $this->fileMapper->update($fileEntity);

                        // Clone existing file record

                        $newFileEntity = $this->cloneFile($fileEntity, $pid);
                    } else {
                        // If for some reason no IDA record exists for a file that exists in the frozen space, create
                        // a record and log an error, so that any file metadata in METAX for that pathname can be updated
                        // to indicate unfreezing or deletion of the file. Integrity checks / monitoring should look for
                        // such errors and their cause investigated, even though we ensure the service is resilient and
                        // is able to recover and proceed with the action.

                        $newFileEntity = $this->registerFile($fileInfo, $action, $project, $pathname, $pid, $timestamp);

                        Util::writeLog(
                            'ida',
                            'registerFiles: ERROR: Frozen file data not found!'
                                . ' action=' . $action
                                . ' pid=' . $pid
                                . ' project=' . $project
                                . ' pathname=' . $pathname
                                . ' node=' . $fileInfo->getId(),
                            \OCP\Util::ERROR
                        );
                    }

                    $fileEntities[] = $newFileEntity;
                }
            }
        }

        return $fileEntities;
    }

    /**
     * Return a valid Nextcloud node ID (defaulting to zero) according to the specified pathname.
     *
     * If the specified node ID is null or zero, attempt to retrieve the node ID based on the action,
     * project, and pathname.
     *
     * @param int    $nextcloudNodeId the Nextcloud node ID
     * @param string $action          the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project         the project to which the node belongs
     * @param string $pathname        the relative pathname of the node within the shared project staging or frozen folder
     *
     * @return int
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function resolveNextcloudNodeId($nextcloudNodeId, $action, $project, $pathname)
    {
        Util::writeLog(
            'ida',
            'resolveNextcloudNodeId:'
                . ' nextcloudNodeId=' . $nextcloudNodeId
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        try {

            if ($nextcloudNodeId === null || $nextcloudNodeId === 0 || $nextcloudNodeId === '' || $nextcloudNodeId === '0') {

                $nextcloudNodeId = 0;

                $fullPathname = $this->buildFullPathname($action, $project, $pathname);
                $fileInfo = $this->fsView->getFileInfo($fullPathname);

                if ($fileInfo) {
                    $nextcloudNodeId = $fileInfo->getId();
                    Util::writeLog('ida', 'resolveNextcloudNodeId: nextcloudNodeId=' . $nextcloudNodeId, \OCP\Util::DEBUG);
                }
            }
        } catch (Exception $e) {;
            return 0;
        }

        return $nextcloudNodeId;
    }

    /**
     * Register one or more frozen files, within the scope of a specified node, associating them with the specified repair action PID.
     *
     * The most recently modified file record, if it exists, will be reinstated, else an entirely new file record will be created.
     *
     * @param string     $project        the project to which the files belongs
     * @param FileInfo[] $nextcloudNodes one or more FileInfo instances within the scope of the action
     * @param string     $pid            the PID of the action with which the files should be associated
     * @param string     $timestamp      the timestamp of when the action was initiated
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function repairFrozenFiles($project, $nextcloudNodes, $pid, $timestamp)
    {
        Util::writeLog(
            'ida',
            'repairFrozenFiles:'
                . ' project=' . $project
                . ' nextcloudNodes=' . count($nextcloudNodes)
                . ' pid=' . $pid
                . ' timestamp=' . $timestamp,
            \OCP\Util::DEBUG
        );

        foreach ($nextcloudNodes as $fileInfo) {

            // Node should only ever be file, but we check anyway, just to be sure...

            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {

                // Retrieve last created frozen file record, if any, for the given file

                $fileEntity = $this->fileMapper->findByNextcloudNodeId($fileInfo->getId(), $project, true);

                // If record exists, clone it

                if ($fileEntity != null) {

                    // Clone existing file record, associating it with the repair action

                    $newFileEntity = $this->cloneFile($fileEntity, $pid);

                    // Ensure existing file record marked as cleared (even though it ought to already be)

                    $fileEntity->setCleared($timestamp);
                    $this->fileMapper->update($fileEntity);

                    // Ensure cloned file record is treated as actively frozen

                    $newFileEntity->setRemoved(null);
                    $newFileEntity->setCleared(null);

                    // Ensure technical metadata is accurately recorded for cloned file record

                    if ($newFileEntity->getSize() === null) {
                        $newFileEntity->setSize(0 + $fileInfo->getSize());
                        // If the size was unknown, assume the checksum is invalid and purge it (to be repaired by the agent)
                        $checksum = $fileInfo->getChecksum();
                        if ($checksum === null || $checksum === '') {
                            $newFileEntity->setChecksum(null);
                        }
                        else {
                            if (substr($checksum, 0, 7) === "sha256:") {
                                $checksum = substr($checksum, 7);
                            }
                            $newFileEntity->setChecksum($checksum);
                        }
                    }
                    if ($newFileEntity->getModified() === null) {
                        $newFileEntity->setModified(Generate::newTimestamp($fileInfo->getMTime()));
                    }
                    if ($newFileEntity->getFrozen() === null) {
                        $newFileEntity->setFrozen($timestamp);
                    }

                    $this->fileMapper->update($newFileEntity);
                }

                // Else, create new record

                else {
                    $pathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());
                    $this->registerFile($fileInfo, 'freeze', $project, $pathname, $pid, $timestamp);
                }
            }
        }
    }

    /**
     * Return true if any of the pathnames of any files in the specified Nextcloud FileInfo instances, per the
     * specified action, which intersect with any files occupying the same pathname within the target space; else
     * return false.
     *
     * @param string     $action         the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string     $project        the project with which the files are associated
     * @param FileInfo[] $nextcloudNodes one or more FileInfo instances within the scope of the action
     *
     * @return boolean
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function checkIntersectionWithExistingFiles($action, $project, $nextcloudNodes)
    {
        Util::writeLog(
            'ida',
            'checkIntersectionWithExistingFiles:'
                . ' project=' . $project
                . ' action=' . $action
                . ' nextcloudNodes=' . count($nextcloudNodes),
            \OCP\Util::DEBUG
        );

        foreach ($nextcloudNodes as $fileInfo) {

            // Only check file nodes...

            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {

                $pathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());

                if ($action === 'freeze') {
                    $targetPathname = $this->buildFullPathname('unfreeze', $project, $pathname);
                } else {
                    $targetPathname = $this->buildFullPathname('freeze', $project, $pathname);
                }

                $fileInfo = $this->fsView->getFileInfo($targetPathname);

                if ($fileInfo != null) {
                    Util::writeLog('ida', 'checkIntersectionWithExistingFiles: INTERSECTION EXISTS'
                        . ' project=' . $project
                        . ' action=' . $action
                        . ' pathname=' . $targetPathname, \OCP\Util::DEBUG);

                    return true;
                }
            }
        }

        return false;
    }

    /**
     * Return true if any incomplete actions have associated with them any file having a pathname which intersects
     * with any files in the Nextcloud node FileInfo instances, regardless of whether the files are in the staging
     * or frozen areas; else, return false.
     *
     * @param string     $project        the project with which the node is associated
     * @param string     $scope          the scope of the new action
     * @param FileInfo[] $nextcloudNodes one or more FileInfo instances within the scope of the action
     * @param string     $action         the pid of a just-initiated action (optional)
     *
     * @return boolean
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function checkIntersectionWithIncompleteActions($project, $scope, $nextcloudNodes, $action = null)
    {
        Util::writeLog(
            'ida',
            'checkIntersectionWithIncompleteActions:'
                . ' project=' . $project
                . ' pathname=' . $scope
                . ' action=' . $action
                . ' nextcloudNodes=' . count($nextcloudNodes),
            \OCP\Util::DEBUG
        );

        // Retrieve all incomplete actions for the project

        $actionEntities = $this->actionMapper->findActions('incomplete', $project);

        // The project normally will have at least one just-initiated action which is incomplete, the pid of
        // which should have been provided via the action parameter; but in case no incomplete actions exist,
        // simply return false.

        if (count($actionEntities) === 0) {
            return false;
        }

        // If the new action scope does not intersect an incomplete action scope, ignoring any action with the
        // specified pid (i.e. the just-initiated action), then there are no conflicts.

        if (!$this->scopeIntersectsAction($scope, $actionEntities, $action)) {
            return false;
        }

        // Check for actual intersection of one or more files with any ongoing action, ignoring any action with
        // the specified pid (i.e. the just-initiated action)...

        // Create assoc array registering all action PIDs

        $actionPids = array();

        foreach ($actionEntities as $actionEntity) {
            $pid = $actionEntity->getPid();
            if ($pid != $action) {
                array_push($actionPids, $pid);
            }
        }

        Util::writeLog('ida', 'checkIntersectionWithIncompleteActions: actionPids: ' . implode(" ", $actionPids), \OCP\Util::DEBUG);

        // For each file node associated with new action, check if there exists a frozen file record with
        // the same pathname which is associated with one of the incomplete actions

        foreach ($nextcloudNodes as $fileInfo) {
            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {
                $pathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());
                Util::writeLog('ida', 'checkIntersectionWithIncompleteActions: pathname: ' . $pathname, \OCP\Util::DEBUG);
                # Attempt to retrieve the latest frozen file record by pathname, even if inactive
                $fileEntity = $this->fileMapper->findByProjectPathname($project, $pathname, null, true);
                if ($fileEntity) {
                    # If frozen file record found, check if associated action is incomplete, if so report intersection
                    $actionPid = $fileEntity->getAction();
                    Util::writeLog('ida', 'checkIntersectionWithIncompleteActions: actionPid: ' . $actionPid, \OCP\Util::DEBUG);
                    if (in_array($actionPid, $actionPids, true)) {
                        Util::writeLog(
                            'ida',
                            'checkIntersectionWithIncompleteActions: INTERSECTION EXISTS'
                                . ' project=' . $project
                                . ' action=' . $actionPid
                                . ' pathname=' . $pathname,
                            \OCP\Util::DEBUG
                        );
                        return true;
                    }
                }
            }
        }

        return false;
    }

    /**
     * If the specified node is a file, return false; else, if the specified node is a folder, recursively search for
     * a file within the scope of the specified folder, returning false upon encountering the first file, else return
     * true.
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the node
     *
     * @return boolean
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function isEmptyFolder($action, $project, $pathname)
    {
        Util::writeLog('ida', 'isEmptyFolder: action=' . $action . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        $fullPathname = $this->buildFullPathname($action, $project, $pathname);

        Util::writeLog('ida', 'isEmptyFolder: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

        $fileInfo = $this->fsView->getFileInfo($fullPathname);

        if ($fileInfo) {

            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {
                return false;
            }

            $children = $this->fsView->getDirectoryContent($fullPathname);

            $folders = array();

            foreach ($children as $child) {

                if ($child->getType() === FileInfo::TYPE_FILE) {
                    return false;
                } else {
                    $folders[] = $child;
                }
            }

            foreach ($folders as $folder) {
                if ($this->isEmptyFolder($action, $project, $this->stripRootProjectFolder($project, $folder->getPath())) === false) {
                    return false;
                }
            }
        }

        return true;
    }

    /**
     * Retrieve an ordered array of Nextcloud FileInfo instances for all frozen files which have a pathname
     * in the array of specified frozen file pathnames.
     *
     * @param string $project   the project to which the nodes belongs
     * @param array  $pathnames the pathnames of the frozen file nodes to include
     *
     * @return FileInfo[]
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function getNextcloudFrozenNodesByPathnames($project, $pathnames)
    {
        Util::writeLog(
            'ida',
            'getNextcloudFrozenNodesByPathnames:'
                . ' project=' . $project
                . ' pathnames=' . count($pathnames),
            \OCP\Util::DEBUG
        );

        $nodes = array();

        foreach ($pathnames as $pathname) {

            $fullPathname = $this->buildFullPathname('unfreeze', $project, $pathname);

            Util::writeLog('ida', 'getNextcloudFrozenNodesByPathnames: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo && $fileInfo->getType() === FileInfo::TYPE_FILE) {
                array_push($nodes, $fileInfo);
            }
        }

        Util::writeLog('ida', 'getNextcloudFrozenNodesByPathnames:' . ' nodecount=' . count($nodes), \OCP\Util::DEBUG);

        return ($nodes);
    }

    /**
     * Retrieve an ordered array of Nextcloud FileInfo instances for all files within the scope of the
     * specified node in the staging or frozen space, depending on the specified action.
     *
     * If the node is a file, then the set of instances will include only that file, else if a folder, it will include
     * that all files within the scope of that folder.
     *
     * If the maximum number of files is exceeded for a single action, an exception will be thrown.
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the nodes belongs
     * @param string $pathname the pathname of a node relative to the root shared folder
     * @param int    $limit    the maximum total number of files allowed (zero = no limit)
     *
     * @return FileInfo[]
     *
     * @throws MaximumAllowedFilesExceeded
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    /* CLEANUP
    protected function getNextcloudNodes($action, $project, $pathname, $limit = Constants::MAX_FILE_COUNT)
    {
        Util::writeLog(
            'ida',
            'getNextcloudNodes:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname
                . ' limit=' . $limit,
            \OCP\Util::DEBUG
        );

        $result = array('filecount' => 0, 'nodes' => array());

        $result = $this->getNextcloudNodesR($action, $project, $pathname, $limit, $result);

        Util::writeLog(
            'ida',
            'getNextcloudNodes:'
                . ' filecount=' . $result['filecount']
                . ' nodecount=' . count($result['nodes']),
            \OCP\Util::DEBUG
        );

        return ($result['nodes']);
    }
    */
    protected function getNextcloudNodes($action, $project, $pathname, $limit = Constants::MAX_FILE_COUNT)
    {
        Util::writeLog(
            'ida',
            'getNextcloudNodes:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname
                . ' limit=' . $limit,
            \OCP\Util::DEBUG
        );

        $fullPathname = $this->buildFullPathname($action, $project, $pathname);

        Util::writeLog('ida', 'getNextcloudNodes: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

        $result = $this->fileDetailsHelper->getFileDetails($project, $fullPathname, $limit);

        Util::writeLog('ida', 'getNextcloudNodes:' . ' count=' . $result['count'], \OCP\Util::DEBUG);

        // If limit to be enforced and maximum file count exceeded, throw exception

        if ($limit > 0 && $result['count'] > $limit) {
            throw new MaximumAllowedFilesExceeded();
        }

        return ($result['files']);
    }

    /**
     * Recursively build an ordered array of Nextcloud FileInfo instances for all files within the scope of the
     * specified node in the staging or frozen space, depending on the specified action. Keep track of the total
     * number of files and throw an exception if the maximum is exceeded.
     *
     * If the node is a file, then the set of instances will include only that file, else if a folder, it will include
     * that all files within the scope of that folder.
     *
     * If the maximum number of files is exceeded for a single action, an exception will be thrown.
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the nodes belongs
     * @param string $pathname the pathname of a node relative to the root shared folder
     * @param int    $limit    the maximum total number of files allowed (zero = no limit)
     * @param array  $result   the aggregated result so far
     * @param int    $level    the file store structural level (i.e. directory depth)
     *
     * @return array
     *
     * @throws MaximumAllowedFilesExceeded
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    /* CLEANUP
    protected function getNextcloudNodesR($action, $project, $pathname, $limit, $result, $level = 1)
    {
        Util::writeLog(
            'ida',
            'getNextcloudNodesR:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname
                . ' limit=' . $limit
                . ' level=' . $level
                . ' filecount=' . $result['filecount'],
            \OCP\Util::DEBUG
        );

        // If limit to be enforced and maximum file count exceeded, throw exception

        if ($limit > 0 && $result['filecount'] > $limit) {
            throw new MaximumAllowedFilesExceeded();
        }

        // Order the nodes so that at each folder level, files are first, followed by folders

        $fullPathname = $this->buildFullPathname($action, $project, $pathname);

        Util::writeLog('ida', 'getNextcloudNodesR: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

        $fileInfo = $this->fsView->getFileInfo($fullPathname);

        if ($fileInfo) {

            if ($fileInfo->getType() === FileInfo::TYPE_FOLDER) {

                Util::writeLog('ida', 'getNextcloudNodesR: level=' . $level . ' folder=' . $fileInfo->getPath(), \OCP\Util::DEBUG);

                $children = $this->fsView->getDirectoryContent($fullPathname);
                $folders = array();

                foreach ($children as $child) {

                    if ($child->getType() === FileInfo::TYPE_FILE) {
                        $result['nodes'][] = $child;
                        $result['filecount'] = $result['filecount'] + 1;
                        // Logging the file pathname as INFO here allows one to see all files included in the scope of
                        // an action which has had its initiation logged previously
                        Util::writeLog(
                            'ida',
                            'getNextcloudNodesR:'
                                . ' filecount=' . $result['filecount']
                                . ' file=' . $child->getPath(),
                            \OCP\Util::DEBUG
                        );
                    } else {
                        $folders[] = $child;
                    }
                }

                $level = $level + 1;

                foreach ($folders as $folder) {
                    $result = $this->getNextcloudNodesR(
                        $action,
                        $project,
                        $this->stripRootProjectFolder($project, $folder->getPath()),
                        $limit,
                        $result,
                        $level
                    );
                }
            } else {
                $result['nodes'][] = $fileInfo;
                $result['filecount'] = $result['filecount'] + 1;
                Util::writeLog(
                    'ida',
                    'getNextcloudNodesR:'
                        . ' filecount=' . $result['filecount']
                        . ' file=' . $fileInfo->getPath(),
                    \OCP\Util::DEBUG
                );
            }
        }

        // If limit to be enforced and maximum file count exceeded, throw exception

        if ($limit > 0 && $result['filecount'] > $limit) {
            throw new MaximumAllowedFilesExceeded();
        }

        return $result;
    }
    */

    /**
     * Construct and return the full filesystem pathname of a node based on the action, project, and its relative pathname
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the node within the shared project staging or frozen folder
     *
     * @return string
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function buildFilesystemPathname($action, $project, $pathname)
    {
        //Util::writeLog('ida', 'buildFilesystemPathname:' . ' action=' . $action . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        $fullPathname = $this->buildFullPathname($action, $project, $pathname);

        $filesystemPathname = OC::$server->getConfig()->getSystemValue('datadirectory')
            . '/'
            . Constants::PROJECT_USER_PREFIX
            . $project
            . '/files'
            . $fullPathname;

        //Util::writeLog('ida', 'buildFilesystemPathname: filesystemPathname=' . $filesystemPathname, \OCP\Util::DEBUG);

        return $filesystemPathname;
    }

    /**
     * Construct and return the full Nextcloud pathname of a node based on the action, project, and its relative pathname
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the node within the shared project staging or frozen folder
     *
     * @return string
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function buildFullPathname($action, $project, $pathname)
    {
        //Util::writeLog('ida', 'buildFullPathname:' . ' action=' . $action . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        if ($pathname === '/') {
            $pathname = '';
        }

        if ($action === 'freeze') {
            $fullPathname = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $pathname;
        } else {
            $fullPathname = '/' . $project . $pathname;
        }

        //Util::writeLog('ida', 'buildFullPathname: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

        return $fullPathname;
    }

    /**
     * Get the parent folder of the specified pathname
     *
     * @param string $pathname the full pathname
     *
     * @return string
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function getParentPathname($pathname)
    {
        //Util::writeLog('ida', 'getParentPathname: pathname=' . $pathname, \OCP\Util::DEBUG);

        $pattern = '/\/[^\/][^\/]*$/';

        if ($pathname && trim($pathname) != '') {
            $parentPathname = preg_replace($pattern, '', $pathname);
        } else {
            $parentPathname = null;
        }

        //Util::writeLog('ida', 'getParentPathname: parentPathname=' . $parentPathname, \OCP\Util::DEBUG);

        return $parentPathname;
    }

    /**
     * Strip the root project folder from the specified full Nextcloud pathname, returning a relative pathname
     *
     * @param string $project  the project to which the node belongs
     * @param string $pathname the full Nextcloud pathname of a node, including the project staging or frozen root folder
     *
     * @return string
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function stripRootProjectFolder($project, $pathname)
    {
        //Util::writeLog('ida', 'stripRootProjectFolder:' . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        $pattern = '/^.*\/files\/' . $project . '[^\/]*\//';

        if ($pathname && trim($pathname) != '') {
            $relativePathname = preg_replace($pattern, '/', $pathname);
        } else {
            $relativePathname = null;
        }

        // Util::writeLog('ida', 'stripRootProjectFolder: relativePathname=' . $relativePathname, \OCP\Util::DEBUG);

        return $relativePathname;
    }

    /**
     * Clone all files associated with a failed action with a retry action, marking all files associated
     * with the failed action being retried as removed. If the failed action has no timestamp for PID
     * generation, then any existing files are cleared but no new files are created for the retry action,
     * as that will be done in a subsequent step as part of generating and initiating the retry action.
     *
     * @param Action $failedAction the failed action being retried
     * @param Action $retryAction  the action retrying the failed action
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function cloneFiles($failedAction, $retryAction)
    {
        $failedActionPid = $failedAction->getPid();
        $retryActionPid = $retryAction->getPid();

        Util::writeLog(
            'ida',
            'cloneFiles:'
                . ' failedActionPid=' . $failedActionPid
                . ' retryActionPid=' . $retryActionPid,
            \OCP\Util::DEBUG
        );

        $timestamp = Generate::newTimestamp();

        foreach ($this->fileMapper->findFiles($failedActionPid) as $fileEntity) {

            if ($failedAction->getPids() != null) {
                $this->cloneFile($fileEntity, $retryActionPid);
            }

            $fileEntity->setCleared($timestamp);
            $this->fileMapper->update($fileEntity);
        }
    }

    /**
     * Create a new frozen file record from an existing record, setting its action to an optionally
     * specified value.
     *
     * @param File   $fileEntity an existing frozen file record
     * @param string $pid        the PID of the action with which the files should be associated
     *
     * @return File
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function cloneFile($fileEntity, $pid = null)
    {
        $fileEntityPid = $fileEntity->getPid();

        Util::writeLog('ida', 'cloneFile: fileEntityPid=' . $fileEntityPid . ' pid=' . $pid, \OCP\Util::DEBUG);

        $newFileEntity = new File();

        if ($pid !== null) {
            $newFileEntity->setAction($pid);
        } else {
            $newFileEntity->setAction($fileEntity->getAction());
        }

        $newFileEntity->setNode($fileEntity->getNode());
        $newFileEntity->setPathname($fileEntity->getPathname());
        $newFileEntity->setPid($fileEntity->getPid());
        $newFileEntity->setType($fileEntity->getType());
        $newFileEntity->setProject($fileEntity->getProject());
        $newFileEntity->setSize(0 + $fileEntity->getSize());
        $newFileEntity->setChecksum($fileEntity->getChecksum());
        $newFileEntity->setModified($fileEntity->getModified());
        $newFileEntity->setFrozen($fileEntity->getFrozen());
        $newFileEntity->setMetadata($fileEntity->getMetadata());
        $newFileEntity->setReplicated($fileEntity->getReplicated());
        $newFileEntity->setRemoved($fileEntity->getRemoved());
        $newFileEntity->setCleared($fileEntity->getCleared());

        return ($this->fileMapper->insert($newFileEntity));
    }

    /**
     * Move all immediate child nodes within the specified folder node from/to the staging space from/to the frozen space of the specified project, depending on the action
     *
     * The WebDAV REST API is used, along with the PSO user credentials, to allow all project members to move content to/from the frozen space.
     *
     * It is presumed that there are no file conflicts (i.e. that checkIntersectionWithExistingFiles() has been called prior to
     * calling this function on the root node of the action).
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the folder node
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function moveNextcloudNodeChildren($action, $project, $pathname)
    {
        Util::writeLog(
            'ida',
            'moveNextcloudNodeChildren:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        if ($action === 'freeze') {
            $sourcePathname = $this->buildFullPathname('freeze', $project, $pathname);
        } else {
            $sourcePathname = $this->buildFullPathname('unfreeze', $project, $pathname);
        }

        $children = $this->fsView->getDirectoryContent($sourcePathname);

        foreach ($children as $child) {
            $this->moveNextcloudNode($action, $project, $pathname . '/' . $child->getName());
        }
    }

    /**
     * Move the specified node from/to the staging space from/to the frozen space of the specified project, depending on the action
     *
     * The WebDAV REST API is used, along with the PSO user credentials, to allow all project members to move content to/from the frozen space.
     *
     * If the node is a file, then the file is moved. If the node is a folder, and the folder does not exist in the target space, then
     * the folder is moved; else, the function is recursively called for each immediate child of the folder.
     *
     * It is presumed that there are no file conflicts (i.e. that checkIntersectionWithExistingFiles() has been called prior to
     * calling this function on the root node of the action), but conflicts are also checked for files, in case any modifications
     * to the filesystem occur while the function is executing.
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the node within the shared project staging or frozen folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function moveNextcloudNode($action, $project, $pathname)
    {
        Util::writeLog(
            'ida',
            'moveNextcloudNode:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        // Initialize IDA change mode from client (e.g. UI) if it was provided in request, else default to 'api'
        $idaMode = 'api';
		if (isset($_SERVER['HTTP_IDA_MODE'])) {
			$values = explode(',', $_SERVER['HTTP_IDA_MODE']);
			$idaMode = $values[0];
		}

        // If pathname is the root folder '/', move all children within the scope of the root folder.

        if ($pathname === '/' || $pathname === '' || $pathname === null) {
            return $this->moveNextcloudNodeChildren($action, $project, $pathname);
        }

        if ($action === 'freeze') {
            $sourcePathname = $this->buildFullPathname('freeze', $project, $pathname);
            $targetPathname = $this->buildFullPathname('unfreeze', $project, $pathname);
        } else {
            $sourcePathname = $this->buildFullPathname('unfreeze', $project, $pathname);
            $targetPathname = $this->buildFullPathname('freeze', $project, $pathname);
        }

        Util::writeLog(
            'ida',
            'moveNextcloudNode:'
                . ' sourcePathname=' . $sourcePathname
                . ' targetPathname=' . $targetPathname,
            \OCP\Util::DEBUG
        );

        // Check that source node exists

        $fileInfo = $this->fsView->getFileInfo($sourcePathname);

        if ($fileInfo) {

            // Check if the target node exists

            $targetExists = $this->fsView->getFileInfo($targetPathname) != null;

            // If node is a file and target node exists, signal a conflict

            if ($targetExists && $fileInfo->getType() === FileInfo::TYPE_FILE) {
                throw new PathConflict('A file already exists with the target pathname: ' . $targetPathname);
            }

            // Initialize for either move or delete...

            $username = Constants::PROJECT_USER_PREFIX . $project;
            $password = $this->config['PROJECT_USER_PASS'];
            $baseURI = $this->config['FILE_API'];
            $sourceURI = $baseURI . API::urlEncodePathname($sourcePathname);
            $targetURI = $baseURI . API::urlEncodePathname($targetPathname);

            Util::writeLog('ida', 'moveNextcloudNode:' . ' sourceURI=' . $sourceURI . ' targetURI=' . $targetURI, \OCP\Util::DEBUG);

            // If target node does not exist, no matter whether folder or file, move from source to target and we're done

            if ($targetExists === false) {

                // Ensure all ancestor folders in target path exist

                $this->createNextcloudPathFolders($project, $targetPathname);

                // Move the folder from source to target pathname

                $ch = curl_init($sourceURI);

                curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'MOVE');
                curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                    'Destination: ' . $targetURI,
                    'IDA-Mode: ' . $idaMode,
                    'IDA-Authenticated-User: ' . $this->userId
                ));
                curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_ANY);
                curl_setopt($ch, CURLOPT_UNRESTRICTED_AUTH, true);
                curl_setopt($ch, CURLOPT_NOBODY, true);
                curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                curl_setopt($ch, CURLOPT_FAILONERROR, true);
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);

                $response = curl_exec($ch);

                if ($response === false) {
                    Util::writeLog('ida', 'moveNextcloudNode: MOVE'
                        . ' sourceURI=' . $sourceURI
                        . ' targetURI=' . $targetURI
                        . ' user=' . $this->userId
                        . ' mode=' . $idaMode
                        . ' curl_errno=' . curl_errno($ch)
                        . ' response=' . $response, \OCP\Util::ERROR);
                    curl_close($ch);
                    throw new Exception('Failed to move node from "' . $sourcePathname . '" to "' . $targetPathname . '"');
                }

                curl_close($ch);
            }

            // Else, the node is a folder which exists in the target space, so recursively call function on each of
            // the immediate children of the folder, to move them into the target space, and then delete the folder
            // from the source space

            else {

                $this->moveNextcloudNodeChildren($action, $project, $pathname);

                $ch = curl_init($sourceURI);

                curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
                curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                    'IDA-Mode: ' . $idaMode,
                    'IDA-Authenticated-User: ' . $this->userId
                ));
                curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_ANY);
                curl_setopt($ch, CURLOPT_UNRESTRICTED_AUTH, true);
                curl_setopt($ch, CURLOPT_NOBODY, true);
                curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                curl_setopt($ch, CURLOPT_FAILONERROR, true);
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);

                $response = curl_exec($ch);

                if ($response === false) {
                    Util::writeLog('ida', 'moveNextcloudNode: DELETE'
                        . ' sourceURI=' . $sourceURI
                        . ' user=' . $this->userId
                        . ' mode=' . $idaMode
                        . ' curl_errno=' . curl_errno($ch)
                        . ' response=' . $response, \OCP\Util::ERROR);
                    curl_close($ch);
                    throw new Exception('Failed to delete now-empty folder "' . $sourcePathname . '"');
                }

                curl_close($ch);
            }
        } else {
            throw new Exception('Node not found: ' . $sourcePathname);
        }
    }

    /**
     * Delete all immediate child nodes within the specified folder node from the frozen space of the specified project
     *
     * The WebDAV REST API is used, along with the PSO user credentials, to allow all project members to move content to/from the frozen space.
     *
     * It is presumed that there are no file conflicts (i.e. that checkIntersectionWithExistingFiles() has been called prior to
     * calling this function on the root node of the action).
     *
     * @param string $action   the action being performed, one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the folder node
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function deleteNextcloudNodeChildren($project, $pathname)
    {
        Util::writeLog(
            'ida',
            'deleteNextcloudNodeChildren:'
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        $sourcePathname = $this->buildFullPathname('unfreeze', $project, $pathname);

        $children = $this->fsView->getDirectoryContent($sourcePathname);

        foreach ($children as $child) {
            $this->deleteNextcloudNode($project, $pathname . '/' . $child->getName());
        }
    }

    /**
     * Delete the specified node from the frozen space of the specified project
     *
     * The WebDAV REST API is used, along with the PSO user credentials, to allow all project members to delete content from the frozen space.
     *
     * @param string $project  the project to which the node belongs
     * @param string $pathname the relative pathname of the node within the shared project staging or frozen folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function deleteNextcloudNode($project, $pathname)
    {
        Util::writeLog('ida', 'deleteNextcloudNode:' . ' project=' . $project . ' pathname=' . $pathname, \OCP\Util::INFO);

        // Initialize IDA change mode from client (e.g. UI) if it was provided in request, else default to 'api'
        $idaMode = 'api';
		if (isset($_SERVER['HTTP_IDA_MODE'])) {
			$values = explode(',', $_SERVER['HTTP_IDA_MODE']);
			$idaMode = $values[0];
		}

        // If pathname is the root folder '/', delete all children within the scope of the root folder.

        if ($pathname === '/' || $pathname === '' || $pathname === null) {
            return $this->deleteNextcloudNodeChildren($project, $pathname);
        }

        $sourcePathname = '/' . $project . $pathname;

        Util::writeLog('ida', 'deleteNextcloudNode:' . ' sourcePathname=' . $sourcePathname, \OCP\Util::DEBUG);

        // Check that source node exists

        $fileInfo = $this->fsView->getFileInfo($sourcePathname);

        if ($fileInfo) {

            // Delete the specified node

            $username = Constants::PROJECT_USER_PREFIX . $project;
            $password = $this->config['PROJECT_USER_PASS'];
            $baseURI = $this->config['FILE_API'];
            $sourceURI = $baseURI . API::urlEncodePathname($sourcePathname);

            Util::writeLog(
                'ida',
                'deleteNextcloudNode:'
                    . ' sourceURI=' . $sourceURI
                    . ' username=' . $username
                    . ' password=' . $password,
                \OCP\Util::DEBUG
            );

            $ch = curl_init($sourceURI);

            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
            curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                'IDA-Mode: ' . $idaMode,
                'IDA-Authenticated-User: ' . $this->userId
            ));
            curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
            curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_ANY);
            curl_setopt($ch, CURLOPT_UNRESTRICTED_AUTH, true);
            curl_setopt($ch, CURLOPT_NOBODY, true);
            curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
            curl_setopt($ch, CURLOPT_FAILONERROR, true);
            curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);

            $response = curl_exec($ch);

            if ($response === false) {
                Util::writeLog('ida', 'deleteNextcloudNode: DELETE'
                    . ' sourceURI=' . $sourceURI
                    . ' user=' . $this->userId
                    . ' mode=' . $idaMode
                    . ' curl_errno=' . curl_errno($ch)
                    . ' response=' . $response, \OCP\Util::ERROR);
                curl_close($ch);
                throw new Exception('Failed to delete node "' . $sourcePathname . '"');
            }

            curl_close($ch);
        } else {
            throw new Exception('Node not found: ' . $sourcePathname);
        }
    }

    /**
     * Create any missing ancestor folders in specified target pathname, so subsequent move request succeeds
     *
     * The WebDAV REST API is used, along with the PSO user credentials, to allow all project members to create folders in the frozen space.
     *
     * @param string $project  the project to which the folder belongs
     * @param string $pathname the full pathname
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function createNextcloudPathFolders($project, $pathname)
    {
        Util::writeLog('ida', 'createNextcloudPathFolders: project=' . $project . ' pathname=' . $pathname, \OCP\Util::DEBUG);

        // Initialize IDA change mode from client (e.g. UI) if it was provided in request, else default to 'api'
        $idaMode = 'api';
		if (isset($_SERVER['HTTP_IDA_MODE'])) {
			$values = explode(',', $_SERVER['HTTP_IDA_MODE']);
			$idaMode = $values[0];
		}

        $folderPath = substr($this->getParentPathname($pathname), 1);

        $folders = explode('/', $folderPath);

        Util::writeLog('ida', 'createNextcloudPathFolders: folderPath=' . $folderPath . ' count=' . count($folders), \OCP\Util::DEBUG);

        if (count($folders) > 0) {

            $username = Constants::PROJECT_USER_PREFIX . $project;
            $password = $this->config['PROJECT_USER_PASS'];
            $baseURI = $this->config['FILE_API'];
            $rootPathname = '';

            foreach ($folders as $folder) {

                $folderPathname = $rootPathname . '/' . $folder;

                Util::writeLog('ida', 'createNextcloudPathFolders:' . ' folderPathname=' . $folderPathname, \OCP\Util::DEBUG);

                $fileInfo = $this->fsView->getFileInfo($folderPathname);

                // If folder doesn't exist, create it

                if ($fileInfo === false) {

                    $folderURI = $baseURI . API::urlEncodePathname($folderPathname);

                    Util::writeLog(
                        'ida',
                        'createNextcloudPathFolders:'
                            . ' folderURI=' . $folderURI
                            . ' username=' . $username
                            . ' password=' . $password,
                        \OCP\Util::DEBUG
                    );

                    $ch = curl_init($folderURI);

                    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'MKCOL');
                    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                        'IDA-Mode: ' . $idaMode,
                        'IDA-Authenticated-User: ' . $this->userId
                    ));
                    curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                    curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_ANY);
                    curl_setopt($ch, CURLOPT_UNRESTRICTED_AUTH, true);
                    curl_setopt($ch, CURLOPT_NOBODY, true);
                    curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                    curl_setopt($ch, CURLOPT_FAILONERROR, true);
                    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);

                    $response = curl_exec($ch);

                    if ($response === false) {
                        Util::writeLog('ida', 'createNextcloudPathFolders: MKCOL'
                            . ' folderURI=' . $folderURI
                            . ' user=' . $this->userId
                            . ' mode=' . $idaMode
                            . ' curl_errno=' . curl_errno($ch)
                            . ' response=' . $response, \OCP\Util::ERROR);
                        curl_close($ch);
                        throw new Exception('Failed to create path folder "' . $folderPathname . '"');
                    }

                    curl_close($ch);
                }

                $rootPathname = $rootPathname . '/' . $folder;
            }
        }
    }

    /**
     * Clear all failed and/or pending actions in the database, optionally limited to a particular status or one or more projects
     *
     * Restricted to admin
     *
     * @param string $status   one of 'failed' (default) or 'pending'
     * @param string $projects one or more projects, comma separated, with no whitespace
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function clearActions($status = 'failed', $projects = null)
    {
        if ($status !== 'failed' && $status !== 'pending') {
            return API::badRequestErrorResponse('Invalid status.');
        }

        if ($this->userId === 'admin') {
            $entities = $this->actionMapper->clearActions($status, $projects);
            return new DataResponse($entities);
        } else {
            return API::forbiddenErrorResponse();
        }
    }

    /**
     * Flush and/or generate database records to load query and index performance, for testing.
     *
     * Restricted to admin user. Only executable in a test environment.
     *
     * @param string $flush          one of 'true' or 'false' (default)
     * @param string $action         either 'delete' (default) or 'freeze'
     * @param int    $actions        the number of action records to generate
     * @param int    $filesPerAction the number of file records to generate per action (required if action defined)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function dbLoad($flush = 'false', $action = 'delete', $actions = null, $filesPerAction = null)
    {
        try {

            if ($flush === 'false' && $actions === null) {
                return API::badRequestErrorResponse('Insufficient parameters specified');
            }

            if ($actions !== null) {
                try {
                    API::validateIntegerParameter('actions', $actions);
                    API::verifyRequiredIntegerParameter('filesPerAction', $filesPerAction);
                } catch (Exception $e) {
                    return API::badRequestErrorResponse($e->getMessage());
                }
            }

            // Allowed for admin

            if ($this->userId !== 'admin') {
                return API::forbiddenErrorResponse();
            }

            // Allowed only in test environment

            if ($this->config['IDA_ENVIRONMENT'] !== 'TEST') {
                return API::serverErrorResponse('Operation is only permitted in test environment');
            }

            // Flush records if specified

            if ($flush === 'true') {
                $this->actionMapper->deleteAllActions('test_dbload');
                $this->fileMapper->deleteAllFiles('test_dbload');
            }

            // Generate new records if specified

            if ($actions !== null) {

                $pidBase = '5c18cb0291956461057262dbload';

                for ($i = 1; $i <= $actions; $i++) {

                    // Create action record

                    $timestamp = Generate::newTimestamp();
                    $fakeActionNodeId = 900000000 + $i * $filesPerAction;

                    $actionEntity = new Action();
                    $actionEntity->setPid($pidBase . $i . 'a');
                    $actionEntity->setAction($action);
                    $actionEntity->setUser('admin');
                    $actionEntity->setProject('test_dbload');
                    $actionEntity->setNode($fakeActionNodeId);
                    $actionEntity->setPathname('/dbload/folder_' . $i);
                    $actionEntity->setInitiated($timestamp);
                    $actionEntity->setStorage($timestamp);
                    $actionEntity->setPids($timestamp);
                    $actionEntity->setChecksums($timestamp);
                    $actionEntity->setMetadata($timestamp);
                    $actionEntity->setCompleted($timestamp);
                    $this->actionMapper->insert($actionEntity);

                    for ($j = 1; $j <= $filesPerAction; $j++) {

                        // Create frozen file record

                        $fileEntity = new File();
                        $fileEntity->setAction($actionEntity->getPid());
                        $fileEntity->setNode($fakeActionNodeId + $j);
                        $fileEntity->setPid($pidBase . $i . 'f' . $j);
                        $fileEntity->setFrozen($timestamp);
                        $fileEntity->setProject('test_dbload');
                        $fileEntity->setPathname('/dbload/folder_' . $i . '/test_file_' . $j);
                        $fileEntity->setSize(123);
                        $fileEntity->setChecksum("e119a3ede6ea938a50b54c068503f4544e57754e36790b78efdd5c73ea4c4cb2");
                        $fileEntity->setModified($timestamp);
                        if ($action != 'freeze') {
                            $fileEntity->setRemoved($timestamp);
                        }
                        $this->fileMapper->insert($fileEntity);
                    }
                }
            }

            return $this->dbLoadSummary();

        } catch (Exception $e) {
            return API::serverErrorResponse('dbLoad: ' . $e->getMessage());
        }
    }

    /**
     * Return a summary of all existing db load records
     *
     * Restricted to admin user. Only executable in a test environment.
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function dbLoadSummary()
    {
        try {

            // Allowed for admin

            if ($this->userId !== 'admin') {
                return API::forbiddenErrorResponse();
            }

            // Allowed only in test environment

            if ($this->config['IDA_ENVIRONMENT'] !== 'TEST') {
                return API::serverErrorResponse('Operation is only permitted in test environment');
            }

            $actionCount = $this->actionMapper->countActions(null, 'test_dbload');
            $activeFileCount = $this->fileMapper->countFiles(null, 'test_dbload', false);
            $totalFileCount = $this->fileMapper->countFiles(null, 'test_dbload', true);

            $summary = array();

            $summary['project'] = 'test_dbload';
            $summary['actions'] = $actionCount;
            $summary['activeFiles'] = $activeFileCount;
            $summary['totalFiles'] = $totalFileCount;

            return new DataResponse($summary);
        } catch (Exception $e) {
            return API::serverErrorResponse('dbLoadSummary: ' . $e->getMessage());
        }
    }

    /**
     * Flush all action and frozen file records from the database.
     *
     * Restricted to admin or PSO user of specified project. For safety's sake, PSO credentials must
     * be used for each specific project, and admin credentials must be used with the explicit project
     * parameter value 'all' to flush all project records.
     *
     * @param string $project the project to flush (required, must be 'all' for admin user)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function flushDatabase($project)
    {
        try {
            API::verifyRequiredStringParameter('project', $project);
        } catch (Exception $e) {
            return API::badRequestErrorResponse($e->getMessage());
        }

        // Allowed for admin or PSO user only

        if ($this->userId !== 'admin' && strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
            return API::forbiddenErrorResponse();
        }

        // All projects allowed for admin only

        if ($project === 'all') {

            if ($this->userId === 'admin') {

                $this->actionMapper->deleteAllActions('all');
                $this->fileMapper->deleteAllFiles('all');

                return new DataResponse('Database flushed for all projects.');
            }

            return API::forbiddenErrorResponse();

        } else {

            // PSO user must belong to project

            if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                ($project !== substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX)))
            ) {
                return API::forbiddenErrorResponse();
            }

            $this->actionMapper->deleteAllActions($project);
            $this->fileMapper->deleteAllFiles($project);
            $this->dataChangeMapper->deleteAllDataChanges($project);

            return new DataResponse('Database flushed for project ' . $project . '.');
        }
    }

    /**
     * Create action and frozen file database entities for all files within either the staging or frozen
     * areas of the project of the authenticated PSO user based on the pathnames provided as input. Any existing
     * action and frozen file entities will be first flushed from the database. Only files corresponding to the
     * input pathnames will be bootstrapped.
     *
     * Restricted to PSO user. Project name is derived from PSO username
     * This function uses the 'batch-actions' RabbitMQ exchange
     *
     * @param string $action    one of 'migrate-s' (staging) or 'migrate-f' (frozen)
     * @param array  $checksums associative array of pathname to checksum mappings
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function bootstrapProject($action = null, $checksums = null)
    {
        if ($action === null) {
            return API::badRequestErrorResponse('No action specified.');
        }

        if ($checksums === null) {
            return API::badRequestErrorResponse('No checksums specified.');
        }

        if ($action != 'migrate-s' && $action != 'migrate-f') {
            return API::badRequestErrorResponse('Invalid action specified: ' . $action);
        }

        $project = null;

        try {

            Util::writeLog('ida', 'bootstrapProject:' . ' user=' . $this->userId . ' action=' . $action, \OCP\Util::INFO);

            // Ensure user is PSO user...

            if (strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
                return API::forbiddenErrorResponse();
            }

            // Extract project name from PSO user name...

            $project = substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX));

            // Reject the action if the project is suspended

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Lock the project so no other user can initiate an action

            if (!Access::lockProject($project)) {
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // Flush any existing action and frozen file records from db for project...

            $this->flushDatabase($project);

            $targetPathnameRoot = '/' . $project;

            if ($action === 'migrate-s') {
                $targetPathnameRoot = $targetPathnameRoot . Constants::STAGING_FOLDER_SUFFIX;
            }

            $pathnames = array_keys($checksums);
            $pathnameCount = count($pathnames);

            if ($pathnameCount === 0) {
                Access::unlockProject($project);

                return API::badRequestErrorResponse('No checksums specified.');
            }

            Util::writeLog('ida', 'bootstrapProject:' . ' pathnameCount=' . $pathnameCount, \OCP\Util::DEBUG);

            $fileEntities = [];

            $actionEntity = $this->registerAction(0, $action, $project, 'service', '/', true);
            $timestamp = Generate::newTimestamp();
            $actionEntity->setStorage($timestamp);
            if ($action === 'migrate-f') {
                $actionEntity->setPids($timestamp);
                $actionEntity->setChecksums($timestamp);
                $actionEntity->setMetadata($timestamp);
            }
            if ($action === 'migrate-s') {
                $actionEntity->setCompleted($timestamp);
            }
            $this->actionMapper->update($actionEntity);

            if ($action === 'migrate-s') {
                $action = 'unfreeze';
            } else {
                $action = 'freeze';
            }

            $pid = $actionEntity->getPid();

            foreach ($pathnames as $pathname) {

                $targetPathname = $targetPathnameRoot . $pathname;

                $fileInfo = $this->fsView->getFileInfo($targetPathname);

                if ($fileInfo) {
                    $fileEntity = $this->registerFile($fileInfo, $action, $project, $pathname, $pid, $timestamp);
                    $fileEntity->setChecksum($checksums[$pathname]);
                    $fileEntity = $this->fileMapper->update($fileEntity);
                    $fileEntities[] = $fileEntity;
                }
            }

            Util::writeLog('ida', 'bootstrapProject: actionPid=' . $pid . ' filecount=' . count($fileEntities), \OCP\Util::INFO);

            // Unlock project and return file details

            Access::unlockProject($project);

            return new DataResponse($fileEntities);
        } catch (Exception $e) {

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse('bootstrapProject: ' . $e->getMessage());
        }
    }

    /**
     * Create action and frozen file database entities for all files within frozen area of
     * the project of the authenticated PSO user. Any pending or failed actions will be cleared.
     * All active frozen file records will be marked as cleared.
     *
     * For all files physically in the frozen area of the project, if a frozen file pathname matches
     * an existing frozen file record, that record will be cloned, preserving the original file details,
     * and the cloned file record marked as active, else a new frozen file record will be created. All
     * active frozen file records will be associated with a special 'repair' action.
     *
     * Restricted to PSO user. Project name is derived from PSO username.
     * This function uses the 'batch-actions' RabbitMQ exchange
     *
     * The project is suspended while the repair is ongoing, forcing the project into read-only mode.
     *
     * This method will publish the special "repair" action to rabbitmq for postprocessing. The
     * postprocessing agents will recognize the special type of "repair" action and adjust their
     * behavior accordingly.
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function repairProject()
    {
        Util::writeLog('ida', 'repairProject:' . ' user=' . $this->userId, \OCP\Util::INFO);

        $project = null;

        try {

            // Ensure user is PSO user...

            if (strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
                return API::forbiddenErrorResponse();
            }

            // Extract project name from PSO user name...

            $project = substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX));

            // Verify RabbitMQ is accepting connections, if not, abandon action and inform the user to try again later...

            if (!$this->verifyRabbitMQConnectionOK()) {
                Util::writeLog('ida', 'repairProject: ERROR: Unable to open connection to RabbitMQ!', \OCP\Util::ERROR);
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // Ensure project is locked

            Access::lockProject($project);

            // Get current time

            $timestamp = Generate::newTimestamp();

            // Clear any incomplete actions (except 'suspend' action)

            $incompleteActions = $this->actionMapper->findActions('incomplete', $project);

            if (count($incompleteActions) > 0) {
                foreach ($incompleteActions as $actionEntity) {
                    if ($actionEntity->getAction() != 'suspend') {
                        $actionEntity->setCleared($timestamp);
                        $this->actionMapper->update($actionEntity);
                    }
                }
            }

            // Create repair action, which will suspend project and keep project into read-only mode until the action
            // is recorded as completed, due to the root scope.

            $repairActionEntity = $this->registerAction(0, 'repair', $project, 'service', '/', true);

            // Process request body, if present

            $frozenFilePathnames = null;
            $jsonBody = file_get_contents('php://input');

            if ($jsonBody && !empty($jsonBody)) {
                // Decode JSON string into PHP array
                $frozenFilePathnames = json_decode($jsonBody, true);
            }

            $frozenFilePathnamesProvided = ($frozenFilePathnames && is_array($frozenFilePathnames) && count($frozenFilePathnames) > 0);

            Util::writeLog('ida', 'repairProject:' . ' frozenFilePathnamesProvided=' . $frozenFilePathnamesProvided, \OCP\Util::DEBUG);

            // If frozen file pathnames are provided in request body, extract and limit to frozen files
            // with pathname in set of specified pathnames, else retrieve all active frozen file records

            if ($frozenFilePathnamesProvided) {
                $frozenFileEntities = $this->fileMapper->findFrozenFilesByPathnames($project, $frozenFilePathnames);
            }
            else {
                $frozenFileEntities = $this->fileMapper->findFrozenFiles($project);
            }

            // Mark all selected frozen files as cleared. Files which are physically present in the frozen area will
            // have those same records cloned below.

            if (count($frozenFileEntities) > 0) {
                foreach ($frozenFileEntities as $fileEntity) {
                    $fileEntity->setCleared($timestamp);
                    $this->fileMapper->update($fileEntity);
                }
            }

            // Retrieve and reinstate all files in the frozen area.

            if ($frozenFilePathnamesProvided) {
                $nextcloudNodes = $this->getNextcloudFrozenNodesByPathnames($project, $frozenFilePathnames);
            }
            else {
                // Disable file count limit by specifying limit as zero.
                $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, '/', 0);
            }

            // Register all files in frozen area, associating them with the new 'repair' action...
            // (this is the only time the special action 'repair' is used)

            if (count($nextcloudNodes) > 0) {
                $this->repairFrozenFiles($project, $nextcloudNodes, $repairActionEntity->getPid(), $repairActionEntity->getInitiated());
            }

            $timestamp = Generate::newTimestamp();
            $repairActionEntity->setPids($timestamp);
            $repairActionEntity->setStorage($timestamp);
            $this->actionMapper->update($repairActionEntity);

            // Publish new action message to RabbitMQ

            $this->publishActionMessage($repairActionEntity, true);

            // Unlock project

            Access::unlockProject($project);

            // Return new repair action details

            return new DataResponse($repairActionEntity);

        } catch (Exception $e) {

            // Cleanup and report error

            if ($repairActionEntity != null) {
                $this->actionMapper->deleteAction($repairActionEntity->getPid());
            }

            Access::unlockProject($project);

            return API::serverErrorResponse('repairProject: ' . $e->getMessage());
        }
    }


    /**
     * Repair the Nextcloud node modification timestamp for a specific folder or file pathname as
     * reported in an auditing report, beginning with either the prefix 'staging/' or 'frozen/'.
     *
     * Restricted to PSO user. Project name is derived from PSO username.
     *
     * @param string $pathname   pathname of the file, beginning with either 'frozen/' or 'staging/'
     * @param string $timestamp  the ISO UTC formatted timestamp string to be recorded
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function repairNodeTimestamp($pathname, $modified)
    {
        Util::writeLog('ida', 'repairNodeTimestamp:'
            . ' user=' . $this->userId
            . ' pathname=' . $pathname
            . ' modified=' . $modified,
            \OCP\Util::DEBUG);

        try {

            // Ensure user is PSO user...

            if (strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
                return API::forbiddenErrorResponse();
            }

            // Extract project name from PSO user name...

            $project = substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX));

            // If pathname starts with 'frozen/' then use action 'unfreeze' to get full pathname,
            // else pathname starts with 'staging/' so use action 'freeze' to get full pathname;
            // and remove the prefix from the pathname.

            if (str_starts_with($pathname, 'frozen/')) {
                $action = 'unfreeze';
                $relativePathname = substr($pathname, strlen('frozen'));
            }
            else {
                $action = 'freeze';
                $relativePathname = substr($pathname, strlen('staging'));
            }

            $fullPathname = $this->buildFullPathname($action, $project, $relativePathname);

            Util::writeLog('ida', 'repairNodeTimestamp: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo) {

                $nodeId = $fileInfo->getId();

                $ts = strtotime($modified);

                Util::writeLog('ida', 'repairNodeTimestamp: nodeId=' . $nodeId, \OCP\Util::DEBUG);

                $data = [ 'mtime' => $ts, 'storage_mtime' => $ts ];

                $fileInfo->getStorage()->getCache()->update($nodeId, $data);

                Util::writeLog('ida', 'repairNodeTimestamp: project=' . $project
                    . ' pathname=' . $pathname
                    . ' modified=' . $modified, \OCP\Util::INFO);

                return new DataResponse(array(
                    'project' => $project,
                    'pathname' => $pathname,
                    'modified' => $modified,
                    'nodeId' => $nodeId
                ));
            }

            // No node found with the specified pathname so return 404
            return API::notFoundErrorResponse();

        } catch (Exception $e) {
            return API::serverErrorResponse('repairNodeTimestamp: ' . $e->getMessage());
        }
    }

    /**
     * Repair the Nextcloud file cache checksum for a specific file pathname as reported in an auditing
     * report, beginning with either the prefix 'staging/' or 'frozen/'.
     *
     * Restricted to PSO user. Project name is derived from PSO username.
     *
     * @param string $pathname  pathname of the file, beginning with either 'frozen/' or 'staging/'
     * @param string $checksum  an SHA-256 checksum, either in URI form or without URI prefix
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function repairCacheChecksum($pathname, $checksum)
    {
        Util::writeLog('ida', 'repairCacheChecksum:'
            . ' user=' . $this->userId
            . ' pathname=' . $pathname
            . ' checksum=' . $checksum,
            \OCP\Util::DEBUG);

        try {

            // Ensure user is PSO user...

            if (strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
                return API::forbiddenErrorResponse();
            }

            // Extract project name from PSO user name...

            $project = substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX));

            // If pathname starts with 'frozen/' then use action 'unfreeze' to get full pathname,
            // else pathname starts with 'staging/' so use action 'freeze' to get full pathname;
            // and remove the prefix from the pathname.

            if (str_starts_with($pathname, 'frozen/')) {
                $action = 'unfreeze';
                $relativePathname = substr($pathname, strlen('frozen'));
            }
            else {
                $action = 'freeze';
                $relativePathname = substr($pathname, strlen('staging'));
            }

            $fullPathname = $this->buildFullPathname($action, $project, $relativePathname);

            Util::writeLog('ida', 'repairCacheChecksum: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo) {

                $nodeId = $fileInfo->getId();

                if (substr($checksum, 0, 7) != "sha256:") {
                    $checksum = 'sha256:' . $checksum;
                }

                Util::writeLog('ida', 'repairCacheChecksum: nodeId=' . $nodeId, \OCP\Util::DEBUG);

                $data = [ 'checksum' => $checksum ];

                $fileInfo->getStorage()->getCache()->update($nodeId, $data);

                Util::writeLog('ida', 'repairCacheChecksum: project=' . $project . ' pathname=' . $pathname . ' checksum=' . $checksum, \OCP\Util::INFO);

                return new DataResponse(array(
                    'project' => $project,
                    'pathname' => $pathname,
                    'checksum' => $checksum,
                    'nodeId' => $nodeId
                ));
            }

            // No node found with the specified pathname so return 404
            return API::notFoundErrorResponse();

        } catch (Exception $e) {
            return API::serverErrorResponse('repairCacheChecksum: ' . $e->getMessage());
        }
    }

    /**
     * Retrieve the Nextcloud file cache checksum for a specific file pathname as reported in an auditing
     * report, beginning with either the prefix 'staging/' or 'frozen/' (if any).
     *
     * Restricted to PSO user. Project name is derived from PSO username.
     *
     * @param string $pathname  pathname of the file, beginning with either 'frozen/' or 'staging/'
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function retrieveCacheChecksum($pathname)
    {
        Util::writeLog('ida', 'retrieveCacheChecksum:'
            . ' user=' . $this->userId
            . ' pathname=' . $pathname,
            \OCP\Util::DEBUG);

        try {

            // Ensure user is PSO user...

            if (strpos($this->userId, Constants::PROJECT_USER_PREFIX) !== 0) {
                return API::forbiddenErrorResponse();
            }

            // Extract project name from PSO user name...

            $project = substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX));

            // If pathname starts with 'frozen/' then use action 'unfreeze' to get full pathname,
            // else pathname starts with 'staging/' so use action 'freeze' to get full pathname;
            // and remove the prefix from the pathname.

            if (str_starts_with($pathname, 'frozen/')) {
                $action = 'unfreeze';
                $relativePathname = substr($pathname, strlen('frozen'));
            }
            else {
                $action = 'freeze';
                $relativePathname = substr($pathname, strlen('staging'));
            }

            $fullPathname = $this->buildFullPathname($action, $project, $relativePathname);

            Util::writeLog('ida', 'retrieveCacheChecksum: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

            $fileInfo = $this->fsView->getFileInfo($fullPathname);

            if ($fileInfo) {

                $nodeId = $fileInfo->getId();
                $checksum = strtolower($fileInfo->getChecksum());

                Util::writeLog('ida', 'retrieveCacheChecksum: checksum=' . $checksum, \OCP\Util::DEBUG);

                return new DataResponse(array(
                    'project' => $project,
                    'pathname' => $pathname,
                    'checksum' => $checksum,
                    'nodeId' => $nodeId
                ));
            }

            // No node found with the specified pathname so return 404
            return API::notFoundErrorResponse();

        } catch (Exception $e) {
            return API::serverErrorResponse('retrieveCacheChecksum: ' . $e->getMessage());
        }
    }

    /**
     * Test whether RabbitMQ connection can be opened for publication.
     *
     * @return boolean
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function verifyRabbitMQConnectionOK()
    {
        try {
            $rabbitMQconnection = $this->openRabbitMQConnection();
            $rabbitMQconnection->close();
        } catch (Exception $e) {
            Util::writeLog('ida', 'verifyRabbitMQConnectionOK: ERROR: Unable to successfully connect with RabbitMQ: ' . $e->getMessage(), \OCP\Util::ERROR);
            return false;
        }

        return true;
    }

    /**
     * Open a connection to RabbitMQ for publication
     *
     * @return AMQPStreamConnection
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function openRabbitMQConnection()
    {
        $host = $this->config['RABBIT_HOST'];
        $port = $this->config['RABBIT_PORT'];
        $vhost = $this->config['RABBIT_VHOST'];
        $username = $this->config['RABBIT_WORKER_USER'];
        $password = $this->config['RABBIT_WORKER_PASS'];

        return new AMQPStreamConnection($host, $port, $username, $password, $vhost);
    }

    /**
     * Publish a message to RabbitMQ about the specified action
     *
     * If the HTTP header X-SIMULATE-AGENTS is defined, it takes precidence over the configuration
     * variable SIMULATE_AGENTS. If agents are to be simulated, the action is simply marked as
     * completed and no action message is published to rabbitmq.
     *
     * @param Entity $actionEntity database entity for the new action about which the message should be published
     * @param bool $batch specifies whether to use the actions or the batch-actions RabbitMQ exchange
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function publishActionMessage($actionEntity, $batch = false)
    {
        $rabbitMQconnection = null;

        try {

            if ($actionEntity) {

                // Convert boolean to string for logging
                $batch_string = var_export($batch, true);

                Util::writeLog(
                    'ida',
                    'publishActionMessage:'
                        . ' pid=' . $actionEntity->getPid()
                        . ' action=' . $actionEntity->getAction()
                        . ' project=' . $actionEntity->getProject()
                        . ' user=' . $actionEntity->getUser()
                        . ' pathname=' . $actionEntity->getPathname()
                        . ' initiated=' . $actionEntity->getInitiated()
                        . ' batch=' . $batch_string,
                    \OCP\Util::INFO
                );

                $simulateAgents = false;

                // If HTTP header is specified, ignore configuration
                if (isset($_SERVER['HTTP_X_SIMULATE_AGENTS'])) {
                    if ($_SERVER['HTTP_X_SIMULATE_AGENTS'] === "true") {
                        $simulateAgents = true;
                    }
                } else {
                    if ($this->config['SIMULATE_AGENTS']) {
                        $simulateAgents = true;
                    }
                }

                if ($simulateAgents === true) {
                    $timestamp = Generate::newTimestamp();
                    if ($actionEntity->getAction() === 'freeze' || $actionEntity->getAction() === 'repair') {
                        $actionEntity->setChecksums($timestamp);
                        $actionEntity->setReplication($timestamp);
                    }
                    $actionEntity->setMetadata($timestamp);
                    $actionEntity->setCompleted($timestamp);
                    $this->actionMapper->update($actionEntity);

                    Util::writeLog('ida', 'publishActionMessage: SIMULATED', \OCP\Util::DEBUG);
                } else {

                    try {
                        $rabbitMQconnection = $this->openRabbitMQConnection();
                    } catch (Exception $e) {
                        Util::writeLog('ida', 'publishActionMessage: ERROR: Unable to open connection to RabbitMQ: ' . $e->getMessage(), \OCP\Util::ERROR);
                        throw $e;
                    }

                    // Use 'batch-actions' exchange for batch actions, otherwise 'actions'
                    if ($batch === true) {
                        $exchange = 'batch-actions';
                    } else {
                        $exchange = 'actions';
                    }

                    $channel = $rabbitMQconnection->channel();
                    $message = new AMQPMessage(json_encode($actionEntity));
                    $channel->basic_publish($message, $exchange, $actionEntity->getAction());
                    $channel->close();
                    $rabbitMQconnection->close();

                    Util::writeLog('ida', 'publishActionMessage: message=' . $message->getBody(), \OCP\Util::DEBUG);
                }
            }
        } catch (Exception $e) {
            Util::writeLog('ida', 'publishActionMessage: ERROR: Unable to publish message to RabbitMQ: ' . $e->getMessage(), \OCP\Util::ERROR);
            if ($rabbitMQconnection) {
                try {
                    $rabbitMQconnection->close();
                } catch (Exception $e) {
                }
            }
            throw $e;
        }
    }

    /**
     * Check if the specified pathname intersects the scope of any action for a project which is still being initiated,
     * such that the storage has not been fully updated. Return 200 OK if no intersection, else return 409 Conflict
     * if there is an intersection.
     *
     * @param string $project  project to check
     * @param string $pathname pathname corresponding to the scope to check
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function scopeOK($project, $pathname)
    {
        try {

            Util::writeLog(
                'ida',
                'scopeOK:'
                    . ' project=' . $project
                    . ' pathname=' . $pathname
                    . ' user=' . $this->userId,
                \OCP\Util::DEBUG
            );

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // If service is locked, always report conflict

            if (Access::projectIsLocked('all')) {
                return API::conflictErrorResponse('Service temporarily unavailable. Please try again later.');
            }

            // If project is suspended, always report conflict

            if ($this->actionMapper->isSuspended($project)) {
                return API::conflictErrorResponse('Project suspended. Action not permitted.');
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::forbiddenErrorResponse($e->getMessage());
            }

            // Check if scope intersects incomplete action of project

            if ($this->scopeIntersectsInitiatingAction($pathname, $project)) {
                return API::conflictErrorResponse('The specified scope conflicts with an ongoing action in the specified project.');
            }

            // We only log success responses for scope checks if debug logging is enabled, otherwise, no logging is done. This is to
            // prevent log files from being filled needlessly with success response messages, since scope checks are done frequently.
            return API::successResponse('The specified scope does not conflict with any ongoing action in the specified project.', true);

        } catch (Exception $e) {
            return API::serverErrorResponse('scopeOK: ' . $e->getMessage());
        }
    }

    /**
     * Return true if the input scope intersects the scope of any action of the specified
     * project which is still being initiated such that the storage has not been fully
     * updated; else, return false.
     *
     * We are stricter about scope intersections for operations in the staging area than we are
     * for freeze/unfreeze/delete actions because we have no explicit set of file pathnames to
     * compare and cannot know the extent of possible collision from such an operation.
     *
     * @param $inputScope
     * @param $project
     *
     * @return boolean
     * @throws Exception
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function scopeIntersectsInitiatingAction($inputScope, $project)
    {
        if ($inputScope === null) {
            throw new Exception('Null input scope.');
        }

        if ($project === null) {
            throw new Exception('Null project.');
        }

        $initiatingActions = $this->actionMapper->findActions('initiating', $project);

        return ($this->scopeIntersectsAction($inputScope, $initiatingActions));
    }

    /**
     * Return true if the input scope intersects the scope of any of the provided actions; else, return false.
     *
     * @param string   $inputScope     the scope to test against all actions
     * @param Action[] $actionEntities the actions to be tested
     * @param string   $action         the pid of a just-initiated action, to be ignored (optional)
     *
     * @throws Exception
     * @return boolean
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function scopeIntersectsAction($inputScope, $actionEntities, $action = null)
    {
        if ($inputScope === null) {
            throw new Exception('Null input scope.');
        }

        if ($actionEntities === null) {
            throw new Exception('Null action array.');
        }

        $inputScopeLength = strlen($inputScope);

        foreach ($actionEntities as $actionEntity) {

            if ($actionEntity->getPid() != $action) {

                $actionScope = $actionEntity->getPathname();

                if ($actionScope === null) {
                    throw new Exception('Null action scope.');
                }

                Util::writeLog(
                    'ida',
                    'scopeIntersectsAction:'
                        . ' inputScope=' . $inputScope
                        . ' actionScope=' . $actionScope,
                    \OCP\Util::DEBUG
                );

                // If either scope is absolute, they intersect.

                if ($actionScope === '/' || $inputScope === '/') {

                    Util::writeLog(
                        'ida',
                        'scopeIntersectsAction: ABSOLUTE SCOPE INTERSECTION:'
                            . ' project: ' . $actionEntity->getProject()
                            . ' action: ' . $actionEntity->getPid()
                            . ' inputScope: ' . $inputScope
                            . ' actionScope: ' . $actionScope,
                        \OCP\Util::INFO
                    );

                    return true;
                }

                // If the scopes are the same, they intersect.

                if ($actionScope === $inputScope) {

                    Util::writeLog(
                        'ida',
                        'scopeIntersectsAction: IDENTICAL SCOPE INTERSECTION:'
                            . ' project: ' . $actionEntity->getProject()
                            . ' action: ' . $actionEntity->getPid()
                            . ' inputScope: ' . $inputScope
                            . ' actionScope: ' . $actionScope,
                        \OCP\Util::INFO
                    );

                    return true;
                }

                // Check for pathname intersection. We do not bother checking if either scope
                // is a file but simply proceed as if the shorter pathname is a folder by
                // appending '/'. If the shorter scope corresponds to a file, then there is no
                // intersection. If the two scopes are of equal length, no comparison will be made
                // and there is no intersection.

                $actionScopeLength = strlen($actionScope);

                // If the action scope length is shorter than the input scope length, and the
                // action scope is a folder path prefix of the input scope, they intersect.

                if ($actionScopeLength < $inputScopeLength && substr($inputScope, 0, ($actionScopeLength + 1)) === ($actionScope . '/')) {

                    Util::writeLog(
                        'ida',
                        'scopeIntersectsAction: ACTION SCOPE PREFIX INTERSECTION:'
                            . ' project: ' . $actionEntity->getProject()
                            . ' action: ' . $actionEntity->getPid()
                            . ' inputScope: ' . $inputScope
                            . ' actionScope: ' . $actionScope,
                        \OCP\Util::INFO
                    );

                    return true;
                }

                // If the input scope length is shorter than the action scope length, and the
                // input scope is a folder path prefix of the action scope, they intersect.

                if ($inputScopeLength < $actionScopeLength && substr($actionScope, 0, ($inputScopeLength + 1)) === ($inputScope . '/')) {

                    Util::writeLog(
                        'ida',
                        'scopeIntersectsAction: INPUT SCOPE PREFIX INTERSECTION:'
                            . ' project: ' . $actionEntity->getProject()
                            . ' action: ' . $actionEntity->getPid()
                            . ' inputScope: ' . $inputScope
                            . ' actionScope: ' . $actionScope,
                        \OCP\Util::INFO
                    );

                    return true;
                }
            }
        }

        // No intersection.

        Util::writeLog('ida', 'scopeIntersectsAction: no intersection', \OCP\Util::DEBUG);

        return false;

        // Given actions with the following scopes:
        //
        //     /a/b/c/foo.data
        //     /x/y
        //
        // the following input scopes are considered to intersect:
        //
        //     /                  '/' is always an intersection
        //     /a                 '/a/' is a prefix of '/a/b/c/foo.data'
        //     /x/y               '/x/y' is equal to '/x/y'
        //     /x/y/z/bar.data    '/x/y/' is a prefix of '/x/y/z/bar.data'
        //
        // whereas the following input scopes are not considered to intersect:
        //
        //     /k
        //     /e/f/bas.data
        //     /a/b/c/boo.data
        //     /a/b/c/foo.data~
        //     /a/b/n
        //     /x/p
    }

}
