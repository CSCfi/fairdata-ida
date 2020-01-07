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
    <link rel="icon" href="<?php print_unescaped(image_path('', 'favicon.ico')); /* IE11+ supports png */ ?>">
    <link rel="apple-touch-icon-precomposed" href="<?php print_unescaped(image_path('', 'favicon-touch.png')); ?>">
    <link rel="mask-icon" sizes="any" href="<?php print_unescaped(image_path('', 'favicon-mask.svg')); ?>" color="<?php p($theme->getColorPrimary()); ?>">
    <?php if (isset($_['inline_ocjs'])) : ?>
    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" type="text/javascript">
        <?php print_unescaped($_['inline_ocjs']); ?>
    </script>
    <?php endif; ?>
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
</head>

<body id="body-login">
    <div id="ida-body-login">
        <table style="max-width: 1280px">
            <tr>
                <td rowspan="5">
                    <div id="ida-login" class="wrapper">
                        <div class="v-align">
                            <?php if (strpos($_SERVER['REQUEST_URI'], '/s/NOT_FOR_PUBLICATION_') !== false) : ?>
                            <div class="local-login-form">
                                <p id="ida-local-login-form-header">
                                    <?php p($l->t('Enter temporary share password:')); ?>
                                </p>
                                <?php print_unescaped($_['content']); ?>
                            </div>
                            <?php else : ?>
                            <div class="haka-login">
                                <?php if (\OC::$server->getAppManager()->isEnabledForUser('user_saml')) {
                                        print_unescaped('<a href="');
                                        $shib_target = \OC::$server->getURLGenerator()->linkToRouteAbsolute('user_saml.SAML.login')
                                            . '?requesttoken='
                                            . urlencode(\OC::$server->getCsrfTokenManager()->getToken()->getEncryptedValue());
                                        print_unescaped($shib_target);
                                        print_unescaped('" ><img id="haka-login-button" src="/apps/ida/img/Haka_login_vaaka.jpg"></a>');
                                    } ?>
                            </div>
                            <div class="local-login-form">
                                <?php print_unescaped($_['content']); ?>
                                <p id="ida-local-login-form-footer">
                                    <?php p($l->t('Personal CSC accounts are created and managed in')) ?>
                                    <br><a href="https://sui.csc.fi/" target="_blank">
                                        <?php p($l->t('CSC Customer Portal')) ?>
                                    </a>
                                </p>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </td>
                <td colspan="2">
                    <div id="header">
                        <div class="logo">
                            <img src="<?php p($theme->getLogo()); ?>" />
                        </div>
                    </div>
                </td>
            </tr>
            <tr>
                <td class="ida-login-heading">
                    What is IDA?
                </td>
                <td class="ida-login-heading">
                    Mikä IDA on?
                </td>
            </tr>
            <tr>
                <td class="ida-login-text">
                    IDA is a research data storage service offered free of charge to its users.
                    <br><br>
                    The service is intended for stable research data, both raw data and processed datasets.
                </td>
                <td class="ida-login-text">
                    IDA on tutkimusdatan säilytyspalvelu, joka tarjotaan loppukäyttäjille maksuttomasti.
                    <br><br>
                    Palvelu on tarkoitettu tutkimusaineistoihin liittyvälle datalle.
                </td>
            </tr>
            <tr>
                <td class="ida-login-heading">
                    Who is IDA for?
                </td>
                <td class="ida-login-heading">
                    Kenelle IDA on tarkoitettu?
                </td>
            </tr>
            <tr>
                <td class="ida-login-text">
                    The service is offered to Finnish universities and polytechnics, research institutes and research funded by the Academy of Finland.
                    <br><br>
                    The users of the service can belong to one or more projects with which they collaborate.
                    <a href="https://www.fairdata.fi/en/ida/" target="_blank">More information...</a>
                    <br><br><br><br><br><br>
                </td>
                <td class="ida-login-text">
                    Palvelua tarjotaan Suomen korkeakouluille, tutkimuslaitoksille ja Suomen Akatemian rahoittamalle tutkimukselle.
                    <br><br>
                    Käyttäjät voivat kuulua yhteen tai useampaan palvelua käyttävään projektiin.
                    <a href="https://www.fairdata.fi/ida/" target="_blank">Lisätietoa...</a>
                </td>
            </tr>
        </table>
    </div>
    <footer>
        IDA is organized by the Finnish Ministry of Education and Culture.
        The service is produced by CSC — IT Center for Science
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <img style="height: 50px; vertical-align:middle;" src="/apps/ida/img/csc-logo.png">
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a>
    </footer>
</body>

</html>