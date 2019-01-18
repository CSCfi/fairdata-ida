<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Bart Visscher <bartv@thisnet.nl>
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Christopher Schäpers <kondou@ts.unde.re>
 * @author Christoph Wurst <christoph@owncloud.com>
 * @author Georg Ehrke <georg@owncloud.com>
 * @author Jakob Sack <mail@jakobsack.de>
 * @author Jan-Christoph Borchardt <hey@jancborchardt.net>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Marvin Thomas Rabe <mrabe@marvinrabe.de>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 * @author Vincent Petry <pvince81@owncloud.com>
 * @author Volkan Gezer <volkangezer@gmail.com>
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

OC_Util::checkLoggedIn();

$defaults = \OC::$server->getThemingDefaults();
$certificateManager = \OC::$server->getCertificateManager();
$accountManager = new \OC\Accounts\AccountManager(
	\OC::$server->getDatabaseConnection(),
	\OC::$server->getEventDispatcher(),
	\OC::$server->getJobList()
);
$config = \OC::$server->getConfig();
$urlGenerator = \OC::$server->getURLGenerator();

// Highlight navigation entry
OC_Util::addScript('settings', 'authtoken');
OC_Util::addScript('settings', 'authtoken_collection');
OC_Util::addScript('settings', 'authtoken_view');
OC_Util::addScript('settings', 'usersettings');
OC_Util::addScript('settings', 'federationsettingsview');
OC_Util::addScript('settings', 'federationscopemenu');
OC_Util::addScript('settings', 'personal');
OC_Util::addScript('settings', 'certificates');
OC_Util::addStyle( 'settings', 'settings' );
\OC_Util::addVendorScript('strengthify/jquery.strengthify');
\OC_Util::addVendorStyle('strengthify/strengthify');
\OC_Util::addScript('files', 'jquery.fileupload');
\OC_Util::addVendorScript('jcrop/js/jquery.Jcrop');
\OC_Util::addVendorStyle('jcrop/css/jquery.Jcrop');

\OC::$server->getEventDispatcher()->dispatch('OC\Settings\Personal::loadAdditionalScripts');

// Highlight navigation entry
OC::$server->getNavigationManager()->setActiveEntry('personal');

$storageInfo=OC_Helper::getStorageInfo('/');

$user = OC::$server->getUserManager()->get(OC_User::getUser());

$forceLanguage = $config->getSystemValue('force_language', false);
if ($forceLanguage === false) {
	$userLang=$config->getUserValue( OC_User::getUser(), 'core', 'lang', \OC::$server->getL10NFactory()->findLanguage() );
	$languageCodes = \OC::$server->getL10NFactory()->findAvailableLanguages();

	// array of common languages
	$commonLangCodes = array(
		'en', 'es', 'fr', 'de', 'de_DE', 'ja', 'ar', 'ru', 'nl', 'it', 'pt_BR', 'pt_PT', 'da', 'fi_FI', 'nb_NO', 'sv', 'tr', 'zh_CN', 'ko'
	);

	$languages=array();
	$commonLanguages = array();
	foreach($languageCodes as $lang) {
		$l = \OC::$server->getL10N('settings', $lang);
		// TRANSLATORS this is the language name for the language switcher in the personal settings and should be the localized version
		$potentialName = (string) $l->t('__language_name__');
		if($l->getLanguageCode() === $lang && substr($potentialName, 0, 1) !== '_') {//first check if the language name is in the translation file
			$ln = array('code' => $lang, 'name' => $potentialName);
		} elseif ($lang === 'en') {
			$ln = ['code' => $lang, 'name' => 'English (US)'];
		}else{//fallback to language code
			$ln=array('code'=>$lang, 'name'=>$lang);
		}

		// put appropriate languages into appropriate arrays, to print them sorted
		// used language -> common languages -> divider -> other languages
		if ($lang === $userLang) {
			$userLang = $ln;
		} elseif (in_array($lang, $commonLangCodes)) {
			$commonLanguages[array_search($lang, $commonLangCodes)]=$ln;
		} else {
			$languages[]=$ln;
		}
	}

	// if user language is not available but set somehow: show the actual code as name
	if (!is_array($userLang)) {
		$userLang = [
			'code' => $userLang,
			'name' => $userLang,
		];
	}

	ksort($commonLanguages);

	// sort now by displayed language not the iso-code
	usort( $languages, function ($a, $b) {
		if ($a['code'] === $a['name'] && $b['code'] !== $b['name']) {
			// If a doesn't have a name, but b does, list b before a
			return 1;
		}
		if ($a['code'] !== $a['name'] && $b['code'] === $b['name']) {
			// If a does have a name, but b doesn't, list a before b
			return -1;
		}
		// Otherwise compare the names
		return strcmp($a['name'], $b['name']);
	});
}

