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

OC.L10N.register(
    "ida",
    {
        "It is safe to log out from the IDA service and close your browser. Ongoing background operations will not be affected.": "Voit halutessasi kirjautua ulos IDA-palvelusta ja sulkea selaimesi. Se ei vaikuta käynnissä oleviin taustaoperaatioihin.",
        "Be absolutely sure you want to unfreeze or delete all files within the selected folder before proceeding with either option.": "Ennen kuin jatkat, olethan täysin varma, että haluat poistaa tai palauttaa valmistelualueelle kaikki valitun kansion tiedostot.",
        "Unfreezing will move all files within the selected folder back to the staging area, making them fully editable.": "Valmistelualueelle palauttaminen siirtää valitun kansion kaikki tiedostot valmistelualueelle ja tekee niistä muokattavia.",
        "Deleting will entirely remove all files within the selected folder from the service.": "Poistaminen tarkoittaa, että kaikki valitun kansion sisältämät tiedostot poistetaan palvelusta pysyvästi.",
        "Action not allowed: Datasets would be deprecated!": "Toiminto ei ole sallittu: Tutkimusaineistot rikkoutuisivat!",
        "The specified action is not allowed because it would deprecate the datasets listed below, for which the digital preservation process is ongoing.": "Toiminto ei ole sallittu, sillä se vaikuttaisi seuraaviin PAS-prosessissa oleviin aineistoihin:",
        "If you have questions, please contact <a href=\"mailto:pas-support@csc.fi\" target=\"_blank\" style=\"color: #007FAD;\">pas-support@csc.fi</a>": "Jos sinulla on kysymyksiä, ole hyvä ja ota yhteyttä <a href=\"mailto:pas-support@csc.fi\" target=\"_blank\" style=\"color: #007FAD;\">pas-support@csc.fi</a>",
        "Warning: Datasets will be deprecated!": "Varoitus: Tutkimusaineistot rikkoutuvat!",
        "One or more files included in the specified action belong to a dataset. Proceeding with the specified action will permanently deprecate the datasets listed below.": "Yksi tai useampi valitsemistasi tiedostoista on osa tutkimusaineistoa. Jos jatkat, alle listatut tutkimusaineistot rikkoutuvat pysyvästi.",
        "Do you wish to proceed?": "Haluatko jatkaa?",
        "An error occurred when checking for datasets which may be deprecated by the requested action.": "Tapahtui virhe listattaessa tutkimusaineistoja, jotka pyydetty toiminto voi rikkoa.",
        "Action Failed": "Toiminto epäonnistui",
        "Action initiated successfully. Show frozen data?": "Toiminto aloitettu onnistuneesti. Näytä jäädytetty data?",
        "Action initiated successfully. Files deleted.": "Toiminto aloitettu onnistuneesti. Tiedostot poistettu.",
        "Action initiated successfully. Show unfrozen data?": "Toiminto aloitettu onnistuneesti. Näytä valmistelualueelle palautettu data?",
        "Action": "Toiminto",
        "Actions": "Toiminnot",
        "Additional information will be available once the action is complete.": "Lisätietoa saatavilla sen jälkeen, kun toiminto on suoritettu loppuun.",
        "Are you sure you want to delete the selected item(s)? THIS ACTION CANNOT BE UNDONE!": "Oletko varma, että haluat poistaa valitsemasi kohteen/kohteet? TÄTÄ TOIMINTOA EI VOIDA PERUUTTAA!",
        "Are you sure you want to delete the selected item? THIS ACTION CANNOT BE UNDONE!": "Oletko varma, että haluat poistaa valitsemasi kohteen? TÄTÄ TOIMINTOA EI VOIDA PERUUTTAA!",
        "Are you sure you want to delete this file, permanently removing it from the service?": "Oletko varma, että haluat poistaa tämän tiedoston? Tiedosto poistetaan palvelusta pysyvästi.",
        "Are you sure you want to delete this folder, permanently removing it and all files within it from the service?": "Oletko varma, että haluat poistaa tämän kansion? Kansio ja sen sisältö poistetaan palvelusta pysyvästi.",
        "Are you sure you want to freeze all files within this folder, moving them to the frozen area and making them read-only?": "Oletko varma, että haluat jäädyttää kaikki tiedostot tässä kansiossa? Kansio ja sen sisältö siirretään jäädytetylle alueelle (vain lukuoikeudet).",
        "Are you sure you want to freeze this file, moving it to the frozen area and making it read-only?": "Oletko varma, että haluat jäädyttää tämän tiedoston? Tiedosto siirretään jäädytetylle alueelle (vain lukuoikeudet).",
        "Are you sure you want to unfreeze all files within this folder, and move them back to the staging area?": "Oletko varma, että haluat palauttaa tämän kansion kaikki tiedostot takaisin valmistelualueelle ja mitätöidä jäädytystoimenpiteet?",
        "Are you sure you want to unfreeze this file, and move it back to the staging area?": "Oletko varma, että haluat palauttaa tämän tiedoston takaisin valmistelualueelle ja mitätöidä jäädytystoimenpiteet?",
        "Be absolutely sure you want to freeze the file before proceeding.": "Olethan täysin varma, että haluat jäädyttää tiedoston ennen kuin jatkat.",
        "Be absolutely sure you want to freeze the folder before proceeding.": "Olethan täysin varma, että haluat jäädyttää kansion ennen kuin jatkat.",
        "Be absolutely sure you want to unfreeze or delete the file before proceeding with either option.": "Olethan täysin varma, että haluat palauttaa tiedoston valmistelualueelle tai poistaa sen, ennen kuin jatkat.",
        "Be absolutely sure you want to unfreeze or delete the folder, and all files within it, before proceeding with either option.": "Olethan täysin varma, että haluat palauttaa kansion kaikkine tiedoistoineen valmistelualueelle tai poistaa sen, ennen kuin jatkat.",
        "Checksum": "Tarkistussumma",
        "Delete File?": "Poista tiedosto?",
        "Delete Folder?": "Poista kansio?",
        "Delete": "Poista",
        "Deleting will entirely remove the selected file from the service.": "Poistaminen tarkoittaa, että valittu tiedosto poistetaan pysyvästi palvelusta.",
        "Deleting will entirely remove the selected folder, and all files within it, from the service.": "Poistaminen tarkoittaa, että valittu kansio ja kaikki sen sisältö poistetaan pysyvästi palvelusta.",
        "Depending on the amount of data, the background operations may still take several hours.": "Datan määrästä riippuen taustaoperaatiot voivat kestää vielä useita tunteja.",
        "Do you wish to view the data in its frozen location?": "Haluatko siirtyä tarkastelemaan dataa jäädytetyllä alueella?",
        "Do you wish to view the data in its staging location?": "Haluatko siirtyä tarkastelemaan dataa valmistelualueella?",
        "Either action will initiate several background operations.": "Kumpikin toiminnoista aloittaa useita taustaoperaatioita.",
        "File ID": "Tiedoston tunniste",
        "Files can be added only in the Staging area (root folder ending in +)": "Tiedostoja voidaan lisätä ainoastaan Valmistelualueelle (juurikansio jonka päätteenä on +)",
        "Freeze File?": "Jäädytä tiedosto?",
        "Freeze Folder?": "Jäädytä kansio?",
        "Freeze": "Jäädytä",
        "Freezing will move all files within the selected folder to the frozen area, making all files read-only and visible to other services, and will initiate several background operations.": "Jäädyttäminen siirtää kaikki valitun kansion sisältämät tiedostot jäädytetylle alueelle (vain lukuoikeudet), tekee ne näkyviksi muille palveluille sekä aloittaa useita taustaoperaatioita.",
        "Freezing will move the selected file to the frozen area, making it read-only and visible to other services, and will initiate several background operations.": "Jäädyttäminen siirtää valitun tiedoston jäädytetylle alueelle (vain lukuoikeudet), tekee sen näkyväksi muille palveluille sekä aloittaa useita taustaoperaatioita.",
        "Freezing": "Jäädytys",
        "Frozen files will be replicated to separate physical storage to guard against loss of data due to hardware failure.": "Jäädytetyt tiedostot kopioidaan toiselle fyysiselle tallennusmedialle, mikä suojaa niitä vakavissa vikatilanteissa.",
        "Frozen": "Jäädytetty",
        "NOTICE": "HUOMAA",
        "Once initiated, the progress of the action can be checked from the <a href=\"../ida/actions/pending\">Pending Actions</a> view.": "Aloitetun toiminnon edistymistä voidaan seurata <a href=\"../ida/actions/pending\">Odottavat toiminnot</a> näkymästä.",
        "Root project folders may not be modified.": "Projektien juurikansiot eivät ole muokattavissa.",
        "See the <a href=\"https://www.fairdata.fi/en/ida/user-guide\" target=\"_blank\">IDA User&apos;s Guide</a> for details.": "Katso lisätietoja <a href=\"https://www.fairdata.fi/ida/kayttoopas\" target=\"_blank\">IDAn käyttöoppaasta</a>.",
        "Size": "Koko",
        "THIS ACTION CANNOT BE UNDONE.": "TÄTÄ TOIMINTOA EI VOIDA PERUUTTAA.",
        "Temporary share link": "Väliaikainen jakolinkki",
        "The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.": "Toimintoa ei voida peruuttaa ennen kuin se on suoritettu loppuun. Datan määrästä riippuen taustaoperaatiot voivat kestää useita tunteja.",
        "The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.": "Toimintoa ei voida peruuttaa ennen kuin se on suoritettu loppuun. Tiedoston koosta riippuen taustaoperaatiot voivat kestää useita tunteja.",
        "The action cannot be terminated before it is complete.": "Toimintoa ei voida peruuttaa ennen kuin se on suoritettu loppuun.",
        "The data has been successfully frozen and moved to the frozen project space.": "Data on jäädytetty onnistuneesti ja siirretty projektin jäädytetylle alueelle.",
        "The data has been successfully unfrozen and moved back to the project staging space.": "Data on onnistuneesti palautettu projektin valmistelualueelle ja jäädytystoimenpiteet on mitätöity.",
        "The files have been successfully deleted.": "Tiedostot ovat onnistuneesti poistettu.",
        "The frozen file will be replicated to separate physical storage to guard against loss of data due to hardware failure.": "Jäädytetty tiedosto kopioidaan toiselle fyysiselle tallennusmedialle, mikä suojaa sitä vakavissa vikatilanteissa.",
        "The initiated action is": "Aloitettu toiminto on",
        "The progress of the ongoing action can be viewed by clicking on the action ID above.": "Aloitetun toiminnon edistymistä voidaan seurata klikkaamalla toiminnon tunnistetta (yllä).",
        "This file is part of an ongoing action.": "Tämä tiedosto on osa suoritettavaa toimintoa.",
        "Unable to delete the specified files:": "Seuraavia tiedostoja ei voitu poistaa:",
        "Unable to freeze the specified files:": "Seuraavia tiedostoja ei voitu jäädyttää:",
        "Unable to unfreeze the specified files:": "Seuraavia tiedostoja ei voitu palauttaa valmistelualueelle:",
        "Unfreeze File?": "Palauta tiedosto valmistelualuelle?",
        "Unfreeze Folder?": "Palauta kansio valmistelualueelle?",
        "Unfreeze": "Palauta valmistelualueelle",
        "Unfreezing will move all files within the specified folder back to the staging area, making them fully editable.": "Valmistelualueelle palauttaminen siirtää valitun kansion kaiken sisällön takaisin valmistelualueelle ja tekee sisällöstä täysin muokattavan.",
        "Unfreezing will move the selected file back to the staging area, making it fully editable.": "Valmistelualueelle palauttaminen siirtää valitun tiedoston takaisin valmistelualueelle ja tekee siitä täysin muokattavan.",
        "Unfrozen and deleted files will no longer to be accessible to other services, making all external references to them invalid. All replicated copies of unfrozen and deleted files will be removed.": "Valmistelualueelle palautetut ja poistetut tiedostot eivät ole enää muiden palvelujen käyttävissä ja kaikki niihin ulkoa tehdyt viittaukset mitätöityvät. Valmistelualueelle palautettujen ja poistettujen tiedostojen tiedostokopiot poistetaan."
    },
    "nplurals=2; plural=(n != 1);"
);
