<div id="app-navigation">
    <ul class="with-icon">
        <!-- IDA MODIFICATION -->
        <!-- BEGIN ORIGINAL -->
        <!--
		<li id="quota" class="section <?php
        if ($_['quota'] !== \OCP\Files\FileInfo::SPACE_UNLIMITED) {
            ?>has-tooltip" title="<?php p($_['usage_relative'] . '%');
        } ?>">
			<a href="#" class="nav-icon-quota svg">
				<p id="quotatext"><?php
        if ($_['quota'] !== \OCP\Files\FileInfo::SPACE_UNLIMITED) {
            p($l->t('%s of %s used', [$_['usage'], $_['total_space']]));
        }
        else {
            p($l->t('%s used', [$_['usage']]));
        } ?></p>
				<div class="quota-container">
					<div style="width:<?php p($_['usage_relative']); ?>%"
						 <?php if ($_['usage_relative'] > 80): ?>class="quota-warning"<?php endif; ?>>
					</div>
				</div>
			</a>
		</li>
		-->
        <!-- END ORIGINAL -->
        <?php foreach ($_['navigationItems'] as $item) { ?>
            <li data-id="<?php p($item['id']) ?>" class="nav-<?php p($item['id']) ?>">
                <a href="<?php p(isset($item['href']) ? $item['href'] : '#') ?>"
                   class="nav-icon-<?php p($item['icon'] !== '' ? $item['icon'] : $item['id']) ?> svg">
                    <?php p($item['name']); ?>
                </a>
            </li>
        <?php } ?>
    </ul>

    <!-- IDA MODIFICATION -->
    <!-- BEGIN MODIFICATION -->
    <?php if ($l->getLanguageCode() == 'fi') { ?>
        <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
            <p>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/idan-pikaopas"
                   target="_blank">IDAn&nbsp;pikaopas</a><br>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas" target="_blank">IDAn&nbsp;käyttöopas</a>
            </p>
        </div>
        <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 30px;">
            <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
                <b>Huomaa:</b>&nbsp;Tiedostot&nbsp;ovat<br>
                varsinaisessa&nbsp;säilytyksessä<br>
                IDAssa&nbsp;vasta&nbsp;kun&nbsp;ne&nbsp;ovat<br>
                Jäädytetyllä&nbsp;alueella.<br>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas#projektin-datan-sailytysalueet"
                   target="_blank">Lisätietoja&nbsp;...</a>
            </p>
        </div>
    <?php } elseif ($l->getLanguageCode() == 'sv') { ?>
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
                <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide#project-data-storage"
                   target="_blank">Läs mer&nbsp;...</a>
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
                <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide#project-data-storage"
                   target="_blank">More information&nbsp;...</a>
            </p>
        </div>
    <?php } ?>

    <!-- END MODIFICATION -->

    <div id="app-settings">
        <div id="app-settings-header">
            <button class="settings-button" data-apps-slide-toggle="#app-settings-content">
                <?php p($l->t('Settings')); ?>
            </button>
        </div>
        <div id="app-settings-content">
            <div id="files-setting-showhidden">
                <input class="checkbox" id="showhiddenfilesToggle" checked="checked" type="checkbox">
                <label for="showhiddenfilesToggle"><?php p($l->t('Show hidden files')); ?></label>
            </div>
            <!-- IDA MODIFICATION -->
            <!-- BEGIN ORIGINAL -->
            <!--
			<label for="webdavurl"><?php p($l->t('WebDAV')); ?></label>
			<input id="webdavurl" type="text" readonly="readonly" value="<?php p(\OCP\Util::linkToRemote('webdav')); ?>" />
			<em><?php print_unescaped($l->t('Use this address to <a href="%s" target="_blank" rel="noreferrer">access your Files via WebDAV</a>', array(link_to_docs('user-webdav')))); ?></em>
            -->
            <!-- END ORIGINAL -->
        </div>
    </div>
</div>
