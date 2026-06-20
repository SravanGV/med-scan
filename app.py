from __future__ import annotations

import cgi
import logging
from html import escape
from wsgiref.simple_server import make_server

from ml_model import predict_scan


HTML_PAGE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Med Scan AI</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 2rem auto; line-height: 1.5; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.2rem; margin-top: 1rem; }}
    .ok {{ color: #176b2c; }}
    .warn {{ color: #8f4c00; }}
    .alert {{ color: #9f1717; }}
  </style>
</head>
<body>
  <h1>Med Scan AI Prototype</h1>
  <p>Upload a medical image to scan for possible tumor or defect patterns.</p>
  <form action=\"/scan\" method=\"post\" enctype=\"multipart/form-data\">
    <input type=\"file\" name=\"image\" accept=\".png,.jpg,.jpeg,.bmp,.tif,.tiff\" required />
    <button type=\"submit\">Scan Image</button>
  </form>
  {result}
</body>
</html>
"""
LOGGER = logging.getLogger(__name__)


def _result_class(label: str) -> str:
    if label == "tumor_suspected":
        return "alert"
    if label == "defect_suspected":
        return "warn"
    return "ok"


def _render_result(result_html: str = "") -> bytes:
    return HTML_PAGE.format(result=result_html).encode("utf-8")


def application(environ, start_response):
    if environ["REQUEST_METHOD"] == "GET":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [_render_result()]

    if environ["REQUEST_METHOD"] == "POST" and environ.get("PATH_INFO", "") == "/scan":
        form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)

        if "image" not in form:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [_render_result("<div class='card alert'>No image uploaded.</div>")]

        file_item = form["image"]
        if not getattr(file_item, "file", None):
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [_render_result("<div class='card alert'>No image uploaded.</div>")]

        image_bytes = file_item.file.read()
        filename = escape(getattr(file_item, "filename", "uploaded-file"))

        try:
            scan_result = predict_scan(image_bytes)
            css_class = _result_class(scan_result.label)
            result_html = (
                f"<div class='card {css_class}'>"
                f"<strong>File:</strong> {filename}<br/>"
                f"<strong>Prediction:</strong> {escape(scan_result.label)}<br/>"
                f"<strong>Confidence:</strong> {scan_result.confidence:.2%}<br/>"
                f"<strong>Risk Probability:</strong> {scan_result.probability:.2%}<br/>"
                f"<strong>Notes:</strong> {escape(scan_result.message)}"
                "</div>"
            )
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
            return [_render_result(result_html)]
        except ValueError:
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
            return [_render_result("<div class='card alert'>Invalid or empty image file.</div>")]
        except Exception:
            LOGGER.exception("Image processing failed")
            start_response("500 Internal Server Error", [("Content-Type", "text/html; charset=utf-8")])
            return [
                _render_result(
                    "<div class='card alert'>An error occurred while processing the image. Please try again.</div>"
                )
            ]

    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not Found"]


if __name__ == "__main__":
    server = make_server("127.0.0.1", 8000, application)
    print("Med Scan AI running at http://127.0.0.1:8000")
    server.serve_forever()
