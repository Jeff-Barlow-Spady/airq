import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch, MagicMock
from air_monitor import AirQualityCalculator, DisplayHandler, SensorHandler

class TestAirQualityMonitor(unittest.TestCase):
    def test_state_determination(self):
        test_cases = [
            # (co2, voc, expected_state)
            (500, 80, "good"),
            (800, 200, "medium"),
            (1500, 300, "caution"),
            (3000, 600, "warning"),
            (None, 100, "error")
        ]

        for co2, voc, expected in test_cases:
            with self.subTest(f"{co2},{voc}->{expected}"):
                result = AirQualityCalculator.determine_state(co2, voc)
                self.assertEqual(result, expected)

    @patch.object(DisplayHandler, '_draw_x_eyes')
    def test_warning_display(self, mock_draw):
        display = DisplayHandler()
        display.draw_state("warning")
        mock_draw.assert_called_once()

    def test_threshold_boundaries(self):
        self.assertEqual(
            AirQualityCalculator.determine_state(600, 100),
            "good"
        )
        self.assertEqual(
            AirQualityCalculator.determine_state(601, 101),
            "medium"
        )

    @patch('bme680_sensor.adafruit_bme680.Adafruit_BME680_I2C')
    def test_bme680_integration(self, mock_bme):
        mock_instance = MagicMock()
        mock_instance.get_readings.return_value = {
            'temperature': 25.0,
            'gas': 150000,
            'humidity': 45.0,
            'pressure': 1013.25,
            'altitude': 0.0
        }
        mock_bme.return_value = mock_instance

        handler = SensorHandler(mock_mode=False)
        gas, humi = handler.get_readings()
        self.assertEqual(gas, 150000)
        self.assertEqual(humi, 45.0)

if __name__ == "__main__":
    unittest.main()