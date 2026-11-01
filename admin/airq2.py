import time
import board
import busio
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306

# Import priority sensor libraries
import adafruit_sgp30  # For CO2 and VOC
import adafruit_bme680  # For temp, humidity, and pressure

# Release any resources currently in use for the displays
displayio.release_displays()

class AirQualityMonitor:
    def __init__(self, mock_mode=False):
        print("Air Quality Monitor Starting...")
        self.mock_mode = mock_mode
        self.sensors = {}
        self.i2c = None

        if not mock_mode:
            # Initialize I2C bus
            self.i2c = busio.I2C(board.GP15, board.GP14) # SDA, SCL for Pico

            # Try to initialize essential sensors
            if self._try_init_sgp30():
                print("✓ Air quality sensor detected")
            else:
                print("✗ No air quality sensor found")

            if self._try_init_bme680():
                print("✓ Temperature/humidity sensor detected")
            else:
                print("✗ No temperature/humidity sensor found")

            # Fall back to mock mode if no sensors found
            if not self.sensors:
                print("No sensors detected - using simulated data")
                self.mock_mode = True

        if self.mock_mode:
            print("Running with simulated sensor data")
            self.mock_data = {
                'eco2': 800,
                'tvoc': 150,
                'temperature': 22.5,
                'humidity': 45.0,
                'pressure': 1013.25
            }

        # Initialize display
        self._init_display()

    def _init_display(self):
        try:
            # Initialize display
            display_bus = displayio.I2CDisplay(self.i2c if self.i2c else busio.I2C(board.GP1, board.GP0),
                                              device_address=0x3C)
            self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

            # Create display group
            self.root_group = displayio.Group()
            self.display.show(self.root_group)

            # Show welcome message
            self._show_welcome()
            print("✓ Display initialized")
        except Exception as e:
            print(f"✗ Display error: {e}")

    def _show_welcome(self):
        """Show a welcome message on startup"""
        while len(self.root_group) > 0:
            self.root_group.pop()

        title = label.Label(terminalio.FONT, text="Air Quality Monitor", x=5, y=10, scale=1)
        subtitle = label.Label(terminalio.FONT, text="Starting up...", x=20, y=30, scale=1)
        version = label.Label(terminalio.FONT, text="v1.0", x=50, y=50, scale=1)

        self.root_group.append(title)
        self.root_group.append(subtitle)
        self.root_group.append(version)

        time.sleep(2)

    def _try_init_sgp30(self):
        """Initialize SGP30 air quality sensor"""
        try:
            sgp30 = adafruit_sgp30.Adafruit_SGP30(self.i2c)
            sgp30.iaq_init()
            self.sensors['sgp30'] = sgp30
            return True
        except Exception as e:
            print(f"SGP30 init error: {e}")
            return False

    def _try_init_bme680(self):
        """Initialize BME680 temperature/humidity/pressure sensor"""
        try:
            # Try common addresses
            try:
                bme680 = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=0x76)
            except:
                bme680 = adafruit_bme680.Adafruit_BME680_I2C(self.i2c, address=0x77)

            bme680.sea_level_pressure = 1013.25
            self.sensors['bme680'] = bme680
            return True
        except Exception as e:
            print(f"BME680 init error: {e}")
            return False

    def get_readings(self):
        """Get sensor readings or generate mock data"""
        readings = {}

        if self.mock_mode:
            # Add some random variation to mock data
            import random
            readings = {
                'eco2': self.mock_data['eco2'] + random.randint(-50, 50),
                'tvoc': self.mock_data['tvoc'] + random.randint(-20, 20),
                'temperature': self.mock_data['temperature'] + random.uniform(-0.5, 0.5),
                'humidity': self.mock_data['humidity'] + random.uniform(-2, 2),
                'pressure': self.mock_data['pressure'] + random.uniform(-1, 1),
            }
            return readings

        # Get SGP30 readings (Air Quality)
        if 'sgp30' in self.sensors:
            try:
                sgp30 = self.sensors['sgp30']
                readings['eco2'] = sgp30.eCO2
                readings['tvoc'] = sgp30.TVOC
            except Exception as e:
                print(f"SGP30 reading error: {e}")

        # Get BME680 readings (Environmental)
        if 'bme680' in self.sensors:
            try:
                bme680 = self.sensors['bme680']
                readings['temperature'] = bme680.temperature
                readings['humidity'] = bme680.relative_humidity
                readings['pressure'] = bme680.pressure
            except Exception as e:
                print(f"BME680 reading error: {e}")

        return readings

    def assess_air_quality(self, readings):
        """Assess air quality based on CO2 and VOC readings"""
        result = {
            'status': 'Unknown',
            'co2_level': 'Unknown',
            'voc_level': 'Unknown',
            'comfort': 'Unknown',
            'description': 'Unable to determine air quality',
            'action': 'Check sensor connections'
        }

        # Check CO2 levels
        co2 = readings.get('eco2')
        if co2 is not None:
            if co2 < 700:
                result['co2_level'] = 'Excellent'
            elif co2 < 1000:
                result['co2_level'] = 'Good'
            elif co2 < 1500:
                result['co2_level'] = 'Fair'
            elif co2 < 2000:
                result['co2_level'] = 'Poor'
            else:
                result['co2_level'] = 'Unhealthy'

        # Check VOC levels
        tvoc = readings.get('tvoc')
        if tvoc is not None:
            if tvoc < 100:
                result['voc_level'] = 'Excellent'
            elif tvoc < 250:
                result['voc_level'] = 'Good'
            elif tvoc < 500:
                result['voc_level'] = 'Fair'
            elif tvoc < 1000:
                result['voc_level'] = 'Poor'
            else:
                result['voc_level'] = 'Unhealthy'

        # Check comfort based on temperature and humidity
        temp = readings.get('temperature')
        humidity = readings.get('humidity')
        if temp is not None and humidity is not None:
            if 20 <= temp <= 25 and 40 <= humidity <= 60:
                result['comfort'] = 'Ideal'
            elif 18 <= temp <= 28 and 30 <= humidity <= 70:
                result['comfort'] = 'Comfortable'
            else:
                result['comfort'] = 'Suboptimal'

        # Determine overall status based on worst indicator
        if 'Unhealthy' in [result['co2_level'], result['voc_level']]:
            result['status'] = 'Unhealthy'
            result['description'] = 'Air quality is unhealthy'
            result['action'] = 'Ventilate immediately'
        elif 'Poor' in [result['co2_level'], result['voc_level']]:
            result['status'] = 'Poor'
            result['description'] = 'Air quality is concerning'
            result['action'] = 'Open windows soon'
        elif 'Fair' in [result['co2_level'], result['voc_level']]:
            result['status'] = 'Fair'
            result['description'] = 'Air quality is acceptable'
            result['action'] = 'Consider ventilation'
        elif 'Good' in [result['co2_level'], result['voc_level']]:
            result['status'] = 'Good'
            result['description'] = 'Air quality is good'
            result['action'] = 'No action needed'
        elif 'Excellent' in [result['co2_level'], result['voc_level']]:
            result['status'] = 'Excellent'
            result['description'] = 'Air quality is excellent'
            result['action'] = 'Maintain current conditions'

        return result

    def display_main_screen(self, readings, assessment):
        """Display the main air quality information screen"""
        # Clear the display
        while len(self.root_group) > 0:
            self.root_group.pop()

        # Draw header with overall status
        status_text = assessment['status'].upper()
        header = label.Label(terminalio.FONT, text=f"AIR QUALITY: {status_text}", x=0, y=8)
        self.root_group.append(header)

        # Display CO2 and VOC readings
        co2 = readings.get('eco2')
        if co2 is not None:
            co2_text = label.Label(terminalio.FONT, text=f"CO2: {co2} ppm ({assessment['co2_level']})", x=0, y=24)
            self.root_group.append(co2_text)

        tvoc = readings.get('tvoc')
        if tvoc is not None:
            voc_text = label.Label(terminalio.FONT, text=f"VOC: {tvoc} ppb ({assessment['voc_level']})", x=0, y=36)
            self.root_group.append(voc_text)

        # Display recommendation
        action_text = label.Label(terminalio.FONT, text=f"Action: {assessment['action']}", x=0, y=54)
        self.root_group.append(action_text)

        # Add status indicator (visual cue about air quality)
        self._add_status_indicator(assessment['status'])

    def display_environment_screen(self, readings, assessment):
        """Display environmental conditions screen"""
        # Clear the display
        while len(self.root_group) > 0:
            self.root_group.pop()

        # Draw header
        header = label.Label(terminalio.FONT, text="ENVIRONMENT", x=10, y=8)
        self.root_group.append(header)

        # Display temperature
        temp = readings.get('temperature')
        if temp is not None:
            temp_text = label.Label(terminalio.FONT, text=f"Temperature: {temp:.1f}°C", x=0, y=24)
            self.root_group.append(temp_text)

        # Display humidity with comfort level
        humidity = readings.get('humidity')
        if humidity is not None:
            hum_text = label.Label(terminalio.FONT, text=f"Humidity: {humidity:.1f}%", x=0, y=36)
            self.root_group.append(hum_text)

        # Display comfort assessment
        if assessment['comfort'] != 'Unknown':
            comfort_text = label.Label(terminalio.FONT, text=f"Comfort: {assessment['comfort']}", x=0, y=48)
            self.root_group.append(comfort_text)

        # Display pressure if available
        pressure = readings.get('pressure')
        if pressure is not None:
            press_text = label.Label(terminalio.FONT, text=f"Pressure: {pressure/100:.1f} hPa", x=0, y=60)
            self.root_group.append(press_text)

    def display_info_screen(self, assessment):
        """Display information about air quality readings"""
        # Clear the display
        while len(self.root_group) > 0:
            self.root_group.pop()

        # Draw header
        header = label.Label(terminalio.FONT, text="UNDERSTANDING READINGS", x=0, y=8)
        self.root_group.append(header)

        # Add explanation based on current readings
        explanation_lines = []

        if assessment['status'] == 'Excellent':
            explanation_lines = [
                "Air quality is excellent!",
                "All levels are within",
                "healthy ranges.",
                "Enjoy your clean air."
            ]
        elif assessment['status'] == 'Good':
            explanation_lines = [
                "Air quality is good.",
                "Levels are in a healthy",
                "range. No action needed",
                "at this time."
            ]
        elif assessment['status'] == 'Fair':
            explanation_lines = [
                "Air quality is fair.",
                "Consider ventilation",
                "to improve conditions",
                "soon."
            ]
        elif assessment['status'] == 'Poor':
            explanation_lines = [
                "Air quality is poor.",
                "Open windows or doors",
                "to increase fresh air",
                "circulation."
            ]
        elif assessment['status'] == 'Unhealthy':
            explanation_lines = [
                "Air quality is unhealthy!",
                "Ventilate immediately.",
                "High levels may cause",
                "headaches & fatigue."
            ]
        else:
            explanation_lines = [
                "Could not determine",
                "air quality status.",
                "Check sensor",
                "connections."
            ]

        # Add explanation text
        for i, line in enumerate(explanation_lines):
            y_pos = 20 + (i * 10)
            text = label.Label(terminalio.FONT, text=line, x=0, y=y_pos)
            self.root_group.append(text)

    def _add_status_indicator(self, status):
        """Add a visual indicator of air quality status"""
        # Create bitmap for status indicator
        bitmap = displayio.Bitmap(20, 20, 2)
        palette = displayio.Palette(2)
        palette[0] = 0x000000  # Black
        palette[1] = 0xFFFFFF  # White

        # Fill the circle based on status
        for x in range(20):
            for y in range(20):
                if ((x - 10) ** 2 + (y - 10) ** 2) < 100:  # Circle with radius ~10
                    bitmap[x, y] = 1

        # Add a symbol in the middle based on status
        if status == 'Excellent' or status == 'Good':
            # Checkmark
            for i in range(7):
                bitmap[5 + i, 12 - i] = 0 if i < 3 else 1
                bitmap[11 + i, 6 + i] = 0
        elif status == 'Fair':
            # Equals sign
            for x in range(6, 14):
                for y in range(7, 9):
                    bitmap[x, y] = 0
                for y in range(11, 13):
                    bitmap[x, y] = 0
        elif status == 'Poor' or status == 'Unhealthy':
            # X mark
            for i in range(10):
                bitmap[5 + i, 5 + i] = 0
                bitmap[14 - i, 5 + i] = 0

        # Position the indicator in the top-right corner
        indicator = displayio.TileGrid(bitmap, pixel_shader=palette, x=105, y=8)
        self.root_group.append(indicator)

    def run(self):
        """Main loop to run the monitor"""
        try:
            current_screen = 0  # 0=main, 1=environment, 2=info
            screen_change_time = time.monotonic()

            while True:
                # Get readings and assessment
                readings = self.get_readings()
                assessment = self.assess_air_quality(readings)

                # Print readings to console for debugging
                print("\n----- Air Quality Status -----")
                print(f"Overall: {assessment['status']}")
                print(f"CO2: {readings.get('eco2')} ppm ({assessment['co2_level']})")
                print(f"VOC: {readings.get('tvoc')} ppb ({assessment['voc_level']})")
                if 'temperature' in readings:
                    print(f"Temperature: {readings['temperature']:.1f}°C")
                if 'humidity' in readings:
                    print(f"Humidity: {readings['humidity']:.1f}%")
                print(f"Recommendation: {assessment['action']}")

                # Handle screen rotation every 5 seconds
                current_time = time.monotonic()
                if current_time - screen_change_time >= 5:
                    current_screen = (current_screen + 1) % 3
                    screen_change_time = current_time

                # Update display based on current screen
                if current_screen == 0:
                    self.display_main_screen(readings, assessment)
                elif current_screen == 1:
                    self.display_environment_screen(readings, assessment)
                else:  # screen 2
                    self.display_info_screen(assessment)

                # Wait before next update
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nExiting gracefully...")
        except Exception as e:
            print(f"Error: {e}")
            try:
                # Show error on display
                while len(self.root_group) > 0:
                    self.root_group.pop()

                error_title = label.Label(terminalio.FONT, text="ERROR!", x=40, y=10)
                error_msg = label.Label(terminalio.FONT, text=str(e)[:20], x=10, y=30)
                error_help = label.Label(terminalio.FONT, text="Restart device", x=20, y=50)

                self.root_group.append(error_title)
                self.root_group.append(error_msg)
                self.root_group.append(error_help)
            except:
                pass


if __name__ == "__main__":
    monitor = AirQualityMonitor(mock_mode=False)  # Set True for testing without sensors
    monitor.run()