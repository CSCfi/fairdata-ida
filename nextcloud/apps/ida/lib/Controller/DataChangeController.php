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

use OCA\IDA\Model\DataChange;
use OCA\IDA\Model\DataChangeMapper;
use OCA\IDA\Util\API;
use OCA\IDA\Util\Access;
use OCA\IDA\Util\Constants;
use OCA\IDA\Util\Generate;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\IConfig;
use OCP\IRequest;
use OCP\Util;
use OCP\User;
use Exception;
use OCA\IDA\Util\NotProjectUser;

/**
 * Data Change Event Controller
 */
class DataChangeController extends Controller
{
    protected $dataChangeMapper;
    protected $userId;
    protected $config;

    /**
     * Creates the AppFramwork Controller
     *
     * @param string           $appName           name of the app
     * @param IRequest         $request           request object
     * @param DataChangeMapper $dataChangeMapper  data change event mapper
     * @param string           $userId            userid
     * @param IConfig          $config            global configuration
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function __construct(
        $appName,
        IRequest $request,
        DataChangeMapper $dataChangeMapper,
        $userId,
        IConfig $config
    ) {
        parent::__construct($appName, $request);
        $this->dataChangeMapper = $dataChangeMapper;
        $this->userId = $userId;
        $this->config = $config;
    }

    public function getConfig()
    {
        return $this->config;
    }

    /**
     * Return the timestamp for when a project was added to the IDA service
     *
     * @param string $project  the project name
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getInitialization($project)
    {
        Util::writeLog('ida', 'getInitialization project=' . $project, \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure the project exists

            $datadir = $this->config->getSystemValue('datadirectory');

            if ($datadir === null) {
                throw new Exception('Failed to get data storage root pathname');
            }

            $projectRoot = $datadir . '/' . Constants::PROJECT_USER_PREFIX . $project . '/';

            Util::writeLog('ida', 'getLastDataChange: projectRoot=' . $projectRoot, \OCP\Util::DEBUG);

            if (! is_dir($projectRoot)) {
                return API::notFoundErrorResponse('Unknown project: ' . $project);
            }

            // If user is not admin, nor PSO user, verify user belongs to project

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                Access::verifyIsAllowedProject($project);
            }

            return new DataResponse($this->dataChangeMapper->getInitializationDetails($project));

        } catch (NotProjectUser $e) {
            return API::forbiddenErrorResponse('getInitialization: ' . $e->getMessage());
        } catch (Exception $e) {
            return API::serverErrorResponse('getInitialization: ' . $e->getMessage());
        }
    }

    /**
     * Return the last recorded data change event for a project, if any, else return details
     * from original legacy data migration event.
     *
     * @param string $project  the project name
     * @param string $user     get last change by a particular user, if specified
     * @param string $change   get last change event for a particular change, if specified
     * @param string $mode     get last change event for a particular mode, if specified
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getLastDataChange($project, $user = null, $change = null, $mode = null)
    {
        Util::writeLog('ida', 'getLastDataChange:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' mode=' . $mode
            , \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure the project exists

            $datadir = $this->config->getSystemValue('datadirectory');

            if ($datadir === null) {
                throw new Exception('Failed to get data storage root pathname');
            }

            $projectRoot = $datadir . '/' . Constants::PROJECT_USER_PREFIX . $project . '/';

            Util::writeLog('ida', 'getLastDataChange: projectRoot=' . $projectRoot, \OCP\Util::DEBUG);

            if (! is_dir($projectRoot)) {
                return API::notFoundErrorResponse('Unknown project: ' . $project);
            }

            // If user is not admin, nor PSO user, verify user belongs to project

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                Access::verifyIsAllowedProject($project);
            }

            return new DataResponse($this->dataChangeMapper->getLastDataChangeDetails($project, $user, $change, $mode));

        } catch (Exception $e) {
            return API::serverErrorResponse('getLastDataChange: ' . $e->getMessage());
        }
    }

    /**
     * Return one or more recorded data change events for a project, if any, else return details
     * from original legacy data migration event.
     *
     * @param string $project  the project name
     * @param string $user     limit changes to a particular user, if specified
     * @param string $change   limit changes to a particular data change, if specified
     * @param string $mode     limit changes to a particular mode, if specified
     * @param int    $limit    the number of changes to return, null = unlimited
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function getDataChanges($project, $user = null, $change = null, $mode = null, $limit = null)
    {
        Util::writeLog('ida', 'getDataChanges:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' mode=' . $mode
            . ' limit=' . $limit
            , \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
                API::validateIntegerParameter('limit', $limit);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            // Ensure the project exists

            $datadir = $this->config->getSystemValue('datadirectory');

            if ($datadir === null) {
                throw new Exception('Failed to get data storage root pathname');
            }

            $projectRoot = $datadir . '/' . Constants::PROJECT_USER_PREFIX . $project . '/';

            Util::writeLog('ida', 'getDataChanges: projectRoot=' . $projectRoot, \OCP\Util::DEBUG);

            if (! is_dir($projectRoot)) {
                return API::notFoundErrorResponse('Unknown project: ' . $project);
            }

            // If user is not admin, nor PSO user, verify user belongs to project

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                Access::verifyIsAllowedProject($project);
            }

            return new DataResponse($this->dataChangeMapper->getDataChangeDetails($project, $user, $change, $mode, $limit));

        } catch (Exception $e) {
            return API::serverErrorResponse('getDataChanges: ' . $e->getMessage());
        }
    }

    /**
     * Record a data change event for a project.
     *
     * Restricted to admin or PSO user for project.
     *
     * @param string $project    the project name
     * @param string $user       the user making the change
     * @param string $change     the data change
     * @param string $pathname   the pathname of the scope of the change
     * @param string $target     the target pathname, required for rename, move, or copy change, error otherwise if not null
     * @param string $timestamp  the datetime of the event (defaults to current datetime if not specified)
     * @param string $mode       the mode via which the change was made (defaults to 'api')
     *
     * @return DataResponse
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    public function recordDataChange($project, $user, $change, $pathname, $target = null, $timestamp = null, $mode = null)
    {
        Util::writeLog('ida', 'recordDataChange:'
            . ' project=' . $project
            . ' user=' . $user
            . ' change=' . $change
            . ' pathname=' . $pathname
            . ' target=' . $target
            . ' timestamp=' . $timestamp
            . ' mode=' . $mode
            , \OCP\Util::DEBUG);

        try {

            try {
                API::verifyRequiredStringParameter('project', $project);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            try {
                API::verifyRequiredStringParameter('user', $user);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            try {
                API::verifyRequiredStringParameter('change', $change);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            try {
                API::verifyRequiredStringParameter('pathname', $pathname);
            } catch (Exception $e) {
                return API::badRequestErrorResponse($e->getMessage());
            }

            if ($timestamp !== null) {
                try {
                    API::validateStringParameter('timestamp', $timestamp);
                } catch (Exception $e) {
                    return API::badRequestErrorResponse($e->getMessage());
                }
                try {
                    API::validateTimestamp($timestamp);
                } catch (Exception $e) {
                    return API::badRequestErrorResponse($e->getMessage());
                }
            } else {
                $timestamp = Generate::newTimestamp();
            }

            // Ensure the project exists

            $datadir = $this->config->getSystemValue('datadirectory');

            if ($datadir === null) {
                throw new Exception('Failed to get data storage root pathname');
            }

            $projectRoot = $datadir . '/' . Constants::PROJECT_USER_PREFIX . $project . '/';

            Util::writeLog('ida', 'getDataChanges: projectRoot=' . $projectRoot, \OCP\Util::DEBUG);

            if (! is_dir($projectRoot)) {
                return API::notFoundErrorResponse('Unknown project: ' . $project);
            }

            if ($this->userId !== 'admin' && $this->userId !== Constants::PROJECT_USER_PREFIX . $project) {
                return API::forbiddenErrorResponse();
            }

            if (! in_array($change, DataChange::CHANGES)) {
                return API::badRequestErrorResponse('Invalid change: ' . $change);
            }

            if (in_array($change, DataChange::TARGET_CHANGES) && ($target === null || $target === '')) {
                return API::badRequestErrorResponse('Target must be specified for ' . $change . ' change');
            }

            if ($mode !== null) {
                try {
                    API::validateStringParameter('mode', $mode);
                } catch (Exception $e) {
                    return API::badRequestErrorResponse($e->getMessage());
                }
                if (! in_array($mode, DataChange::MODES)) {
                    return API::badRequestErrorResponse('Invalid mode: ' . $mode);
                }
            }

            // Only record changes to project data, where pathname begins with either staging or frozen folder, unless initialization
            if ($change !== 'init') {
                if (! (  strpos($pathname, '/' . $project . '/') === 0
                      || strpos($pathname, '/' . $project . Constants::STAGING_FOLDER_SUFFIX . '/') === 0)) {
                    return API::badRequestErrorResponse('Pathname must begin with staging or frozen root folder');
                }
            }

            if (! (  $target == null
                  || strpos($target, '/' . $project . '/') === 0
                  || strpos($target, '/' . $project . Constants::STAGING_FOLDER_SUFFIX . '/') === 0)) {
                return API::badRequestErrorResponse('Target must begin with staging or frozen root folder');
            }

            return new DataResponse($this->dataChangeMapper->recordDataChangeDetails($project, $user, $change, $pathname, $target, $timestamp, $mode));

        } catch (Exception $e) {
            return API::serverErrorResponse('recordDataChange: ' . $e->getMessage());
        }
    }

    public static function processNextcloudOperation($change, $pathname, $target = null, $idaUser = null, $idaMode = null) {

        try {

            Util::writeLog('ida', 'processNextcloudOperation:'
                . ' change=' . $change
                . ' pathname=' . $pathname
                . ' target=' . $target
                . ' idaUser=' . $idaUser
                . ' idaMode=' . $idaMode
                , \OCP\Util::DEBUG);

            if ($pathname === null) {
                throw new Exception('processNextcloudOperation: pathname parameter cannot be null');
            }

            // Ignore appdata changes
            if (strpos($pathname, '/appdata') === 0 || strpos($pathname, 'appdata') === 0) {
                Util::writeLog('ida', 'processNextcloudOperation: ignoring appdata change', \OCP\Util::DEBUG);
                return;
            }

            // Ignore PSO account changes
            if (strpos($pathname, '/' . Constants::PROJECT_USER_PREFIX) === 0 || strpos($pathname, Constants::PROJECT_USER_PREFIX) === 0) {
                Util::writeLog('ida', 'processNextcloudOperation: ignoring PSO account change', \OCP\Util::DEBUG);
                return;
            }

            // Ignore internal operations not bound to an authenticated user session
            try {
                $currentUser = User::getUser();
            }
            catch (Exception $e) {
                throw new Exception('ida', 'processNextcloudOperation: failed to retrieve current user');
            }
            if ($currentUser === null || trim($currentUser) === '') {
                // Allow backend changes to be processes, e.g. from occ files:scan
                if ($idaUser === 'service' && $idaMode === 'system') {
                    $currentUser = 'service';
                } else {
                    Util::writeLog('ida', 'processNextcloudOperation: ignoring non-authenticated user change', \OCP\Util::DEBUG);
                    return;
                }
            }

            if ($change === null) {
                throw new Exception('processNextcloudOperation: change parameter cannot be null');
            }

            if (! in_array($change, \OCA\IDA\Model\DataChange::CHANGES)) {
                throw new Exception('processNextcloudOperation: unsupported change: ' . $change);
            }

		    if ($change === 'rename' && $target && dirname($pathname) != dirname($target)) {
			    $change = 'move';
		    }

            if (strpos($pathname, '//') === 0) {
                $pathname = '/' . ltrim($pathname, '/');
            }

            try {
                $project = rtrim(explode('/', ltrim($pathname, '/'))[0], '+');
            } catch (Exception $e) {
                throw new Exception('processNextcloudOperation: Failed to extract project name from pathname ' . $pathname . ': ' . $e->getMessage());
            }

            if ($project === null || $project === '') {
                throw new Exception('processNextcloudOperation: project name cannot be null');
            }

            Util::writeLog('ida', 'processNextcloudOperation:'
                . ' project=' . $project
                . ' change=' . $change
                . ' pathname=' . $pathname
                . ' target=' . $target
                . ' idaUser=' . $idaUser
                . ' currentUser=' . $currentUser
                , \OCP\Util::DEBUG);

            $config = \OC::$server->getConfig();
            if ($config === null) {
                throw new Exception('processNextcloudOperation: Failed to get Nextcloud configuration');
            }
            Util::writeLog('ida', 'processNextcloudOperation: config=' . json_encode($config), \OCP\Util::DEBUG);

            $idaconfig = $config->getSystemValue('ida');
            if ($idaconfig === null || !is_array($idaconfig)) {
                throw new Exception('processNextcloudOperation: Failed to get IDA configuration');
            }
            Util::writeLog('ida', 'processNextcloudOperation: idaconfig=' . json_encode($idaconfig), \OCP\Util::DEBUG);

            $datadir = $config->getSystemValue('datadirectory');
            if ($datadir === null) {
                throw new Exception('processNextcloudOperation: Failed to get data storage root pathname');
            }
            Util::writeLog('ida', 'processNextcloudOperation: datadir=' . $datadir, \OCP\Util::DEBUG);

            $idahome = $config->getSystemValue('IDA_HOME');
            if ($datadir === null) {
                throw new Exception('processNextcloudOperation: Failed to get data storage root pathname');
            }
            Util::writeLog('ida', 'processNextcloudOperation: idahome=' . $idahome, \OCP\Util::DEBUG);

            if (array_key_exists('PROJECT_USER_PASS', $idaconfig)) {
                $psopass = $idaconfig['PROJECT_USER_PASS'];
                Util::writeLog('ida', 'processNextcloudOperation: psopass=' . $psopass, \OCP\Util::DEBUG);
            } else {
                throw new Exception('processNextcloudOperation: Failed to get data PSO password');
            }

            // If the parsing of the project name from the path does not derive to a valid project, tested by constructing
            // the PSO user root directory pathname, ignore the request, as the pathname does not start with either a staging
            // or frozen folder and does not pertain to a project data change but some other internal operation
    
            $projectRoot = $datadir . '/' . Constants::PROJECT_USER_PREFIX . $project . '/';
            Util::writeLog('ida', 'processNextcloudOperation: projectRoot=' . $projectRoot, \OCP\Util::DEBUG);
    
            if (! is_dir($projectRoot)) {
                Util::writeLog('ida', 'processNextcloudOperation: ignoring non-project data change - no PSO root found', \OCP\Util::DEBUG);
                return;
            }
    
            // If the pathname is not within either the staging or frozen folder, ignore the change
            if (! (  strpos($pathname, '/' . $project . '/') === 0
                  || strpos($pathname, '/' . $project . Constants::STAGING_FOLDER_SUFFIX . '/') === 0)) {
                Util::writeLog('ida', 'processNextcloudOperation: ignoring non-project data change - pathname not within staging or frozen root folder', \OCP\Util::DEBUG);
                return;
            }

            if ($idaUser !== null) {
                $user = $idaUser;
            } else {
                $user = $currentUser;
            }

            if ($idaMode !== null) {
                $mode = strtolower($idaMode);
            } else {
                $mode = 'api';
            }

            $username = Constants::PROJECT_USER_PREFIX . $project;
            $password =  $psopass;
            $requestURL = $idahome . '/apps/ida/api/dataChanges';
            $postbody = json_encode(
                array(
                    'project'  => $project,
                    'user'     => $user,
                    'change'   => $change,
                    'pathname' => $pathname,
                    'target'   => $target,
                    'mode'     => $mode
                )
            );

            Util::writeLog('ida', 'processNextcloudOperation:'
                . ' username=' . $username
                . ' password=' . $password
                . ' requestURL=' . $requestURL
                . ' postbody=' . $postbody
                , \OCP\Util::DEBUG);

            $ch = curl_init($requestURL);

            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'POST');
            curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postbody);
            curl_setopt($ch, CURLOPT_HEADER, false);
            curl_setopt($ch, CURLOPT_HTTPHEADER,
                array(
                    'Accept: application/json',
                    'Content-Type: application/json',
                    'Content-Length: ' . strlen($postbody)
                )
            );
            curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
            curl_setopt($ch, CURLOPT_FAILONERROR, true);
            curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);

            Util::writeLog('ida', 'processNextcloudOperation: curlinfo=' . json_encode($ch), \OCP\Util::DEBUG);
    
            $response = curl_exec($ch);

            Util::writeLog('ida', 'processNextcloudOperation: curlinfo=' . json_encode(curl_getinfo($ch)), \OCP\Util::DEBUG);

            if ($response === false) {
                Util::writeLog('ida', 'processNextcloudOperation: '
                    . ' curl_errno=' . curl_errno($ch)
                    . ' response=' . $response, \OCP\Util::ERROR);
                curl_close($ch);
                throw new Exception('Failed to record data change from Nextcloud operation');
            }

            curl_close($ch);
        }
        catch (Exception $e) {
            // Log any errors but don't prevent Nextcloud from otherwise working
            Util::writeLog('core', 'Error encountered trying to record data change: ' . $e->getMessage(), \OCP\Util::ERROR);
        }
    }
}
