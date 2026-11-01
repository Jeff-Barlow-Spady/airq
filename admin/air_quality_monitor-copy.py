import time
import board
import busio
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import argparse

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

# Configure GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

class SensorHandler:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        self.sensors = {}
        self.found_sensors = []

        if not mock_mode:
            # Initialize I2C bus
            self.i2c = busio.I2C(board.SCL, board.SDA)
            print("Scanning I2C bus...")

            # Try to initialize each sensor
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

    def _try_init_sgp30(self):
        try:
            sgp30 = adafruit_sgp30.Adafruit_SGP30(self.i2c)
            sgp30.iaq_init()
            # Try to set baseline values (optional)
            try:
                sgp30.set_iaq_baseline(0x8973, 0x8AAE)
            except Exception as e:
                print(f"SGP30 baseline setting error: {e}")

            print("SGP30 initialized")
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
            print("AHT21 initialized")
            self.sensors['aht21'] = aht21
            self.found_sensors.append('AHT21')
        except Exception as e:
            print(f"AHT21 init error: {e}")

    def _try_init_bmp280(self):
        try:
            # Use 0x76 instead of default 0x77
            self.bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=0x76)
            print("BMP280 initialized")
            self.sensors['bmp280'] = self.bmp280
            self.found_sensors.append('BMP280')
            return True
        except Exception as e:
            print(f"BMP280 init error: {e}")
            return False

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
    def __init__(self):
        # Initialize I2C bus for display
        i2c = busio.I2C(board.SCL, board.SDA)
        self.oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

        # Clear display
        self.oled.fill(0)
        self.oled.show()

        # Current page for display rotation
        self.current_page = 0
        self.total_pages = 4  # CO2/VOC, Temp/Humidity, Pressure/Gas, Status

        print("Display initialized")

    def draw_readings_page(self, readings, page):
        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Clear the display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        if page == 0:  # CO2/VOC page
            draw.text((0, 0), "Air Quality", font=font, fill=1)

            co2 = readings.get('eco2') or readings.get('ens_eco2')
            tvoc = readings.get('tvoc') or readings.get('ens_tvoc')

            if co2:
                draw.text((0, 16), f"CO2: {co2} ppm", font=font, fill=1)
            if tvoc:
                draw.text((0, 32), f"TVOC: {tvoc} ppb", font=font, fill=1)

            # Add AQI if available
            aqi = readings.get('ens_aqi')
            if aqi:
                draw.text((0, 48), f"AQI: {aqi}", font=font, fill=1)

        elif page == 1:  # Temperature/Humidity page
            draw.text((0, 0), "Temperature & Humidity", font=font, fill=1)

            # Get temperature from any available sensor
            temp = (readings.get('temperature') or
                   readings.get('aht_temperature') or
                   readings.get('bmp_temperature'))

            # Get humidity from any available sensor
            humidity = (readings.get('humidity') or
                       readings.get('aht_humidity'))

            if temp:
                draw.text((0, 16), f"Temp: {temp:.1f}°C", font=font, fill=1)
            if humidity:
                draw.text((0, 32), f"Humidity: {humidity:.1f}%", font=font, fill=1)

                # Draw humidity bar
                bar_width = int((humidity / 100) * self.oled.width)
                draw.rectangle((0, 48, self.oled.width, 54), outline=1, fill=0)
                draw.rectangle((0, 48, bar_width, 54), outline=1, fill=1)

        elif page == 2:  # Pressure/Gas page
            draw.text((0, 0), "Pressure & Gas", font=font, fill=1)

            # Get pressure from any available sensor
            pressure = (readings.get('pressure') or
                       readings.get('bmp_pressure'))

            # Get gas resistance from BME680
            gas = readings.get('gas')

            # Get altitude from any available sensor
            altitude = (readings.get('altitude') or
                       readings.get('bmp_altitude'))

            if pressure:
                draw.text((0, 16), f"Press: {pressure/100:.1f} hPa", font=font, fill=1)
            if gas:
                draw.text((0, 32), f"Gas: {gas/1000:.1f} kΩ", font=font, fill=1)
            if altitude:
                draw.text((0, 48), f"Alt: {altitude:.1f} m", font=font, fill=1)

        elif page == 3:  # Status page
            draw.text((0, 0), "Sensor Status", font=font, fill=1)

            y = 16
            for i, sensor in enumerate(['SGP30', 'BME680', 'AHT21', 'BMP280', 'ENS160']):
                # Only draw 3 sensors per page to avoid crowding
                if i > 2 and y >= 48:
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
                draw.text((0, y), f"{sensor}: {status}", font=font, fill=1)
                y += 16

        # Display the image
        self.oled.image(image)
        self.oled.show()

    def draw_canary_state(self, state):
        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)

        # Clear the display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        # Draw the canary
        draw.ellipse((40, 20, 80, 45), outline=1, fill=1)  # body
        draw.ellipse((75, 15, 90, 30), outline=1, fill=1)  # head
        draw.polygon([(90, 20), (98, 23), (90, 26)], outline=1, fill=1)  # beak
        draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)  # tail
        draw.line((60, 45, 60, 55), fill=1, width=2)  # leg

        # Draw state-specific elements
        if state == "warning":
            draw.line((77, 17, 82, 22), fill=1, width=1)  # X eye 1
            draw.line((77, 22, 82, 17), fill=1, width=1)  # X eye 2

            # Add warning text
            font = ImageFont.load_default()
            draw.text((2, 2), "WARNING!", font=font, fill=1)

        elif state == "good":
            # Draw musical notes for happy canary
            draw.ellipse((95, 10, 99, 14), outline=1, fill=1)  # note head
            draw.line((99, 12, 99, 4), fill=1, width=1)  # note stem
            draw.ellipse((105, 8, 109, 12), outline=1, fill=1)  # note head
            draw.line((109, 10, 109, 2), fill=1, width=1)  # note stem

            # Add happy text
            font = ImageFont.load_default()
            draw.text((2, 2), "GOOD AIR", font=font, fill=1)

        elif state == "medium" or state == "caution":
            # Draw neutral face for canary
            draw.line((77, 20, 82, 20), fill=1, width=1)  # straight mouth

            # Add caution text
            font = ImageFont.load_default()
            message = "CAUTION" if state == "caution" else "MODERATE"
            draw.text((2, 2), message, font=font, fill=1)

        else:  # error or unknown state
            # Draw question mark
            font = ImageFont.load_default()
            draw.text((82, 20), "?", font=font, fill=1)
            draw.text((2, 2), "ERROR", font=font, fill=1)

        # Display the image
        self.oled.image(image)
        self.oled.show()

    def show_error(self, message):
        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Clear the display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        # Draw error message
        draw.text((0, 0), "ERROR:", font=font, fill=1)

        # Split message into multiple lines if needed
        words = message.split()
        current_line = ""
        y = 16

        for word in words:
            test_line = current_line + word + " "
            # Check if adding this word exceeds display width
            if draw.textlength(test_line, font=font) <= self.oled.width:
                current_line = test_line
            else:
                draw.text((0, y), current_line, font=font, fill=1)
                y += 10
                current_line = word + " "

                # Stop if we run out of vertical space
                if y >= self.oled.height - 10:
                    break

        # Draw any remaining text
        if current_line:
            draw.text((0, y), current_line, font=font, fill=1)

        # Display the image
        self.oled.image(image)
        self.oled.show()


