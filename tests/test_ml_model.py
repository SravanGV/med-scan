import unittest

from ml_model import extract_features, predict_scan


class MLModelTests(unittest.TestCase):
    def test_extract_features_rejects_empty_bytes(self):
        with self.assertRaises(ValueError):
            extract_features(b"")

    def test_extract_features_returns_expected_keys(self):
        features = extract_features(bytes([10, 20, 30, 220, 240]))

        self.assertEqual(
            set(features.keys()),
            {
                "mean",
                "std",
                "high_intensity_ratio",
                "transition_ratio",
                "entropy",
                "center_intensity",
            },
        )
        for value in features.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_predict_scan_flags_high_entropy_pattern(self):
        image_bytes = bytes(range(256)) * 16
        result = predict_scan(image_bytes)
        self.assertIn(result.label, {"tumor_suspected", "defect_suspected"})
        self.assertGreaterEqual(result.probability, 0.45)

    def test_predict_scan_identifies_low_variance_pattern(self):
        image_bytes = bytes([40]) * 2048
        result = predict_scan(image_bytes)
        self.assertEqual(result.label, "no_obvious_defect")
        self.assertLess(result.probability, 0.45)


if __name__ == "__main__":
    unittest.main()
