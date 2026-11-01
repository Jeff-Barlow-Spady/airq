from board import SCL, SDA
import time
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import busio
import digitalio
import vectorio
######SENSORS######
#import adafruit_bme680
import adafruit_sgp30
import displayio
import terminalio
# Initialize display
displayio.release_displays()

# Hardware Setup
class SensorHandler:
    def __init__(self, mock_mode=True):
        self.mock_mode = mock_mode
        if not mock_mode:
            # Initialize I2C1 bus for SGP30 (matching your working example)
            i2c = busio.I2C(board.GP15, board.GP14)  # SCL, SDA for I2C1
            print("I2C addresses found:", [hex(x) for x in i2c.scan()])

            try:
                self.sensor = adafruit_sgp30.Adafruit_SGP30(i2c)
                self.sensor.iaq_init()
                self.sensor.set_iaq_baseline(0x89E7, 0x8A3D)
                print("SGP30 serial #", [hex(i) for i in self.sensor.serial])
            except Exception as e:
                print(f"Error initializing sensor: {e}")
                self.mock_mode = True

        if self.mock_mode:
            self.mock_co2 = 600
            self.mock_voc = 100

    def get_readings(self):
        try:
            if self.mock_mode:
                return self.mock_co2, self.mock_voc
            return self.sensor.eCO2, self.sensor.TVOC
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
    def __init__(self):
        displayio.release_displays()
        # Initialize I2C0 bus for display (matching your working example)
        i2c = busio.I2C(board.GP1, board.GP0)  # SCL, SDA for I2C0
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

        # Create the display context
        self.main_group = displayio.Group()
        self.display.show(self.main_group)

        # Create palette for shapes
        self.palette = displayio.Palette(2)
        self.palette[0] = 0x000000  # Black
        self.palette[1] = 0xFFFFFF  # White

        self.current_view = "canary"  # Options: "canary", "numbers"

        print("Display initialized")

    def draw_numbers_view(self, co2, voc, gas_resistance):
        while len(self.main_group) > 0:
            self.main_group.pop()

        co2_text = label.Label(
            terminalio.FONT,
            text=f"CO2: {co2:.1f}",
            color=0xFFFFFF,
            x=10,
            y=20
        )
        voc_text = label.Label(
            terminalio.FONT,
            text=f"VOC: {voc:.1f}",
            color=0xFFFFFF,
            x=10,
            y=40
        )
        gas_text = label.Label(
            terminalio.FONT,
            text=f"Gas: {gas_resistance:.1f}",
            color=0xFFFFFF,
            x=10,
            y=60
        )
        self.main_group.append(co2_text)
        self.main_group.append(voc_text)
        self.main_group.append(gas_text)

    def draw_state(self, state, co2=None, voc=None, gas=None):
        if self.current_view == "numbers" and co2 is not None and voc is not None and gas is not None:
            self.draw_numbers_view(co2, voc, gas)
            return

        print(f"Drawing state: {state}")

        while len(self.main_group) > 0:
            self.main_group.pop()

        # Draw canary body (circle)
        body = vectorio.Circle(
            pixel_shader=self.palette,
            radius=15,
            x=60,
            y=32,
            color=1
        )

        # Draw head (smaller circle)
        head = vectorio.Circle(
            pixel_shader=self.palette,
            radius=8,
            x=82,
            y=22,
            color=1
        )

        # Draw beak (triangle)
        beak_points = [(90, 20), (98, 23), (90, 26)]
        beak = vectorio.Polygon(
            pixel_shader=self.palette,
            points=beak_points,
            x=0,
            y=0,
            color=1
        )

        # Draw leg (rectangle)
        leg = vectorio.Rectangle(
            pixel_shader=self.palette,
            width=2,
            height=10,
            x=60,
            y=45,
            color=1
        )

        self.main_group.append(body)
        self.main_group.append(head)
        self.main_group.append(beak)
        self.main_group.append(leg)

        if state == "warning":
            # Add X eyes using small lines
            eye1 = vectorio.Rectangle(
                pixel_shader=self.palette,
                width=5,
                height=1,
                x=77,
                y=20,
                color=1
            )
            eye2 = vectorio.Rectangle(
                pixel_shader=self.palette,
                width=5,
                height=1,
                x=77,
                y=24,
                color=1
            )
            self.main_group.append(eye1)
            self.main_group.append(eye2)

        elif state == "good":
            # Add musical notes
            note1 = vectorio.Circle(
                pixel_shader=self.palette,
                radius=2,
                x=97,
                y=12,
                color=1
            )
            note_stem1 = vectorio.Rectangle(
                pixel_shader=self.palette,
                width=1,
                height=8,
                x=99,
                y=4,
                color=1
            )
            self.main_group.append(note1)
            self.main_group.append(note_stem1)

    def show_error(self, message):
        print(f"Showing error: {message}")
        while len(self.main_group) > 0:
            self.main_group.pop()

        error_text = label.Label(
            terminalio.FONT,
            text=message,
            color=0xFFFFFF,
            x=0,
            y=32
        )
        self.main_group.append(error_text)

def main(mock_sensors=True):
    print("Initializing...")
    sensors = SensorHandler(mock_mode=mock_sensors)
    display = DisplayHandler()
    last_state = None

    try:
        while True:
            print("Getting readings...")
            gas, co2, voc = sensors.get_readings()
            state = AirQualityCalculator.determine_state(co2, voc)
            print(f"State: {state}, CO2: {co2}, VOC: {voc}, Gas: {gas}")

            if state != last_state:
                if state == "error":
                    display.show_error("Sensor Error")
                else:
                    display.draw_state(state, co2, voc, gas)
                last_state = state

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")

if __name__ == "__main__":
    main(mock_sensors=True)  # Set to False when using real sensors