//links to clients
$clients = array(
	'desktop' => $config->getSystemValue('customclient_desktop', $defaults->getSyncClientUrl()),
	'android' => $config->getSystemValue('customclient_android', $defaults->getAndroidClientUrl()),
	'ios'     => $config->getSystemValue('customclient_ios', $defaults->getiOSClientUrl())
);

// only show root certificate import if external storages are enabled
$enableCertImport = false;
$externalStorageEnabled = \OC::$server->getAppManager()->isEnabledForUser('files_external');
if ($externalStorageEnabled) {
	/** @var \OCA\Files_External\Service\BackendService $backendService */
	$backendService = \OC_Mount_Config::$app->getContainer()->query('\OCA\Files_External\Service\BackendService');
	$enableCertImport = $backendService->isUserMountingAllowed();
}


// Return template
$l = \OC::$server->getL10N('settings');
$tmpl = new OC_Template( 'settings', 'personal', 'user');
$tmpl->assign('usage', OC_Helper::humanFileSize($storageInfo['used']));
if ($storageInfo['quota'] === \OCP\Files\FileInfo::SPACE_UNLIMITED) {
	$totalSpace = $l->t('Unlimited');
} else {
	$totalSpace = OC_Helper::humanFileSize($storageInfo['total']);
}

$uid = $user->getUID();
$userData = $accountManager->getUser($user);

$tmpl->assign('total_space', $totalSpace);
$tmpl->assign('usage_relative', $storageInfo['relative']);
$tmpl->assign('quota', $storageInfo['quota']);
$tmpl->assign('clients', $clients);
$tmpl->assign('email', $userData[\OC\Accounts\AccountManager::PROPERTY_EMAIL]['value']);
if ($forceLanguage === false) {
	$tmpl->assign('languages', $languages);
	$tmpl->assign('commonlanguages', $commonLanguages);
	$tmpl->assign('activelanguage', $userLang);
}
$tmpl->assign('passwordChangeSupported', OC_User::canUserChangePassword(OC_User::getUser()));
$tmpl->assign('displayNameChangeSupported', OC_User::canUserChangeDisplayName(OC_User::getUser()));
$tmpl->assign('displayName', $userData[\OC\Accounts\AccountManager::PROPERTY_DISPLAYNAME]['value']);

$tmpl->assign('phone', $userData[\OC\Accounts\AccountManager::PROPERTY_PHONE]['value']);
$tmpl->assign('website', $userData[\OC\Accounts\AccountManager::PROPERTY_WEBSITE]['value']);
$tmpl->assign('twitter', $userData[\OC\Accounts\AccountManager::PROPERTY_TWITTER]['value']);
$tmpl->assign('address', $userData[\OC\Accounts\AccountManager::PROPERTY_ADDRESS]['value']);

$tmpl->assign('avatarScope', $userData[\OC\Accounts\AccountManager::PROPERTY_AVATAR]['scope']);
$tmpl->assign('displayNameScope', $userData[\OC\Accounts\AccountManager::PROPERTY_DISPLAYNAME]['scope']);
$tmpl->assign('phoneScope', $userData[\OC\Accounts\AccountManager::PROPERTY_PHONE]['scope']);
$tmpl->assign('emailScope', $userData[\OC\Accounts\AccountManager::PROPERTY_EMAIL]['scope']);
$tmpl->assign('websiteScope', $userData[\OC\Accounts\AccountManager::PROPERTY_WEBSITE]['scope']);
$tmpl->assign('twitterScope', $userData[\OC\Accounts\AccountManager::PROPERTY_TWITTER]['scope']);
$tmpl->assign('addressScope', $userData[\OC\Accounts\AccountManager::PROPERTY_ADDRESS]['scope']);

