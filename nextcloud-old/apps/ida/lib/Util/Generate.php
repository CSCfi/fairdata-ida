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

namespace OCA\IDA\Util;

/**
 * Various value generation methods
 */
class Generate
{
    /**
     * Generate a new PID, with optional suffix
     *
     * Current conventions used for suffixes:
     *    action PIDs are given the suffix 'a' + the Nextcloud node ID of the folder
     *    folder PIDs are given the suffix 'd' + the Nextcloud node ID
     *    file PIDs are given the suffix 'f' + the Nextcloud node ID
     *
     * @param string $suffix optional suffix to append to generated PID, limited to 10 characters in length
     *
     * @return string
     */
    public static function newPid($suffix = null) {
        
        // If suffix defined, limit to max 10 initial characters
        
        if ($suffix != null) {
            $suffix = substr($suffix, 0, 10);
        }
        
        $pid = uniqid(null, true);
        $pid = str_replace('.', '', $pid);
        
        return $pid . $suffix;
    }
    
    /**
     * Generate ISO standard formatted timestamp string for current UTC time, or for UNIX integer timestamp, if specified
     *
     * @return string
     */
    public static function newTimestamp($timestamp = null) {
        if ($timestamp === null) {
            return str_replace('+0000', 'Z', gmdate(DATE_ISO8601));
        } else {
            return str_replace('+0000', 'Z', gmdate(DATE_ISO8601, $timestamp));
        }
    }
    
}
