import time
import board
import busio
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import vectorio
from digitalio import DigitalInOut, Direction, Pull

# Import sensor libraries
import adafruit_ens160  # Air quality sensor
import adafruit_ahtx0   # Temperature/humidity sensor
import adafruit_bme680  # Temperature/humidity/pressure/gas sensor

# Release any resources currently in use for the displays
displayio.release_displays()

# For dual-color display - top 1/4 (16 pixels) is yellow, rest is blue
YELLOW_SECTION_HEIGHT = 16

class AnimatedBird:
    def __init__(self, palette):
        self.palette = palette
        self.notes = []
        self.note_positions = [(95, 30), (105, 28), (115, 32)]  # Below yellow section
        self.note_directions = [1, -1, 1]  # Up/down movement

        # Create bird body parts - centered in display
        x_center = 64 - 20  # Center horizontally
        y_offset = YELLOW_SECTION_HEIGHT + 8  # Start below yellow section

        self.body = vectorio.Circle(pixel_shader=palette, radius=18, x=x_center+18, y=32+y_offset)
        self.head = vectorio.Circle(pixel_shader=palette, radius=8, x=x_center+38, y=22+y_offset)
        self.beak = vectorio.Triangle(pixel_shader=palette,
                                     points=[(x_center+46, 20+y_offset),
                                             (x_center+54, 23+y_offset),
                                             (x_center+46, 26+y_offset)])
        self.tail = vectorio.Triangle(pixel_shader=palette,
                                     points=[(x_center-10, 25+y_offset),
                                             (x_center, 30+y_offset),
                                             (x_center-10, 35+y_offset)])
        self.leg = vectorio.Rectangle(pixel_shader=palette, width=2, height=10,
                                     x=x_center+18, y=45+y_offset)

        # Create musical notes
        for x, y in self.note_positions:
            note = vectorio.Circle(pixel_shader=palette, radius=2, x=x, y=y)
            stem = vectorio.Rectangle(pixel_shader=palette, width=1, height=8, x=x+2, y=y-8)
            self.notes.append((note, stem))

    def animate_notes(self):
        for i, (note, stem) in enumerate(self.notes):
            # Move note and stem up or down
            note.y += self.note_directions[i]
            stem.y += self.note_directions[i]

            # Reverse direction at boundaries - keep within blue section
            if note.y > 40 or note.y < YELLOW_SECTION_HEIGHT + 5:
                self.note_directions[i] *= -1

    def add_to_group(self, group):
        group.append(self.body)
        group.append(self.head)
        group.append(self.beak)
        group.append(self.tail)
        group.append(self.leg)
        for note, stem in self.notes:
            group.append(note)
            group.append(stem)

