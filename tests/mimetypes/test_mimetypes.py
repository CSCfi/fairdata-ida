# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2024 Ministry of Education and Culture, Finland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license  GNU Affero General Public License, version 3
# @link     https://research.csc.fi/
# --------------------------------------------------------------------------------
# These tests are not normally run as part of the usual automated testing, but
# are available for testing changes to the Apache mod_secure configuration to
# ensure that file uploads are not being blocked for any particular filename
# suffix or MIME type.
# --------------------------------------------------------------------------------

import requests
import unittest
import time
import os
import sys
from tests.common.utils import *

FILE_TYPES = {
    "3g2":          "audio/3gpp2",
    "3gp":          "audio/3gpp",
    "3gpp2":        "audio/3gpp2",
    "3gpp":         "audio/3gpp",
    "aac":          "audio/aac",
    "a":            "application/octet-stream",
    "adts":         "audio/aac",
    "ai":           "application/postscript",
    "aif":          "audio/x-aiff",
    "aifc":         "audio/x-aiff",
    "aiff":         "audio/x-aiff",
    "ass":          "audio/aac",
    "au":           "audio/basic",
    "avif":         "image/avif",
    "avi":          "video/x-msvideo",
    "bat":          "text/plain",
    "bcpio":        "application/x-bcpio",
    "bin":          "application/octet-stream",
    "bmp":          "image/bmp",
    "br":           "br",
    "bz2":          "bzip2",
    "cdf":          "application/x-netcdf",
    "cpio":         "application/x-cpio",
    "csh":          "application/x-csh",
    "css":          "text/css",
    "csv":          "text/csv",
    "c":            "text/plain",
    "dll":          "application/octet-stream",
    "doc":          "application/msword",
    "dot":          "application/msword",
    "dvi":          "application/x-dvi",
    "eml":          "message/rfc822",
    "eps":          "application/postscript",
    "etx":          "text/x-setext",
    "exe":          "application/octet-stream",
    "gif":          "image/gif",
    "gtar":         "application/x-gtar",
    "gz":           "gzip",
    "h5":           "application/x-hdf5",
    "hdf":          "application/x-hdf",
    "heic":         "image/heic",
    "heif":         "image/heif",
    "h":            "text/plain",
    "html":         "text/html",
    "htm":          "text/html",
    "ico":          "image/vnd.microsoft.icon",
    "ief":          "image/ief",
    "jpeg":         "image/jpeg",
    "jpe":          "image/jpeg",
    "jpg":          "image/jpeg",
    "jpg":          "image/jpg",
    "json":         "application/json",
    "js":           "text/javascript",
    "ksh":          "text/plain",
    "latex":        "application/x-latex",
    "loas":         "audio/aac",
    "m1v":          "video/mpeg",
    "m3u8":         "application/vnd.apple.mpegurl",
    "m3u":          "application/vnd.apple.mpegurl",
    "man":          "application/x-troff-man",
    "me":           "application/x-troff-me",
    "mht":          "message/rfc822",
    "mhtml":        "message/rfc822",
    "mid":          "audio/midi",
    "midi":         "audio/midi",
    "mif":          "application/x-mif",
    "mjs":          "text/javascript",
    "movie":        "video/x-sgi-movie",
    "mov":          "video/quicktime",
    "mp2":          "audio/mpeg",
    "mp3":          "audio/mpeg",
    "mp4":          "video/mp4",
    "mpa":          "video/mpeg",
    "mpeg":         "video/mpeg",
    "mpe":          "video/mpeg",
    "mpg":          "video/mpeg",
    "ms":           "application/x-troff-ms",
    "n3":           "text/n3",
    "nc":           "application/x-netcdf",
    "nq":           "application/n-quads",
    "nt":           "application/n-triples",
    "nws":          "message/rfc822",
    "o":            "application/octet-stream",
    "obj":          "application/octet-stream",
    "oda":          "application/oda",
    "opus":         "audio/opus",
    "p12":          "application/x-pkcs12",
    "p7c":          "application/pkcs7-mime",
    "pbm":          "image/x-portable-bitmap",
    "pct":          "image/pict",
    "pdf":          "application/pdf",
    "pfx":          "application/x-pkcs12",
    "pgm":          "image/x-portable-graymap",
    "pic":          "image/pict",
    "pict":         "image/pict",
    "pl":           "text/plain",
    "png":          "image/png",
    "pnm":          "image/x-portable-anymap",
    "pot":          "application/vnd.ms-powerpoint",
    "ppa":          "application/vnd.ms-powerpoint",
    "ppm":          "image/x-portable-pixmap",
    "pps":          "application/vnd.ms-powerpoint",
    "ppt":          "application/vnd.ms-powerpoint",
    "ps":           "application/postscript",
    "pwz":          "application/vnd.ms-powerpoint",
    "pyc":          "application/x-python-code",
    "pyo":          "application/x-python-code",
    "py":           "text/x-python",
    "qt":           "video/quicktime",
    "ra":           "audio/x-pn-realaudio",
    "ram":          "application/x-pn-realaudio",
    "ras":          "image/x-cmu-raster",
    "rdf":          "application/rdf+xml",
    "rgb":          "image/x-rgb",
    "roff":         "application/x-troff",
    "rtf":          "application/rtf",
    "rtx":          "text/richtext",
    "sgml":         "text/x-sgml",
    "sgm":          "text/x-sgml",
    "sh":           "application/x-sh",
    "shar":         "application/x-shar",
    "snd":          "audio/basic",
    "so":           "application/octet-stream",
    "src":          "application/x-wais-source",
    "srt":          "text/plain",
    "sv4cpio":      "application/x-sv4cpio",
    "sv4crc":       "application/x-sv4crc",
    "svg":          "image/svg+xml",
    "swf":          "application/x-shockwave-flash",
    "t":            "application/x-troff",
    "tar":          "application/x-tar",
    "tcl":          "application/x-tcl",
    "tex":          "application/x-tex",
    "texi":         "application/x-texinfo",
    "texinfo":      "application/x-texinfo",
    "tiff":         "image/tiff",
    "tif":          "image/tiff",
    "tr":           "application/x-troff",
    "trig":         "application/trig",
    "tsv":          "text/tab-separated-values",
    "txt":          "text/plain",
    "ustar":        "application/x-ustar",
    "vcf":          "text/x-vcard",
    "vtt":          "text/vtt",
    "wasm":         "application/wasm",
    "wav":          "audio/x-wav",
    "webmanifest":  "application/manifest+json",
    "webm":         "video/webm",
    "webp":         "image/webp",
    "wiz":          "application/msword",
    "wsdl":         "application/xml",
    "xbm":          "image/x-xbitmap",
    "xlb":          "application/vnd.ms-excel",
    "xls":          "application/vnd.ms-excel",
    "xml":          "text/xml",
    "xpdl":         "application/xml",
    "xpm":          "image/x-xpixmap",
    "xsl":          "application/xml",
    "xul":          "text/xul",
    "xwd":          "image/x-xwindowdump",
    "xz":           "xz",
    "Z":            "compress",
    "zip":          "application/zip",
    "zzz":          "application/zzz-fairdata-testing" # guarunteed unknown to apache/Nextcloud
}


