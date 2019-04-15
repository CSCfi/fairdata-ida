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

use OCA\IDA\Model\File;
use OCA\IDA\Model\FileMapper;
use OCA\IDA\Util\API;
use OCA\IDA\Util\Access;
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Generate;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\IRequest;
use OCP\Util;
use OC\Files\Filesystem;
use OC\Files\FileInfo;
use Exception;

/**
 * File Controller
 */
class FileController extends Controller
{
    protected $fileMapper;
    protected $userId;
    protected $fsView;

    /**
     * Creates the AppFramwork Controller
     *
     * @param string     $appName    name of the app
     * @param IRequest   $request    request object
     * @param FileMapper $fileMapper file mapper
     * @param string     $userId     userid
     */
    public function __construct(
        $appName,
        IRequest $request,
        FileMapper $fileMapper,
        $userId
    ) {
        parent::__construct($appName, $request);
        $this->fileMapper = $fileMapper;
        $this->userId = strtolower($userId);
        Filesystem::init($userId, '/');
        $this->fsView = Filesystem::getView();
    }

    /**
     * Retrieve all files associated with an optional action, and/or restricted to one or more projects (if admin)
     *
     * Restricted to the project access scope of the user.
     *
     * @param string $pid      the PID of an action
     * @param string $projects a comma separated list of project names, with no whitespace
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFiles($pid = null, $projects = null) {

        Util::writeLog('ida', 'getFiles:' . ' pid=' . $pid . ' projects=' . $projects, \OCP\Util::DEBUG);

        try {

            try {
                API::validateStringParameter('pid', $pid);
                API::validateStringParameter('projects', $projects);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $queryProjects = null;

            // Special case to retrieve all file details for all actions for one or more projects, used for admin operations only

            if (($this->userId === 'admin') && ($pid === "all") && ($projects !== null)) {
                $pid = null;
            }

            // Initialize set of projects to any specified in request

            if ($projects !== null) {
                $queryProjects = Access::cleanProjectList($projects);
            }

            // If user is not admin, get user projects and verify user belongs to at least one project, limiting
            // query to the intersection of user projects and any specified projects

            if ($this->userId !== 'admin') {

                $userProjects = Access::getUserProjects();

                if ($userProjects === null) {
                    return API::unauthorizedErrorResponse('Session user does not belong to any projects.');
                }

                // If any projects are specified with the request, reduce the user project list to the
                // intersection of the input projects and allowed user projects

                if ($queryProjects !== null && $userProjects !== null) {
                    $queryProjects = implode(',', array_intersect(explode(',', $userProjects), explode(',', $queryProjects)));
                }

                // Else set the project list to the list of user projects

                else {
                    $queryProjects = $userProjects;
                }
            }

            Util::writeLog('ida', 'getFiles:' . ' queryProjects=' . $queryProjects, \OCP\Util::DEBUG);

            // If the user is not admin and the intersection with any explicitly speciied projects
            // and user projects is empty, return an empty array.

            if ($this->userId !== 'admin' && ($queryProjects == '')) {
                return new DataResponse(array());
            }

            $fileEntities = $this->fileMapper->findFiles($pid, $queryProjects);

            // If an expicit action PID was specified and no files found, then assume the action does not exist

            if ($pid !== null && count($fileEntities) == 0) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }

            return new DataResponse($fileEntities);
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Retrieve the latest frozen file record based on the provided file PID
     *
     * Restricted to the project access scope of the user.
     *
     * @param string $pid the PID of the file
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFile($pid, $includeInactive = false) {

        Util::writeLog('ida', 'getFile:' . ' pid=' . $pid, \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('pid', $pid);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $projects = null;

            // If user is not admin, verify access rights
            if ($this->userId != 'admin') {

                // Get user projects and verify user belongs to at least one project
                $userProjects = Access::getUserProjects();

                if ($userProjects == null) {
                    return API::unauthorizedErrorResponse('The current user does not belong to any projects.');
                } // Else set the project list to the list of user projects
                else {
                    $projects = $userProjects;
                }
            }

            $fileEntity = $this->fileMapper->findFile($pid, $projects, $includeInactive);

            if ($fileEntity == null) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            return new DataResponse($fileEntity);
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Retrieve the latest created frozen file record based on the provided Nextcloud node ID
     *
     * Restricted to the project access scope of the user.
     *
     * @param string $node the Nextcloud node ID of the file
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFileByNextcloudNodeId($node, $includeInactive = false) {

        Util::writeLog('ida', 'getFileByNextcloudNodeId:' . ' node=' . $node, \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('node', $node);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $projects = null;

            // If user is not admin, verify access rights
            if ($this->userId != 'admin') {

                // Get user projects and verify user belongs to at least one project
                $userProjects = Access::getUserProjects();

                if ($userProjects == null) {
                    return API::unauthorizedErrorResponse('The current user does not belong to any projects.');
                } // Else set the project list to the list of user projects
                else {
                    $projects = $userProjects;
                }
            }

            $fileEntity = $this->fileMapper->findByNextcloudNodeId($node, $projects, $includeInactive);

            if ($fileEntity == null) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            return new DataResponse($fileEntity);
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Retrieve the latest frozen file record based on its project pathname
     *
     * @param string $project  the project to which the file belongs
     * @param string $pathname the pathname of the file
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getFileByProjectPathname($project, $pathname, $includeInactive = false) {

        try {
            try {
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $projects = null;

            // If user is not admin, verify access rights
            if ($this->userId != 'admin') {

                // Get user projects and verify user belongs to at least one project
                $userProjects = Access::getUserProjects();

                if ($userProjects == null) {
                    return API::unauthorizedErrorResponse('The current user does not belong to any projects.');
                } // Else set the project list to the list of user projects
                else {
                    $projects = $userProjects;
                }
            }

            $fileEntity = $this->fileMapper->findByProjectPathname($project, $pathname, $projects, $includeInactive);

            if ($fileEntity == null) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            return new DataResponse($fileEntity);
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Create a new frozen file record
     *
     * Restricted to admin and PSO users for the specified project.
     *
     * @param string $action     the PID of the project with which the file is associated
     * @param string $project    the project to which the file belongs
     * @param string $pathname   the relative pathname of the file
     * @param int    $node       the Nextcloud node ID of the file
     * @param int    $size       the size of the file
     * @param string $checksum   the checksum of a file
     * @param string $metadata   timestamp indicating when metadata for file was successfully published or updated
     * @param string $replicated timestamp indicating when the file was successfully replicated
     * @param string $removed    timestamp indicating when the file was removed from the frozen space
     * @param string $cleared    timestamp indicating when the file was cleared (as part of a cleared action)
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function createFile($action, $project, $pathname, $node = null, $size = null, $checksum = null,
                               $metadata = null, $replicated = null, $removed = null, $cleared = null) {

        Util::writeLog('ida', 'createAction:'
            . ' action=' . $action
            . ' project=' . $project
            . ' pathname=' . $pathname
            . ' node=' . $node
            , \OCP\Util::INFO);

        try {
            try {
                API::verifyRequiredStringParameter('action', $action);
                API::verifyRequiredStringParameter('project', $project);
                API::verifyRequiredStringParameter('pathname', $pathname);
                API::validateIntegerParameter('node', $node);
                API::validateIntegerParameter('size', $size);
                API::validateStringParameter('checksum', $checksum);
                API::validateTimestamp($metadata);
                API::validateTimestamp($replicated);
                API::validateTimestamp($removed);
                API::validateTimestamp($cleared);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Restrict to admin and PSO user for the specified project
            if ($this->userId != 'admin' && $this->userId != Constants::PROJECT_USER_PREFIX . $project) {
                return API::unauthorizedErrorResponse();
            }

            if ($node === null) {
                // TODO Get Nextcloud node ID based on project and pathname...?
                $nextcloudNodeId = '0';
            }
            else {
                $nextcloudNodeId = $node;
            }

            $fileEntity = new File();
            $fileEntity->setAction($action);
            $fileEntity->setNode($nextcloudNodeId);
            $fileEntity->setPid(Generate::newPid('f' . $nextcloudNodeId));
            $fileEntity->setFrozen(Generate::newTimestamp());
            $fileEntity->setProject($project);
            $fileEntity->setPathname($pathname);

            // Set all allowed specified parameter values

            if ($size !== null) {
                $fileEntity->setSize(0 + $size);
            }
            if ($checksum !== null) {
                $fileEntity->setChecksum((trim($checksum) === '') ? null : $checksum);
            }
            if ($metadata !== null) {
                $fileEntity->setMetadata($metadata);
            }
            if ($replicated !== null) {
                $fileEntity->setReplication($replicated);
            }
            if ($removed !== null) {
                $fileEntity->setRemoved($removed);
            }
            if ($cleared !== null) {
                $fileEntity->setCleared($cleared);
            }

            return new DataResponse($this->fileMapper->insert($fileEntity));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Update the latest existing frozen file record with the specified PID
     *
     * Restricted to admin and PSO users for the project specified for the action.
     *
     * @param string $pid        the PID of the file
     * @param string $checksum   the checksum of a file
     * @param string $metadata   timestamp indicating when metadata for file was successfully published or updated
     * @param string $replicated timestamp indicating when the file was successfully replicated
     * @param string $removed    timestamp indicating when the file was removed from the frozen space
     * @param string $cleared    timestamp indicating when the file was cleared (as part of a cleared action)
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function updateFile($pid, $size = null, $modified = null, $frozen = null, $checksum = null,
                               $metadata = null, $replicated = null, $removed = null, $cleared = null) {

        try {
            try {
                API::verifyRequiredStringParameter('pid', $pid);
                API::validateIntegerParameter('size', $size, true);
                API::validateStringParameter('checksum', $checksum, true);
                API::validateTimestamp($modified, true);
                API::validateTimestamp($frozen, true);
                API::validateTimestamp($metadata, true);
                API::validateTimestamp($replicated, true);
                API::validateTimestamp($removed, true);
                API::validateTimestamp($cleared, true);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $fileEntity = $this->fileMapper->findFile($pid, null, true);

            if ($fileEntity == null) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            // Restrict to admin and PSO user for the specified project. In order to prevent unauthorized users
            // determining whether certain entities exist by randomly trying PIDs, we treat this as a not found
            // error rather than an unauthorized error.

            if ($this->userId != 'admin' && $this->userId != strtolower(Constants::PROJECT_USER_PREFIX . $fileEntity->getProject())) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            // Clear all specified parameter values defined explicitly as the string 'null'

            if ($size === 'null') {
                $fileEntity->setSize(null); $size = null;
            }
            if ($modified === 'null') {
                $fileEntity->setModified(null); $modified = null;
            }
            if ($frozen === 'null') {
                $fileEntity->setFrozen(null); $frozen = null;
            }
            if ($checksum === 'null') {
                $fileEntity->setChecksum(null); $checksum = null;
            }
            if ($metadata === 'null') {
                $fileEntity->setMetadata(null); $metadata = null;
            }
            if ($replicated === 'null') {
                $fileEntity->setReplicated(null); $replicated = null;
            }
            if ($removed === 'null') {
                $fileEntity->setRemoved(null); $removed = null;
            }
            if ($cleared === 'null') {
                $fileEntity->setCleared(null); $cleared = null;
            }

            // Set all allowed specified parameter values and update database record

            if ($size !== null) {
                $fileEntity->setSize(0 + $size);
            }
            if ($checksum !== null) {
                $fileEntity->setChecksum((trim($checksum) === '') ? null : $checksum);
            }
            if ($modified !== null) {
                $fileEntity->setModified($modified);
            }
            if ($frozen !== null) {
                $fileEntity->setFrozen($frozen);
            }
            if ($metadata !== null) {
                $fileEntity->setMetadata($metadata);
            }
            if ($replicated !== null) {
                $fileEntity->setReplicated($replicated);
            }
            if ($removed !== null) {
                $fileEntity->setRemoved($removed);
            }
            if ($cleared !== null) {
                $fileEntity->setCleared($cleared);
            }

            return new DataResponse($this->fileMapper->update($fileEntity));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

    /**
     * Delete all existing frozen file records with the specified PID
     *
     * Restricted to admin and PSO users for the project specified for the action.
     *
     * @param string $pid the PID of the file
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function deleteFile($pid) {

        try {
            try {
                API::verifyRequiredStringParameter('pid', $pid);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            $fileEntity = $this->fileMapper->findFile($pid, null, true);

            if ($fileEntity == null) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            // Restrict to admin and PSO user for the specified project. In order to prevent unauthorized users
            // determining whether certain entities exist by randomly trying PIDs, we treat this as a not found
            // error rather than an unauthorized error.

            if ($this->userId != 'admin' && $this->userId != strtolower(Constants::PROJECT_USER_PREFIX . $fileEntity->getProject())) {
                return API::notFoundErrorResponse('The specified file was not found.');
            }

            $this->fileMapper->deleteFile($pid);

            return API::successResponse('File deleted.');
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }

}
