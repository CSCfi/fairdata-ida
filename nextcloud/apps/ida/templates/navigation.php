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
-->

<div id="app-navigation">
    <ul id="app-lists">
        <?php foreach ($_['navigations'] as $navigation) { ?>
            <li id="app-list-<?php p($navigation['id']) ?>" <?php if ($_['activeNavigation'] === $navigation['id']) : ?> class="active"<?php endif; ?>>
                <a data-navigation="<?php p($navigation['id']) ?>" href="<?php p($navigation['url']) ?>">
                    <?php p($l->t($navigation['name'])) ?>
                </a>
            </li>
        <?php } ?>
    </ul>

    <?php if($l->getLanguageCode() === 'fi') { ?>
        <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
            <p>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/idan-pikaopas" rel="noopener" target="_blank">IDAn&nbsp;pikaopas</a><br>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas" rel="noopener" target="_blank">IDAn&nbsp;käyttöopas</a>
            </p>
        </div>
        <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 74px;">
            <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
                <b>Huomaa:</b>&nbsp;Tiedostot&nbsp;ovat<br>
                varsinaisessa&nbsp;säilytyksessä<br>
                IDAssa&nbsp;vasta&nbsp;kun&nbsp;ne&nbsp;ovat<br>
                Jäädytetyllä&nbsp;alueella.<br>
                <a style="color: #007FAD;" href="https://www.fairdata.fi/ida/kayttoopas#projektin-datan-sailytysalueet" rel="noopener" target="_blank">Lisätietoja</a>
            </p>
        </div>
    <?php } else { ?>
    <div style="padding-left: 25px; padding-top: 0px; padding-bottom: 20px;">
        <p>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/quick-start-guide" rel="noopener" target="_blank">IDA&nbsp;Quick&nbsp;Start&nbsp;Guide</a><br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide" rel="noopener" target="_blank">IDA&nbsp;User&apos;s&nbsp;Guide</a>
        </p>
        </div>
        <div style="padding: 15px; padding-right: 25px; padding-top: 0px; padding-bottom: 74px;">
            <p style="padding: 7px; border: 1px; border-style:solid; border-color:#555; color:#555; line-height: 120%">
            <b>Note:</b>&nbsp;Files&nbsp;are&nbsp;safely&nbsp;stored<br>
            in&nbsp;the&nbsp;IDA&nbsp;service&nbsp;when&nbsp;they<br>
            are&nbsp;in&nbsp;the&nbsp;Frozen&nbsp;area.<br>
            <a style="color: #007FAD;" href="https://www.fairdata.fi/en/ida/user-guide#project-data-storage" rel="noopener" target="_blank">More information</a>
        </p>
    </div>
    
    <?php } ?>

</div>
