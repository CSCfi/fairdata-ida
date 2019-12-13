<!--
This file is part of the IDA research data storage service
 
@author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@link     https://research.csc.fi/
-->

<div id="app-navigation">
	<ul class="with-icon">

		<?php

		$pinned = 0;
		foreach ($_['navigationItems'] as $item) {
			$pinned = NavigationListElements($item, $l, $pinned);
		}
		?>
	</ul>

    <?php if($l->getLanguageCode() == 'fi') { ?>
    <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
        <p>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/idan-pikaopas" target="_blank">IDAn&nbsp;pikaopas</a><br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas" target="_blank">IDAn&nbsp;käyttöopas</a>
        </p>
    </div>
    <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 30px;">
        <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
            <b>Huomaa:</b>&nbsp;Tiedostot&nbsp;ovat<br>
            varsinaisessa&nbsp;säilytyksessä<br>
            IDAssa&nbsp;vasta&nbsp;kun&nbsp;ne&nbsp;ovat<br>
            Jäädytetyllä&nbsp;alueella.<br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas#projektin-datan-sailytysalueet" target="_blank">Lisätietoja&nbsp;...</a>
        </p>
    </div>
    <?php } elseif($l->getLanguageCode() == 'sv') { ?>
    <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
        <p>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/quick-start-guide" target="_blank">IDA&nbsp;Quick&nbsp;Start&nbsp;Guide</a><br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide" target="_blank">IDA&nbsp;User&apos;s&nbsp;Guide</a>
        </p>
        </div>
        <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 30px;">
            <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
            <b>Notera:</b>&nbsp;Filerna&nbsp;är&nbsp;i&nbsp;egentlig<br>
            lagring&nbsp;först&nbsp;då&nbsp;de&nbsp;är&nbsp;frysta.<br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide#project-data-storage" target="_blank">Läs mer&nbsp;...</a>
        </p>
    </div>
    <?php } else { ?>
    <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
        <p>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/quick-start-guide" target="_blank">IDA&nbsp;Quick&nbsp;Start&nbsp;Guide</a><br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide" target="_blank">IDA&nbsp;User&apos;s&nbsp;Guide</a>
        </p>
        </div>
        <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 30px;">
            <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
            <b>Note:</b>&nbsp;Files&nbsp;are&nbsp;safely&nbsp;stored<br>
            in&nbsp;the&nbsp;IDA&nbsp;service&nbsp;when&nbsp;they<br>
            are&nbsp;in&nbsp;the&nbsp;Frozen&nbsp;area.<br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide#project-data-storage" target="_blank">More information&nbsp;...</a>
        </p>
    </div>
	<?php } ?>
	
	<div id="app-settings" style="visibility: hidden">
		<div id="app-settings-header">
			<button class="settings-button"
					data-apps-slide-toggle="#app-settings-content">
				<?php p($l->t('Settings')); ?>
			</button>
		</div>
		<div id="app-settings-content">
			<div id="files-setting-showhidden">
				<input class="checkbox" id="showhiddenfilesToggle"
					   checked="checked" type="checkbox" checked>
				<label for="showhiddenfilesToggle"><?php p($l->t('Show hidden files')); ?></label>
			</div>
		</div>
	</div>

</div>


<?php

/**
 * Prints the HTML for a single Entry.
 *
 * @param $item The item to be added
 * @param $l Translator
 * @param $pinned IntegerValue to count the pinned entries at the bottom
 *
 * @return int Returns the pinned value
 */
function NavigationListElements($item, $l, $pinned) {
	strpos($item['classes'] ?? '', 'pinned') !== false ? $pinned++ : '';
	?>
	<li
		data-id="<?php p($item['id']) ?>"
		<?php if (isset($item['dir'])) { ?> data-dir="<?php p($item['dir']); ?>" <?php } ?>
		<?php if (isset($item['view'])) { ?> data-view="<?php p($item['view']); ?>" <?php } ?>
		<?php if (isset($item['expandedState'])) { ?> data-expandedstate="<?php p($item['expandedState']); ?>" <?php } ?>
		class="nav-<?php p($item['id']) ?>
		<?php if (isset($item['classes'])) { p($item['classes']); } ?>
		<?php p($pinned === 1 ? 'first-pinned' : '') ?>
		<?php if (isset($item['defaultExpandedState']) && $item['defaultExpandedState']) { ?> open<?php } ?>"
		<?php if (isset($item['folderPosition'])) { ?> folderposition="<?php p($item['folderPosition']); ?>" <?php } ?>>

		<a href="<?php p(isset($item['href']) ? $item['href'] : '#') ?>"
		   class="nav-icon-<?php p(isset($item['icon']) && $item['icon'] !== '' ? $item['icon'] : $item['id']) ?> svg"><?php p($item['name']); ?></a>


		<?php
		NavigationElementMenu($item);
		if (isset($item['sublist'])) {
			?>
			<button class="collapse app-navigation-noclose" <?php if (sizeof($item['sublist']) == 0) { ?> style="display: none" <?php } ?>></button>
			<ul id="sublist-<?php p($item['id']); ?>">
				<?php
				foreach ($item['sublist'] as $item) {
					$pinned = NavigationListElements($item, $l, $pinned);
				}
				?>
			</ul>
		<?php } ?>
	</li>


	<?php
	return $pinned;
}

/**
 * Prints the HTML for a dotmenu.
 *
 * @param $item The item to be added
 *
 * @return void
 */
function NavigationElementMenu($item) {
	if (isset($item['menubuttons']) && $item['menubuttons'] === 'true') {
		?>
		<div id="dotmenu-<?php p($item['id']); ?>"
			 class="app-navigation-entry-utils" <?php if (isset($item['enableMenuButton']) && $item['enableMenuButton'] === 0) { ?> style="display: none"<?php } ?>>
			<ul>
				<li class="app-navigation-entry-utils-menu-button svg">
					<button id="dotmenu-button-<?php p($item['id']) ?>"></button>
				</li>
			</ul>
		</div>
		<div id="dotmenu-content-<?php p($item['id']) ?>"
			 class="app-navigation-entry-menu">
			<ul>

			</ul>
		</div>
	<?php }
}
