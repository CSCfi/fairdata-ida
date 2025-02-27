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
 */

namespace OCA\IDA\Util;

use Exception;
use OC;
use OCP\Util;
use OC\User\User;

/**
 * Class NotProjectUser
 *
 * Exception class to signal when the authenticated user does not belong to a specified project
 */
class NotProjectUser extends Exception
{
    public function __construct($message = null)
    {
        if ($message === null) {
            $this->message = 'Session user does not belong to the specified project.';
        } else {
            $this->message = $message;
        }
    }
}

/**
 * Various access management functions
 */
class Access
{
    /**
     * Return a string of comma separated names of all projects to which the user belongs.
     *
     * @return string
     */
    public static function getUserProjects() {
        
        $userProjects = null;
        
        $user = \OC::$server->getUserSession()->getUser();
        $userId = $user->getUID();
        
        if (strlen($userId) <= 0) {
            throw new Exception('No user found for session.');
        }
        
        // Fetch names of all project groups to which the user belongs
        $projects = implode(',', \OC::$server->getGroupManager()->getUserGroupIds($user));
        
        Util::writeLog('ida', 'getUserProjects: projects=' . $projects, \OCP\Util::DEBUG);
        
        return $projects;
    }
    
    /**
     * Produced a clean, comma separated sequence of project names, with no superfluous whitespace.
     *
     * @param string $projects a comma separated sequence of project names
     *
     * @return string
     */
    public static function cleanProjectList($projects) {
        
        $cleanProjects = null;
        
        if ($projects != null) {
            $projects = trim($projects);
            $first = true;
            if ($projects != null && $projects != '') {
                foreach (explode(',', $projects) as $project) {
                    if ($first) {
                        $cleanProjects = trim($project);
                        $first = false;
                    }
                    else {
                        $cleanProjects = $cleanProjects . ',' . trim($project);
                    }
                }
            }
        }
        
        return $cleanProjects;
    }
    
    /**
     * Throw exception if current user does not have rights to access the specified project (either is not a member
     * of the project or is not an admin).
     *
     * @param string $project the project name
     *
     * @throws NotProjectUser
     */
    public static function verifyIsAllowedProject($project) {
        
        $userId = \OC::$server->getUserSession()->getUser()->getUID();
        
        Util::writeLog('ida', 'verifyIsAllowedProject: userId=' . $userId . ' project=' . $project, \OCP\Util::DEBUG);
        
        if (strlen($userId) <= 0) {
            throw new Exception('No user found for session.');
        }
        
        // If user is PSO user for project, return (OK)
        if ($userId === Constants::PROJECT_USER_PREFIX . $project) {
            return;
        }
        
        // Throw exception if user is admin or does not belong to specified project group
        
        if ($userId === 'admin' || !\OC::$server->getGroupManager()->isInGroup($userId, $project)) {
            throw new NotProjectUser();
        }
    }
    
    /**
     * Returns true if the project lock file exists (e.g. due to an ongoing action), else returns false.
     *
     * @param string $project          the project name
     * @param string $lockFilePathname the full system pathname of the project lock file, if known
     *
     * @return bool
     */
    public static function projectIsLocked($project, $lockFilePathname = null) {
        if (!$project) {
            throw new Exception('Null project');
        }
        Util::writeLog('ida', 'projectIsLocked: project=' . $project . ' lockFilePathname=' . $lockFilePathname, \OCP\Util::DEBUG);
        if ($lockFilePathname === null) {
            $lockFilePathname = self::buildLockFilePathname($project);
        }
        
        return (file_exists($lockFilePathname));
    }
    
    /**
     * Locks the specified project by creating the project lock file.
     * 
     * If the specified project is 'all', locks the entire service. If the service is already
     * locked, still returns true and the service remains locked.
     *
     * Returns true on success, else returns false if the project cannot be locked because either
     * the service is locked, or the project is already locked e.g. by another action. 
     * 
     * @param string $project the project name
     *
     * @return bool
     */
    public static function lockProject($project) {
        if (!$project) {
            throw new Exception('Null project');
        }
        Util::writeLog('ida', 'lockProject: project=' . $project, \OCP\Util::DEBUG);
        if (self::projectIsLocked('all')) {
            if ($project !== 'all') {
                return false;
            }
            return true;
        }
        $lockFilePathname = self::buildLockFilePathname($project);
        if (self::projectIsLocked($project, $lockFilePathname)) {
            return false;
        }
        if (!touch($lockFilePathname)) {
            throw new Exception('Failed to create lock file for project ' . $project);
        }
        return true;
    }
    
