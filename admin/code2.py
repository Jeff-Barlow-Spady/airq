import time
import board
import busio
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306

# Import sensor libraries
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

# Release any resources currently in use for the displays
displayio.release_displays()

class SensorHandler:
    # Known I2C addresses for common sensors
    KNOWN_ADDRESSES = {
        0x58: "SGP30",
        0x76: "BME680/BMP280 (alternate)",
        0x77: "BME680/BMP280 (default)",
        0x38: "AHT21/AHT20",
        0x5A: "ENS160 (default)",
        0x53: "ENS160 (alternate)",
        0x3C: "SSD1306 OLED Display",
        0x3D: "SSD1306 OLED Display (alternate)"
    }

    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        self.sensors = {}
        self.found_sensors = []
        self.detected_addresses = []

        if not mock_mode:
            # Initialize I2C bus for RP2040
            self.i2c = busio.I2C(board.GP15, board.GP14)  # SDA, SCL for Pico
            print("Scanning I2C bus...")

            # Scan for I2C devices
            self._scan_i2c_bus()

            # Try to initialize each sensor with explicit addresses
            self._try_init_sgp30()
            self._try_init_bme680()
            self._try_init_aht21()
            self._try_init_bmp280()
            self._try_init_ens160()

            if not self.found_sensors:
                print("No sensors found, falling back to mock mode")
                self.mock_mode = True

        if self.mock_mode:
            print("Running in mock mode with simulated sensor data")
            self.mock_data = {
                'eco2': 600,
                'tvoc': 100,
                'temperature': 22.5,
                'humidity': 45.0,
                'pressure': 1013.25,
                'gas': 150000,
                'altitude': 0.0,
                'aqi': 50
            }

    def _scan_i2c_bus(self):
        """Scan the I2C bus for connected devices using CircuitPython."""
        try:
            print("Scanning I2C bus for devices...")
            print("Found devices at addresses:")

            # CircuitPython I2C scanning approach
            while not self.i2c.try_lock():
                pass

            try:
                for addr in self.i2c.scan():
                    self.detected_addresses.append(addr)
                    device_name = self.KNOWN_ADDRESSES.get(addr, "Unknown device")
                    print(f"  0x{addr:02X}: {device_name}")
            finally:
                self.i2c.unlock()

            if not self.detected_addresses:
                print("No I2C devices found!")

        except Exception as e:
            print(f"Error scanning I2C bus: {e}")

    def _try_init_sgp30(self):
        # SGP30 typically has address 0x58
        if 0x58 not in self.detected_addresses:
            print("SGP30 not detected on I2C bus (0x58)")
            return

        try:
            sgp30 = adafruit_sgp30.Adafruit_SGP30(self.i2c)
            sgp30.iaq_init()
            # Try to set baseline values (optional)
            try:
                sgp30.set_iaq_baseline(0x8973, 0x8AAE)
            except Exception as e:
                print(f"SGP30 baseline setting error: {e}")

            print("SGP30 initialized at address 0x58")
            self.sensors['sgp30'] = sgp30
            self.found_sensors.append('SGP30')
        except Exception as e:
            print(f"SGP30 init error: {e}")

    def _try_init_bme680(self):
        # Check for BME680 at address 0x76 first (most common)
        bme680_address = None
        if 0x76 in self.detected_addresses:
            bme680_address = 0x76
        elif 0x77 in self.detected_addresses:
            bme680_address = 0x77

        if bme680_address is None:
            print("BME680 not detected on I2C bus (0x76 or 0x77)")
            return

        try:
            bme680 = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=bme680_address)
            bme680.sea_level_pressure = 1013.25
            print(f"BME680 initialized at address 0x{bme680_address:02X}")
            self.sensors['bme680'] = bme680
            self.found_sensors.append('BME680')
        except Exception as e:
            print(f"BME680 init error: {e}")

    def _try_init_aht21(self):
        # AHT21 typically has address 0x38
        if 0x38 not in self.detected_addresses:
            print("AHT21 not detected on I2C bus (0x38)")
            return

        try:
            aht21 = adafruit_ahtx0.AHTx0(self.i2c, address=0x38)
            print("AHT21 initialized at address 0x38")
            self.sensors['aht21'] = aht21
            self.found_sensors.append('AHT21')
        except Exception as e:
            print(f"AHT21 init error: {e}")

    def _try_init_bmp280(self):
        # BMP280 typically at address 0x76 or 0x77
        # First check if BME680 is using those addresses
        if 'BME680' in self.found_sensors:
            bme680_addr = self.sensors['bme680']._addr
            if bme680_addr == 0x76:
                bmp280_addr = 0x77
            else:
                bmp280_addr = 0x76
        else:
            # Try both addresses
            if 0x76 in self.detected_addresses:
                bmp280_addr = 0x76
            elif 0x77 in self.detected_addresses:
                bmp280_addr = 0x77
            else:
                print("BMP280 not detected on I2C bus (0x76 or 0x77)")
                return False

        try:
            bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=bmp280_addr)
            print(f"BMP280 initialized at address 0x{bmp280_addr:02X}")
            self.sensors['bmp280'] = bmp280
            self.found_sensors.append('BMP280')
            return True
        except Exception as e:
            print(f"BMP280 init error: {e}")
            return False

    def _try_init_ens160(self):
        if not HAS_ENS160:
            return

        # ENS160 can be at 0x5A (default) or 0x53
        ens160_address = None
        if 0x5A in self.detected_addresses:
            ens160_address = 0x5A
        elif 0x53 in self.detected_addresses:
            ens160_address = 0x53

        if ens160_address is None:
            print("ENS160 not detected on I2C bus (0x5A or 0x53)")
            return

        try:
            ens160 = adafruit_ens160.ENS160(self.i2c, address=ens160_address)
            print(f"ENS160 initialized at address 0x{ens160_address:02X}")
            self.sensors['ens160'] = ens160
            self.found_sensors.append('ENS160')
        except Exception as e:
            print(f"ENS160 init error: {e}")

    def get_readings(self):
        readings = {}

        if self.mock_mode:
            # Add some random variation to mock data
            import random
            readings = {
                'eco2': self.mock_data['eco2'] + random.randint(-20, 20),
                'tvoc': self.mock_data['tvoc'] + random.randint(-10, 10),
                'temperature': self.mock_data['temperature'] + random.uniform(-0.5, 0.5),
                'humidity': self.mock_data['humidity'] + random.uniform(-2, 2),
                'pressure': self.mock_data['pressure'] + random.uniform(-1, 1),
                'gas': self.mock_data['gas'] + random.randint(-5000, 5000),
                'altitude': self.mock_data['altitude'] + random.uniform(-1, 1),
                'aqi': self.mock_data['aqi'] + random.randint(-5, 5)
            }
            return readings

        # Get SGP30 readings
        if 'sgp30' in self.sensors:
            try:
                sgp30 = self.sensors['sgp30']
                readings['eco2'] = sgp30.eCO2
                readings['tvoc'] = sgp30.TVOC
            except Exception as e:
                print(f"SGP30 reading error: {e}")

        # Get BME680 readings
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

        # Get AHT21 readings
        if 'aht21' in self.sensors:
            try:
                aht21 = self.sensors['aht21']
                readings['aht_temperature'] = aht21.temperature
                readings['aht_humidity'] = aht21.relative_humidity
            except Exception as e:
                print(f"AHT21 reading error: {e}")

        # Get BMP280 readings
        if 'bmp280' in self.sensors:
            try:
                bmp280 = self.sensors['bmp280']
                readings['bmp_temperature'] = bmp280.temperature
                readings['bmp_pressure'] = bmp280.pressure
                readings['bmp_altitude'] = bmp280.altitude
            except Exception as e:
                print(f"BMP280 reading error: {e}")

        # Get ENS160 readings
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
        "voc": {
            "warning": 600,
            "caution": 300,
            "medium": 200,
            "good": 100
        }
    }

    @classmethod
    def determine_state(cls, readings):
        # Get CO2 value from any available sensor
        co2 = None
        if 'eco2' in readings:
            co2 = readings['eco2']
        elif 'ens_eco2' in readings:
            co2 = readings['ens_eco2']

        # Get TVOC value from any available sensor
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
            (level for level, value in cls.THRESHOLDS["voc"].items()
             if tvoc >= value),
            "good"
        )

        # Return the more severe state
        severity = ["good", "medium", "caution", "warning", "error"]
        return max([co2_state, tvoc_state], key=lambda x: severity.index(x))


