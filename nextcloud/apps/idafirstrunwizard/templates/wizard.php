<?php

/**
 * @var array        $_
 * @var \OCP\IL10N   $l
 * @var \OC_Defaults $theme
 */
/*
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2018 Ministry of Education and Culture, Finland
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License,
 * or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 * @author    CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @license   GNU Affero General Public License, version 3
 * @link      https://research.csc.fi/
 */

$CURRENT_LANGUAGE = null;

if (array_key_exists('HTTP_HOST', $_SERVER)) {
	$domain = $_SERVER['HTTP_HOST'];
	$domain = substr($domain, strpos($domain, ".") + 1);
	$domain = preg_replace('/[^a-zA-Z0-9]/', '_', $domain);
	$cookie = $domain . '_fd_language';
	if (array_key_exists($cookie, $_COOKIE)) {
		$CURRENT_LANGUAGE = $_COOKIE[$cookie];
	}
}

if (!$CURRENT_LANGUAGE) {
    $CURRENT_LANGUAGE = substr($l->getLanguageCode(), 0, 2);
}

if ($CURRENT_LANGUAGE != 'en' && $CURRENT_LANGUAGE != 'fi' && $CURRENT_LANGUAGE != 'sv') {
    $CURRENT_LANGUAGE = 'all';
}

?>
<div id="idafirstrunwizard">

    <div class="idafirstrunwizard-header">
        <a id="closeWizard" class="close">
            <img class="svg" src="<?php p(image_path('core', 'actions/view-close.svg')); ?>">
        </a>
    </div>

    <div class="idafirstrunwizard-content">

        <?php if ($CURRENT_LANGUAGE == "en" || $CURRENT_LANGUAGE == 'all') : ?>
            <h2>
                We hate reading manuals!<br>You probably do too, but...
            </h2>
            <p>
                There are a few special concepts, terms, and features which you should understand to
                get up to speed quickly with the IDA service.
            </p>
            <p>
                We promise it won't take long, and you
                can review the full user guide later, if you like.
            </p>
            <p>
                Read the <a href="https://www.fairdata.fi/en/ida/quick-start-guide" rel="noreferrer noopener" target="_blank">IDA Quick Start Guide</a>
            </p>
        <?php endif; ?>

        <?php if ($CURRENT_LANGUAGE == "fi" || $CURRENT_LANGUAGE == 'all') : ?>
            <h2>
                Käyttöoppaiden lukeminen on tylsää!<br>Niin varmasti sinunkin mielestäsi, mutta...
            </h2>
            <p>
                Muutaman palvelukohtaisen termin ja ominaisuuden ymmärtäminen helpottaa kuitenkin huomattavasti IDA-palvelun käyttöönottoa.
            </p>
            <p>
                Näihin tutustuminen on nopeaa. Voit halutessasi myöhemmin tutustua laajempaan käyttöoppaaseen.
            </p>
            <p>
                Lue <a href="https://www.fairdata.fi/ida/idan-pikaopas" rel="noreferrer noopener" target="_blank">IDAn pikaopas</a>
            </p>
        <?php endif; ?>

        <?php if ($CURRENT_LANGUAGE == "sv" || $CURRENT_LANGUAGE == 'all') : ?>
            <h2>
                Vi ogillar att läsa manualer!<br>Säkert du också, men...
            </h2>
            <p>
                Det finns ett par speciella koncept, termer och funktioner som det underlättar att förstå, före du börjar använda IDA-tjänsten.
            </p>
            <p>
                Detta tar inte länge och du kan gå igenom den fullständiga användarguiden senare, om du vill.
            </p>
            <p>
                Läs <a href="https://www.fairdata.fi/en/ida/quick-start-guide" target="_blank">IDA:s snabbstartguide (på engelska)</a>
            </p>
        <?php endif; ?>

    </div>

</div>
</div>