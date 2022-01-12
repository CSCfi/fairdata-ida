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
function showIDAFirstRunWizard(){
	$.colorbox({
		opacity: 0.7,
		transition: 'elastic',
		speed: 100,
		href: OC.generateUrl('/apps/idafirstrunwizard/wizard'),
		onClosed : function() {
			$.ajax({
				url: OC.generateUrl('/apps/idafirstrunwizard/wizard'),
				type: 'delete'
			});
		}
	});
}

jQuery.fn.extend({
    live: function (event, callback) {
       if (this.selector) {
            jQuery(document).on(event, this.selector, callback);
        }
        return this;
    }
});

$(document).ready(function() {
	$('#showWizard').live('click', function () {
		showIDAFirstRunWizard();
	});

	$('#closeWizard').live('click', function () {
		$.colorbox.close();
	});
});