class DisplayHandler:
    def __init__(self, i2c):
        # Initialize DisplayIO for SSD1306
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

        # Current page for display rotation
        self.current_page = 0
        self.total_pages = 4  # CO2/VOC, Temp/Humidity, Pressure/Gas, Status

        # Create a root group to hold all display elements
        self.root_group = displayio.Group()
        self.display.show(self.root_group)

        print("Display initialized")

    def draw_readings_page(self, readings, page):
        # Clear the display group
        while len(self.root_group) > 0:
            self.root_group.pop()

        if page == 0:  # CO2/VOC page
            title = label.Label(terminalio.FONT, text="Air Quality", x=0, y=8)
            self.root_group.append(title)

            co2 = readings.get('eco2') or readings.get('ens_eco2')
            tvoc = readings.get('tvoc') or readings.get('ens_tvoc')

            if co2:
                co2_text = label.Label(terminalio.FONT, text=f"CO2: {co2} ppm", x=0, y=24)
                self.root_group.append(co2_text)
            if tvoc:
                tvoc_text = label.Label(terminalio.FONT, text=f"TVOC: {tvoc} ppb", x=0, y=40)
                self.root_group.append(tvoc_text)

            # Add AQI if available
            aqi = readings.get('ens_aqi')
            if aqi:
                aqi_text = label.Label(terminalio.FONT, text=f"AQI: {aqi}", x=0, y=56)
                self.root_group.append(aqi_text)

        elif page == 1:  # Temperature/Humidity page
            title = label.Label(terminalio.FONT, text="Temp & Humidity", x=0, y=8)
            self.root_group.append(title)

            # Get temperature from any available sensor
            temp = (readings.get('temperature') or
                   readings.get('aht_temperature') or
                   readings.get('bmp_temperature'))

            # Get humidity from any available sensor
            humidity = (readings.get('humidity') or
                       readings.get('aht_humidity'))

            if temp:
                temp_text = label.Label(terminalio.FONT, text=f"Temp: {temp:.1f}°C", x=0, y=24)
                self.root_group.append(temp_text)
            if humidity:
                hum_text = label.Label(terminalio.FONT, text=f"Humidity: {humidity:.1f}%", x=0, y=40)
                self.root_group.append(hum_text)

                # Create a humidity bar using a Bitmap
                bitmap = displayio.Bitmap(128, 8, 2)
                palette = displayio.Palette(2)
                palette[0] = 0x000000  # Black
                palette[1] = 0xFFFFFF  # White

                # Draw border and fill based on humidity
                bar_width = int((humidity / 100) * 128)
                for x in range(128):
                    for y in range(8):
                        if x < bar_width and (y > 0 and y < 7):
                            bitmap[x, y] = 1  # White
                        elif x == 0 or x == 127 or y == 0 or y == 7:
                            bitmap[x, y] = 1  # White border
                        else:
                            bitmap[x, y] = 0  # Black

                bar_grid = displayio.TileGrid(bitmap, pixel_shader=palette, x=0, y=50)
                self.root_group.append(bar_grid)

        elif page == 2:  # Pressure/Gas page
            title = label.Label(terminalio.FONT, text="Pressure & Gas", x=0, y=8)
            self.root_group.append(title)

            # Get pressure from any available sensor
            pressure = (readings.get('pressure') or
                       readings.get('bmp_pressure'))

            # Get gas resistance from BME680
            gas = readings.get('gas')

            # Get altitude from any available sensor
            altitude = (readings.get('altitude') or
                       readings.get('bmp_altitude'))

            if pressure:
                press_text = label.Label(terminalio.FONT, text=f"Press: {pressure/100:.1f} hPa", x=0, y=24)
                self.root_group.append(press_text)
            if gas:
                gas_text = label.Label(terminalio.FONT, text=f"Gas: {gas/1000:.1f} kΩ", x=0, y=40)
                self.root_group.append(gas_text)
            if altitude:
                alt_text = label.Label(terminalio.FONT, text=f"Alt: {altitude:.1f} m", x=0, y=56)
                self.root_group.append(alt_text)

        elif page == 3:  # Status page
            title = label.Label(terminalio.FONT, text="Sensor Status", x=0, y=8)
            self.root_group.append(title)

            y_pos = 24
            for i, sensor in enumerate(['SGP30', 'BME680', 'AHT21', 'BMP280', 'ENS160']):
                # Only draw 3 sensors per page to avoid crowding
                if i > 2 and y_pos >= 56:
                    continue

                # Check if we have relevant readings for this sensor
                has_sensor = False
                if sensor == 'SGP30' and ('eco2' in readings or 'tvoc' in readings):
                    has_sensor = True
                elif sensor == 'BME680' and ('temperature' in readings or 'humidity' in readings):
                    has_sensor = True
                elif sensor == 'AHT21' and ('aht_temperature' in readings or 'aht_humidity' in readings):
                    has_sensor = True
                elif sensor == 'BMP280' and ('bmp_temperature' in readings or 'bmp_pressure' in readings):
                    has_sensor = True
                elif sensor == 'ENS160' and ('ens_aqi' in readings or 'ens_tvoc' in readings):
                    has_sensor = True

                status = "✓" if has_sensor else "✗"
                status_text = label.Label(terminalio.FONT, text=f"{sensor}: {status}", x=0, y=y_pos)
                self.root_group.append(status_text)
                y_pos += 16

    def draw_canary_state(self, state):
        # Clear the display group
        while len(self.root_group) > 0:
            self.root_group.pop()

        # Draw state text at top
        if state == "warning":
            title = label.Label(terminalio.FONT, text="WARNING!", x=2, y=8)
        elif state == "good":
            title = label.Label(terminalio.FONT, text="GOOD AIR", x=2, y=8)
        elif state == "medium" or state == "caution":
            message = "CAUTION" if state == "caution" else "MODERATE"
            title = label.Label(terminalio.FONT, text=message, x=2, y=8)
        else:  # error or unknown state
            title = label.Label(terminalio.FONT, text="ERROR", x=2, y=8)

        self.root_group.append(title)

        # Create a bitmap for the canary
        bitmap = displayio.Bitmap(128, 64, 2)
        palette = displayio.Palette(2)
        palette[0] = 0x000000  # Black
        palette[1] = 0xFFFFFF  # White

        # Draw a simplified canary in bitmap
        # Body (circle approximation)
        for x in range(40, 80):
            for y in range(20, 45):
                if ((x - 60) ** 2 + (y - 32) ** 2) < 150:
                    bitmap[x, y] = 1

        # Head (smaller circle)
        for x in range(75, 90):
            for y in range(15, 30):
                if ((x - 82) ** 2 + (y - 22) ** 2) < 40:
                    bitmap[x, y] = 1

        # Beak (triangle)
        for x in range(90, 98):
            for y in range(20, 27):
                if y > (x - 90) * 0.3 + 20 and y < 26 - (x - 90) * 0.3:
                    bitmap[x, y] = 1

        # Leg
        for x in range(59, 61):
            for y in range(45, 55):
                bitmap[x, y] = 1

        # Add state-specific features to bitmap
        if state == "warning":
            # X eyes
            for i in range(5):
                bitmap[77+i, 17+i] = 1
                bitmap[77+i, 22-i] = 1
                bitmap[82-i, 17+i] = 1
                bitmap[82-i, 22-i] = 1

        elif state == "good":
            # Musical notes
            for x in range(95, 99):
                for y in range(10, 14):
                    if ((x - 97) ** 2 + (y - 12) ** 2) < 5:
                        bitmap[x, y] = 1

            # Note stem
            for y in range(4, 13):
                bitmap[99, y] = 1

            # Second note
            for x in range(105, 109):
                for y in range(8, 12):
                    if ((x - 107) ** 2 + (y - 10) ** 2) < 5:
                        bitmap[x, y] = 1

            # Second stem
            for y in range(2, 11):
                bitmap[109, y] = 1

        elif state == "medium" or state == "caution":
            # Straight mouth
            for x in range(77, 83):
                bitmap[x, 20] = 1

        else:  # error
            # Question mark
            bitmap[82, 20] = 1
            bitmap[82, 21] = 1
            bitmap[83, 20] = 1
            bitmap[83, 21] = 1

        canary_grid = displayio.TileGrid(bitmap, pixel_shader=palette, x=0, y=0)
        self.root_group.append(canary_grid)

    def show_error(self, message):
        # Clear the display group
        while len(self.root_group) > 0:
            self.root_group.pop()

        # Add error title
        error_title = label.Label(terminalio.FONT, text="ERROR:", x=0, y=8)
        self.root_group.append(error_title)

        # Break message into multiple lines if needed
        words = message.split()
        current_line = ""
        y_pos = 24

        for word in words:
            test_line = current_line + word + " "
            # Check if adding this word would exceed display width
            # This is an approximation since we can't measure exact width with terminalio
            if len(test_line) * 6 > 128:  # Assume ~6 pixels per character
                error_line = label.Label(terminalio.FONT, text=current_line, x=0, y=y_pos)
                self.root_group.append(error_line)
                y_pos += 16
                current_line = word + " "

                # Stop if we run out of vertical space
                if y_pos >= 64:
                    break
            else:
                current_line = test_line

        # Add any remaining text
        if current_line and y_pos < 64:
            error_line = label.Label(terminalio.FONT, text=current_line, x=0, y=y_pos)
            self.root_group.append(error_line)


