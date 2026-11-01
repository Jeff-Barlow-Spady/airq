import time
import board
import busio
import displayio
import terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import label
import vectorio

# Import all sensor libraries
import adafruit_sgp30
import adafruit_bme680
import adafruit_ahtx0
import adafruit_bmp280

# Try to import ENS160 library
try:
    import adafruit_ens160
    HAS_ENS160 = True
except ImportError:
    HAS_ENS160 = False
    print("ENS160 library not found - this sensor will be skipped")

# Release any displays already in use
displayio.release_displays()

class SensorHandler:
    def __init__(self):
        # Store detected sensors
        self.sensors = {}
        self.found_sensors = []

        # Initialize I2C bus for sensors
        self.i2c = busio.I2C(board.GP1, board.GP0)

        # Scan for devices
        devices = self.i2c.scan()
        print("I2C addresses found:", [hex(x) for x in devices])

        # Try to initialize each sensor type
        self._try_init_sgp30()
        self._try_init_bme680()
        self._try_init_aht21()
        self._try_init_bmp280()
        self._try_init_ens160()

        print(f"Found sensors: {', '.join(self.found_sensors)}")

    def _try_init_sgp30(self):
        try:
            sgp30 = adafruit_sgp30.Adafruit_SGP30(self.i2c)
            sgp30.iaq_init()
            # Try to get previously saved baseline values
            try:
                sgp30.set_iaq_baseline(0x8973, 0x8AAE)  # Default baseline values
                print("SGP30 baseline set")
            except Exception as e:
                print(f"SGP30 baseline setting error: {e}")

            print("SGP30 initialized, serial #", [hex(i) for i in sgp30.serial])
            self.sensors['sgp30'] = sgp30
            self.found_sensors.append('SGP30')
        except Exception as e:
            print(f"SGP30 init error: {e}")

    def _try_init_bme680(self):
        try:
            bme680 = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
            bme680.sea_level_pressure = 1013.25
            print("BME680 initialized")
            self.sensors['bme680'] = bme680
            self.found_sensors.append('BME680')
        except Exception as e:
            print(f"BME680 init error: {e}")

    def _try_init_aht21(self):
        try:
            aht21 = adafruit_ahtx0.AHTx0(self.i2c)
            print("AHTx0 initialized")
            self.sensors['aht21'] = aht21
            self.found_sensors.append('AHT21')
        except Exception as e:
            print(f"AHT21 init error: {e}")

    def _try_init_bmp280(self):
        try:
            bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c)
            bmp280.sea_level_pressure = 1013.25
            print("BMP280 initialized")
            self.sensors['bmp280'] = bmp280
            self.found_sensors.append('BMP280')
        except Exception as e:
            print(f"BMP280 init error: {e}")

    def _try_init_ens160(self):
        if not HAS_ENS160:
            return

        try:
            ens160 = adafruit_ens160.ENS160(self.i2c)
            print("ENS160 initialized")
            self.sensors['ens160'] = ens160
            self.found_sensors.append('ENS160')
        except Exception as e:
            print(f"ENS160 init error: {e}")

    def get_readings(self):
        readings = {}

        # Get SGP30 readings if available
        if 'sgp30' in self.sensors:
            try:
                sgp30 = self.sensors['sgp30']
                readings['eco2'] = sgp30.eCO2
                readings['tvoc'] = sgp30.TVOC
            except Exception as e:
                print(f"SGP30 reading error: {e}")
                readings['eco2'] = None
                readings['tvoc'] = None

        # Get BME680 readings if available
        if 'bme680' in self.sensors:
            try:
                bme680 = self.sensors['bme680']
                readings['temperature'] = bme680.temperature
                readings['humidity'] = bme680.relative_humidity
                readings['pressure'] = bme680.pressure
                readings['gas'] = bme680.gas
                readings['altitude'] = bme680.altitude
            except Exception as e:
                print(f"BME680 reading error: {e}")

        # Get AHT21 readings if available
        if 'aht21' in self.sensors:
            try:
                aht21 = self.sensors['aht21']
                readings['aht_temperature'] = aht21.temperature
                readings['aht_humidity'] = aht21.relative_humidity
            except Exception as e:
                print(f"AHT21 reading error: {e}")

        # Get BMP280 readings if available
        if 'bmp280' in self.sensors:
            try:
                bmp280 = self.sensors['bmp280']
                readings['bmp_temperature'] = bmp280.temperature
                readings['bmp_pressure'] = bmp280.pressure
                readings['bmp_altitude'] = bmp280.altitude
            except Exception as e:
                print(f"BMP280 reading error: {e}")

        # Get ENS160 readings if available
        if 'ens160' in self.sensors:
            try:
                ens160 = self.sensors['ens160']
                readings['ens_aqi'] = ens160.AQI
                readings['ens_tvoc'] = ens160.TVOC
                readings['ens_eco2'] = ens160.eCO2
            except Exception as e:
                print(f"ENS160 reading error: {e}")

        return readings


