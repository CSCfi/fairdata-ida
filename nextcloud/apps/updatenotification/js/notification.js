/**
 * Copyright (c) 2015 ownCloud Inc
 *
 * @author Morris Jobke <hey@morrisjobke.de>
 *
 * This file is licensed under the Affero General Public License version 3
 * or later.
 *
 * See the COPYING-README file.
 *
 */

/**
 * this gets only loaded if an update is available and then shows a temporary notification
 */
$(document).ready(function(){
	var text = t('core', '{version} is available. Get more information on how to update.', {version: oc_updateState.updateVersion}),
		element = $('<a>').attr('href', oc_updateState.updateLink).attr('target','_blank').text(text);

	OC.Notification.show(element, 
		{
			isHTML: true,
			type: 'error'
		}
	);
});
