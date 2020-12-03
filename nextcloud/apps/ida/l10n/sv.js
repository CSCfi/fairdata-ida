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
        "It is safe to log out from the IDA service and close your browser. Ongoing background operations will not be affected.": "Du kan logga ut från IDA-tjänsten och stänga din webbläsare. Pågående bakgrundsoperationer kommer ej att påverkas.",
        "Be absolutely sure you want to unfreeze or delete all files within the selected folder before proceeding with either option.": "Före du fortsätter, var säker på att du faktiskt vill ta bort filerna i den valda mappen eller flytta tillbaka dem till preparering.",
        "Unfreezing will move all files within the selected folder back to the staging area, making them fully editable.": "Om du väljer att flytta tillbaka mappen till preparering kommer alla filer i den valda mappen bli redigerbara.",
        "Deleting will entirely remove all files within the selected folder from the service.": "Borttagning betyder att alla filer i den valda mappen kommer att raderas från servicen.",
        "Action not allowed: Datasets would be deprecated!": "Förbjuden åtgärd: Åtgärden skulle söndra dataset!",
        "The specified action is not allowed because it would deprecate the datasets listed below, for which the digital preservation process is ongoing.": "Denna åtgärd är inte tillåten, eftersom den skulle påverka följande dataset, som är på väg in i långsiktig bevaring:",
        "If you have questions, please contact <a href=\"mailto:pas-support@csc.fi\" target=\"_blank\" style=\"color: #007FAD;\">pas-support@csc.fi</a>": "Om du har frågor, var god och kontakta <a href=\"mailto:pas-support@csc.fi\" target=\"_blank\" style=\"color: #007FAD;\">pas-support@csc.fi</a>",
        "Warning: Datasets will be deprecated!": "Varning! Forskningsmaterialet söndras!",
        "One or more files included in the specified action belong to a dataset. Proceeding with the specified action will permanently deprecate the datasets listed below.": "En eller flera av de filer du valt för åtgärden ingår i ett dataset. Om du fortsätter förstörs de dataset som listas nedan permanent.",
        "Do you wish to proceed?": "Vill du fortsätta?",
        "An error occurred when checking for datasets which may be deprecated by the requested action.": "Ett fel uppstod under granskningen av dataset som potentiellt skulle söndras av den valda åtgärden.",
        "Action Failed": "Åtgärden misslyckades",
        "Action initiated successfully. Show frozen data?": "Åtgärden påbörjad. Visa frysta data?",
        "Action initiated successfully. Files deleted.": "Åtgärden påbörjad. Filer borttagna.",
        "Action initiated successfully. Show unfrozen data?": "Åtgärden påbörjad. Visa återtagna data?",
        "Action": "Åtgärd",
        "Actions": "Åtgärder",
        "Additional information will be available once the action is complete.": "Mera information blir tillgänglig när åtgärden är slutförd.",
        "Are you sure you want to delete the selected item(s)? THIS ACTION CANNOT BE UNDONE!": "Är du säker på att du vill ta bort detta/dessa objekt? DU KAN INTE ÅNGRA ÅTGÄRDEN!",
        "Are you sure you want to delete the selected item? THIS ACTION CANNOT BE UNDONE!": "Är du säker på att du vill ta bort objektet? DU KAN INTE ÅNGRA ÅTGÄRDEN!",
        "Are you sure you want to delete this file, permanently removing it from the service?": "Är du säker på att du vill ta bort filen? Filen tas bort permanent.",
        "Are you sure you want to delete this folder, permanently removing it and all files within it from the service?": "Är du säker på att du vill ta bort mappen och allt dess innehåll? Dessa tas bort permanent.",
        "Are you sure you want to freeze all files within this folder, moving them to the frozen area and making them read-only?": "Är du säker på att du vill frysa alla filer i denna mapp? De blir då skrivskyddade (read-only).",
        "Are you sure you want to freeze this file, moving it to the frozen area and making it read-only?": "Är du säker på att du vill frysa filen? Den blir då skrivskyddad (read-only).",
        "Are you sure you want to unfreeze all files within this folder, and move them back to the staging area?": "Är du säker på att du vill ta bort alla filer i denna mapp från det frysta området och flytta dem tillbaka till preparering?",
        "Are you sure you want to unfreeze this file, and move it back to the staging area?": "Är du säker på att du vill ta bort filen från det frysta området och flytta den tillbaka till preparering?",
        "Be absolutely sure you want to freeze the file before proceeding.": "Frys inte filer om du inte är säker på vad det innebär.",
        "Be absolutely sure you want to freeze the folder before proceeding.": "Frys inte mappen om du inte är säker på vad det innebär.",
        "Be absolutely sure you want to unfreeze or delete the file before proceeding with either option.": "Frys inte eller ta inte bort filer från det frysta området om du inte är säker på vad det innebär.",
        "Be absolutely sure you want to unfreeze or delete the folder, and all files within it, before proceeding with either option.": "Frys inte eller ta inte bort mappar med filer från det frysta området om du inte är säker på vad det innebär.",
        "Checksum": "Kontrollsumma",
        "Delete File?": "Ta bort filen?",
        "Delete Folder?": "Ta bort mappen?",
        "Delete": "Ta bort",
        "Deleting will entirely remove the selected file from the service.": "Om du tar bort den valda filen betyder det att den avlägsnas slutgiltigt.",
        "Deleting will entirely remove the selected folder, and all files within it, from the service.": "Om du tar bort den valda mappen och all filer i den betyder det att dessa avlägsnas slutgiltigt.",
        "Depending on the amount of data, the background operations may still take several hours.": "Åtgärden kan ta upp till flera timmar om datamängden är stor.",
        "Do you wish to view the data in its frozen location?": "Vill du se materialet på det frysta området?",
        "Do you wish to view the data in its staging location?": "Vill du se materialet i området för preparering?",
        "Either action will initiate several background operations.": "Båda åtgärderna initierar flera bakgrundsoperationer.",
        "File ID": "Filidentifierare",
        "Files can be added only in the Staging area (root folder ending in +)": "Filer kan läggas till endast i mappar med plustecken (+, område för preparering)",
        "Freeze File?": "Frys filen?",
        "Freeze Folder?": "Frys mappen?",
        "Freeze": "Frys",
        "Freezing will move all files within the selected folder to the frozen area, making all files read-only and visible to other services, and will initiate several background operations.": "Då du fryser mappen och dess filer flyttas de till det frysta området och blir skrivskyddade (read-only). Vid åtgärden initieras flera bakgrundsoperationer och materialet blir då synligt för andra Fairdata-tjänster.",
        "Freezing will move the selected file to the frozen area, making it read-only and visible to other services, and will initiate several background operations.": "Då du fryser filen flyttas den till det frysta området och blir skrivskyddad (read-only). Vid åtgärden initieras flera bakgrundsoperationer och filen blir då synlig för andra Fairdata-tjänster.",
        "Freezing": "Frysning",
        "Frozen files will be replicated to separate physical storage to guard against loss of data due to hardware failure.": "Frysta filer replikeras till annan media vilket skyddar data.",
        "Frozen": "Fryst",
        "NOTICE": "OBSERVERA",
        "Once initiated, the progress of the action can be checked from the <a href=\"../ida/actions/pending\">Pending Actions</a> view.": "Du kan följa med hur processen fortskrider i vyn för <a href=\"../ida/actions/pending\">Väntande åtgärder</a>.",
        "Root project folders may not be modified.": "Projektets rotmapp kan inte ändras.",
        "See the <a href=\"https://www.fairdata.fi/en/ida/user-guide\" target=\"_blank\">IDA User&apos;s Guide</a> for details.": "Läs mera i <a href=\"https://www.fairdata.fi/en/ida/user-guide\" target=\"_blank\">IDA User&apos;s Guide</a>.",
        "Size": "Storlek",
        "THIS ACTION CANNOT BE UNDONE.": "DENNA ÅTGÄRD KAN INTE ÅNGRAS.",
        "Temporary share link": "Tillfällig länk för delning",
        "The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.": "Åtgärden kan inte avbrytas. Bakgrundsoperationerna kan upp till flera timmar om datamängden är stor.",
        "The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.": "Åtgärden kan inte avbrytas. Bakgrundsoperationerna kan upp till flera timmar om filen är stor.",
        "The action cannot be terminated before it is complete.": "Åtgärden kan inte avbrytas.",
        "The data has been successfully frozen and moved to the frozen project space.": "Materialet har frysts och flyttats till det frysta området.",
        "The data has been successfully unfrozen and moved back to the project staging space.": "Materialet har flyttats tillbaka till preparering och är inte längre skrivskyddat.",
        "The files have been successfully deleted.": "Filerna har tagits bort.",
        "The frozen file will be replicated to separate physical storage to guard against loss of data due to hardware failure.": "Den frysta filen kopieras till ett annat medium, vilket skyddar den vill allvarliga tillbud.",
        "The initiated action is": "Den initierade operationen är",
        "The progress of the ongoing action can be viewed by clicking on the action ID above.": "Du kan följa med processens framskridande genom att klicka på åtgärdens identifierare.",
        "This file is part of an ongoing action.": "Denna fil är föremål för en pågående åtgärd.",
        "Unable to delete the specified files:": "Dessa filer kunde inte tas bort:",
        "Unable to freeze the specified files:": "Dessa filer kunde inte frysas:",
        "Unable to unfreeze the specified files:": "Dessa filer kunde inte flyttas tillbaka till preparering:",
        "Unfreeze File?": "Flytta fil till preparering?",
        "Unfreeze Folder?": "Flytta mapp till preparering?",
        "Unfreeze": "Flytta tillbaka till preparering",
        "Unfreezing will move all files within the specified folder back to the staging area, making them fully editable.": "Då du flyttar tillbaka mappen till preparering blir den och alla filer som ingår möjliga att ändra.",
        "Unfreezing will move the selected file back to the staging area, making it fully editable.": "Då du flyttar tillbaka filen till preparering blir den möjlig att ändra igen.",
        "Unfrozen and deleted files will no longer to be accessible to other services, making all external references to them invalid. All replicated copies of unfrozen and deleted files will be removed.": "Material som flyttas bort från det frysta området är inte längre tillgängliga för andra Fairdata-tjänster och alla eventuella hänvisningar går permanent sönder."
    },
    "nplurals=2; plural=(n != 1);"
);