def main():
    # Add command-line argument parsing
    parser = argparse.ArgumentParser(description='Air Quality Monitor')
    parser.add_argument('--enable-button', action='store_true',
                        help='Enable button on GPIO17 to toggle display view')
    parser.add_argument('--mock', action='store_true',
                        help='Use mock data instead of real sensors')
    args = parser.parse_args()

    try:
        print("Air Quality Monitor with Multiple Sensors")
        print("----------------------------------------")

        # Initialize sensor handler and display
        sensors = SensorHandler(mock_mode=args.mock)
        display = DisplayHandler()

        # Setup button on GPIO17 if enabled
        if args.enable_button:
            print("Button control enabled on GPIO17")
            GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            last_button_state = GPIO.input(17)
            last_button_time = time.time()
            button_debounce_time = 0.3  # Debounce time in seconds

        page_change_time = time.time()
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

            # Check button state if enabled
            if args.enable_button:
                current_button_state = GPIO.input(17)
                current_time = time.time()

                # Button pressed (GPIO17 goes LOW when pressed with pull-up)
                if current_button_state == GPIO.LOW and last_button_state == GPIO.HIGH:
                    # Debounce check
                    if current_time - last_button_time > button_debounce_time:
                        print("Button pressed - toggling display mode")

                        if canary_mode:
                            # Switch to data mode and reset page counter
                            canary_mode = False
                            display.current_page = 0
                        else:
                            # Cycle through data pages or switch to canary mode
                            display.current_page = (display.current_page + 1) % display.total_pages
                            if display.current_page == 0:
                                canary_mode = True

                        # Reset page change timer when button is pressed
                        page_change_time = current_time

                    last_button_time = current_time

                last_button_state = current_button_state

            # Toggle between canary and data pages every 10 seconds (if not interrupted by button)
            current_time = time.time()
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
            time.sleep(0.1)  # Shorter sleep to make button more responsive

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
    except Exception as e:
        print(f"Error: {e}")
        # Try to show error on display
        try:
            display.show_error(str(e))
        except:
            pass
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
