<?php
/*
 * This file is part of the IDA research data storage service
 * 
 * @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @link     https://research.csc.fi/
 */

/**
 * @copyright Copyright (c) 2017 Arthur Schiwon <blizzz@arthur-schiwon.de>
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Thomas Citharel <tcit@tcit.fr>
 *
 * @license GNU AGPL version 3 or any later version
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

/** @var \OCP\IL10N $l */
/** @var array $_ */

script('settings', [
	'usersettings',
	'templates',
	'federationsettingsview',
	'federationscopemenu',
	'settings/personalInfo',
]);
?>

<div id="personal-settings">

	<div class="personal-settings-container" style="display: inline-grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr;">
		<div class="personal-settings-setting-box" style="padding: 10px">
			<h3>
				<label for="displayname"><?php p($l->t('Username')); ?></label>
			</h3>
			<div type="text" id="displayname" name="displayname" style="padding-left: 20px">
				<span><?php if(isset($_['displayName']) && !empty($_['displayName'])) { p($_['displayName']); } else { p($l->t('No display name set')); } ?></span>
			</div>
		</div>

	    <div class="personal-settings-setting-box" style="padding: 10px">
		    <h3>
			    <?php p($l->t('Groups')); ?>
		    </h3>
		    <div style="padding-left: 20px">
		        <p>
			        <?php p(implode(', ', $_['groups'])); ?>
		        </p>
		    </div>
        </div>
	</div>

	<div class="profile-settings-container" style="display: inline-grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr;">

		<div class="personal-settings-setting-box personal-settings-language-box">
			<?php if (isset($_['activelanguage'])) { ?>
				<form id="language" class="section">
					<h3>
						<label for="languageinput"><?php p($l->t('Language'));?></label>
					</h3>
			        <div type="text" style="padding-left: 20px">
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
			        </div>
				</form>
			<?php } ?>
		</div>

		<div class="personal-settings-setting-box personal-settings-locale-box">
			<?php if (isset($_['activelocale'])) { ?>
				<form id="locale" class="section">
					<h3>
						<label for="localeinput"><?php p($l->t('Locale'));?></label>
					</h3>
			        <div type="text" style="padding-left: 20px">
                        <?php
                            switch ($_['activelocale']['code']) {
                                 case 'fi_FI':
                                     p('Suomi');
                                     break;
                                 case 'fi':
                                     p('Suomi');
                                     break;
                                 case 'sv_FI':
                                     p('Svenska');
                                     break;
                                 case 'sv_SE':
                                     p('Svenska');
                                     break;
                                 case 'sv':
                                     p('Svenska');
                                     break;
                                 case 'en_US':
                                     p('English (US)');
                                     break;
                                 case 'en_GB':
                                     p('English (UK)');
                                     break;
                                 case 'en':
                                     p('English');
                                     break;
                                 default:
                                     p($_['activelocale']['code']);
                            } ?>
                    </div>
					<div id="localeexample" class="personal-info icon-timezone">
						<p>
							<span id="localeexample-date"></span> <span id="localeexample-time"></span>
						</p>
						<p id="localeexample-fdow"></p>
					</div>
				</form>
			<?php } ?>
		</div>
		<span class="msg"></span>
	</div>

	<div style="padding-left: 10px; padding-top: 30px;">
        <?php if ($_['activelanguage']['code'] == 'fi') {?>
            <p>CSC-salasanan hallinta tehdään <a style="color: #007FAD" href="https://my.csc.fi" rel="noreferrer noopener" target="_blank">CSC:n asiakasportaalissa</a>.</p>
        <?php } elseif ($_['activelanguage']['code'] == 'sv') {?>
            <p>CSC lösenord sker i <a style="color: #007FAD;" href="https://my.csc.fi" rel="noreferrer noopener" target="_blank">CSC:s kundportal</a>.</p>
        <?php } else { ?>
            <p>CSC passwords can be changed in the <a style="color: #007FAD" href="https://my.csc.fi" rel="noreferrer noopener" target="_blank">CSC Customer Portal</a>.</p>
		<?php }?>
	</div>

	<div style="padding-left: 10px; padding-top: 10px; padding-bottom: 30px;">
        <p lang="en">To change the language, you must log out and select another language from the top right of the home view.</p>
        <p lang="fi">Jos haluat vaihtaa käyttöliittymän kielen, kirjaudu ulos palvelusta ja valitse toinen kieli sivun oikeasta yläkulmasta.</p>
        <p lang="sv">För att ändra språk måste du logga ut och välja ett annat språk högst upp till höger i hemvyn.</p>
	</div>

	<script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>">
        document.title = "Personal info - Settings - IDA"; 
    </script>
</div>