    /**
     * Unlocks the specified project by removing the project lock file.
     *
     * Returns true on succeess, else throws exception if existing lock cannot be removed.
     *
     * @param string $project the project name
     *
     * @return bool
     */
    public static function unlockProject($project) {
        if (!$project) {
            throw new Exception('Null project');
        }
        Util::writeLog('ida', 'unlockProject: project=' . $project, \OCP\Util::DEBUG);
        $lockFilePathname = self::buildLockFilePathname($project);
        if (self::projectIsLocked($project, $lockFilePathname)) {
            if (!unlink($lockFilePathname)) {
                throw new Exception('Failed to delete lock file for project ' . $project);
            }
        }
        return true;
    }
    
    /**
     * Builds and returns the full pathname of the lock file for the specified project.
     * 
     * If the specified project is 'all', builds and resturns system lock file pathname.
     *
     * @param string $project the project name
     *
     * @return string
     */
    protected static function buildLockFilePathname($project) {
        $dataRootPathname = \OC::$server->getConfig()->getSystemValue('datadirectory', '/mnt/storage_vol01/ida');
        if ($project === 'all') {
            $lockFilePathname = $dataRootPathname . '/control/LOCK';
        }
        else {
            $lockFilePathname = $dataRootPathname . '/' . Constants::PROJECT_USER_PREFIX . $project . '/files/LOCK';
        }
        Util::writeLog('ida', 'buildLockFilePathname: lockFilePathname=' . $lockFilePathname, \OCP\Util::DEBUG);
        
        return ($lockFilePathname);
    }
    
    /**
     * Puts the service into offline mode by creating the OFFLINE sentinel file.
     *
     * Returns true on success, else returns false. Always succeeds if the service is already in offline mode.
     *
     * @return bool
     */
    public static function setOfflineMode() {
        Util::writeLog('ida', 'setOfflineMode', \OCP\Util::DEBUG);
        $dataRootPathname = \OC::$server->getConfig()->getSystemValue('datadirectory', '/mnt/storage_vol01/ida');
        $sentinelFile = $dataRootPathname . '/control/OFFLINE';
        if (!file_exists($sentinelFile)) {
            if (!file_put_contents($sentinelFile, 'Service put into offline mode by explicit admin request')) {
                throw new Exception('Failed to create offline sentinel file');
            }
        }
        return true;
    }
    
    /**
     * Puts the service into online mode by removing any OFFLINE sentinel file.
     *
     * Returns true on success, else returns false. Always succeeds if the service is already in online mode.
     *
     * @return bool
     */
    public static function setOnlineMode() {
        Util::writeLog('ida', 'setOnlineMode', \OCP\Util::DEBUG);
        $dataRootPathname = \OC::$server->getConfig()->getSystemValue('datadirectory', '/mnt/storage_vol01/ida');
        $sentinelFile = $dataRootPathname . '/control/OFFLINE';
        if (file_exists($sentinelFile)) {
            if (!unlink($sentinelFile)) {
                throw new Exception('Failed to delete offline sentinel file');
            }
        }
        return true;
    }
    
    /**
     * Escapes all single quotes which might exist in an SQL query string component, preventing SQL injection
     * (and thereby preventing disallowed access to data)
     *
     * @param string $component the query string compoent
     *
     * @return string
     */
    public static function escapeQueryStringComponent($component) {
        Util::writeLog('ida', 'escapeQueryStringComponent: component=' . $component, \OCP\Util::DEBUG);
        if ($component === null || $component === '') {
            $escapedComponent = $component;
        }
        else {
            $escapedComponent = str_replace('\'', '\'\'', $component);
        }
        Util::writeLog('ida', 'escapeQueryStringComponent: escapedComponent=' . $escapedComponent, \OCP\Util::DEBUG);
        
        return ($escapedComponent);
    }

}
