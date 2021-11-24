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
use OCA\IDA\Util\Access;
use OCA\IDA\Util\API;
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Generate;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Db\Entity;
use OCP\AppFramework\Http\DataResponse;
use OCP\IConfig;
use OCP\IRequest;
use OCP\Util;
use OC\Files\FileInfo;
use OC\Files\Filesystem;
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
        if ($message == null) {
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
        if ($message == null) {
            $this->message = 'A node already exists with the target pathname.';
        } else {
            $this->message = $message;
        }
    }
}

/**
 * Frozen State Controller
 */
class FreezingController extends Controller
{
    protected $actionMapper;
    protected $fileMapper;
    protected $userId;
    protected $fsView;
    protected $config;

    /**
     * Creates the AppFramwork Controller
     *
     * @param string       $appName      name of the app
     * @param IRequest     $request      request object
     * @param ActionMapper $actionMapper action mapper
     * @param FileMapper   $fileMapper   file mapper
     * @param string       $userId       current user
     * @param IConfig      $config       global configuration
     * 
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function __construct(
        $appName,
        IRequest $request,
        ActionMapper $actionMapper,
        FileMapper $fileMapper,
        $userId,
        IConfig $config
    ) {
        parent::__construct($appName, $request);
        $this->actionMapper = $actionMapper;
        $this->fileMapper = $fileMapper;
        $this->userId = $userId;
        $this->fsView = null;
        try {
            Filesystem::init($userId, '/' . $userId . '/files');
            $this->fsView = Filesystem::getView();
        } catch (\Exception $e) {
        }
        $this->config = $config->getSystemValue('ida');
    }

    /**
     * Return an inventory of all project files stored in the IDA service, both in staging
     * and frozen areas, with all technical metadata about each file.
     *
     * @param string $project  the project to which the nodes belongs
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFileInventory($project)
    {
        try {

            Util::writeLog('ida', 'getFileInventory:' . ' project=' . $project, \OCP\Util::INFO);

            $totalStagedFiles = 0;
            $totalFrozenFiles = 0;

            $stagedFiles = array();
            $frozenFiles = array();

            # Aggregate files from staging area

            $nextcloudNodes = $this->getNextcloudNodes('freeze', $project, "/", 0);

            foreach ($nextcloudNodes as $nodeInfo) {

                if ($nodeInfo->getType() === FileInfo::TYPE_FILE) {

                    $pathname = $this->stripRootProjectFolder($project, $nodeInfo->getPath());

                    $fileInfo = array(
                        'size' => $nodeInfo->getSize(),
                        'modified' => Generate::newTimestamp($nodeInfo->getMTime())
                    );

                    $stagedFiles[$pathname] = $fileInfo;
                    $totalStagedFiles++;
                }
            }

            # Aggregate files from frozen area

            $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, "/", 0);

            foreach ($nextcloudNodes as $nodeInfo) {

                if ($nodeInfo->getType() === FileInfo::TYPE_FILE) {

                    $pathname = $this->stripRootProjectFolder($project, $nodeInfo->getPath());

                    $fileInfo = array(
                        'size' => $nodeInfo->getSize(),
                        'modified' => Generate::newTimestamp($nodeInfo->getMTime()),
                    );

                    $frozenFile = $this->fileMapper->findByNextcloudNodeId($nodeInfo->getId(), $project);

                    if ($frozenFile != null) {

                        if ($frozenFile->getPid() != null) {
                            $fileInfo['pid'] = $frozenFile->getPid();
                        }

                        $checksum = $frozenFile->getChecksum();

                        if ($checksum != null) {
                            // Ensure the checksum is returned as an sha256: checksum URI
                            if ($checksum[0] === 's' && substr($checksum, 0, 7) === "sha256:") {
                                $fileInfo['checksum'] = $checksum;
                            } else {
                                $fileInfo["checksum"] = 'sha256:' . $checksum;
                            }
                        }

                        if ($frozenFile->getFrozen() != null) {
                            $fileInfo['frozen'] = $frozenFile->getFrozen();
                        }
                    }

                    $frozenFiles[$pathname] = $fileInfo;
                    $totalFrozenFiles++;
                }
            }

            $totalFiles = $totalStagedFiles + $totalFrozenFiles;

            Util::writeLog(
                'ida',
                'getInventory:'
                    . ' totalFiles=' . $totalFiles
                    . ' totalStagedFiles=' . $totalStagedFiles
                    . ' totalFrozenFiles=' . $totalFrozenFiles,
                \OCP\Util::INFO
            );

            return new DataResponse(array(
                'project' => $project,
                'created' => Generate::newTimestamp(),
                'totalFiles' => $totalFiles,
                'totalStagedFiles' => $totalStagedFiles,
                'totalFrozenFiles' => $totalFrozenFiles,
                'staging' => $stagedFiles,
                'frozen' => $frozenFiles
            ));
        } catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
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

            Util::writeLog(
                'ida',
                'projectIsLocked:'
                    . ' project=' . $project
                    . ' user=' . $this->userId,
                \OCP\Util::DEBUG
            );

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
                    return API::unauthorizedErrorResponse($e->getMessage());
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
            return API::serverErrorResponse($e->getMessage());
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

            if ($this->userId !== 'admin' && $this->userId !== (Constants::PROJECT_USER_PREFIX . $project)) {
                return API::unauthorizedErrorResponse();
            }

            // Admin is limited only to setting service lock

            if ($this->userId === 'admin' && $project !== 'all') {
                return API::unauthorizedErrorResponse();
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            if ($this->userId !== 'admin') {
                try {
                    Access::verifyIsAllowedProject($project);
                } catch (Exception $e) {
                    return API::unauthorizedErrorResponse($e->getMessage());
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
            return API::serverErrorResponse($e->getMessage());
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

            if ($this->userId !== 'admin' && $this->userId !== (Constants::PROJECT_USER_PREFIX . $project)) {
                return API::unauthorizedErrorResponse();
            }

            // Admin is limited only to clearing service lock

            if ($this->userId === 'admin' && $project !== 'all') {
                return API::unauthorizedErrorResponse();
            }

            // Verify that current user has rights to the specified project, rejecting request if not...

            if ($this->userId !== 'admin') {
                try {
                    Access::verifyIsAllowedProject($project);
                } catch (Exception $e) {
                    return API::unauthorizedErrorResponse($e->getMessage());
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
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Freeze staged files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
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
                return API::unauthorizedErrorResponse($e->getMessage());
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
                return API::conflictErrorResponse('The requested change conflicts with an ongoing action in the specified project.');
            }

            // Store freeze action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'freeze', $project, $this->userId, $pathname);

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

                if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) == 0) &&
                    ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                    ($token == $this->config['BATCH_ACTION_TOKEN'])
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

            $this->publishActionMessage($actionEntity);

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
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Unfreeze frozen files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
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
                return API::unauthorizedErrorResponse($e->getMessage());
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

            // Store unfreeze action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'unfreeze', $project, $this->userId, $pathname);

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

                if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) == 0) &&
                    ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                    ($token == $this->config['BATCH_ACTION_TOKEN'])
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

            $this->publishActionMessage($actionEntity);

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
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Delete frozen files within the scope of a particular node
     *
     * If the user is the PSO user, and a specified token parameter matches the batch action token
     * defined in the service configuration, no file limit will be imposed.
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
                return API::unauthorizedErrorResponse($e->getMessage());
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

            // Store delete action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked.

            $actionEntity = $this->registerAction($nextcloudNodeId, 'delete', $project, $this->userId, $pathname);

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

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) == 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token == $this->config['BATCH_ACTION_TOKEN'])
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

                $this->publishActionMessage($actionEntity);
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
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse($e->getMessage());
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

            if ($failedActionEntity == null) {
                return API::notFoundErrorResponse('The specified action does not exist.');
            }

            $project = $failedActionEntity->getProject();

            // Verify that current user has rights to the action project, rejecting request if not...

            try {
                Access::verifyIsAllowedProject($project);
            } catch (Exception $e) {
                return API::unauthorizedErrorResponse($e->getMessage());
            }

            // Verify that the action actually is failed action

            if ($failedActionEntity->getFailed() == null) {
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

            // Store retry action details (the action will be deleted if a conflict arises).
            // Creating the action immediately ensures that any attempted operations in the staging area with an
            // intersecting scope will be blocked. Create new retry action with failed action details.

            $retryActionEntity = $this->registerAction(
                $failedActionEntity->getNode(),
                $failedActionEntity->getAction(),
                $failedActionEntity->getProject(),
                $failedActionEntity->getUser(),
                $failedActionEntity->getPathname()
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

            if ($retryActionEntity->getPids() == null && $retryActionEntity->getAction() == 'freeze') {

                // Collect all nodes within scope of action, signalling error if maximum file count is exceeded

                $action   = $retryActionEntity->getAction();
                $pathname = $retryActionEntity->getPathname();

                try {

                    // If PSO user and batch action token valid, impose no file limit, else use default limit

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) == 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token == $this->config['BATCH_ACTION_TOKEN'])
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

                $nextcloudNodes = $this->fileMapper->findFiles($failedActionEntity);

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

            if ($retryActionEntity->getStorage() == null) {

                // Determine how storage needs to be modified

                if ($retryActionEntity->getAction() == 'delete') {

                    $this->deleteNextcloudNode($retryActionEntity->getProject(), $retryActionEntity->getPathname());
                } else { // action == 'freeze' or 'unfreeze'

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

            $this->publishActionMessage($retryActionEntity);

            // Unlock project and return new action details

            Access::unlockProject($project);

            return new DataResponse($failedActionEntity);
        } catch (Exception $e) {
            try {
                if ($retryActionEntity != null) {
                    $retryActionEntity->setFailed(Generate::newTimestamp());
                    $retryActionEntity->setError($e->getMessage());
                    $this->actionMapper->update($retryActionEntity);
                }
            } catch (Exception $e) {
            }

            // Cleanup and report error

            Access::unlockProject($project);

            return API::serverErrorResponse($e->getMessage());
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
                return API::unauthorizedErrorResponse($e->getMessage());
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

            return API::serverErrorResponse($e->getMessage());
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
     *
     * @return Entity
     * 
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function registerAction($nextcloudNodeId, $action, $project, $user, $pathname)
    {

        Util::writeLog(
            'ida',
            'registerAction:'
                . ' nextcloudNodeId=' . $nextcloudNodeId
                . ' action=' . $action
                . ' project=' . $project
                . ' user=' . $user
                . ' pathname=' . $pathname,
            \OCP\Util::INFO
        );

        // Verify Nextcloud node ID per specified pathname

        try {
            $nextcloudNodeId = $this->resolveNextcloudNodeId($nextcloudNodeId, $action, $project, $pathname);
        } catch (Exception $e) {
            return API::badRequestErrorResponse($e->getMessage());
        }

        // If the user is the PSO user, record the user as 'service'

        if ($user == Constants::PROJECT_USER_PREFIX . $project) {
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
                return API::unauthorizedErrorResponse($e->getMessage());
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

                    if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) == 0) &&
                        ($token != null) && ($this->config['BATCH_ACTION_TOKEN'] != null) &&
                        ($token == $this->config['BATCH_ACTION_TOKEN'])
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
            return API::serverErrorResponse($e->getMessage());
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

        $queryURL = $this->config['METAX_API_ROOT_URL'] . '/files/datasets';
        $username = $this->config['METAX_API_USER'];
        $password = $this->config['METAX_API_PASS'];
        $postbody = json_encode($filePIDs);

        Util::writeLog('ida', 'checkDatasets: queryURL=' . $queryURL
                       . ' username=' . $username
                       . ' password=' . $password
                       . ' postbody=' . $postbody
                       , \OCP\Util::DEBUG);

        $ch = curl_init($queryURL);

        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postbody);
        curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
        curl_setopt($ch, CURLOPT_HEADER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER,
            array(
                'Accept: application/json',
                'Content-Type: application/json',
                'Content-Length: ' . strlen($postbody)
            )
        );
        curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
        curl_setopt($ch, CURLOPT_FAILONERROR, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);

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

        Util::writeLog('ida', 'checkDatasets: datasets_response=' . $response, \OCP\Util::DEBUG);

        if ($httpcode == 200) {

            $intersecting_dataset_ids = json_decode($response, true);

            if (! is_array($intersecting_dataset_ids)) {
                list($ignore, $keep) = explode("200 OK", $response, 2);
                list($ignore, $body) = explode("\r\n\r\n", $keep, 2);
                Util::writeLog('ida', 'checkDatasets: body=' . $body, \OCP\Util::DEBUG);
                $intersecting_dataset_ids = json_decode($body, true);
            }

            Util::writeLog('ida', 'checkDatasets: ids=' . json_encode($intersecting_dataset_ids), \OCP\Util::DEBUG);

            foreach ($intersecting_dataset_ids as $intersecting_dataset_id) {

                // Query Metax for dataset details, first try as PID, then as preferred identifier

                $queryURL = $this->config['METAX_API_ROOT_URL'] . '/datasets/' . $intersecting_dataset_id;

                $ch = curl_init($queryURL);

                curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "GET");
                curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                curl_setopt($ch, CURLOPT_FAILONERROR, false);
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);
        
                $response = curl_exec($ch);
        
                Util::writeLog('ida', 'checkDatasets: dataset_response=' . $response, \OCP\Util::DEBUG);

                if ($response === false) {
                    Util::writeLog('ida', 'checkDatasets:'
                        . ' curl_errno=' . curl_errno($ch)
                        . ' response=' . $response, \OCP\Util::ERROR);
                    curl_close($ch);
                    throw new Exception('Failed to retrieve dataset by PID');
                }

                $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

                curl_close($ch);

                if ($httpcode == 200) {

                    Util::writeLog('ida', 'checkDatasets: pid=' . $intersecting_dataset_id , \OCP\Util::DEBUG);
                    $metax_datasets[] = json_decode($response, true);

                }
                else {

                    $queryURL = $this->config['METAX_API_ROOT_URL'] . '/datasets?preferred_identifier=' . urlencode($intersecting_dataset_id);
    
                    $ch = curl_init($queryURL);
    
                    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "GET");
                    curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
                    curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
                    curl_setopt($ch, CURLOPT_FAILONERROR, false);
                    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
                    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 60);
            
                    $response = curl_exec($ch);
            
                    Util::writeLog('ida', 'checkDatasets: dataset_response=' . $response, \OCP\Util::DEBUG);

                    if ($response === false) {
                        Util::writeLog('ida', 'checkDatasets:'
                            . ' curl_errno=' . curl_errno($ch)
                            . ' response=' . $response, \OCP\Util::ERROR);
                        curl_close($ch);
                        throw new Exception('Failed to retrieve dataset by preferred identifier');
                    }
    
                    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

                    curl_close($ch);

                    if ($httpcode == 200) {

                        Util::writeLog('ida', 'checkDatasets: preferred_identifier=' . $intersecting_dataset_id , \OCP\Util::DEBUG);
                        $metax_datasets[] = json_decode($response, true);

                    }
                    else {
                        Util::writeLog('ida', 'checkDatasets: ' . $response, \OCP\Util::ERROR);
                        throw new Exception('Failed to retrieve dataset by either PID or preferred identifier');
                    }
                }
            }
        }

        foreach ($metax_datasets as $metax_dataset) {

            $dataset = array();

            $dataset['pid'] = $metax_dataset['identifier'];

            $dataset['title'] = $metax_dataset['research_dataset']['title']['en']
                ?? $metax_dataset['research_dataset']['title']['fi']
                ?? $metax_dataset['research_dataset']['title']['sv']
                ?? $metax_dataset['research_dataset']['preferred_identifier']
                ?? $metax_dataset['identifier'];

            $dataset['pas'] = false;

            // Any dataset for which the PAS ingestion process is ongoing, indicated by having a
            // preservation state greater than zero but less than 120
            if (array_key_exists('preservation_state', $metax_dataset)
                    &&
                    $metax_dataset['preservation_state'] > 0
                    &&
                    $metax_dataset['preservation_state'] < 120) {
                $dataset['pas'] = true;
            }
            
            $datasets[] = $dataset;
        }

        Util::writeLog('ida', 'checkDatasets: datasetCount=' . count($datasets), \OCP\Util::DEBUG);

        return ($datasets);
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
        if ($action == 'freeze') {
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

            if ($nextcloudNodeId == null || $nextcloudNodeId == 0 || $nextcloudNodeId == '' || $nextcloudNodeId == '0') {

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
                        $newFileEntity->setChecksum(null);
                    }
                    if ($newFileEntity->getModified() == null) {
                        $newFileEntity->setModified(Generate::newTimestamp($fileInfo->getMTime()));
                    }
                    if ($newFileEntity->getFrozen() == null) {
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
                        . ' pathname=' . $targetPathname, \OCP\Util::INFO);

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
                . ' nextcloudNodes=' . count($nextcloudNodes),
            \OCP\Util::DEBUG
        );

        // Retrieve all incomplete actions for the project

        $actionEntities = $this->actionMapper->findActions('incomplete', $project);

        // The project normally will have at least one just-initiated action which is incomplete, the pid of
        // which should have been provided via the action parameter; but in case no incomplete actions exist,
        // simply return false.

        if (count($actionEntities) == 0) {
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
                $actionPids[$pid] = true;
            }
        }

        // For each file node associated with new action, check if there exists a frozen file record with
        // the same pathname which is associated with one of the incomplete actions

        foreach ($nextcloudNodes as $fileInfo) {
            if ($fileInfo->getType() === FileInfo::TYPE_FILE) {
                $pathname = $this->stripRootProjectFolder($project, $fileInfo->getPath());
                $fileEntity = $this->fileMapper->findByNextcloudNodeId($fileInfo->getId(), null, true);
                if ($fileEntity) {
                    $actionPid = $fileEntity->getAction();
                    if ($actionPids[$actionPid]) {
                        Util::writeLog(
                            'ida',
                            'checkIntersectionWithIncompleteActions: INTERSECTION EXISTS'
                                . ' project=' . $project
                                . ' action=' . $actionPid
                                . ' pathname=' . $pathname,
                            \OCP\Util::INFO
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
    protected function getNextcloudNodes($action, $project, $pathname, $limit = Constants::MAX_FILE_COUNT)
    {

        Util::writeLog(
            'ida',
            'getNextcloudNodes:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname
                . ' limit=' . $limit,
            \OCP\Util::INFO
        );

        $result = array('filecount' => 0, 'nodes' => array());

        $result = $this->getNextcloudNodesR($action, $project, $pathname, $limit, $result);

        Util::writeLog(
            'ida',
            'getNextcloudNodes:'
                . ' filecount=' . $result['filecount']
                . ' nodecount=' . count($result['nodes']),
            \OCP\Util::INFO
        );

        return ($result['nodes']);
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
                            \OCP\Util::INFO
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
                // Logging the file pathname as INFO here allows one to see all files included in the scope of
                // an action which has had its initiation logged previously
                Util::writeLog(
                    'ida',
                    'getNextcloudNodesR:'
                        . ' filecount=' . $result['filecount']
                        . ' file=' . $fileInfo->getPath(),
                    \OCP\Util::INFO
                );
            }
        }

        // If limit to be enforced and maximum file count exceeded, throw exception

        if ($limit > 0 && $result['filecount'] > $limit) {
            throw new MaximumAllowedFilesExceeded();
        }

        return $result;
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

        Util::writeLog(
            'ida',
            'buildFullPathname:'
                . ' action=' . $action
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        if ($pathname === '/') {
            $pathname = '';
        }

        if ($action === 'freeze') {
            $fullPathname = '/' . $project . Constants::STAGING_FOLDER_SUFFIX . $pathname;
        } else {
            $fullPathname = '/' . $project . $pathname;
        }

        Util::writeLog('ida', 'buildFullPathname: fullPathname=' . $fullPathname, \OCP\Util::DEBUG);

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

        Util::writeLog('ida', 'getParentPathname: pathname=' . $pathname, \OCP\Util::DEBUG);

        $pattern = '/\/[^\/][^\/]*$/';

        if ($pathname && trim($pathname) != '') {
            $parentPathname = preg_replace($pattern, '', $pathname);
        } else {
            $parentPathname = null;
        }

        Util::writeLog('ida', 'getParentPathname: parentPathname=' . $parentPathname, \OCP\Util::DEBUG);

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

        Util::writeLog(
            'ida',
            'stripRootProjectFolder:'
                . ' project=' . $project
                . ' pathname=' . $pathname,
            \OCP\Util::DEBUG
        );

        $pattern = '/^.*\/files\/' . $project . '[^\/]*\//';

        if ($pathname && trim($pathname) != '') {
            $relativePathname = preg_replace($pattern, '/', $pathname);
        } else {
            $relativePathname = null;
        }

        Util::writeLog('ida', 'stripRootProjectFolder: relativePathname=' . $relativePathname, \OCP\Util::DEBUG);

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
            \OCP\Util::INFO
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
            \OCP\Util::INFO
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
            \OCP\Util::INFO
        );

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
            $baseURI = $this->config['URL_BASE_FILE'];
            $sourceURI = $baseURI . API::urlEncodePathname($sourcePathname);
            $targetURI = $baseURI . API::urlEncodePathname($targetPathname);

            Util::writeLog('ida', 'moveNextcloudNode:' . ' sourceURI=' . $sourceURI . ' targetURI=' . $targetURI, \OCP\Util::DEBUG);

            // If target node does not exist, no matter whether folder or file, move from source to target and we're done

            if ($targetExists == false) {

                // Ensure all ancestor folders in target path exist

                $this->createNextcloudPathFolders($project, $targetPathname);

                // Move the folder from source to target pathname

                $ch = curl_init($sourceURI);

                curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'MOVE');
                curl_setopt($ch, CURLOPT_HTTPHEADER, array('Destination: ' . $targetURI));
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
            \OCP\Util::INFO
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
            $baseURI = $this->config['URL_BASE_FILE'];
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

        $folderPath = substr($this->getParentPathname($pathname), 1);

        $folders = explode('/', $folderPath);

        Util::writeLog('ida', 'createNextcloudPathFolders: folderPath=' . $folderPath . ' count=' . count($folders), \OCP\Util::DEBUG);

        if (count($folders) > 0) {

            $username = Constants::PROJECT_USER_PREFIX . $project;
            $password = $this->config['PROJECT_USER_PASS'];
            $baseURI = $this->config['URL_BASE_FILE'];
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
    public function clearActions($status = 'failed', $projects)
    {

        // TODO Determine whether and how to lock all specified projects during operation

        if ($status !== 'failed' && $status !== 'pending') {
            return API::badRequestErrorResponse('Invalid status.');
        }

        if ($this->userId === 'admin') {
            $entities = $this->actionMapper->clearActions($status, $projects);

            return new DataResponse($entities);
        } else {
            return API::unauthorizedErrorResponse();
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
                return API::unauthorizedErrorResponse();
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
            return API::serverErrorResponse($e->getMessage());
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
                return API::unauthorizedErrorResponse();
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
            return API::serverErrorResponse($e->getMessage());
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
            return API::unauthorizedErrorResponse();
        }

        // All projects allowed for admin only

        if ($project == 'all') {

            if ($this->userId == 'admin') {

                $this->actionMapper->deleteAllActions('all');
                $this->fileMapper->deleteAllFiles('all');

                return new DataResponse('Database flushed for all projects.');
            }

            return API::unauthorizedErrorResponse();
        } else {

            // PSO user must belong to project

            if ((strpos($this->userId, Constants::PROJECT_USER_PREFIX) === 0) &&
                ($project !== substr($this->userId, strlen(Constants::PROJECT_USER_PREFIX)))
            ) {
                return API::unauthorizedErrorResponse();
            }

            $this->actionMapper->deleteAllActions($project);
            $this->fileMapper->deleteAllFiles($project);

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

        if ($action == null) {
            return API::badRequestErrorResponse('No action specified.');
        }

        if ($checksums == null) {
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
                return API::unauthorizedErrorResponse();
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

            if ($pathnameCount == 0) {
                Access::unlockProject($project);

                return API::badRequestErrorResponse('No checksums specified.');
            }

            Util::writeLog('ida', 'bootstrapProject:' . ' pathnameCount=' . $pathnameCount, \OCP\Util::DEBUG);

            $fileEntities = [];

            $actionEntity = $this->registerAction(0, $action, $project, 'service', '/');
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

            return API::serverErrorResponse($e->getMessage());
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
                return API::unauthorizedErrorResponse();
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

            $repairActionEntity = $this->registerAction(0, 'repair', $project, 'service', '/');

            // Retrieve all active frozen file records

            $frozenFileEntities = $this->fileMapper->findFrozenFiles($project);

            // Mark any existing frozen files as cleared. Files which are physically present in the frozen area will
            // have those same records cloned below.

            if (count($frozenFileEntities) > 0) {
                foreach ($frozenFileEntities as $fileEntity) {
                    $fileEntity->setCleared($timestamp);
                    $this->fileMapper->update($fileEntity);
                }
            }

            // Retrieve and reinstate all files in the frozen area.
            // Disable file count limit by specifying limit as zero.

            $nextcloudNodes = $this->getNextcloudNodes('unfreeze', $project, '/', 0);

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

            $this->publishActionMessage($repairActionEntity);

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

            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Test whether RabbitMQ connection can be opened for publication.
     * 
     * TODO: Once the health check endpoint service monitors RabbitMQ, we should be able to do away with
     * all of these connection verifications prior to proceeding with each action...
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
     * 
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    protected function publishActionMessage($actionEntity)
    {

        $rabbitMQconnection = null;

        try {

            if ($actionEntity) {

                Util::writeLog(
                    'ida',
                    'publishActionMessage:'
                        . ' pid=' . $actionEntity->getPid()
                        . ' action=' . $actionEntity->getAction()
                        . ' project=' . $actionEntity->getProject()
                        . ' user=' . $actionEntity->getUser()
                        . ' pathname=' . $actionEntity->getPathname()
                        . ' initiated=' . $actionEntity->getInitiated(),
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

                    $channel = $rabbitMQconnection->channel();
                    $message = new AMQPMessage(json_encode($actionEntity));
                    $channel->basic_publish($message, 'actions', $actionEntity->getAction());
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
    public function checkScope($project, $pathname)
    {

        try {

            Util::writeLog(
                'ida',
                'checkScope:'
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
                return API::unauthorizedErrorResponse($e->getMessage());
            }

            // Check if scope intersects incomplete action of project

            if ($this->scopeIntersectsInitiatingAction($pathname, $project)) {
                return API::conflictErrorResponse('The specified scope conflicts with an ongoing action in the specified project.');
            }

            return API::successResponse('The specified scope does not conflict with any ongoing action in the specified project.');
        } catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
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
    public function scopeIntersectsInitiatingAction($inputScope, $project)
    {

        if ($inputScope == null) {
            throw new Exception('Null input scope.');
        }

        if ($project == null) {
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
    public function scopeIntersectsAction($inputScope, $actionEntities, $action = null)
    {

        if ($inputScope == null) {
            throw new Exception('Null input scope.');
        }

        if ($actionEntities === null) {
            throw new Exception('Null action array.');
        }

        $inputScopeLength = strlen($inputScope);

        foreach ($actionEntities as $actionEntity) {

            if ($actionEntity->getPid() != $action) {

                $actionScope = $actionEntity->getPathname();

                if ($actionScope == null) {
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