class AirMonitor:
    def __init__(self):
        # Initialize I2C
        self.i2c = busio.I2C(board.GP1, board.GP0)  # SCL, SDA for RP2040-Zero

        # Initialize button
        self.button = DigitalInOut(board.GP16)  # Button pin for RP2040-Zero
        self.button.direction = Direction.INPUT
        self.button.pull = Pull.UP

        # Initialize display
        display_bus = displayio.I2CDisplay(self.i2c, device_address=0x3C)
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

        # Setup display groups
        self.root_group = displayio.Group()
        self.display.show(self.root_group)

        # Create palette
        self.palette = displayio.Palette(2)
        self.palette[0] = 0x000000  # Black
        self.palette[1] = 0xFFFFFF  # White

        # Initialize bird
        self.bird = AnimatedBird(self.palette)

        # State management
        self.current_view = 0  # 0: Bird, 1: Basic Stats, 2: Status
        self.is_running = True  # Start immediately
        self.button_last_press = time.monotonic()
        self.press_count = 0
        self.found_sensors = []

        self._init_sensors()

        # Show welcome message
        self._show_welcome()

    def _show_welcome(self):
        """Show a welcome message on startup"""
        while len(self.root_group) > 0:
            self.root_group.pop()

        title = label.Label(terminalio.FONT, text="Air Quality Monitor", x=5, y=10)
        subtitle = label.Label(terminalio.FONT, text="Starting up...", x=20, y=30)
        version = label.Label(terminalio.FONT, text="v1.0", x=50, y=50)

        self.root_group.append(title)
        self.root_group.append(subtitle)
        self.root_group.append(version)

        time.sleep(2)

    def _init_sensors(self):
        """Initialize sensors"""
        self.sensors = {}

        # Try to initialize ENS160
        try:
            self.sensors['ens160'] = adafruit_ens160.ENS160(self.i2c)
            print("✓ ENS160 air quality sensor ready")
            self.found_sensors.append('ENS160')
        except Exception as e:
            print(f"✗ ENS160 init error: {e}")

        # Try to initialize AHT21
        try:
            self.sensors['aht21'] = adafruit_ahtx0.AHTx0(self.i2c)
            print("✓ AHT21 temperature/humidity sensor ready")
            self.found_sensors.append('AHT21')
        except Exception as e:
            print(f"✗ AHT21 init error: {e}")

        # Try to initialize BME680
        try:
            self.sensors['bme680'] = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
            print("✓ BME680 environmental sensor ready")
            self.found_sensors.append('BME680')
        except Exception as e:
            print(f"✗ BME680 init error: {e}")

    def get_readings(self):
        """Get readings from all available sensors"""
        readings = {}

        # Get ENS160 readings
        if 'ens160' in self.sensors:
            try:
                ens = self.sensors['ens160']
                readings['aqi'] = ens.AQI
                readings['tvoc'] = ens.TVOC
                readings['eco2'] = ens.eCO2
            except Exception as e:
                print(f"ENS160 reading error: {e}")

        # Get AHT21 readings
        if 'aht21' in self.sensors:
            try:
                aht = self.sensors['aht21']
                readings['temperature'] = aht.temperature
                readings['humidity'] = aht.relative_humidity
            except Exception as e:
                print(f"AHT21 reading error: {e}")

        # Get BME680 readings
        if 'bme680' in self.sensors:
            try:
                bme = self.sensors['bme680']
                # Only use BME680 temperature/humidity if AHT21 not available
                if 'temperature' not in readings:
                    readings['temperature'] = bme.temperature
                if 'humidity' not in readings:
                    readings['humidity'] = bme.relative_humidity
                readings['pressure'] = bme.pressure
                readings['gas'] = bme.gas
            except Exception as e:
                print(f"BME680 reading error: {e}")

        # If no sensors available, use mock data
        if not readings:
            readings = {
                'eco2': 800,
                'tvoc': 150,
                'temperature': 22.5,
                'humidity': 45.0,
                'pressure': 1013.25,
                'gas': 150000,
                'aqi': 50
            }

        return readings

    def get_air_quality_text(self):
        """Get air quality text based on readings"""
        readings = self.get_readings()

        # Check AQI if available
        aqi = readings.get('aqi', 0)
        if aqi > 0:
            if aqi > 300:
                return "HAZARDOUS"
            elif aqi > 200:
                return "VERY UNHEALTHY"
            elif aqi > 150:
                return "UNHEALTHY"
            elif aqi > 100:
                return "MODERATE"
            elif aqi > 50:
                return "FAIR"
            else:
                return "GOOD"

        # Check CO2 levels
        co2 = readings.get('eco2', 0)
        if co2 > 1500:
            return "POOR"
        elif co2 > 1000:
            return "FAIR"
        elif co2 > 800:
            return "GOOD"
        else:
            return "EXCELLENT"

    def determine_air_quality(self, readings):
        """Determine air quality state based on readings"""
        # Check CO2 levels
        co2 = readings.get('eco2', 0)
        if co2 > 1500:
            return "warning"
        elif co2 > 1000:
            return "caution"
        elif co2 > 800:
            return "medium"

        # Check VOC levels
        tvoc = readings.get('tvoc', 0)
        if tvoc > 600:
            return "warning"
        elif tvoc > 300:
            return "caution"
        elif tvoc > 200:
            return "medium"

        # Check AQI if available
        aqi = readings.get('aqi', 0)
        if aqi > 150:
            return "warning"
        elif aqi > 100:
            return "caution"
        elif aqi > 50:
            return "medium"

        return "good"

    def check_air_quality(self):
        """Check if air quality is good"""
        readings = self.get_readings()
        state = self.determine_air_quality(readings)
        return state == "good"

    def handle_button(self):
        """Handle button press"""
        current_time = time.monotonic()

        if not self.button.value:  # Button pressed
            if current_time - self.button_last_press > 0.2:  # Debounce
                self.press_count += 1
                if self.press_count >= 5:
                    self.is_running = not self.is_running
                    self.press_count = 0
                else:
                    self.current_view = (self.current_view + 1) % 3
                self.button_last_press = current_time
        elif current_time - self.button_last_press > 2:  # Reset count after 2 seconds
            self.press_count = 0

    def update_display(self):
        """Update display based on current view"""
        while len(self.root_group) > 0:
            self.root_group.pop()

        if not self.is_running:
            text = label.Label(terminalio.FONT, text="Press 5x to start", x=20, y=32)
            self.root_group.append(text)
            return

        readings = self.get_readings()
        air_quality_text = self.get_air_quality_text()
        air_quality_state = self.determine_air_quality(readings)

        if self.current_view == 0:
            # Bird view with air quality status
            # Add air quality status in yellow section
            status_text = label.Label(terminalio.FONT, text=air_quality_text, x=5, y=8)
            self.root_group.append(status_text)

            # Add bird and notes
            self.bird.add_to_group(self.root_group)
            self.bird.animate_notes()

            # Add state-specific elements based on air quality
            if air_quality_state == "warning":
                # Add warning indicator
                warning = label.Label(terminalio.FONT, text="!", x=64, y=YELLOW_SECTION_HEIGHT + 25,
                                     color=0xFFFFFF, background_color=0x000000)
                self.root_group.append(warning)

        elif self.current_view == 1:
            # Basic stats view - Air Quality
            title = label.Label(terminalio.FONT, text="Air Quality", x=5, y=8)
            self.root_group.append(title)

            # Show CO2 and TVOC
            co2 = readings.get('eco2', 'N/A')
            tvoc = readings.get('tvoc', 'N/A')
            aqi = readings.get('aqi', 'N/A')

            self.root_group.append(label.Label(terminalio.FONT,
                text=f"CO2: {co2} ppm", x=10, y=YELLOW_SECTION_HEIGHT + 5))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"TVOC: {tvoc} ppb", x=10, y=YELLOW_SECTION_HEIGHT + 20))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"AQI: {aqi}", x=10, y=YELLOW_SECTION_HEIGHT + 35))

            # Add bar for CO2
            if co2 != 'N/A':
                co2_bar = vectorio.Rectangle(
                    pixel_shader=self.palette,
                    width=min(int(co2/20), 100),  # Scale to fit display
                    height=5,
                    x=10,
                    y=YELLOW_SECTION_HEIGHT + 10
                )
                self.root_group.append(co2_bar)

            # Add bar for TVOC
            if tvoc != 'N/A':
                tvoc_bar = vectorio.Rectangle(
                    pixel_shader=self.palette,
                    width=min(int(tvoc/10), 100),  # Scale to fit display
                    height=5,
                    x=10,
                    y=YELLOW_SECTION_HEIGHT + 25
                )
                self.root_group.append(tvoc_bar)

        else:  # current_view == 2
            # Environment view
            title = label.Label(terminalio.FONT, text="Environment", x=5, y=8)
            self.root_group.append(title)

            # Show temperature, humidity, pressure
            temp = readings.get('temperature', 'N/A')
            if temp != 'N/A':
                temp = f"{temp:.1f}"

            humidity = readings.get('humidity', 'N/A')
            if humidity != 'N/A':
                humidity = f"{humidity:.1f}"

            pressure = readings.get('pressure', 'N/A')
            if pressure != 'N/A':
                pressure = f"{pressure/100:.0f}"

            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Temp: {temp}°C", x=10, y=YELLOW_SECTION_HEIGHT + 5))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Humidity: {humidity}%", x=10, y=YELLOW_SECTION_HEIGHT + 20))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Pressure: {pressure} hPa", x=10, y=YELLOW_SECTION_HEIGHT + 35))

            # Add humidity bar
            if humidity != 'N/A':
                try:
                    hum_value = float(humidity)
                    humidity_bar = vectorio.Rectangle(
                        pixel_shader=self.palette,
                        width=int(hum_value),  # Scale to percentage
                        height=5,
                        x=10,
                        y=YELLOW_SECTION_HEIGHT + 25
                    )
                    self.root_group.append(humidity_bar)
                except ValueError:
                    pass

    def run(self):
        """Main loop"""
        print("Air Quality Monitor Starting...")
        print(f"Found sensors: {', '.join(self.found_sensors) if self.found_sensors else 'None (using mock data)'}")

        while True:
            try:
                self.handle_button()
                self.update_display()
                time.sleep(0.1)

            except Exception as e:
                print(f"Error: {e}")
                # Show error on display
                while len(self.root_group) > 0:
                    self.root_group.pop()
                error_text = label.Label(terminalio.FONT,
                                       text="Error! Check sensors",
                                       x=5, y=32)
                self.root_group.append(error_text)
                time.sleep(5)

if __name__ == "__main__":
    monitor = AirMonitor()
    monitor.run()