def main():
    try:
        print("Air Quality Monitor with Multiple Sensors")
        print("----------------------------------------")

        # Initialize sensor handler
        sensors = SensorHandler(mock_mode=False)  # Set to True to use mock data

        # Initialize display
        display = DisplayHandler(sensors.i2c if not sensors.mock_mode else busio.I2C(board.GP1, board.GP0))

        page_change_time = time.monotonic()
        last_state = None
        canary_mode = False  # Toggle between data display and canary

        print(f"Found sensors: {', '.join(sensors.found_sensors) if sensors.found_sensors else 'None (using mock data)'}")

        while True:
            # Get sensor readings
            readings = sensors.get_readings()

            # Determine air quality state
            state = AirQualityCalculator.determine_state(readings)

            # Print readings to console for debugging
            print("\n----- Sensor Readings -----")
            for key, value in readings.items():
                print(f"{key}: {value}")
            print(f"Air quality state: {state}")

            # Toggle between canary and data pages every 10 seconds
            current_time = time.monotonic()
            if current_time - page_change_time >= 10:
                if canary_mode:
                    # Switch to data mode and reset page counter
                    canary_mode = False
                    display.current_page = 0
                else:
                    # Cycle through data pages or switch to canary mode
                    display.current_page = (display.current_page + 1) % display.total_pages
                    if display.current_page == 0:
                        canary_mode = True

                page_change_time = current_time

            # Update display based on current mode
            if canary_mode:
                if state != last_state:
                    display.draw_canary_state(state)
                    last_state = state
            else:
                display.draw_readings_page(readings, display.current_page)

            # Wait before next reading
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
    except Exception as e:
        print(f"Error: {e}")
        # Try to show error on display
        try:
            display.show_error(str(e))
        except:
            pass


if __name__ == "__main__":
    main()