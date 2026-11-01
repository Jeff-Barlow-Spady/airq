import board
import time
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import busio
import digitalio
import adafruit_bme680
import RPi.GPIO as GPIO
from board import SCL, SDA  # Add this import
# Configure GPIO mode - must be at the start
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
i2c = busio.I2C(SCL, SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)

# Hardware Setup
class SensorHandler:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        if not mock_mode:
            # Use explicit SCL/SDA pins
            self.sensor = sensor
        else:
            self.mock_co2 = 600
            self.mock_voc = 100

    def get_readings(self):
        """Get sensor data from BME680"""
        try:
            if self.mock_mode:
                return self.mock_co2, self.mock_voc
            return self.sensor.gas, self.sensor.humidity
        except Exception as e:
            print(f"Sensor error: {e}")
            return None, None

class AirQualityCalculator:
    # Updated thresholds to match test cases
    THRESHOLDS = {
        "co2": {
            "warning": 1500,
            "caution": 1000,
            "medium": 800,
            "good": 600
        },
        "voc": {
            "warning": 600,
            "caution": 300,
            "medium": 200,
            "good": 100
        }
    }

    @classmethod
    def determine_state(cls, co2, voc):
        if co2 is None or voc is None:
            return "error"

        # Check thresholds in descending order of severity
        co2_state = next(
            (level for level, value in cls.THRESHOLDS["co2"].items()
             if co2 >= value),
            "good"
        )
        voc_state = next(
            (level for level, value in cls.THRESHOLDS["voc"].items()
             if voc >= value),
            "good"
        )

        # Return the more severe state
        severity = ["good", "medium", "caution", "warning", "error"]
        return max([co2_state, voc_state], key=lambda x: severity.index(x))

class DisplayHandler:
    def __init__(self, oled):
        # Use explicit SCL/SDA pins
        self.oled = oled

        # Add view state
        self.current_view = "canary"  # Options: "canary", "numbers"

        # Initialize display
        self.oled.fill(0)
        self.oled.show()
        time.sleep(1)

        print("Display initialized")

    def draw_numbers_view(self, co2, voc):
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)

        font = ImageFont.load_default()
        draw.text((10, 10), f"CO2: {co2:.1f}", font=font, fill=1)
        draw.text((10, 30), f"VOC: {voc:.1f}", font=font, fill=1)

        self.oled.image(image)
        self.oled.show()

    def draw_state(self, state, co2=None, voc=None):
        if self.current_view == "numbers" and co2 is not None and voc is not None:
            self.draw_numbers_view(co2, voc)
            return

        print(f"Drawing state: {state}")

        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        self.oled.fill(0)

        # Draw the canary
        draw.ellipse((40, 20, 80, 45), outline=1, fill=1)
        draw.ellipse((75, 15, 90, 30), outline=1, fill=1)
        draw.polygon([(90, 20), (98, 23), (90, 26)], outline=1, fill=1)
        draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)
        draw.line((60, 45, 60, 55), fill=1, width=2)
        draw.line((55, 55, 65, 55), fill=1, width=1)

        if state == "warning":
            draw.line((77, 17, 82, 22), fill=1, width=1)
            draw.line((77, 22, 82, 17), fill=1, width=1)
        elif state == "good":
            draw.ellipse((95, 10, 99, 14), outline=1, fill=1)  # note head
            draw.line((99, 12, 99, 4), fill=1, width=1)  # note stem
            draw.ellipse((105, 8, 109, 12), outline=1, fill=1)  # note head
            draw.line((109, 10, 109, 2), fill=1, width=1)  # note stem

        try:
            self.oled.image(image)
            self.oled.show()
            print("Display updated")
        except Exception as e:
            print(f"Display error: {e}")

    def show_error(self, message):
        print(f"Showing error: {message}")  # Debug print
        self.oled.fill(0)
        self.oled.text(message, 0, 0)
        self.oled.show()

def main(mock_sensors=False):
    print("Initializing...")
    sensors = SensorHandler(mock_mode=mock_sensors)
    display = DisplayHandler(oled)
    last_state = None

    try:
        while True:
            print("Getting readings...")
            co2, voc = sensors.get_readings()
            state = AirQualityCalculator.determine_state(co2, voc)
            print(f"State: {state}, CO2: {co2}, VOC: {voc}")  # Debug print

            if state != last_state:
                if state == "error":
                    display.show_error("Sensor Error")
                else:
                    display.draw_state(state, co2, voc)
                last_state = state

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        display.oled.fill(0)
        display.oled.show()
    finally:
        GPIO.cleanup()  # Add GPIO cleanup

if __name__ == "__main__":
    main(mock_sensors=False)  # Set to False when using real sensors