class AirQualityCalculator:
    # Thresholds for air quality assessment
    THRESHOLDS = {
        "co2": {
            "warning": 1500,
            "caution": 1000,
            "medium": 800,
            "good": 600
        },
        "tvoc": {
            "warning": 600,
            "caution": 300,
            "medium": 200,
            "good": 100
        }
    }

    @classmethod
    def determine_state(cls, readings):
        if not readings:
            return "error"

        # Get CO2 value from either SGP30 or ENS160
        co2 = None
        if 'eco2' in readings:
            co2 = readings['eco2']
        elif 'ens_eco2' in readings:
            co2 = readings['ens_eco2']

        # Get TVOC value from either SGP30 or ENS160
        tvoc = None
        if 'tvoc' in readings:
            tvoc = readings['tvoc']
        elif 'ens_tvoc' in readings:
            tvoc = readings['ens_tvoc']

        if co2 is None or tvoc is None:
            return "error"

        # Check thresholds in descending order of severity
        co2_state = next(
            (level for level, value in cls.THRESHOLDS["co2"].items()
             if co2 >= value),
            "good"
        )
        tvoc_state = next(
            (level for level, value in cls.THRESHOLDS["tvoc"].items()
             if tvoc >= value),
            "good"
        )

        # Return the more severe state
        severity = ["good", "medium", "caution", "warning", "error"]
        return max([co2_state, tvoc_state], key=lambda x: severity.index(x))


class DisplayHandler:
    def __init__(self):
        # Initialize I2C bus for display
        i2c = busio.I2C(board.GP0, board.GP1)

        # Initialize display
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

        # Create display group
        self.main_group = displayio.Group()
        self.display.show(self.main_group)

        # Create color palette
        self.palette = displayio.Palette(2)
        self.palette[0] = 0x000000  # Black
        self.palette[1] = 0xFFFFFF  # White

        self.current_view = "sensors"  # Options: "sensors", "canary"
        print("Display initialized")

    def draw_sensors_view(self, readings):
        # Clear the group
        while len(self.main_group) > 0:
            self.main_group.pop()

        y_pos = 0
        line_height = 10

        # If no readings, show error message
        if not readings:
            error_text = label.Label(
                terminalio.FONT,
                text="No sensor readings",
                color=0xFFFFFF,
                x=5,
                y=32
            )
            self.main_group.append(error_text)
            return

        # Add sensor data in order of priority
        important_keys = [
            ('eco2', 'CO2'),
            ('tvoc', 'VOC'),
            ('temperature', 'Temp'),
            ('humidity', 'Hum'),
            ('pressure', 'Press'),
            ('gas', 'Gas'),
            ('ens_aqi', 'AQI')
        ]

        for key, display_name in important_keys:
            if key in readings and readings[key] is not None:
                value = readings[key]
                # Format based on typical range for the reading
                if 'temperature' in key:
                    value_str = f"{value:.1f}C"
                elif 'humidity' in key:
                    value_str = f"{value:.0f}%"
                elif 'pressure' in key:
                    value_str = f"{value/100:.0f}hPa"
                elif key == 'gas':
                    value_str = f"{value/1000:.1f}kΩ"
                else:
                    value_str = f"{value:.0f}"

                # Create and add the label
                text_label = label.Label(
                    terminalio.FONT,
                    text=f"{display_name}: {value_str}",
                    color=0xFFFFFF,
                    x=5,
                    y=y_pos + line_height
                )
                self.main_group.append(text_label)
                y_pos += line_height

    def draw_canary_state(self, state):
        print(f"Drawing canary state: {state}")

        # Clear the group
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

        # Add state indicator
        if state == "warning":
            # Add X eyes
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
        # Clear the group
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

    def update_display(self, readings, state):
        if self.current_view == "sensors":
            self.draw_sensors_view(readings)
        else:
            self.draw_canary_state(state)


def main():
    print("Initializing sensors...")
    sensors = SensorHandler()
    print("Initializing display...")
    display = DisplayHandler()
    view_toggle_time = time.monotonic()
    last_state = None

    try:
        while True:
            print("Getting sensor readings...")
            readings = sensors.get_readings()

            # Print all readings to console for debugging
            for key, value in readings.items():
                print(f"{key}: {value}")

            # Determine air quality state
            state = AirQualityCalculator.determine_state(readings)
            print(f"Air quality state: {state}")

            # Update display with new readings
            display.update_display(readings, state)

            # Toggle view every 5 seconds
            current_time = time.monotonic()
            if current_time - view_toggle_time > 5:
                display.current_view = "sensors" if display.current_view == "canary" else "canary"
                view_toggle_time = current_time

            # Wait before next reading
            time.sleep(2)

    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()