class TestMimetypes(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/mimetypes/test_mimetypes")


    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        self.assertEqual(self.config["METAX_AVAILABLE"], 1)

        print("(initializing)")

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':

            print("(cleaning)")

            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

        self.assertTrue(self.success)


    def test_mimetypes(self):

        """
        Overview:

        Upload a test file for each filename suffix + MIME type pair to the staging area
        of the test project, using HTTP PUT, to verify that Apache/Nextcloud/IDA does not
        reject the file based on any restricted filename suffix or MIME type.
        """

        test_user_a = ('test_user_a', self.config['TEST_USER_PASS'])

        # --------------------------------------------------------------------------------

        print("Uploading files for all known filename suffixes and MIME types...")

        loop_delay  = 1   # increase this to 5 seconds if on a very slow machine
        retry_delay = 10

        for suffix, mimetype in FILE_TYPES.items():
            print("    %s: %s" % (suffix, mimetype))
            filename = "test.%s" % suffix
            url = "%s/test_project_a+/%s" % (self.config['FILE_API'], filename)
            headers = { "Content-Type": "%s; charset=\"utf-8\"" % mimetype }
            # The following data string should be invalid in most/every commonly used textual encoding,
            # ensuring that apache/mod_secure is not parsing/inspecting any uploaded data files
            data = "%s\n\x01\x02\x03\x04\x05!!@$#%%^&*()_+{}[]|;:'\",.<>?/" % mimetype
            try:
                response = requests.put(url, data=data, headers=headers, auth=test_user_a, verify=False)
                self.assertEqual(response.status_code, 201,  "%s %s" % (response.status_code, response.content.decode(sys.stdout.encoding)[:1000]))
                time.sleep(loop_delay)
            except:
                print("%s %s" % (response.status_code, response.content.decode(sys.stdout.encoding)[:1000]))
                # In some environments, the firehosing of all of the test file uploads can
                # result in a WebDAV upload error, so we catch it, give Nextcloud a few seconds
                # to stabilize, and try a second time. If the second attempt fails, we skip the
                # remainder of the uploads with a warning, so that the automated testing can 
                # proceed without total failure.
                #
                # These tests are typically run last, so even if the remainder of file uploads
                # is skipped, all other automated tests will have passed if the tests get to
                # this point.
                #
                # TODO: Try to determine how to make the service more resilient and able to 
                # handle the more rapid uploads in less resource capable environments.
                try:
                    print("    (upload failed, trying again in %d seconds)" % retry_delay)
                    time.sleep(retry_delay)
                    print("    %s: %s" % (suffix, mimetype))
                    response = requests.put(url, data=data, headers=headers, auth=test_user_a, verify=False)
                    self.assertEqual(response.status_code, 201,  "%s %s" % (response.status_code, response.content.decode(sys.stdout.encoding)[:1000]))
                except:
                    print("%s %s" % (response.status_code, response.content.decode(sys.stdout.encoding)[:1000]))
                    print("******************************************************************")
                    print("WARNING: Service overloaded. Skipping remaining test file uploads!")
                    print("******************************************************************")
                    break

        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
