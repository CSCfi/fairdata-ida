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

<?php
    $CURRENT_LANGUAGE = $l->getLanguageCode();
    $CURRENT_LANGUAGE = $CURRENT_LANGUAGE ? substr($CURRENT_LANGUAGE, 0 , 2) : 'en';
    $IDA_LANGUAGES = array(
        array(
            "short" => "en",
            "full" => "English (EN)"
        ),
        array(
            "short" => "fi",
            "full" => "Finnish (FI)"
        ),
        array(
            "short" => "sv",
            "full" => "Swedish (SV)"
        )
    );

    function SSOActive() {
        return \OC::$server->getSystemConfig()->getValue('SSO_API') != '';
    }

    function localLoginActive() {
        return \OC::$server->getSystemConfig()->getValue('LOCAL_LOGIN') == true;
    }
?>

<!DOCTYPE html>
<html class="ng-csp" data-placeholder-focus="false" lang="<?php p($_['language']); ?>">

<head data-requesttoken="<?php p($_['requesttoken']); ?>">
    <meta charset="utf-8">
    <title>
        <?php p($theme->getTitle()); ?>
    </title>
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="referrer" content="never">
    <meta name="viewport" content="width=device-width, minimum-scale=1.0, maximum-scale=1.0">
    <meta name="apple-itunes-app" content="app-id=<?php p($theme->getiTunesAppId()); ?>">
    <meta name="theme-color" content="<?php p($theme->getColorPrimary()); ?>">
    <link rel="icon" type="image/png" href="<?php print_unescaped(image_path('', 'favicon.png')); /* IE11+ supports png */ ?>">
    <link rel="apple-touch-icon-precomposed" href="<?php print_unescaped(image_path('', 'favicon.png')); ?>">
    <link rel="mask-icon" sizes="any" href="<?php print_unescaped(image_path('', 'favicon-mask.svg')); ?>" color="<?php p($theme->getColorPrimary()); ?>">
    <?php if (isset($_['inline_ocjs'])) : ?>
        <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" type="text/javascript">
            <?php print_unescaped($_['inline_ocjs']); ?>
        </script>
    <?php endif; ?>
    <link rel="stylesheet" href="/themes/ida/core/css/fairdata.css">
    <?php foreach ($_['cssfiles'] as $cssfile) : ?>
        <link rel="stylesheet" href="<?php print_unescaped($cssfile); ?>">
    <?php endforeach; ?>
    <?php foreach ($_['printcssfiles'] as $cssfile) : ?>
        <link rel="stylesheet" href="<?php print_unescaped($cssfile); ?>" media="print">
    <?php endforeach; ?>
    <?php foreach ($_['jsfiles'] as $jsfile) : ?>
        <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="<?php print_unescaped($jsfile); ?>"></script>
    <?php endforeach; ?>
    <?php print_unescaped($_['headers']); ?>

    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="/themes/ida/core/js/ida-guest.js"></script>
    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="<?php p(\OC::$server->getSystemConfig()->getValue('SSO_API')); ?>/notification.js"></script>
    <link rel="stylesheet" href="/themes/ida/core/css/ida-guest.css">

    <?php
        # We need to increase container width if local login is enabled, as there needs to fit more columns
        if(localLoginActive()) :
    ?>
        <style type="text/css">.fd-content{width: 100%; max-width: 1500px;}</style>
    <?php endif; ?>
    <style type="text/css">
        body {
            font: 500 16px/25px "Lato" !important;
            color: black;
        }
    </style>
