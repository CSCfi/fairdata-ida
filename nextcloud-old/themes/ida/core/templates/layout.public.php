<!--
This file is part of the IDA research data storage service

Copyright (C) 2018 Ministry of Education and Culture, Finland

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

@author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@license  GNU Affero General Public License, version 3
@link     https://research.csc.fi/

NOTE: Derived from original Nextcloud code nextcloud/core/templates/layout.user.php

-->

<?php
function FDWEActive()
{
    return \OC::$server->getSystemConfig()->getValue('FDWE_URL', null) != null;
}
?>

<!DOCTYPE html>
<html class="ng-csp" data-placeholder-focus="false" lang="<?php p($_['language']); ?>" data-locale="<?php p($_['locale']); ?>" >
<head data-requesttoken="<?php p($_['requesttoken']); ?>">
	<meta charset="utf-8">
	<title>
		<?php
		p(!empty($_['application'])?$_['application'].' - ':'');
		p($theme->getTitle());
		?>
	</title>
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
	<meta name="apple-itunes-app" content="app-id=<?php p($theme->getiTunesAppId()); ?>">
	<meta name="apple-mobile-web-app-capable" content="yes">
	<meta name="apple-mobile-web-app-status-bar-style" content="black">
	<meta name="apple-mobile-web-app-title" content="<?php p((!empty($_['application']) && $_['appid']!=='files')? $_['application']:$theme->getTitle()); ?>">
	<meta name="mobile-web-app-capable" content="yes">
	<meta name="theme-color" content="<?php p($theme->getColorPrimary()); ?>">
	<link rel="icon" href="<?php print_unescaped(image_path($_['appid'], 'favicon.ico')); /* IE11+ supports png */ ?>">
	<link rel="apple-touch-icon-precomposed" href="<?php print_unescaped(image_path($_['appid'], 'favicon-touch.png')); ?>">
	<link rel="mask-icon" sizes="any" href="<?php print_unescaped(image_path($_['appid'], 'favicon-mask.svg')); ?>" color="<?php p($theme->getColorPrimary()); ?>">
	<link rel="manifest" href="<?php print_unescaped(image_path($_['appid'], 'manifest.json')); ?>">
	<?php emit_css_loading_tags($_); ?>
	<?php emit_script_loading_tags($_); ?>
	<?php print_unescaped($_['headers']); ?>

    <?php if (FDWEActive()) : ?>
    <meta name="fdwe-service" content="IDA">
    <?php if (strpos($_SERVER["REQUEST_URI"], "NOT_FOR_PUBLICATION") !== false ) : ?>
    <meta name="fdwe-scope" content="FILES / SHARE / ACCESS">
    <?php endif; ?>
    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="<?php p(\OC::$server->getSystemConfig()->getValue('FDWE_URL')); ?>"></script>
    <?php endif; ?>

</head>
<body id="<?php p($_['bodyid']);?>">
<?php include('layout.noscript.warning.php'); ?>
<?php foreach ($_['initialStates'] as $app => $initialState) { ?>
	<input type="hidden" id="initial-state-<?php p($app); ?>" value="<?php p(base64_encode($initialState)); ?>">
<?php }?>
	<div id="notification-container">
		<div id="notification"></div>
	</div>
	<header id="header">
		<div class="header-left">
			<span id="nextcloud">
				<div class="logo logo-icon svg"></div>
				<h1 class="header-appname">
					<?php if (isset($template)) { p($template->getHeaderTitle()); } else { p($theme->getName());} ?>
				</h1>
				<div class="header-shared-by">
					<?php if (isset($template)) { p($template->getHeaderDetails()); } ?>
				</div>
			</span>
		</div>

		<?php
		/** @var \OCP\AppFramework\Http\Template\PublicTemplateResponse $template */
		if(isset($template) && $template->getActionCount() !== 0) {
			$primary = $template->getPrimaryAction();
			$others = $template->getOtherActions();
			?>
		<div class="header-right">
			<span id="header-primary-action" class="<?php if($template->getActionCount() === 1) {  p($primary->getIcon()); } ?>">
				<a href="<?php p($primary->getLink()); ?>" class="primary button">
					<span><?php p($primary->getLabel()) ?></span>
				</a>
			</span>
			<?php if($template->getActionCount() > 1) { ?>
			<div id="header-secondary-action">
				<span id="header-actions-toggle" class="menutoggle icon-more-white"></span>
				<div id="header-actions-menu" class="popovermenu menu">
					<ul>
						<?php
							/** @var \OCP\AppFramework\Http\Template\IMenuAction $action */
							foreach($others as $action) {
								print_unescaped($action->render());
							}
						?>
					</ul>
				</div>
			</div>
			<?php } ?>
		</div>
		<?php } ?>
	</header>
	<div id="content" class="app-<?php p($_['appid']) ?>" role="main">
		<?php print_unescaped($_['content']); ?>
	</div>
	<?php if(isset($template) && $template->getFooterVisible()) { ?>
	<footer>
		<p><?php print_unescaped($theme->getLongFooter()); ?></p>
	</footer>
	<?php } ?>

</body>
</html>
