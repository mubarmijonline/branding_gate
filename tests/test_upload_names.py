"""
An uploaded picture stays a picture, whatever it was called.

`secure_filename()` drops every non-ASCII character, so a file named in
Arabic -- 'تصميم الكوست.jpg' -- was saved as '<stamp>_jpg' with no extension.
/uploads/ decides the content type from the path, found none, and sent the
picture down as an attachment of unknown type that nothing would show (David,
2026-10-28: a cost-sheet image nobody could open). Two fixes, both pinned here:
new uploads keep their extension, and a stored file whose name says nothing
is typed from its first bytes.
"""

import datetime
import os
import shutil
import tempfile
import unittest
from unittest import mock

from werkzeug.utils import secure_filename

import branding_gate
import rbac

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 32


class SafeUploadNameTest(unittest.TestCase):

    def test_the_cause_arabic_names_lose_their_extension_to_secure_filename(self):
        self.assertEqual(secure_filename('تصميم الكوست.jpg'), 'jpg')

    def test_an_arabic_name_keeps_its_extension(self):
        self.assertEqual(branding_gate.safe_upload_name('تصميم الكوست.jpg', 'jpg'), 'file.jpg')
        self.assertEqual(branding_gate.safe_upload_name('صورة.PNG'), 'file.png')

    def test_a_latin_name_is_unchanged_apart_from_what_secure_filename_does(self):
        self.assertEqual(branding_gate.safe_upload_name('Cost sheet (v2).pdf', 'pdf'),
                         'Cost_sheet_v2.pdf')
        self.assertEqual(branding_gate.safe_upload_name('WhatsApp Image 2026-10-28 at 1.42.30 PM.jpeg'),
                         'WhatsApp_Image_2026-10-28_at_1.42.30_PM.jpeg')

    def test_a_mixed_name_keeps_its_latin_part(self):
        self.assertEqual(branding_gate.safe_upload_name('logo نهائي.png', 'png'), 'logo.png')

    def test_no_extension_means_no_extension(self):
        self.assertEqual(branding_gate.safe_upload_name('README'), 'README')
        self.assertEqual(branding_gate.safe_upload_name('ملف'), 'file')

    def test_every_upload_route_names_its_file_this_way(self):
        import inspect
        for endpoint in ('costing_proposal_files', 'costing_add_alternative',
                         'upload_item_attachments'):
            source = inspect.getsource(branding_gate.app.view_functions[endpoint])
            self.assertIn('safe_upload_name(', source, endpoint)
            self.assertNotIn('secure_filename(', source, endpoint)
        self.assertIn('safe_upload_name(', inspect.getsource(branding_gate._save_design_file))


class SniffTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, 'wb') as handle:
            handle.write(data)
        return path

    def test_the_first_bytes_say_what_it_is(self):
        self.assertEqual(branding_gate.sniff_upload_mimetype(self._write('a', PNG)), 'image/png')
        self.assertEqual(branding_gate.sniff_upload_mimetype(self._write('b', JPEG)), 'image/jpeg')
        self.assertEqual(branding_gate.sniff_upload_mimetype(self._write('c', b'%PDF-1.4 ...')),
                         'application/pdf')
        self.assertEqual(branding_gate.sniff_upload_mimetype(
            self._write('d', b'RIFF\x00\x00\x00\x00WEBPVP8 ')), 'image/webp')

    def test_unknown_bytes_are_unknown(self):
        self.assertIsNone(branding_gate.sniff_upload_mimetype(self._write('e', b'hello')))
        self.assertIsNone(branding_gate.sniff_upload_mimetype(os.path.join(self.tmp, 'missing')))


class ServeExtensionlessUploadTest(unittest.TestCase):
    """A costing file saved without its extension is still served as a picture."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        folder = os.path.join(self.tmp, 'costing', '12')
        os.makedirs(folder)
        with open(os.path.join(folder, '20261028_134200_000000_jpg'), 'wb') as handle:
            handle.write(JPEG)
        with open(os.path.join(folder, '20261028_134200_000001_notes.xlsx'), 'wb') as handle:
            handle.write(b'PK\x03\x04')
        branding_gate.app.config['TESTING'] = True
        for name, value in (('UPLOADS_DIR', self.tmp),
                            ('connection', lambda: (mock.Mock(), mock.Mock())),
                            ('upload_access_allowed', lambda cur, parts: True)):
            patcher = mock.patch.object(branding_gate, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = branding_gate.app.test_client()
        with self.client.session_transaction() as s:
            s.update({'user_id': 12, 'mobile': 'm', 'email': 'e', 'username': 'u', 'name': 'n',
                      'roles': ['operations_manager'], 'role_code': 'operations_manager',
                      'perms': rbac.SEED_MATRIX['operations_manager'],
                      'perms_loaded_at': datetime.datetime.now().isoformat()})

    def test_a_picture_with_no_extension_is_shown_inline_as_a_picture(self):
        response = self.client.get('/uploads/costing/12/20261028_134200_000000_jpg')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')
        self.assertNotIn('attachment', response.headers.get('Content-Disposition', ''))
        response.close()

    def test_a_file_of_a_type_the_browser_does_not_show_is_still_a_download(self):
        response = self.client.get('/uploads/costing/12/20261028_134200_000001_notes.xlsx')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/octet-stream')
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        response.close()


if __name__ == '__main__':
    unittest.main()
