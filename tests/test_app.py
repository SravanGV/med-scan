import io
import os
import tempfile
import unittest

from medscan import create_app
from medscan.db import init_db


class MedScanAppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.sqlite")
        self.upload_path = os.path.join(self.tmp_dir.name, "uploads")

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE": self.db_path,
                "UPLOAD_FOLDER": self.upload_path,
            }
        )
        with self.app.app_context():
            init_db()

        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def login(self, username="admin", secret="admin123"):
        return self.client.post(
            "/login",
            data={"username": username, "password": secret},
            follow_redirects=True,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_patient_registration_upload_and_records(self):
        self.login()
        reg = self.client.post(
            "/patients",
            data={
                "patient_code": "P-001",
                "full_name": "Jalaj Tripathi",
                "age": "24",
                "gender": "Male",
                "contact": "9999999999",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Patient registered successfully", reg.data)

        scan = self.client.post(
            "/scans",
            data={
                "patient_id": "1",
                "modality": "X-ray",
                "scan_file": (io.BytesIO(b"imagecontent"), "fracture_scan.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Scan uploaded and analyzed successfully", scan.data)

        records = self.client.get("/records")
        self.assertIn(b"Jalaj Tripathi", records.data)
        self.assertIn(b"Fracture", records.data)

    def test_csv_export(self):
        self.login()
        res = self.client.get("/reports/csv")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "text/csv")


if __name__ == "__main__":
    unittest.main()
