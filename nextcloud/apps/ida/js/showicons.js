/**
 * Makes all relevant notification icons visible based on the status of the projects
 * to which the current user belongs.
 */
$(document).ready(function () {
    $.ajax({
        url: OC.generateUrl('/apps/ida/api/status'),
        type: 'GET',
        contentType: 'application/json',
        cache: false,
        async: false,
        success: function(response) {
            if (response['failed'] === true) {
                $(document).find("#ida-failed-actions-icon").show();
            }
            if (response['pending'] === true) {
                $(document).find("#ida-pending-actions-icon").show();
            }
            if (response['suspended'] === true) {
                $(document).find("#ida-suspended-icon").show();
            }
        }
    });
});