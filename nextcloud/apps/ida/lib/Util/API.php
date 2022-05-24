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

use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\Util;
use Exception;

/**
 * Various validation functions
 */
class API
{
    const TIMESTAMP_PATTERN = '/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]{1,10})?)?Z/';
    
    /**
     * Log the specified response details.
     *
     * @param string $message the message to be logged and returned in the body of the 200 OK response
     * @param bool   $debug   if specified and equal to true, the message is logged as DEBUG rather than INFO 
     *
     * @return DataResponse
     */
    private static function loggedDataResponse($message, $debug = false) {
        if ($debug) {
            Util::writeLog('ida', $message, \OCP\Util::DEBUG);
        }
        else {
            Util::writeLog('ida', $message, \OCP\Util::INFO);
        }
        
        return new DataResponse(['message' => $message, 'status' => 'OK'], Http::STATUS_OK);
    }
    
    /**
     * Log the specified error response details.
     *
     * A 5XX response is logged as an error. Other responses are logged as warnings.
     *
     * @param string $message    the message to be logged and returned in the body of the response
     * @param string $statusCode the status code of the response to be returned
     *
     * @return DataResponse
     */
    private static function loggedErrorResponse($message, $statusCode) {
        if ($statusCode > 499 && $statusCode < 600) {
            Util::writeLog('ida', 'API Request ERROR: ' . $message, \OCP\Util::ERROR);
        }
        else {
            Util::writeLog('ida', 'API Request WARNING: ' . $message, \OCP\Util::WARN);
        }
        
        return new DataResponse(['message' => $message, 'status' => 'error'], $statusCode);
    }
    
    /**
     * Log and return success data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     * @param bool   $debug   if specified and equal to true, the message is logged as DEBUG rather than INFO 
     *
     * @return DataResponse
     */
    public static function successResponse($message, $debug = false) {
        return self::loggedDataResponse($message, $debug);
    }
    
    /**
     * Log and return not found error data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function notFoundErrorResponse($message = 'Not Found') {
        return self::loggedErrorResponse($message, Http::STATUS_NOT_FOUND);
    }
    
    /**
     * Log and return unauthorized error data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function unauthorizedErrorResponse($message = 'Unauthorized') {
        return self::loggedErrorResponse($message, Http::STATUS_UNAUTHORIZED);
    }
    
    /**
     * Log and return forbidden error data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function forbiddenErrorResponse($message = 'Forbidden') {
        return self::loggedErrorResponse($message, Http::STATUS_FORBIDDEN);
    }
    
    /**
     * Log and return bad request error data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function badRequestErrorResponse($message = 'Bad Request') {
        return self::loggedErrorResponse($message, Http::STATUS_BAD_REQUEST);
    }
    
    /**
     * Log and return conflict data response.
     *
     * The conflict response is used when an operation is not allowed, such as when the project is locked
     * due to an ongoing action, or there is a file intersection with a pending action, or some essential
     * component of the service is unavailable (e.g. rabbitmq), etc.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function conflictErrorResponse($message = 'Conflict') {
        return self::loggedErrorResponse($message, Http::STATUS_CONFLICT);
    }
    
    /**
     * Log and return server error data response.
     *
     * @param string $message the message to be logged and returned in the body of the response
     *
     * @return DataResponse
     */
    public static function serverErrorResponse($message = 'Internal Server Error') {
        return self::loggedErrorResponse($message, Http::STATUS_INTERNAL_SERVER_ERROR);
    }
    
    /**
     * Verify that the specified integer parameter is non-null. Throw exception if it is invalid.
     *
     * @param string $name  the name of the parameter
     * @param int    $value the value of the parameter
     *
     * @throws Exception
     */
    public static function verifyRequiredIntegerParameter($name, $value) {
        if ($value === null) {
            throw new Exception('Required integer parameter "' . $name . '" not specified.');
        }
    }
    
    /**
     * Verify that the specified string parameter is non-null and not an empty string. Throw exception if it is invalid.
     *
     * @param string $name  the name of the parameter
     * @param string $value the value of the parameter
     *
     * @throws Exception
     */
    public static function verifyRequiredStringParameter($name, $value) {
        if ($value === null || trim($value) == '') {
            throw new Exception('Required string parameter "' . $name . '" not specified or is empty string.');
        }
    }
    
    /**
     * Validate that the specified integer parameter, if non-null, is actually an integer. Throw exception if it is invalid.
     * Special exception is made for the explicit value 'null' used to remove existing field values.
     *
     * @param string  $name   the name of the parameter
     * @param mixed   $value  the value of the parameter
     * @param boolean $nullOK if true, value may be equal to 'null'
     *
     * @throws Exception
     */
    public static function validateIntegerParameter($name, $value, $nullOK = false) {
        if ($nullOK === true && $value === 'null') { return; }
        if ($value !== null && !is_integer($value)) {
            throw new Exception('Input integer parameter "' . $name . '" has invalid value "' . $value . '".');
        }
    }
    
    /**
     * Validate that the specified string parameter, if non-null, is not the empty string. Throw exception if it is invalid.
     * Special exception is made for the explicit value 'null' used to remove existing field values.
     *
     * @param string  $name   the name of the parameter
     * @param string  $value  the value of the parameter
     * @param boolean $nullOK if true, value may be equal to 'null'
     *
     * @throws Exception
     */
    public static function validateStringParameter($name, $value, $nullOK = false) {
        if ($nullOK === true && $value === 'null') { return; }
        if ($value !== null && trim($value) === '') {
            throw new Exception('Input string parameter "' . $name . '" is an empty string.');
        }
    }
    
    /**
     * Validate that the specified timestamp is properly formatted, if non-null. Throw exception if it is invalid.
     * Special exception is made for the explicit value 'null' used to remove existing field values.
     *
     * @param string  $timestamp the timestamp
     * @param boolean $nullOK    if true, value may be equal to 'null'
     *
     * @throws Exception
     */
    public static function validateTimestamp($timestamp, $nullOK = false) {
        if ($nullOK === true && $timestamp === 'null') { return; }
        if ($timestamp !== null && !preg_match(self::TIMESTAMP_PATTERN, $timestamp)) {
            throw new Exception('Specified timestamp "' . $timestamp . '" is invalid.');
        }
    }
    
    /**
     * Split pathname into slash-delimited components, urlencode, and then rejoin with slashes. The component is
     * first urldecoded, just in case it already has some encoded characters, to avoid any possible double encoding.
     *
     * @param $pathname
     *
     * @return string
     */
    public static function urlEncodePathname($pathname) {
        return (implode('/', array_map(function ($v) {
            return rawurlencode(rawurldecode($v));
        }, explode('/', $pathname))));
    }
}