</head>
<body id="body-login">
    <div class="language-selector-mobile" id="languageChoiceDropdown">
        <div class="language-choice-toggle active">
            <?php
            $activeLanguageIndex = array_search($CURRENT_LANGUAGE, array_column($IDA_LANGUAGES, 'short'));
            if ($activeLanguageIndex !== FALSE) {
                p($IDA_LANGUAGES[$activeLanguageIndex]["full"]);
            }
            ?>
            <img src="<?php print_unescaped(image_path('', 'expand.png')); ?>" id="expandIcon" alt="Expand">
        </div>
        <div id="languageChoices" class="language-choices">
            <?php
            $languagesToDisplay = array_filter($IDA_LANGUAGES, function($lang) use ($CURRENT_LANGUAGE) {
                return $lang["short"] != $CURRENT_LANGUAGE;
            });
            foreach ($languagesToDisplay as $lang) {
                print_unescaped('<div class="language-choice" role="button" tabindex="0" data-language-code="'.$lang["short"].'">'.$lang["full"].'</div>');
            }
            ?>
        </div>
    </div>
    <div class="fd-header container-fluid">
        <div class="row no-gutter">
            <div class="col-8">
                <img src="<?php print_unescaped(image_path('', 'ida-logo-header.png')); ?>" alt="Fairdata logo" class="logo">
            </div>
            <div class="language-selector-wrapper col-4">
                <?php if (SSOActive()) : ?>
                    <a href="<?php p(\OC::$server->getSystemConfig()->getValue('SSO_API')) ?>/login?service=IDA&redirect_url=<?php p(\OC::$server->getSystemConfig()->getValue('IDA_HOME')) ?>">
                        <button class="fd-button login-button"><?php p($l->t("Log in")); ?></button>
                    </a>
                <?php endif; ?>
                <div class="language-selector-container">
                    <?php
                    foreach ($languagesToDisplay as $lang) {
                        print_unescaped('<span class="language-choice" role="button" tabindex="0" data-language-code="'.$lang["short"].'">'.$lang["short"].'</span>');
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>
    <div class="fd-content container">
        <div class="row">
            <?php if(localLoginActive()) : ?>
                <div class="col-lg-4 col-md-12 flex-center-md">
                    <div id="ida-login" class="wrapper">
                        <div class="v-align">
                            <?php if (strpos($_SERVER['REQUEST_URI'], '/s/NOT_FOR_PUBLICATION_') !== false) : ?>
                                <div class="local-login-form">
                                    <p id="ida-local-login-form-header">
                                        <?php p($l->t('Enter temporary share password:')); ?>
                                    </p>
                                    <?php print_unescaped($_['content']); ?>
                                </div>
                            <?php elseif (!SSOActive() || localLoginActive()) : ?>
                                <div class="local-login-form">
                                    <?php print_unescaped($_['content']); ?>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            <?php endif; ?>
            <?php if ($CURRENT_LANGUAGE == "fi") : ?>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12">
                <h2>Tervetuloa Fairdata IDA:han</h2>
                <p>
                    Fairdata IDA on opetus- ja kulttuuriministeriön järjestämä jatkuva tutkimustietojen
                    tallennuspalvelu. Palvelu tarjotaan ilmaiseksi suomalaisille yliopistoille ja
                    ammattikorkeakouluille, tutkimuslaitoksille sekä Suomen Akatemian rahoittamalle tutkimukselle.
                </p>
                    IDA mahdollistaa tutkimusdatan lataamisen, järjestämisen ja jakamisen projektiryhmässä
                    sekä tietojen tallentamisen muuttumattomassa tilassa. IDA: han tallennetut tiedot voidaan
                    sisällyttää tutkimustietokokonaisuuksiin, jotka kuvataan ja saatetaan julkisesti saataville
                    ladattaviksi muiden Fairdata-palveluiden kautta.
                </p>
                <p>
                    <a href="https://www.fairdata.fi/services/ida/" target="_blank">Lue lisää IDA:sta</a>
                </p>
            </div>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12 padding-top">
                <div class="row card-login active">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>IDA</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Tallennat tietoja IDA: han. Voit järjestää ja jäädyttää tietoja lopullisessa muuttumattomassa tilassa.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Qvain</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Jäädytyksen jälkeen valitset ja kuvaat tietosi ja julkaista ne tietojoukkona Qvainin kautta.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Etsin</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Voit löytää ja ladata tietojoukkoja Etsinin kautta.</p>
                    </div>
                </div>
            </div>
            <?php elseif ($CURRENT_LANGUAGE == "sv") : ?>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12">
                <h2>Välkommen till Fairdata IDA</h2>
                <p>
                    Fairdata IDA är en kontinuerlig forskningsdatalagringstjänst som organiseras av ministeriet
                    för utbildning och kultur. Tjänsten erbjuds gratis till finska universitet och universitet
                    för tillämpade vetenskaper, forskningsinstitut samt forskning finansierad av Finlands akademi.
                </p>
                <p>
                    IDA möjliggör överföring, organisering och delning av forskningsdata inom en projektgrupp
                    och lagring av uppgifterna i ett oändligt tillstånd. Uppgifterna lagrade i IDA kan inkluderas
                    i forskningsdatasätt som beskrivs och göras offentligt tillgängliga för nedladdning via andra
                    Fairdata-tjänster.
                </p>
                <p>
                    <a href="https://www.fairdata.fi/en/services/ida/" target="_blank">Läs mer om IDA  (på engelska)</a>
                </p>
            </div>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12 padding-top">
                <div class="row card-login active">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>IDA</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Du laddar upp och lagrar data i IDA. Du kan organisera och frysa data i ett slutligt obestämt tillstånd.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Qvain</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Efter frysning väljer du och beskriver dina data och publicerar dem som en datasats genom Qvain.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Etsin</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>Du kan upptäcka och ladda ner datasätt via Etsin.</p>
                    </div>
                </div>
            </div>
            <?php else : ?>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12">
                <h2>Welcome to Fairdata IDA</h2>
                <p>
                    Fairdata IDA is a continuous research data storage service organized by the Ministry of
                    Education and Culture. The service is offered free of charge to Finnish universities and
                    universities of applied sciences, research institutes, as well as research funded by the
                    Academy of Finland.
                </p>
                <p>
                    IDA enables uploading, organizing and sharing research data within a project group and
                    storing the data in an immutable state. The data stored in IDA can be included in research
                    datasets which are described and made publicly available for download via other Fairdata
                    services.
                <p>
                    <a href="https://www.fairdata.fi/en/services/ida/" target="_blank">Read more about IDA</a>
                </p>
            </div>
            <div class="<?php if(localLoginActive()) p('col-lg-4'); else p('col-lg-6');?> col-md-12 padding-top">
                <div class="row card-login active">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>IDA</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>You upload and store data in IDA. You can organize and freeze data in a final immutable state.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Qvain</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>After freezing, you select and describe your data and publish it as a dataset through Qvain.</p>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 align-center">
                        <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow" alt="Arrow">
                    </div>
                </div>
                <div class="row card-login">
                    <div class="col-sm-2 col-6 align-center align-right-sm">
                        <span>Etsin</span>
                    </div>
                    <div class="col-sm-2 col-6 align-center align-left-sm">
                        <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>" alt="IDA icon">
                    </div>
                    <div class="col-sm-8 col-12">
                        <p>You can discover and download datasets through Etsin.</p>
                    </div>
                </div>
            </div>
            <?php endif; ?>
        </div>
    </div>
    <div class="fd-footer container-fluid">
        <div class="row no-gutters">
            <?php if ($CURRENT_LANGUAGE == "fi") : ?>
            <div class="col col-lg-4 col-md-12 col-sm-12 col-12">
                <span>Fairdata</span>
                <p>
                    Fairdata-palvelut järjestää <strong>opetus- ja kulttuuriministerö </strong> ja toimittaa
                    <strong>CSC – Tieteen tietotekniikan keskus Oy</strong>
                </p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                <span>Tietoa</span>
                <p><a href="https://www.fairdata.fi/hyodyntaminen/kayttopolitiikat-ja-ehdot/" target="_blank">Käyttöpolitiikat ja ehdot

</a></p>
                <p><a href="https://www.fairdata.fi/en/contracts-and-privacy/" target="_blank">Sopimukset ja tietosuoja</a></p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Saavutettavuus</span>
                <p><a href="" target="_blank">Saavutettavuus</a></p>
                <p><a href="#" target="_blank">Sivukartta</a></p>
            </div>
            <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Ota yhteyttä</span>
                <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
            </div>
            <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                <span>Seuraa</span>
                <p><a href="https://twitter.com/Fairdata_fi" target="_blank">Twitter</a></p>
                <p><a href="https://www.fairdata.fi/en/news/" target="_blank">Uutiset</a></p>
            </div>
            <?php elseif ($CURRENT_LANGUAGE == "sv") : ?>
            <div class="col col-lg-4 col-md-12 col-sm-12 col-12">
                <span>Fairdata</span>
                <p>
                    Fairdata-tjänsterna erbjuds av <strong>ministeriet för utbildning och kultur</strong>
                    och produceras av <strong>CSC - IT Center for Science Ltd.</strong>
                </p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                <span>Information</span>
                <p><a href="https://www.fairdata.fi/en/terms-and-policies/" target="_blank">Villkor och policyer</a></p>
                <p><a href="https://www.fairdata.fi/hyodyntaminen/sopimukset/" target="_blank">Kontrakt och integritet</a></p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Tillgänglighet</span>
                <p><a href="" target="_blank">Tillgänglighet uttalande</a></p>
                <p><a href="#" target="_blank">Sitemap</a></p>
            </div>
            <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Kontakt</span>
                <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
            </div>
            <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                <span>Följ</span>
                <p><a href="https://twitter.com/Fairdata_fi" target="_blank">Twitter</a></p>
                <p><a href="https://www.fairdata.fi/ajankohtaista/" target="_blank">Nyheter</a></p>
            </div>
            <?php else : ?>
            <div class="col col-lg-4 col-md-12 col-sm-12 col-12">
                <span>Fairdata</span>
                <p>
                    The Fairdata services are offered by the<strong> Ministry of Education and
                    Culture </strong>and produced by<strong> CSC – IT Center for Science Ltd.</strong>
                </p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                <span>Information</span>
                <p><a href="https://www.fairdata.fi/en/terms-and-policies/" target="_blank">Terms and Policies</a></p>
                <p><a href="https://www.fairdata.fi/en/contracts-and-privacy/" target="_blank">Contracts and Privacy</a></p>
            </div>
            <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Accessibility</span>
                <p><a href="" target="_blank">Accessibility statement</a></p>
                <p><a href="#" target="_blank">Sitemap</a></p>
            </div>
            <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                <span>Contact</span>
                <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
            </div>
            <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                <span>Follow</span>
                <p><a href="https://twitter.com/Fairdata_fi" target="_blank">Twitter</a></p>
                <p><a href="https://www.fairdata.fi/en/news/" target="_blank">What's new</a></p>
            </div>
            <?php endif; ?>
        </div>
    </div>
</body>

</html>