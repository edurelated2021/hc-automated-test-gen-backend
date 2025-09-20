
import PyPDF2

class PDFService:
    def extract_text(self, file_path: str) -> str:
        text_parts = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ''
                except Exception:
                    page_text = ''
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
