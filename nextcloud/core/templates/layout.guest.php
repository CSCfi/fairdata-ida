<?php

use \Firebase\JWT\JWT;

if (isset($_GET['language'])) {
    $CURRENT_LANGUAGE = $_GET['language'];
}
else {
    $CURRENT_LANGUAGE = 'en';
}

if ($CURRENT_LANGUAGE != 'en' && $CURRENT_LANGUAGE != 'fi' && $CURRENT_LANGUAGE != 'sv') {
    if (array_key_exists('HTTP_HOST', $_SERVER)) {
        $hostname = $_SERVER['HTTP_HOST'];
        $domain = substr($hostname, strpos($hostname, ".") + 1);
        $prefix = preg_replace('/[^a-zA-Z0-9]/', '_', $domain);
        $cookie = $prefix . '_fd_sso_session';
        if (array_key_exists($cookie, $_COOKIE)) {
            $key = \OC::$server->getSystemConfig()->getValue('SSO_KEY');
			try {
                $session = @JWT::decode($_COOKIE[$cookie], $key, array('HS256'));
		    } catch (\Exception $e) {
			    $session = null;
		    }
            if ($session && $session->language) {
                $CURRENT_LANGUAGE = $session->language;
            }
        }
    }
}

if ($CURRENT_LANGUAGE != 'en' && $CURRENT_LANGUAGE != 'fi' && $CURRENT_LANGUAGE != 'sv') {
    $CURRENT_LANGUAGE = substr($l->getLanguageCode(), 0, 2);
}

if ($CURRENT_LANGUAGE != 'en' && $CURRENT_LANGUAGE != 'fi' && $CURRENT_LANGUAGE != 'sv') {
    $CURRENT_LANGUAGE = 'en';
}

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

function SSOActive()
{
    if (\OC::$server->getSystemConfig()->getValue('SSO_AUTHENTICATION') === true) {
        return true;
    }
    if (isset($_GET['sso_authentication'])) {
        if ($_GET['sso_authentication'] === 'true') {
            return true;
        }
    }
    return false;
}

function FDWEActive()
{
    return \OC::$server->getSystemConfig()->getValue('FDWE_URL', null) != null;
}

function localLoginActive()
{
    if (!SSOActive()) {
        return true;
    }
    if (isset($_GET['local_login'])) {
        if ($_GET['local_login'] === 'true') {
            return true;
        }
    }
    return \OC::$server->getSystemConfig()->getValue('LOCAL_LOGIN') === true;
}

function localLoginOrSharePasswordActive()
{
    return (localLoginActive() || strpos($_SERVER['REQUEST_URI'], '/s/NOT_FOR_PUBLICATION_') !== false);
}

?>

