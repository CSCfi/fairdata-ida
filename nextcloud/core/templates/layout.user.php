<?php
function FDWEActive()
{
    return \OC::$server->getSystemConfig()->getValue('FDWE_URL', null) != null;
}
?>

<!DOCTYPE html>
<html class="ng-csp" data-placeholder-focus="false" lang="<?php p($_['language']); ?>" data-locale="<?php p($_['locale']); ?>" >
	<head data-user="<?php p($_['user_uid']); ?>" data-user-displayname="<?php p($_['user_displayname']); ?>" data-requesttoken="<?php p($_['requesttoken']); ?>">
		<meta charset="utf-8">
		<title>
			<?php
				p(!empty($_['application'])?$_['application'].' - ':'');
				p($theme->getTitle());
			?>
		</title>
	    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="/core/js/jquery-2.2.4.js"></script>
		<meta http-equiv="X-UA-Compatible" content="IE=edge">
		<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
		<?php if ($theme->getiTunesAppId() !== '') { ?>
		<meta name="apple-itunes-app" content="app-id=<?php p($theme->getiTunesAppId()); ?>">
		<?php } ?>
		<meta name="apple-mobile-web-app-capable" content="yes">
		<meta name="apple-mobile-web-app-status-bar-style" content="black">
		<meta name="apple-mobile-web-app-title" content="<?php p((!empty($_['application']) && $_['appid'] != 'files')? $_['application']:$theme->getTitle()); ?>">
		<meta name="mobile-web-app-capable" content="yes">
		<meta name="theme-color" content="<?php p($theme->getColorPrimary()); ?>">
		<link rel="icon" href="<?php print_unescaped(image_path($_['appid'], 'favicon.ico')); /* IE11+ supports png */ ?>">
		<link rel="apple-touch-icon" href="<?php print_unescaped(image_path($_['appid'], 'favicon-touch.png')); ?>">
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

	    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="/apps/ida/js/showicons.js"></script>
	</head>
	<body id="<?php p($_['bodyid']);?>">
	<?php include 'layout.noscript.warning.php'; ?>

		<?php foreach ($_['initialStates'] as $app => $initialState) { ?>
			<input type="hidden" id="initial-state-<?php p($app); ?>" value="<?php p(base64_encode($initialState)); ?>">
		<?php }?>

		<a href="#app-content" class="button primary skip-navigation skip-content"><?php p($l->t('Skip to main content')); ?></a>
		<a href="#app-navigation" class="button primary skip-navigation"><?php p($l->t('Skip to navigation of app')); ?></a>

		<div id="notification-container">
			<div id="notification"></div>
		</div>
		<header role="banner" id="header">
			<div class="header-left">
				<a href="<?php print_unescaped(link_to('', 'index.php')); ?>"
					style=" color: currentColor; display: inline-block; pointer-events: none; text-decoration: none;"
					id="nextcloud">
					<div class="logo logo-icon">
						<h1 class="hidden-visually">
							<?php p($theme->getName()); ?> <?php p(!empty($_['application'])?$_['application']: $l->t('Apps')); ?>
						</h1>
					</div>
				</a>

				<ul id="appmenu" <?php if ($_['themingInvertMenu']) { ?>class="inverted"<?php } ?>>
					<?php foreach ($_['navigation'] as $entry): ?>
						<li data-id="<?php p($entry['id']); ?>" class="hidden" tabindex="-1">
						    <a href="<?php print_unescaped($entry['href']); ?>" tabindex="3" <?php if ($entry['active']) : ?> class="active" <?php endif; ?>>
							    <p class="ida-app-title" tabindex="-1">
                                    <?php 
                                         $label = strtoupper(!empty($entry['name']) ? $entry['name'] : $l->t('Apps'));
                                         if ($label == 'ÅTGäRDER') { $label = 'ÅTGÄRDER'; }
                                         p($label);
                                     ?>
							    </p>
							</a>
						</li>
					<?php endforeach; ?>
					    
				    <li id="ida-notifications" style="display: inline-flex; cursor: default;">
					    <div id="ida-failed-actions-icon" class="ida-notification-icon" style="display: none">
						    <a href="/apps/ida/actions/failed">
					    	    <img title="<?php p($l->t('Failed Actions')); ?>" src="/apps/ida/img/failed-actions-icon.png" style="width: 20px; height: 20px; padding: 15px;">
						    </a>
					    </div>
					    <div id="ida-pending-actions-icon" class="ida-notification-icon" style="display: none">
						    <a href="/apps/ida/actions/pending">
							    <img title="<?php p($l->t('Pending Actions')); ?>" src="/apps/ida/img/pending-actions-icon.png" style="width: 20px; height: 20px; padding: 15px;">
						    </a>
					    </div>
					    <div id="ida-suspended-icon" class="ida-notification-icon" style="display: none">
						     <img title="<?php p($l->t('Project Suspended')); ?>" src="/apps/ida/img/suspended-icon.png" style="width: 20px; height: 20px; padding: 15px;">
					    </div>
				    </li>
				</ul>

				<nav role="navigation">
					<div id="navigation" style="display: none;"  aria-label="<?php p($l->t('More apps menu')); ?>">
						<div id="apps">
							<ul>
								<?php foreach ($_['navigation'] as $entry): ?>
									<li data-id="<?php p($entry['id']); ?>">
									<a href="<?php print_unescaped($entry['href']); ?>"
										<?php if ($entry['active']): ?> class="active"<?php endif; ?>
										aria-label="<?php p($entry['name']); ?>">
										<svg width="16" height="16" viewBox="0 0 16 16" alt="">
											<defs><filter id="invertMenuMore-<?php p($entry['id']); ?>"><feColorMatrix in="SourceGraphic" type="matrix" values="-1 0 0 0 1 0 -1 0 0 1 0 0 -1 0 1 0 0 0 1 0"></feColorMatrix></filter></defs>
											<image x="0" y="0" width="16" height="16" preserveAspectRatio="xMinYMin meet" filter="url(#invertMenuMore-<?php p($entry['id']); ?>)" xlink:href="<?php print_unescaped($entry['icon'] . '?v=' . $_['versionHash']); ?>"  class="app-icon"></image>
										</svg>
										<span><?php p($entry['name']); ?></span>
									</a>
									</li>
								<?php endforeach; ?>
							</ul>
						</div>
					</div>
				</nav>

			</div>

			<div class="header-right">
				<div id="notifications"></div>
				<div id="unified-search"></div>
				<div id="settings">
					<div id="expand" tabindex="0" role="button" class="menutoggle"
						aria-label="<?php p($l->t('Settings'));?>"
						aria-haspopup="true" aria-controls="expanddiv" aria-expanded="false">
						<div id="expandDisplayName" class="icon-settings-white"></div>
					</div>
					<nav class="settings-menu" id="expanddiv" style="display:none;"
						aria-label="<?php p($l->t('Settings menu'));?>">
					<ul>
					<?php foreach ($_['settingsnavigation'] as $entry):?>
						<li data-id="<?php p($entry['id']); ?>">
							<a href="<?php print_unescaped($entry['href']); ?>"
								<?php if ($entry["active"]): ?> class="active"<?php endif; ?>>
								<img alt="" src="<?php print_unescaped($entry['icon'] . '?v=' . $_['versionHash']); ?>">
								<?php p($entry['name']) ?>
							</a>
						</li>
					<?php endforeach; ?>
					</ul>
					</nav>
				</div>
			</div>
		</header>

		<div id="sudo-login-background" class="hidden"></div>
		<form id="sudo-login-form" class="hidden" method="POST">
			<label>
				<?php p($l->t('This action requires you to confirm your password')); ?><br/>
				<input type="password" class="question" autocomplete="new-password" name="question" value=" <?php /* Hack against browsers ignoring autocomplete="off" */ ?>"
				placeholder="<?php p($l->t('Confirm your password')); ?>" />
			</label>
			<input class="confirm" value="<?php p($l->t('Confirm')); ?>" type="submit">
		</form>

		<div id="content" class="app-<?php p($_['appid']) ?>" role="main">
			<?php print_unescaped($_['content']); ?>
		</div>

	</body>
</html>
