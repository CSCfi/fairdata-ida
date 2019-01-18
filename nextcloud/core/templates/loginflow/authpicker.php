<?php
/**
 * @copyright Copyright (c) 2017 Lukas Reschke <lukas@statuscode.ch>
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

script('core', 'login/authpicker');
style('core', 'login/authpicker');

/** @var array $_ */
/** @var \OCP\IURLGenerator $urlGenerator */
$urlGenerator = $_['urlGenerator'];
?>

<div class="picker-window">
	<p class="info">
		<?php p($l->t('You are about to grant "%s" access to your %s account.', [$_['client'], $_['instanceName']])) ?>
	</p>

	<br/>

	<p id="redirect-link">
		<a href="<?php p($urlGenerator->linkToRouteAbsolute('core.ClientFlowLogin.redirectPage', ['stateToken' => $_['stateToken'], 'clientIdentifier' => $_['clientIdentifier'], 'oauthState' => $_['oauthState']])) ?>">
			<input type="submit" class="login primary icon-confirm-white" value="<?php p('Grant access') ?>">
		</a>
	</p>

	<fieldset id="app-token-login-field" class="hidden">
		<p class="grouptop">
			<input type="text" name="user" id="user" placeholder="<?php p($l->t('Username')) ?>">
			<label for="user" class="infield"><?php p($l->t('Username')) ?></label>
		</p>
		<p class="groupbottom">
			<input type="password" name="password" id="password" placeholder="<?php p($l->t('App token')) ?>">
			<label for="password" class="infield"><?php p($l->t('Password')) ?></label>
		</p>
		<input type="hidden" id="serverHost" value="<?php p($_['serverHost']) ?>" />
		<input id="submit-app-token-login" type="submit" class="login primary icon-confirm-white" value="<?php p('Grant access') ?>">
	</fieldset>
</div>

<?php if(empty($_['oauthState'])): ?>
<a id="app-token-login" class="warning" href="#"><?php p($l->t('Alternative login using app token')) ?></a>
<?php endif; ?>
