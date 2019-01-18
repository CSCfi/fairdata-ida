<?php /**
 * Copyright (c) 2011, Robin Appelman <icewind1991@gmail.com>
 * This file is licensed under the Affero General Public License version 3 or later.
 * See the COPYING-README file.
 */

/** @var $_ mixed[]|\OCP\IURLGenerator[] */
/** @var \OCP\Defaults $theme */
?>

<div id="app-navigation">
	<ul class="with-icon">
	<?php foreach($_['forms'] as $form) {
		if (isset($form['anchor'])) {
			$anchor = '#' . $form['anchor'];
			$class = 'nav-icon-' . $form['anchor'];
			$sectionName = $form['section-name'];
			print_unescaped(sprintf("<li><a href='%s' class='%s'>%s</a></li>", \OCP\Util::sanitizeHTML($anchor),
			\OCP\Util::sanitizeHTML($class), \OCP\Util::sanitizeHTML($sectionName)));
		}
	}?>
	</ul>
</div>

<div id="app-content">


<div id="personal-settings">

<div id="personal-settings-container">
	<div class="personal-settings-setting-box">
		<form id="displaynameform" class="section">
			<h2>
				<label for="displayname"><?php p($l->t('Full name')); ?></label>
				<span class="icon-password"/>
			</h2>
			<input type="text" id="displayname" name="displayname"
				<?php if(!$_['displayNameChangeSupported']) { print_unescaped('disabled="1"'); } ?>
				value="<?php p($_['displayName']) ?>"
				autocomplete="on" autocapitalize="none" autocorrect="off" />
			<span class="icon-checkmark hidden" ></span>
			<span class="icon-error hidden" ></span>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="displaynamescope" value="<?php p($_['displayNameScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<div class="personal-settings-setting-box">
		<form id="emailform" class="section">
			<h2>
				<label for="email"><?php p($l->t('Email')); ?></label>
				<span class="icon-password"/>
			</h2>
			<div class="verify <?php if ($_['email'] === ''  || $_['emailScope'] !== 'public') p('hidden'); ?>">
				<img id="verify-email" title="<?php p($_['emailMessage']); ?>" data-status="<?php p($_['emailVerification']) ?>" src="
				<?php
				switch($_['emailVerification']) {
					case \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS:
						p(image_path('core', 'actions/verifying.svg'));
						break;
					case \OC\Accounts\AccountManager::VERIFIED:
						p(image_path('core', 'actions/verified.svg'));
						break;
					default:
						p(image_path('core', 'actions/verify.svg'));
				}
				?>">
			</div>
			<input type="email" name="email" id="email" value="<?php if(!$_['displayNameChangeSupported'] && empty($_['email'])) p($l->t('No email address set')); else p($_['email']); ?>"
				<?php if(!$_['displayNameChangeSupported']) { print_unescaped('disabled="1"'); } ?>
				placeholder="<?php p($l->t('Your email address')) ?>"
				autocomplete="on" autocapitalize="none" autocorrect="off" />
			<?php if($_['displayNameChangeSupported']) { ?>
				<br />
				<em><?php p($l->t('For password reset and notifications')); ?></em>
			<?php } ?>
			<span class="icon-checkmark hidden"></span>
			<span class="icon-error hidden" ></span>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="emailscope" value="<?php p($_['emailScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<?php if (!empty($_['phone']) || $_['lookupServerUploadEnabled']) { ?>
	<div class="personal-settings-setting-box">
		<form id="phoneform" class="section">
			<h2>
				<label for="phone"><?php p($l->t('Phone number')); ?></label>
				<span class="icon-password"/>
			</h2>
			<input type="tel" id="phone" name="phone" <?php if(!$_['lookupServerUploadEnabled']) print_unescaped('disabled="1"'); ?>
				   value="<?php p($_['phone']) ?>"
				   placeholder="<?php p($l->t('Your phone number')); ?>"
			       autocomplete="on" autocapitalize="none" autocorrect="off" />
			<span class="icon-checkmark hidden"/>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="phonescope" value="<?php p($_['phoneScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<?php } ?>
	<?php if (!empty($_['address']) || $_['lookupServerUploadEnabled']) { ?>
	<div class="personal-settings-setting-box">
		<form id="addressform" class="section">
			<h2>
				<label for="address"><?php p($l->t('Address')); ?></label>
				<span class="icon-password"/>
			</h2>
			<input type="text" id="address" name="address" <?php if(!$_['lookupServerUploadEnabled']) print_unescaped('disabled="1"');  ?>
				   placeholder="<?php p($l->t('Your postal address')); ?>"
				   value="<?php p($_['address']) ?>"
				   autocomplete="on" autocapitalize="none" autocorrect="off" />
			<span class="icon-checkmark hidden"/>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="addressscope" value="<?php p($_['addressScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<?php } ?>
	<?php if (!empty($_['website']) || $_['lookupServerUploadEnabled']) { ?>
	<div class="personal-settings-setting-box">
		<form id="websiteform" class="section">
			<h2>
				<label for="website"><?php p($l->t('Website')); ?></label>
				<span class="icon-password"/>
			</h2>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<div class="verify <?php if ($_['website'] === ''  || $_['websiteScope'] !== 'public') p('hidden'); ?>">
				<img id="verify-website" title="<?php p($_['websiteMessage']); ?>" data-status="<?php p($_['websiteVerification']) ?>" src="
				<?php
				switch($_['websiteVerification']) {
					case \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS:
						p(image_path('core', 'actions/verifying.svg'));
						break;
					case \OC\Accounts\AccountManager::VERIFIED:
						p(image_path('core', 'actions/verified.svg'));
						break;
					default:
						p(image_path('core', 'actions/verify.svg'));
				}
				?>"
				<?php if($_['websiteVerification'] === \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS || $_['websiteVerification'] === \OC\Accounts\AccountManager::NOT_VERIFIED) print_unescaped(' class="verify-action"') ?>
				>
				<div class="verification-dialog popovermenu bubble menu">
					<div class="verification-dialog-content">
						<p class="explainVerification"></p>
						<p class="verificationCode"></p>
						<p><?php p($l->t('It can take up to 24 hours before the account is displayed as verified.'));?></p>
					</div>
				</div>
			</div>
			<?php } ?>
			<input type="text" name="website" id="website" value="<?php p($_['website']); ?>"
			       placeholder="<?php p($l->t('Link https://…')); ?>"
			       autocomplete="on" autocapitalize="none" autocorrect="off"
				   <?php if(!$_['lookupServerUploadEnabled']) print_unescaped('disabled="1"');  ?>
			/>
			<span class="icon-checkmark hidden"/>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="websitescope" value="<?php p($_['websiteScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<?php } ?>
	<?php if (!empty($_['twitter']) || $_['lookupServerUploadEnabled']) { ?>
	<div class="personal-settings-setting-box">
		<form id="twitterform" class="section">
			<h2>
				<label for="twitter"><?php p($l->t('Twitter')); ?></label>
				<span class="icon-password"/>
			</h2>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<div class="verify <?php if ($_['twitter'] === ''  || $_['twitterScope'] !== 'public') p('hidden'); ?>">
				<img id="verify-twitter" title="<?php p($_['twitterMessage']); ?>" data-status="<?php p($_['twitterVerification']) ?>" src="
				<?php
				switch($_['twitterVerification']) {
					case \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS:
						p(image_path('core', 'actions/verifying.svg'));
						break;
					case \OC\Accounts\AccountManager::VERIFIED:
						p(image_path('core', 'actions/verified.svg'));
						break;
					default:
						p(image_path('core', 'actions/verify.svg'));
				}
				?>"
				<?php if($_['twitterVerification'] === \OC\Accounts\AccountManager::VERIFICATION_IN_PROGRESS || $_['twitterVerification'] === \OC\Accounts\AccountManager::NOT_VERIFIED) print_unescaped(' class="verify-action"') ?>
				>
				<div class="verification-dialog popovermenu bubble menu">
					<div class="verification-dialog-content">
						<p class="explainVerification"></p>
						<p class="verificationCode"></p>
						<p><?php p($l->t('It can take up to 24 hours before the account is displayed as verified.'));?></p>
					</div>
				</div>
			</div>
			<?php } ?>
			<input type="text" name="twitter" id="twitter" value="<?php p($_['twitter']); ?>"
				   placeholder="<?php p($l->t('Twitter handle @…')); ?>"
				   autocomplete="on" autocapitalize="none" autocorrect="off"
				   <?php if(!$_['lookupServerUploadEnabled']) print_unescaped('disabled="1"');  ?>
			/>
			<span class="icon-checkmark hidden"/>
			<?php if($_['lookupServerUploadEnabled']) { ?>
			<input type="hidden" id="twitterscope" value="<?php p($_['twitterScope']) ?>">
			<?php } ?>
		</form>
	</div>
	<?php } ?>
	<span class="msg"></span>
