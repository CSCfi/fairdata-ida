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

use OCA\IDA\Util\Access;
use OCA\IDA\Model\ActionMapper;
use OCA\IDA\Model\FileMapper;
use OCA\IDA\Util\API;
use OCA\IDA\View\Navigation;
use OCA\IDA\Util\Constants;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http;
use OCP\IRequest;
use OCP\Util;
use Exception;

/**
 * IDA AppFramework Controller
 */
class ViewController extends Controller
{
    protected $actionMapper;
    protected $fileMapper;
    protected $freezingController;
    protected $userId;
    protected $navigation;
    
    /**
     * Action View Listing Controller
     *
     * @param string             $appName            name of the app
     * @param IRequest           $request            request object
     * @param ActionMapper       $actionMapper       action mapper
     * @param FreezingController $freezingController freezing controller
     * @param string             $userId             userid
     * @param Navigation         $navigation         navigation bar object
     * 
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function __construct(
        $appName,
        IRequest $request,
        ActionMapper $actionMapper,
        FileMapper $fileMapper,
        FreezingController $freezingController,
        $userId,
        Navigation $navigation
    ) {
        parent::__construct($appName, $request);
        $this->actionMapper = $actionMapper;
        $this->fileMapper = $fileMapper;
        $this->freezingController = $freezingController;
        $this->userId = $userId;
        $this->navigation = $navigation;
    }
    
    /**
     * Return action listing view.
     *
     * @param string $status one of 'pending' (default), 'failed', or 'completed'
     *
     * @return TemplateResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getActionTable($status = 'pending') {

        Util::addStyle('ida', 'style');
        Util::addStyle('files', 'files');
        
        // Generate project list based on session user's project membership
        $projects = Access::getUserProjects();
        
        $actions = $this->actionMapper->findActions($status, $projects);
        
        $params = [
            'actions'       => $actions,
            'appNavigation' => $this->navigation->getTemplate($status),
            'status'        => $status,
            'projects'      => $projects
        ];
        
        return new TemplateResponse($this->appName, $status, $params);
    }
    
    /**
     * Return action details view.
     *
     * @param string $pid the PID of the action
     *
     * @return TemplateResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getActionDetails($pid) {

        Util::addStyle('ida', 'style');
        Util::addStyle('files', 'files');
        
        try {
            $action = $this->actionMapper->findAction($pid);
        }
        catch (Exception $e) {
            $action = null;
        }
        
        $files = $this->fileMapper->findFiles($pid, null, Constants::MAX_FILE_COUNT);
        
        $params = [
            'action'        => $action,
            'appNavigation' => $this->navigation->getTemplate('action'),
            'files'         => $files
        ];
        
        return new TemplateResponse($this->appName, 'action', $params);
    }
    
    /**
     * Retry action and redirect to updated action details view.
     *
     * @param string $pid the PID of the action
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function retryAction($pid) {
        
        try {
            
            $response = $this->freezingController->retryAction($pid);
            
            if ($response->getStatus() < 200 || $response->getStatus() > 299) {
                return $response;
            }
            
            return new DataResponse([], Http::STATUS_SEE_OTHER, array('Location' => '/apps/ida/action/' . $pid));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
    /**
     * Clear action and redirect to updated action details view.
     *
     * @param string $pid the PID of the action
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function clearAction($pid) {
        
        try {
            
            $response = $this->freezingController->clearAction($pid);
            
            if ($response->getStatus() < 200 || $response->getStatus() > 299) {
                return $response;
            }
            
            return new DataResponse([], Http::STATUS_SEE_OTHER, array('Location' => '/apps/ida/action/' . $pid));
        }
        catch (Exception $e) {
            return API::serverErrorResponse($e->getMessage());
        }
    }
    
}

