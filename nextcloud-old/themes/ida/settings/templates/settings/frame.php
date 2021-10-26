<?php
/*
 * This file is part of the IDA research data storage service
 * 
 * @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @link     https://research.csc.fi/
 */

/**
 * @copyright Copyright (c) 2016 Arthur Schiwon <blizzz@arthur-schiwon.de>
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
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

style('settings', 'settings');
script('settings', [ 'settings', 'admin', 'log', 'certificates'] );
script('core', 'setupchecks');
script('files', 'jquery.fileupload');

?>

<div id="app-navigation" class="without-app-settings">
	<ul>
		<?php if(!empty($_['forms']['admin'])) { ?>
			<li class="app-navigation-caption"><?php p($l->t('Personal')); ?></li>
		<?php } ?>
		<li>
			<a href="/settings/user">
				<img alt="" src="/core/img/actions/info.svg">
				<span><?php p($l->t('Personal info')); ?></span>
			</a>
		</li>
		<li>
			<a href="/settings/user/security">
				<img alt="" src="/settings/img/password.svg">
				<span><?php p($l->t('Security')); ?></span>
			</a>
		</li>
		<?php
		if(!empty($_['forms']['admin'])) {
			?>
			<li class="app-navigation-caption"><?php p($l->t('Administration')); ?></li>
			<?php
		}
		foreach($_['forms']['admin'] as $form) {
			if (isset($form['anchor'])) {

				$anchor = \OC::$server->getURLGenerator()->linkToRoute('settings.AdminSettings.index', ['section' => $form['anchor']]);
				$class = 'nav-icon-' . $form['anchor'];
				$sectionName = $form['section-name'];
				$active = $form['active'] ? ' class="active"' : '';
		?>
				<li <?php print_unescaped($form['active'] ? ' class="active"' : ''); ?>>
					<a href="<?php p($anchor); ?>">
						<?php if (!empty($form['icon'])) { ?>
							<img alt="" src="<?php print_unescaped($form['icon']); ?>">
							<span><?php p($form['section-name']); ?></span>
						<?php } else { ?>
							<span class="no-icon"><?php p($form['section-name']); ?></span>
						<?php } ?>
					</a>
				</li>
		<?php
			}
		}
		?>
	</ul>
	<div id="ida-server-instance-ip" style="padding-left: 25px; padding-top: 20px; padding-bottom: 20px;">
        <p>
            <span aria-hidden="true">
                <code>Service Node: <?php p(preg_replace('/^.*\./', '', $_SERVER['SERVER_ADDR'])); ?></code>
            </span>
        </p>
    </div>
</div>


<div id="app-content">
	<?php print_unescaped($_['content']); ?>
</div>
