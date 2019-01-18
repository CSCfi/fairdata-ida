<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Bart Visscher <bartv@thisnet.nl>
 * @author Christoph Wurst <christoph@owncloud.com>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 * @author Tom Needham <tom@owncloud.com>
 * @author Vincent Petry <pvince81@owncloud.com>
 *
 * @license AGPL-3.0
 *
 * This code is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License, version 3,
 * as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License, version 3,
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 *
 */

require_once __DIR__ . '/../lib/base.php';

if (\OCP\Util::needUpgrade()
	|| \OC::$server->getSystemConfig()->getValue('maintenance', false)) {
	// since the behavior of apps or remotes are unpredictable during
	// an upgrade, return a 503 directly
	OC_Response::setStatus(OC_Response::STATUS_SERVICE_UNAVAILABLE);
	$response = new OC_OCS_Result(null, OC_Response::STATUS_SERVICE_UNAVAILABLE, 'Service unavailable');
	OC_API::respond($response, OC_API::requestedFormat());
	exit;
}

use Symfony\Component\Routing\Exception\ResourceNotFoundException;
use Symfony\Component\Routing\Exception\MethodNotAllowedException;

/*
 * Try old routes first
 * We first try the old routes since the appframework triggers more login stuff.
 */
try {
	OC_App::loadApps(['session']);
	OC_App::loadApps(['authentication']);
	// load all apps to get all api routes properly setup
	OC_App::loadApps();

	OC::$server->getRouter()->match('/ocs'.\OC::$server->getRequest()->getRawPathInfo());
	return;
} catch (ResourceNotFoundException $e) {
	// Fall through the not found
} catch (MethodNotAllowedException $e) {
	OC_API::setContentType();
	OC_Response::setStatus(405);
	exit();
} catch (Exception $ex) {
	OC_API::respond($ex->getResult(), OC_API::requestedFormat());
	exit();
}

/*
 * Try the appframework routes
 */
try {
	if(!\OC::$server->getUserSession()->isLoggedIn()) {
		OC::handleLogin(\OC::$server->getRequest());
	}
	OC::$server->getRouter()->match('/ocsapp'.\OC::$server->getRequest()->getRawPathInfo());
} catch (ResourceNotFoundException $e) {
	OC_API::setContentType();

	$format = \OC::$server->getRequest()->getParam('format', 'xml');
	$txt='Invalid query, please check the syntax. API specifications are here:'
		.' http://www.freedesktop.org/wiki/Specifications/open-collaboration-services. DEBUG OUTPUT:'."\n";
	OC_API::respond(new OC_OCS_Result(null, \OCP\API::RESPOND_NOT_FOUND, $txt), $format);
} catch (MethodNotAllowedException $e) {
	OC_API::setContentType();
	OC_Response::setStatus(405);
} catch (\OC\OCS\Exception $ex) {
	OC_API::respond($ex->getResult(), OC_API::requestedFormat());
} catch (\OC\User\LoginException $e) {
	OC_API::respond(new OC_OCS_Result(null, \OCP\API::RESPOND_UNAUTHORISED, 'Unauthorised'));
} catch (\Exception $e) {
	\OC::$server->getLogger()->logException($e);
	OC_API::setContentType();

	$format = \OC::$server->getRequest()->getParam('format', 'xml');
	$txt='Invalid query, please check the syntax. API specifications are here:'
		.' http://www.freedesktop.org/wiki/Specifications/open-collaboration-services. DEBUG OUTPUT:'."\n";
	OC_API::respond(new OC_OCS_Result(null, \OCP\API::RESPOND_NOT_FOUND, $txt), $format);
}

