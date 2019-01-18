<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Jakob Sack <mail@jakobsack.de>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Jörn Friedrich Dreyer <jfd@butonic.de>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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
// required for translation purpose
// t('Files')
$l = \OC::$server->getL10N('files');

\OC::$server->getSearch()->registerProvider('OC\Search\Provider\File', array('apps' => array('files')));

$templateManager = \OC_Helper::getFileTemplateManager();
$templateManager->registerTemplate('text/html', 'core/templates/filetemplates/template.html');
$templateManager->registerTemplate('application/vnd.oasis.opendocument.presentation', 'core/templates/filetemplates/template.odp');
$templateManager->registerTemplate('application/vnd.oasis.opendocument.text', 'core/templates/filetemplates/template.odt');
$templateManager->registerTemplate('application/vnd.oasis.opendocument.spreadsheet', 'core/templates/filetemplates/template.ods');

\OCA\Files\App::getNavigationManager()->add(function () use ($l) {
	return [
		'id' => 'files',
		'appname' => 'files',
		'script' => 'list.php',
		'order' => 0,
		'name' => $l->t('All files'),
	];
});

\OCA\Files\App::getNavigationManager()->add(function () use ($l) {
	return [
		'id' => 'recent',
		'appname' => 'files',
		'script' => 'recentlist.php',
		'order' => 2,
		'name' => $l->t('Recent'),
	];
});
