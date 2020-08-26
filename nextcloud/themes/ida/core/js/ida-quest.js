$(document).ready(function() {
    $(".language-choice").on("click", function() {
        fdIDAChangeLanguage($(this).attr("data-language-code"))
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

function fdIDAGetPrefixedCookieName(name) {
    var hostname = window.location.hostname;
    var domain = hostname.substring(hostname.indexOf(".") + 1);
    domain = domain.replace(/[^a-zA-Z0-9]/g, "_")
    return domain + "_" + name
}

function setCookie(name, value) {
    name = fdIDAGetPrefixedCookieName(name);
    var expiryDate = new Date();
    expiryDate.setTime(expiryDate.getTime() + (7*24*60*60*1000));
    var expires = "; expires=" + expiryDate.toUTCString();
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}

function fdIDAChangeLanguage(lang) {
    setCookie("fd_language", lang)
    window.location.reload()
}