<!DOCTYPE html>
<html class="ng-csp" data-placeholder-focus="false" lang="<?php p($_['language']); ?>" data-locale="<?php p($_['locale']); ?>" >
	<head
    <?php if ($_['user_uid']) { ?>
	data-user="<?php p($_['user_uid']); ?>" data-user-displayname="<?php p($_['user_displayname']); ?>"
    <?php } ?>
    data-requesttoken="<?php p($_['requesttoken']); ?>">
	<meta charset="utf-8">
	<title>
	<?php p($theme->getTitle()); ?>
	</title>
	<script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="/core/js/jquery-2.2.4.js"></script>
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
	<?php if ($theme->getiTunesAppId() !== '') { ?>
	<meta name="apple-itunes-app" content="app-id=<?php p($theme->getiTunesAppId()); ?>">
	<?php } ?>
	<meta name="theme-color" content="<?php p($theme->getColorPrimary()); ?>">
	<link rel="icon" href="<?php print_unescaped(image_path('', 'favicon.ico')); /* IE11+ supports png */ ?>">
	<link rel="apple-touch-icon" href="<?php print_unescaped(image_path('', 'favicon-touch.png')); ?>">
	<link rel="mask-icon" sizes="any" href="<?php print_unescaped(image_path('', 'favicon-mask.svg')); ?>" color="<?php p($theme->getColorPrimary()); ?>">
	<link rel="manifest" href="<?php print_unescaped(image_path('', 'manifest.json')); ?>">
	<?php emit_css_loading_tags($_); ?>
	<?php emit_script_loading_tags($_); ?>
	<link rel="stylesheet" href="/themes/ida/core/css/fairdata.css">
	<script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="/themes/ida/core/js/ida-guest.js"></script>

    <?php if (SSOActive()) : ?>
	<link nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" rel="stylesheet" href="<?php p(\OC::$server->getSystemConfig()->getValue('SSO_API')); ?>/notification.css">
	<script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="<?php p(\OC::$server->getSystemConfig()->getValue('SSO_API')); ?>/notification.js"></script>
    <?php endif; ?>

    <link rel="stylesheet" href="/themes/ida/core/css/ida-guest.css">

    <?php
    # We need to increase container width if local login is enabled, as there needs to fit more columns
    if (localLoginOrSharePasswordActive()) :
    ?>
        <style type="text/css">
            .fd-content {
                width: 100%;
                max-width: 1500px;
            }
        </style>
    <?php endif; ?>
    <style type="text/css">
        body {
            font: 500 16px/25px "Lato" !important;
            color: black;
        }
    </style>

    <?php if (FDWEActive()) : ?>
    <meta name="fdwe-service" content="IDA">
    <?php if (strpos($_SERVER["REQUEST_URI"], "NOT_FOR_PUBLICATION") !== false ) : ?>
    <meta name="fdwe-scope" content="FILES / SHARE / ACCESS / PASSWORD">
    <?php else : ?>
    <meta name="fdwe-scope" content="HOME">
    <?php endif; ?>
    <script nonce="<?php p(\OC::$server->getContentSecurityPolicyNonceManager()->getNonce()) ?>" src="<?php p(\OC::$server->getSystemConfig()->getValue('FDWE_URL')); ?>"></script>
    <?php endif; ?>
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
            $languagesToDisplay = array_filter($IDA_LANGUAGES, function ($lang) use ($CURRENT_LANGUAGE) {
                return $lang["short"] != $CURRENT_LANGUAGE;
            });
            foreach ($languagesToDisplay as $lang) {
                print_unescaped('<button aria-label="Change language to ' . $lang["full"] . '" class="language-choice" tabindex="0" data-language-code="' . $lang["short"] . '">' . $lang["full"] . '</button>');
            }
            ?>
        </div>
    </div>
    <div class="fd-header container-fluid">
        <div class="row no-gutter">
            <div class="col-8">
                <img src="<?php print_unescaped(image_path('', 'ida-logo-header.png')); ?>" class="logo">
            </div>
            <div class="language-selector-wrapper col-4">
                <?php if (SSOActive()) : ?>
                    <a href="<?php p(\OC::$server->getSystemConfig()->getValue('SSO_API')) ?>/login?service=IDA&redirect_url=<?php p(\OC::$server->getSystemConfig()->getValue('IDA_HOME')) ?>&language=<?php p($CURRENT_LANGUAGE) ?>">
                        <button class="fd-button login-button"><?php if ($CURRENT_LANGUAGE == "fi") : ?>Kirjaudu<?php elseif ($CURRENT_LANGUAGE == "sv") : ?>Logga in<?php else : ?>Login<?php endif; ?></button>
                    </a>
                <?php endif; ?>
                <div class="language-selector-container">
                    <?php
                    foreach ($languagesToDisplay as $lang) {
                        print_unescaped('<button aria-label="Change language to ' . $lang["full"] . '" class="language-choice" tabindex="0" data-language-code="' . $lang["short"] . '">' . $lang["short"] . '</button>');
                    }
                    ?>
                </div>
            </div>
        </div>
    </div>
    <div class="fd-content container">
        <div class="row">
            <?php if (localLoginOrSharePasswordActive()) : ?>
                <div class="col-lg-4 col-md-12 flex-center-md fd-col" style="max-width: 350px;">
                    <div id="ida-login" class="wrapper">
                        <div class="v-align">
                            <?php if (strpos($_SERVER['REQUEST_URI'], '/s/NOT_FOR_PUBLICATION_') !== false) : ?>
                                <div class="local-login-form">
                                    <p id="ida-local-login-form-header">
                                        <?php p($l->t('Enter temporary share password:')); ?>
                                    </p>
                                    <?php print_unescaped($_['content']); ?>
                                </div>
                            <?php elseif (localLoginActive()) : ?>
                                <div class="local-login-form">
                                    <?php print_unescaped($_['content']); ?>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            <?php endif; ?>
            <?php if ($CURRENT_LANGUAGE == "fi") : ?>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 fd-col">
                    <h2>Tervetuloa Fairdata IDA -palveluun</h2>
                    <p>Fairdata IDA on turvallinen ja maksuton tutkimusdatan säilytyspalvelu, jota tarjotaan Suomen korkeakouluille ja valtion tutkimuslaitoksille. IDA kuuluu opetus- ja kulttuuriministeriön järjestämään Fairdata-palvelukokonaisuuteen.</p>
                    <p>Säilytystila on projektikohtaista. IDAssa säilytettävä data voidaan muiden Fairdata-palvelujen avulla kuvailla tutkimusaineistoksi ja julkaista.</p>
                    <p><a href="https://www.fairdata.fi/ida/" rel="noreferrer noopener" target="_blank">Käytön aloitus ja käyttöoppaat</a></p>
                </div>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 padding-top fd-col">
                    <div class="row card-login active">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>IDA</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Siirrä datasi IDA-palveluun. Voit järjestellä dataa ja jäädyttää sen, kun data on valmis säilytykseen.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Qvain</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Kun datasi on jäädytetty, kuvaile ja julkaise se Qvain-työkalulla.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Etsin</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Etsin-palvelussa voit hakea ja ladata julkaistuja tutkimusaineistoja.</p>
                        </div>
                    </div>
                </div>
            <?php elseif ($CURRENT_LANGUAGE == "sv") : ?>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 fd-col">
                    <h2>Välkommen till Fairdata IDA</h2>
                    <p>Fairdata IDA är en trygg tjänst för lagring av forskningsdata. Tjänsten erbjuds utan kostnad för universitet, yrkeshögskolor och forskningsinstitut i Finland. IDA är en del av Fairdata-tjänsterna som erbjuds av Undervisnings- och kulturministeriet.</p>
                    <p>Bevaringsutrymmet i IDA tilldelas projekt. Data som finns i IDA kan dokumenteras och publiceras som dataset med hjälp av andra Fairdata-tjänster.</p>
                    <p><a href="https://www.fairdata.fi/en/ida/" rel="noreferrer noopener" target="_blank">Hur man tar i bruk och använder IDA (på engelska)</a></p>
                </div>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 padding-top fd-col">
                    <div class="row card-login active">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>IDA</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Flytta dina data till IDA, ordna dem och frys dem.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Qvain</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Då de är frysta kan du dokumentera och publicera dem med hjälp av Qvain.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Etsin</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>Du kan upptäcka och ladda ner dataset via Etsin.</p>
                        </div>
                    </div>
                </div>
            <?php else : ?>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 fd-col">
                    <h2>Welcome to Fairdata IDA</h2>
                    <p>Fairdata IDA is a continuous research data storage service organized by the Ministry of Education and Culture. The service is offered free of charge to Finnish universities, universities of applied sciences and state research institutes.</p>
                    <p>IDA enables uploading, organizing, and sharing research data within a project group and storing the data in an immutable state. The data stored in IDA can be included in research datasets which are described and made publicly available for download via other Fairdata services.</p>
                    <p><a href="https://www.fairdata.fi/en/ida/" rel="noreferrer noopener" target="_blank">How to start using IDA and user guides</a></p>
                </div>
                <div class="<?php if (localLoginOrSharePasswordActive()) p('col-lg-4');
                            else p('col-lg-6'); ?> col-md-12 padding-top fd-col">
                    <div class="row card-login active">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>IDA</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'ida.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>You store data in IDA. You can organize your data and freeze it in a final immutable state.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Qvain</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'qvain.png')); ?>">
                        </div>
                        <div class="col-sm-8 col-12">
                            <p>After freezing, you describe your data and publish it using Qvain.</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-12 align-center">
                            <img src="<?php print_unescaped(image_path('', 'arrow.png')); ?>" class="arrow">
                        </div>
                    </div>
                    <div class="row card-login">
                        <div class="col-sm-2 col-6 align-center align-right-sm">
                            <span>Etsin</span>
                        </div>
                        <div class="col-sm-2 col-6 align-center align-left-sm">
                            <img src="<?php print_unescaped(image_path('', 'etsin.png')); ?>">
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
                    <span>
                        Fairdata
                        <a class="fd-link fd-link-footer" rel="noreferrer noopener" target="_blank" href="https://www.fairdata.fi/en/fairdata-services/">
                            <img width="175px" src="<?php print_unescaped(image_path('', 'supporting-eosc.jpg')); ?>" alt="Supporting class="logo">
                        </a>
                    </span>
                    <p>Fairdata-palvelut järjestää <strong>opetus- ja kulttuuriministeriö </strong> ja toimittaa <strong>CSC – Tieteen tietotekniikan keskus Oy</strong></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                    <span>Tietoa</span>
                    <p><a href="https://www.fairdata.fi/kayttopolitiikat-ja-ehdot/" rel="noreferrer noopener" target="_blank">Käyttöpolitiikat ja ehdot

                        </a></p>
                    <p><a href="https://www.fairdata.fi/sopimukset/" rel="noreferrer noopener" target="_blank">Sopimukset ja tietosuoja</a></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Saavutettavuus</span>
                    <p><a href="https://www.fairdata.fi/saavutettavuus/" rel="noreferrer noopener" target="_blank">Saavutettavuus</a></p>
                </div>
                <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Ota yhteyttä</span>
                    <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
                </div>
                <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                    <span>Seuraa</span>
                    <p><a href="https://x.com/Fairdata_fi" rel="noreferrer noopener" target="_blank" title="The service formally known as Twitter">X&nbsp;@Fairdata_fi</a></p>
                    <p><a href="https://www.fairdata.fi/ajankohtaista/" rel="noreferrer noopener" target="_blank">Uutiset</a></p>
                </div>
            <?php elseif ($CURRENT_LANGUAGE == "sv") : ?>
                <div class="col col-lg-4 col-md-12 col-sm-12 col-12">
                    <span>
                        Fairdata
                        <a class="fd-link fd-link-footer" rel="noreferrer noopener" target="_blank" href="https://www.fairdata.fi/en/fairdata-services/">
                            <img width="175px" src="<?php print_unescaped(image_path('', 'supporting-eosc.jpg')); ?>" alt="Supporting class="logo">
                        </a>
                    </span>
                    <p>Fairdata-tjänsterna erbjuds av <strong>ministeriet för utbildning och kultur</strong> och produceras av <strong>CSC - IT Center for Science Ltd.</strong></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                    <span>Information</span>
                    <p><a href="https://www.fairdata.fi/en/terms-and-policies/" rel="noreferrer noopener" target="_blank">Villkor och policyer</a></p>
                    <p><a href="https://www.fairdata.fi/en/contracts-and-privacy/" rel="noreferrer noopener" target="_blank">Kontrakt och integritet</a></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Tillgänglighet</span>
                    <p><a href="https://www.fairdata.fi/en/accessibility/" rel="noreferrer noopener" target="_blank">Tillgänglighet uttalande</a></p>
                </div>
                <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Kontakt</span>
                    <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
                </div>
                <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                    <span>Följ</span>
                    <p><a href="https://x.com/Fairdata_fi" rel="noreferrer noopener" target="_blank" title="The service formally known as Twitter">X&nbsp;@Fairdata_fi</a></p>
                    <p><a href="https://www.fairdata.fi/en/news/" rel="noreferrer noopener" target="_blank">Nyheter</a></p>
                </div>
            <?php else : ?>
                <div class="col col-lg-4 col-md-12 col-sm-12 col-12">
                    <span>
                        Fairdata
                        <a class="fd-link fd-link-footer" rel="noreferrer noopener" target="_blank" href="https://www.fairdata.fi/en/fairdata-services/">
                            <img width="175px" src="<?php print_unescaped(image_path('', 'supporting-eosc.jpg')); ?>" alt="Supporting class="logo">
                        </a>
                    </span>
                    <p>The Fairdata services are offered by the<strong> Ministry of Education and Culture </strong>and produced by<strong> CSC – IT Center for Science Ltd.</strong></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 offset-lg-1">
                    <span>Information</span>
                    <p><a href="https://www.fairdata.fi/en/terms-and-policies/" rel="noreferrer noopener" target="_blank">Terms and Policies</a></p>
                    <p><a href="https://www.fairdata.fi/en/contracts-and-privacy/" rel="noreferrer noopener" target="_blank">Contracts and Privacy</a></p>
                </div>
                <div class="col padding-right col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Accessibility</span>
                    <p><a href="https://www.fairdata.fi/en/accessibility/" rel="noreferrer noopener" target="_blank">Accessibility statement</a></p>
                </div>
                <div class="col col-lg-2 col-md-3 col-sm-6 col-6">
                    <span>Contact</span>
                    <p><a href="mailto:servicedesk@csc.fi">servicedesk@csc.fi</a></p>
                </div>
                <div class="col col-lg-1 col-md-3 col-sm-6 col-6">
                    <span>Follow</span>
                    <p><a href="https://x.com/Fairdata_fi" rel="noreferrer noopener" target="_blank" title="The service formally known as Twitter">X&nbsp;@Fairdata_fi</a></p>
                    <p><a href="https://www.fairdata.fi/en/news/" rel="noreferrer noopener" target="_blank">What's new</a></p>
                </div>
            <?php endif; ?>
        </div>
    </div>
</body>

</html>