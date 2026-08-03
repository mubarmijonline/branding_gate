from pathlib import Path
import subprocess
import unittest


PROJECT = Path(__file__).resolve().parents[1]
PDF = PROJECT / "docs" / "sales-request-journey-and-privileges.pdf"
GENERATOR = PROJECT / "docs" / "generate-sales-request-journey-pdf.py"
PYTHON = PROJECT / "branding_gate_VENV" / "bin" / "python"


def generate_pdf():
    subprocess.run(
        [str(PYTHON), str(GENERATOR)],
        cwd=PROJECT,
        check=True,
        capture_output=True,
        text=True,
    )


class SalesRequestJourneyPdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generate_pdf()

    def test_pdf_is_two_page_a3_document(self):
        metadata = subprocess.run(
            ["pdfinfo", str(PDF)],
            cwd=PROJECT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertIn("Pages:           2", metadata)
        self.assertIn("Page size:       1190.55 x 841.89 pts (A3)", metadata)

    def test_pdf_contains_only_the_required_sections(self):
        document_text = subprocess.run(
            ["pdftotext", "-layout", str(PDF), "-"],
            cwd=PROJECT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertIn("Sales Request Flowchart", document_text)
        self.assertIn("Sales Request Section Controls", document_text)
        self.assertIn("Urgent Request Approval", document_text)
        self.assertIn("Sales Head Negotiation Review", document_text)
        self.assertIn("approval always sends to Re-Pricing", document_text)
        self.assertIn("Pricing Negotiation Decision", document_text)
        self.assertIn("Re-Price Now, Re-Cost First, or Decline", document_text)
        self.assertIn("Negotiation Re-Costing", document_text)
        self.assertNotIn("Decision Rules and System Controls", document_text)
        self.assertNotIn("Current Permission Alignment Notes", document_text)


if __name__ == "__main__":
    unittest.main()