</div>
</div>

<div class="clear"></div>

<div class="section">
    <?php if ($_['activelanguage']['code'] == 'fi') {?>
        <p><b>Huomaa:</b> henkilökohtaisen tilin asetusten ja salasanan hallinta tehdään <a style="color: #007FAD" href="https://sui.csc.fi" target="_blank">CSC:n asiakasportaalissa (SUI)</a>.</p>
    <?php } elseif ($_['activelanguage']['code'] == 'sv') {?>
        <p><b>Notera:</b> hantering av profilen och lösenord sker i <a style="color: #007FAD;" href="https://sui.csc.fi" target="_blank">CSC:s kundportal (SUI)</a>.</p>
    <?php } else { ?>
        <p><b>Note:</b> personal account settings and passwords can be changed in the <a style="color: #007FAD" href="https://sui.csc.fi" target="_blank">CSC Customer Portal (SUI)</a>.</p>
    <?php }?>
</div>

<div id="groups" class="section">
	<h2><?php p($l->t('Groups')); ?></h2>
	<p><?php p($l->t('You are member of the following groups:')); ?></p>
	<p>
	<?php p(implode(', ', $_['groups'])); ?>
	</p>
</div>

<?php if (isset($_['activelanguage'])) { ?>
<form id="language" class="section">
	<h2>
		<label for="languageinput"><?php p($l->t('Language'));?></label>
	</h2>
    <!-- IDA MODIFICATION -->
    <!-- BEGIN ORIGINAL -->
    <!--
    <select id="languageinput" name="lang" data-placeholder="<?php p($l->t('Language'));?>">
        <option value="<?php p($_['activelanguage']['code']);?>">
            <?php p($_['activelanguage']['name']);?>
        </option>
        <?php foreach($_['commonlanguages'] as $language):?>
            <option value="<?php p($language['code']);?>">
                <?php p($language['name']);?>
            </option>
        <?php endforeach;?>
        <optgroup label="??????????????????????????????"></optgroup>
        <?php foreach($_['languages'] as $language):?>
            <option value="<?php p($language['code']);?>">
                <?php p($language['name']);?>
            </option>
        <?php endforeach;?>
    </select>
    <a href="https://www.transifex.com/nextcloud/nextcloud/"
       target="_blank" rel="noreferrer">
        <em><?php p($l->t('Help translate'));?></em>
    </a>
    -->
    <!-- END ORIGINAL -->
    <!-- BEGIN MODIFICATION -->
    <select id="languageinput" name="lang" data-placeholder="<?php p($l->t('Language'));?>">
        <option value="<?php p($_['activelanguage']['code']);?>">
            <?php
                switch ($_['activelanguage']['code']) {
                     case 'fi':
                         p('Suomi');
                         break;
                     case 'sv':
                         p('Svenska');
                         break;
                     default:
                         p('English');
                } ?>
        </option>
        <optgroup label="––––––––––"></optgroup>
        <option value="en">English</option>
        <option value="fi">Suomi</option>
        <option value="sv">Svenska</option>
    </select>
    <!-- END MODIFICATION -->
</form>
<?php } ?>


    <div id="security" class="section">
        <h2><?php p($l->t('Security'));?></h2>
        <p class="settings-hint hidden-when-empty"><?php p($l->t('Web, desktop, mobile clients and app specific passwords that currently have access to your account.'));?></p>
        <table class="icon-loading">
            <thead class="token-list-header">
            <tr>
                <th><?php p($l->t('Device'));?></th>
                <th><?php p($l->t('Last activity'));?></th>
                <th></th>
            </tr>
            </thead>
            <tbody class="token-list">
            </tbody>
        </table>

        <h3><?php p($l->t('App passwords'));?></h3>
        <p class="settings-hint"><?php p($l->t('Here you can generate individual passwords for apps so you don’t have to give out your password. You can revoke them individually too.'));?></p>

        <div id="app-password-form">
            <input id="app-password-name" type="text" placeholder="<?php p($l->t('App name')); ?>">
            <button id="add-app-password" class="button"><?php p($l->t('Create new app password')); ?></button>
        </div>
        <div id="app-password-result" class="hidden">
		<span>
			<?php p($l->t('Use the credentials below to configure your app or device.')); ?>
            <?php p($l->t('For security reasons this password will only be shown once.')); ?>
		</span>
            <div class="app-password-row">
                <span class="app-password-label"><?php p($l->t('Username')); ?></span>
                <input id="new-app-login-name" type="text" readonly="readonly"/>
            </div>
            <div class="app-password-row">
                <span class="app-password-label"><?php p($l->t('Password')); ?></span>
                <input id="new-app-password" type="text" readonly="readonly"/>
                <a class="clipboardButton icon icon-clippy" data-clipboard-target="#new-app-password"></a>
                <button id="app-password-hide" class="button"><?php p($l->t('Done')); ?></button>
            </div>
        </div>
    </div>


<?php foreach($_['forms'] as $form) {
	if (isset($form['form'])) {?>
	<div id="<?php isset($form['anchor']) ? p($form['anchor']) : p('');?>"><?php print_unescaped($form['form']);?></div>
	<?php }
};?>

<div class="section">
	<h2><?php p($l->t('Version'));?></h2>
	<p><a href="<?php print_unescaped($theme->getBaseUrl()); ?>" target="_blank"><?php p($theme->getTitle()); ?></a> <?php p(OC_Util::getHumanVersion()) ?></p>
	<p><?php include('settings.development.notice.php'); ?></p>
</div>

</div>
