<?php /** @var \OCP\IL10N $l */ ?>
<?php
script('core', 'dist/login');
$CURRENT_LANGUAGE = $l->getLanguageCode();
$CURRENT_LANGUAGE = $CURRENT_LANGUAGE ? substr($CURRENT_LANGUAGE, 0, 2) : 'en';
?>

<form method="post" name="login" action="/login">
    <fieldset>
		<?php if (!empty($_['redirect_url'])) {
			print_unescaped('<input type="hidden" name="redirect_url" value="' . \OCP\Util::sanitizeHTML($_['redirect_url']) . '">');
		} ?>
        <div id="message" class="hidden">
            <img alt="" src="/core/img/loading-dark.gif" class="float-spinner"> <span id="messageText"></span> 
            <div style="clear: both;"></div>
        </div>
        <p class="grouptop">
			<input id="user" type="text" name="user" autocapitalize="off" autocomplete="on" placeholder="Username" aria-label="Username" required="required">
			<label for="user" class="infield">Username</label>
		</p>
        <p class="groupbottom">
			<input id="password" type="password" name="password" autocomplete="on" placeholder="Password" aria-label="Password" required="required">
			<label for="password" class="infield"></label>
		</p>
        <div id="submit-wrapper">
            <input id="submit-form" type="submit" title="" class="login primary" value="Login"> 
            <div class="submit-icon icon-confirm-white"></div>
        </div>
		<input type="hidden" name="timezone_offset" id="timezone_offset" />
		<input type="hidden" name="timezone" id="timezone" />
		<input type="hidden" name="requesttoken" value="<?php p($_['requesttoken']) ?>">
    </fieldset>
</form>