$tmpl->assign('websiteVerification', $userData[\OC\Accounts\AccountManager::PROPERTY_WEBSITE]['verified']);
$tmpl->assign('twitterVerification', $userData[\OC\Accounts\AccountManager::PROPERTY_TWITTER]['verified']);
$tmpl->assign('emailVerification', $userData[\OC\Accounts\AccountManager::PROPERTY_EMAIL]['verified']);

$needVerifyMessage = [\OC\Accounts\AccountManager::PROPERTY_EMAIL, \OC\Accounts\AccountManager::PROPERTY_WEBSITE, \OC\Accounts\AccountManager::PROPERTY_TWITTER];

foreach ($needVerifyMessage as $property) {

	switch ($userData[$property]['verified']) {
		case \OC\Accounts\AccountManager::VERIFIED:
			$message = $l->t('Verifying');
			break;
		case \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS:
			$message = $l->t('Verifying …');
			break;
		default:
			$message = $l->t('Verify');
	}

	$tmpl->assign($property . 'Message', $message);
}

$tmpl->assign('avatarChangeSupported', OC_User::canUserChangeAvatar(OC_User::getUser()));
$tmpl->assign('certs', $certificateManager->listCertificates());
$tmpl->assign('showCertificates', $enableCertImport);
$tmpl->assign('urlGenerator', $urlGenerator);

$federatedFileSharingEnabled = \OC::$server->getAppManager()->isEnabledForUser('federatedfilesharing');
$lookupServerUploadEnabled = false;
if ($federatedFileSharingEnabled) {
	$federatedFileSharing = new \OCA\FederatedFileSharing\AppInfo\Application();
	$shareProvider = $federatedFileSharing->getFederatedShareProvider();
	$lookupServerUploadEnabled = $shareProvider->isLookupServerUploadEnabled();
}

$tmpl->assign('lookupServerUploadEnabled', $lookupServerUploadEnabled);

// Get array of group ids for this user
$groups = \OC::$server->getGroupManager()->getUserIdGroups(OC_User::getUser());
$groups2 = array_map(function($group) { return $group->getGID(); }, $groups);
sort($groups2);
$tmpl->assign('groups', $groups2);

// add hardcoded forms from the template
$formsAndMore = [];
$formsAndMore[]= ['anchor' => 'personal-settings', 'section-name' => $l->t('Personal info')];
// IDA MODIFICATION
// BEGIN MODIFICATION
/*
if (\OC::$server->getAppManager()->isEnabledForUser('firstrunwizard')) {
	$formsAndMore[]= ['anchor' => 'clientsbox', 'section-name' => $l->t('Sync clients')];
}
*/
// END MODIFICATION
$formsAndMore[]= ['anchor' => 'security', 'section-name' => $l->t('Security')];

$forms=OC_App::getForms('personal');


// add bottom hardcoded forms from the template
if ($enableCertImport) {
	$certificatesTemplate = new OC_Template('settings', 'certificates');
	$certificatesTemplate->assign('type', 'personal');
	$certificatesTemplate->assign('uploadRoute', 'settings.Certificate.addPersonalRootCertificate');
	$certificatesTemplate->assign('certs', $certificateManager->listCertificates());
	$certificatesTemplate->assign('urlGenerator', $urlGenerator);
	$forms[] = $certificatesTemplate->fetchPage();
}

$formsMap = array_map(function($form){
	if (preg_match('%(<h2(?P<class>[^>]*)>.*?</h2>)%i', $form, $regs)) {
		$sectionName = str_replace('<h2'.$regs['class'].'>', '', $regs[0]);
		$sectionName = str_replace('</h2>', '', $sectionName);
		if (strpos($regs['class'], 'data-anchor-name') !== false) {
			preg_match('%.*data-anchor-name="(?P<anchor>[^"]*)"%i', $regs['class'], $matches);
			$anchor = $matches['anchor'];
		} else {
			$anchor = strtolower($sectionName);
			$anchor = str_replace(' ', '-', $anchor);
		}

		return array(
			'anchor' => $anchor,
			'section-name' => $sectionName,
			'form' => $form
		);
	}
	return array(
		'form' => $form
	);
}, $forms);

$formsAndMore = array_merge($formsAndMore, $formsMap);

$tmpl->assign('forms', $formsAndMore);
$tmpl->printPage();
