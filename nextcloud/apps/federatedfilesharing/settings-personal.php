<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Bjoern Schiessle <bjoern@schiessle.org>
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Jan-Christoph Borchardt <hey@jancborchardt.net>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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

use OCA\FederatedFileSharing\AppInfo\Application;

\OC_Util::checkLoggedIn();

$l = \OC::$server->getL10N('federatedfilesharing');

$app = new Application();
$federatedShareProvider = $app->getFederatedShareProvider();

$isIE8 = false;
preg_match('/MSIE (.*?);/', $_SERVER['HTTP_USER_AGENT'], $matches);
if (count($matches) > 0 && $matches[1] <= 9) {
	$isIE8 = true;
}

$cloudID = \OC::$server->getUserSession()->getUser()->getCloudId();
$url = 'https://nextcloud.com/federation#' . $cloudID;
$logoPath = \OC::$server->getURLGenerator()->imagePath('core', 'logo-icon.svg');
/** @var \OCP\Defaults $theme */
$theme = \OC::$server->query(\OCP\Defaults::class);
$color = $theme->getColorPrimary();
$textColor = "#ffffff";
if(\OC::$server->getAppManager()->isEnabledForUser("theming")) {
	$logoPath = $theme->getLogo();
	try {
		$util = \OC::$server->query("\OCA\Theming\Util");
		if($util->invertTextColor($color)) {
			$textColor = "#000000";
		}
	} catch (OCP\AppFramework\QueryException $e) {

	}
}


$tmpl = new OCP\Template('federatedfilesharing', 'settings-personal');
$tmpl->assign('outgoingServer2serverShareEnabled', $federatedShareProvider->isOutgoingServer2serverShareEnabled());
$tmpl->assign('message_with_URL', $l->t('Share with me through my #Nextcloud Federated Cloud ID, see %s', [$url]));
$tmpl->assign('message_without_URL', $l->t('Share with me through my #Nextcloud Federated Cloud ID', [$cloudID]));
$tmpl->assign('logoPath', $logoPath);
$tmpl->assign('reference', $url);
$tmpl->assign('cloudId', $cloudID);
$tmpl->assign('showShareIT', !$isIE8);
$tmpl->assign('color', $color);
$tmpl->assign('textColor', $textColor);

return $tmpl->fetchPage();
