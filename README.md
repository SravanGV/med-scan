# med-scan

Med Scan is a lightweight ML-based web application prototype for scanning uploaded medical images and flagging possible tumor/defect patterns.

## Run the web app

```bash
python app.py
```

Open `http://127.0.0.1:8000`, upload a medical image, and review the prediction.

## Run tests

```bash
python -m unittest discover -s tests
```

## Notes

- This project uses a simple byte-feature anomaly model as a prototype classifier.
- Upload limit is 10MB per image.
- Predictions are **not** a clinical diagnosis.
