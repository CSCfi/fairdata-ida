<?php /** @var $l \OCP\IL10N */ ?>
<?php
vendor_script('jsTimezoneDetect/jstz');
script('core', 'merged-login');
?>

<form method="post" name="login">
    <fieldset>
        <?php if (!empty($_['redirect_url'])) {
            print_unescaped('<input type="hidden" name="redirect_url" value="' . \OCP\Util::sanitizeHTML($_['redirect_url']) . '">');
        } ?>
        <?php if (isset($_['apacheauthfailed']) && ($_['apacheauthfailed'])): ?>
            <div class="warning">
                <?php p($l->t('Server side authentication failed!')); ?><br>
                <small><?php p($l->t('Please contact your administrator.')); ?></small>
            </div>
        <?php endif; ?>
        <?php foreach ($_['messages'] as $message): ?>
            <div class="warning">
                <?php p($message); ?><br>
            </div>
        <?php endforeach; ?>
        <?php if (isset($_['internalexception']) && ($_['internalexception'])): ?>
            <div class="warning">
                <?php p($l->t('An internal error occurred.')); ?><br>
                <small><?php p($l->t('Please try again or contact your administrator.')); ?></small>
            </div>
        <?php endif; ?>
        <div id="message" class="hidden">
            <img class="float-spinner" alt=""
                 src="<?php p(image_path('core', 'loading-dark.gif')); ?>">
            <span id="messageText"></span>
            <!-- the following div ensures that the spinner is always inside the #message div -->
            <div style="clear: both;"></div>
        </div>
        <p class="xgrouptop<?php if (!empty($_['invalidpassword'])) { ?> shake<?php } ?>">
            <input type="text" name="user" id="user"
                   placeholder="<?php p($l->t('CSC Username:')); ?>"
                   value="<?php p($_['loginName']); ?>"
                   autocomplete="on" autocapitalize="none" autocorrect="off" required>
            <label for="user" class="infield"><?php p($l->t('CSC Username:')); ?></label>
        </p>
        <p class="xgroupbottom<?php if (!empty($_['invalidpassword'])) { ?> shake<?php } ?>">
            <input type="password" name="password" id="password" value=""
                   placeholder="<?php p($l->t('CSC Password:')); ?>"
                <?php p($_['user_autofocus'] ? '' : 'autofocus'); ?>
                   autocomplete="on" autocapitalize="off" autocorrect="none" required>
            <label for="password" class="infield"><?php p($l->t('CSC Password:')); ?></label>
        </p>
        
        <?php if (!empty($_['invalidpassword'])) { ?>
            <p class="warning">
                <?php p($l->t('Wrong password.')); ?>
            </p>
        <?php } ?>

        <input type="submit" id="submit" class="login primary icon-confirm-white" title=""
               value="<?php p($l->t('Login')); ?>" disabled="disabled"/>

        <input type="hidden" name="timezone_offset" id="timezone_offset"/>
        <input type="hidden" name="timezone" id="timezone"/>
        <input type="hidden" name="requesttoken" value="<?php p($_['requesttoken']) ?>">
    </fieldset>
</form>
