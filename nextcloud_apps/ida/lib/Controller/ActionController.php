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

use OCA\IDA\Model\ActionMapper;
use OCA\IDA\Model\Action;
use OCA\IDA\Util\API;
use OCA\IDA\Util\Access;
use OCA\IDA\Util\Generate;
use OCA\IDA\Util\Constants;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\IRequest;
use OCP\Util;
use Exception;

/**
 * Action Controller
 */
class ActionController extends Controller
{
    protected $actionMapper;
    protected $userId;
    
    /**
     * Creates the AppFramwork Controller
     *
     * @param string       $appName      name of the app
     * @param IRequest     $request      request object
     * @param ActionMapper $actionMapper action mapper
     * @param string       $userId       userid
     */
    public function __construct(
        $appName,
        IRequest $request,
        ActionMapper $actionMapper,
        $userId
    ) {
        parent::__construct($appName, $request);
        $this->actionMapper = $actionMapper;
        $this->userId = strtolower($userId);
    }
    
    /**
     * Retrieve all actions, optionally filtered by status and projects to which the current user has access.
     *
     * Restricted to the project access scope of the user.
     *
     * @param string $status   one of 'pending', 'failed', or 'completed'
     * @param string $projects a comma separated list of project names, with no whitespace
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getActions($status = null, $projects = null) {
        
        Util::writeLog('ida', 'getActions:' . ' status=' . $status . ' projects=' . $projects, \OCP\Util::DEBUG);
        
        try {
            
            if ($projects !== null) {
                $queryProjects = Access::cleanProjectList($projects);
            }
            
            // If user is not admin, get user projects and verify user belongs to at least one project
            
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
            
            Util::writeLog('ida', 'getActions:' . ' queryProjects=' . $queryProjects, \OCP\Util::DEBUG);
            
            // If the user is not admin and the intersection with any explicitly speciied projects
            // and user projects is empty, return an empty array.
            
            if ($this->userId !== 'admin' && ($queryProjects == '')) {
                return new DataResponse(array());
            }
            
            return new DataResponse($this->actionMapper->findActions($status, $queryProjects));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
    /**
     * Retrieve an action based on its PID
     *
     * Restricted to the project access scope of the user.
     *
     * @param string $pid the PID of the action
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getAction($pid) {
        
        Util::writeLog('ida', 'getAction:' . ' pid=' . $pid, \OCP\Util::DEBUG);
        
        try {
            API::verifyRequiredStringParameter('pid', $pid);
        }
        catch (Exception $e) {
            return API::badRequestErrorResponse($e->getMessage());
        }
        
        try {
            
            $projects = null;
            
            // If user is not admin, get user projects and verify user belongs to at least one project
            
            if ($this->userId != 'admin') {
                
                $userProjects = Access::getUserProjects();
                
                if ($userProjects == null) {
                    return API::unauthorizedErrorResponse('Session user does not belong to any projects.');
                }
                
                // Set the allowed project list to the list of user projects
                
                $projects = $userProjects;
            }
            
            $actionEntity = $this->actionMapper->findAction($pid, $projects);
            
            if ($actionEntity == null) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }
            
            return new DataResponse($actionEntity);
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
    /**
     * Create a new action
     *
     * Restricted to admin and PSO users for the specified project.
     *
     * @param string $action   one of 'freeze', 'unfreeze', or 'delete'
     * @param string $project  the project to which the root node belongs
     * @param string $pathname the relative pathname of the root node of the action
     * @param int    $node     the Nextcloud node ID of the root node of the action (optional)
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function createAction($action, $project, $pathname, $node = null) {
        
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
            
            $actionEntity = new Action();
            $actionEntity->setPid(Generate::newPid('a' . $nextcloudNodeId));
            $actionEntity->setAction($action);
            $actionEntity->setUser($this->userId);
            $actionEntity->setProject($project);
            $actionEntity->setPathname($pathname);
            $actionEntity->setInitiated(Generate::newTimestamp());
            
            return new DataResponse($this->actionMapper->insert($actionEntity));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
    /**
     * Update an existing action
     *
     * Restricted to admin and PSO users for the project specified for the action.
     *
     * @param string $pid         the PID of the action
     * @param string $pathname    the relative pathname of the root node of the action
     * @param string $storage     timestamp indicating when physical storage for all files in scope was successfully updated
     * @param string $checksums   timestamp indicating when checksums for all files in scope were successfully generated
     * @param string $metadata    timestamp indicating when metadata for all nodes in scope was successfully published
     * @param string $replication timestamp indicating when replication of all nodes in scope was successfully completed
     * @param string $completed   timestamp indicating when all essential postprocessing operations were successfully completed
     * @param string $failed      timestamp indicating when the action failed
     * @param string $error       string providing the details of the failure
     * @param string $cleared     timestamp indicating when a failed action was deemed resolved or disregarded
     * @param string $retry       the PID of the action used to retry a failed action
     * @param string $retrying    the PID of the action retrying a failed action
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function updateAction($pid, $pathname = null, $pids = null, $storage = null, $checksums = null, $metadata = null, $replication = null, $completed = null,
                                 $failed = null, $error = null, $cleared = null, $retry = null, $retrying = null) {
        
        Util::writeLog('ida', 'updateAction:'
            . ' pid=' . $pid
            . ' pathname=' . $pathname
            . ' pids=' . $pids
            . ' storage=' . $storage
            . ' checksums=' . $checksums
            . ' metadata=' . $metadata
            . ' replication=' . $replication
            . ' completed=' . $completed
            . ' failed=' . $failed
            . ' error=' . $error
            . ' cleared=' . $cleared
            . ' retry=' . $retry
            . ' retrying=' . $retrying
            , \OCP\Util::INFO);
        
        try {
            try {
                API::verifyRequiredStringParameter('pid', $pid);
                API::validateStringParameter('pathname', $pathname, true);
                API::validateTimestamp($pids, true);
                API::validateTimestamp($storage, true);
                API::validateTimestamp($checksums, true);
                API::validateTimestamp($metadata, true);
                API::validateTimestamp($replication, true);
                API::validateTimestamp($completed, true);
                API::validateTimestamp($failed, true);
                API::validateTimestamp($cleared, true);
                API::validateStringParameter('error', $error, true);
                API::validateStringParameter('retry', $retry, true);
                API::validateStringParameter('retrying', $retrying, true);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }
            
            $projects = null;
            
            // If user is not admin, get user projects and verify user belongs to at least one project
            
            if ($this->userId != 'admin') {
                
                $userProjects = Access::getUserProjects();
                
                if ($userProjects == null) {
                    return API::unauthorizedErrorResponse('Session user does not belong to any projects.');
                }
                
                // Set the allowed project list to the list of user projects
                
                $projects = $userProjects;
            }
            
            $actionEntity = $this->actionMapper->findAction($pid, $projects);
            
            if ($actionEntity == null) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }
    
            // Restrict to admin and PSO user for the specified project. In order to prevent unauthorized users
            // determining whether certain entities exist by randomly trying PIDs, we treat this as a not found
            // error rather than an unauthorized error.
    
            $psoUser = strtolower(Constants::PROJECT_USER_PREFIX . $actionEntity->getProject());
    
            if ($this->userId != 'admin' && $this->userId != $psoUser) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }
    
            // Clear all specified parameter values defined explicitly as the string 'null' but only if admin or PSO user
    
            if ($this->userId === 'admin' || $this->userId === $psoUser) {
                if ($pathname === 'null') {
                    $actionEntity->setPathname(null); $pathname = null;
                }
                if ($pids === 'null') {
                    $actionEntity->setPids(null); $pids = null;
                }
                if ($storage === 'null') {
                    $actionEntity->setStorage(null); $storage = null;
                }
                if ($checksums === 'null') {
                    $actionEntity->setChecksums(null); $checksums = null;
                }
                if ($metadata === 'null') {
                    $actionEntity->setMetadata(null); $metadata = null;
                }
                if ($replication === 'null') {
                    $actionEntity->setReplication(null); $replication = null;
                }
                if ($completed === 'null') {
                    $actionEntity->setCompleted(null); $completed = null;
                }
                if ($failed === 'null') {
                    $actionEntity->setFailed(null); $failed = null;
                }
                if ($error === 'null') {
                    $actionEntity->setError(null); $error = null;
                }
                if ($cleared === 'null') {
                    $actionEntity->setCleared(null); $cleared = null;
                }
                if ($retry === 'null') {
                    $actionEntity->setRetry(null); $retry = null;
                }
                if ($retrying === 'null') {
                    $actionEntity->setRetrying(null); $retrying = null;
                }
            }
            
            // Set all allowed specified parameter values and update database record (some values may only be defined by the admin or pso user)
            
            if ($checksums != null) {
                $actionEntity->setChecksums($checksums);
            }
            if ($metadata != null) {
                $actionEntity->setMetadata($metadata);
            }
            if ($replication != null) {
                $actionEntity->setReplication($replication);
                // An action is completed when replication is completed, so automatically set the completed timestamp to the same...
                $actionEntity->setCompleted($replication);
            }
            // Normally, the completed timestamp is set automatically when replication is done and the replication timestamp is set
            // but we allow the admin or PSO user to set it explicitly
            if ($completed != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setCompleted($completed);
            }
            if ($failed != null) {
                if ($error == null || trim($error) == '') {
                    return API::badRequestErrorResponse('The error parameter is required when recording a failed timestamp.');
                }
                $actionEntity->setFailed($failed);
            }
            if ($error != null && trim($error) != '') {
                $actionEntity->setError($error);
            }
            if ($cleared != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setCleared($cleared);
            }
            if ($retry != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setRetry((trim($retry) === '') ? null : $retry);
            }
            if ($retrying != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setRetry((trim($retrying) === '') ? null : $retrying);
            }
            if ($storage != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setStorage($storage);
            }
            if ($pathname != null) {
                if ($this->userId != 'admin' && $this->userId != $psoUser) {
                    return API::unauthorizedErrorResponse('Session user does not have permission to update the specified value.');
                }
                $actionEntity->setPathname($pathname);
            }
            
            return new DataResponse($this->actionMapper->update($actionEntity));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
    /**
     * Delete an existing action
     *
     * Restricted to admin and PSO users for the project specified for the action.
     *
     * @param string $pid the PID of the action
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function deleteAction($pid) {
        
        try {
            try {
                API::verifyRequiredStringParameter('pid', $pid);
            }
            catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }
            
            $actionEntity = $this->actionMapper->findAction($pid);
            
            if ($actionEntity == null) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }
            
            // Restrict to admin and PSO user for the specified project. In order to prevent unauthorized users
            // determining whether certain entities exist by randomly trying PIDs, we treat this as a not found
            // error rather than an unauthorized error.
            
            if ($this->userId != 'admin' && $this->userId != strtolower(Constants::PROJECT_USER_PREFIX . $actionEntity->getProject())) {
                return API::notFoundErrorResponse('The specified action was not found.');
            }
            
            $this->actionMapper->deleteAction($pid);
            
            return API::successResponse('Action deleted.');
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
}

