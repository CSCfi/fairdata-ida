$(document).ready(function() {
    $(".language-choice").on("click", function() {
        window.location.href = "/login?language=" + $(this).attr("data-language-code")
    })

    $(".language-choice-toggle").on("click", function() {
        var rotation = 180;
        if($("#languageChoices").is(":visible")) {
            rotation = 0;
        }
        $("#expandIcon").css({'transform' : 'rotate('+rotation+'deg)'});
        $("#languageChoices").slideToggle(500);
    })
})
