import time
import board
import busio
import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

# Import sensor libraries
import adafruit_ens160  # Air quality sensor
import adafruit_ahtx0   # Temperature/humidity sensor
import adafruit_bme680  # Temperature/humidity/pressure/gas sensor

# Pin definitions for Waveshare RP2040-Zero
# The RP2040-Zero uses different pin definitions than Raspberry Pi
PIN_SCL = board.GP1  # I2C clock pin on RP2040-Zero
PIN_SDA = board.GP0  # I2C data pin on RP2040-Zero
PIN_BUTTON = board.GP16  # Button pin on RP2040-Zero

# Display settings for 0.96" OLED
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_ADDRESS = 0x3C

# Sensor thresholds
CO2_WARNING_LEVEL = 1000  # ppm
TVOC_WARNING_LEVEL = 300  # ppb
AQI_WARNING_LEVEL = 100

class AnimatedBird:
    def __init__(self, draw, width, height):
        self.draw = draw
        self.width = width
        self.height = height
        self.notes = []
        # Adjusted note positions to fit better on small display
        self.note_positions = [(90, 10), (100, 8), (110, 12)]
        self.note_directions = [1, -1, 1]  # Up/down movement

    def draw_bird(self):
        # Optimized bird size for 0.96" display
        self.draw.ellipse((40, 17, 75, 47), outline=1, fill=1)  # Body
        self.draw.ellipse((70, 15, 85, 30), outline=1, fill=1)  # Head
        self.draw.polygon([(85, 20), (93, 23), (85, 26)], outline=1, fill=1)  # Beak
        self.draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)  # Tail
        self.draw.rectangle((57, 45, 59, 55), outline=1, fill=1)  # Leg

        # Add eyes to the bird
        self.draw.ellipse((74, 19, 76, 21), outline=0, fill=0)  # Left eye
        self.draw.ellipse((80, 19, 82, 21), outline=0, fill=0)  # Right eye

    def draw_notes(self):
        for i, (x, y) in enumerate(self.note_positions):
            # Draw note head - smaller for better visibility
            self.draw.ellipse((x, y, x+3, y+3), outline=1, fill=1)
            # Draw note stem
            self.draw.rectangle((x+2, y-6, x+3, y), outline=1, fill=1)

            # Move note position for next frame
            self.note_positions[i] = (x, y + self.note_directions[i])

            # Reverse direction at boundaries
            if y > 15 or y < 5:
                self.note_directions[i] *= -1

class AirMonitor:
    def __init__(self):
        # Initialize I2C bus for RP2040-Zero
        self.i2c = busio.I2C(PIN_SCL, PIN_SDA)

        # Initialize button for RP2040-Zero
        self.button = digitalio.DigitalInOut(PIN_BUTTON)
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = digitalio.Pull.UP

        # Initialize display
        self.display = adafruit_ssd1306.SSD1306_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, self.i2c, addr=DISPLAY_ADDRESS)
        self.width = self.display.width
        self.height = self.display.height

        # Create image buffer for drawing
        self.image = Image.new("1", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

        # Use a smaller font for better readability on 0.96" display
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except IOError:
            self.font = ImageFont.load_default()

        # Initialize bird
        self.bird = AnimatedBird(self.draw, self.width, self.height)

        # State management
        self.current_view = 0  # 0: Bird, 1: Air Quality, 2: Environment, 3: Sensor Status
        self.is_running = True  # Start immediately
        self.button_last_press = time.monotonic()
        self.press_count = 0
        self.found_sensors = []

        self._init_sensors()

        # Show welcome message
        self._show_welcome()

    def _show_welcome(self):
        """Show a welcome message on startup"""
        self.display.fill(0)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        # Draw a decorative border
        self.draw.rectangle((2, 2, self.width-3, self.height-3), outline=1, fill=0)

        # Centered text for small display
        self.draw.text((10, 15), "Air Quality Monitor", font=self.font, fill=255)
        self.draw.text((30, 35), "Starting up...", font=self.font, fill=255)

        self.display.image(self.image)
        self.display.show()
        time.sleep(2)

    def _init_sensors(self):
        """Initialize sensors"""
        self.sensors = {}
        self.found_sensors = []

        # Try to initialize ENS160
        try:
            self.sensors['ens160'] = adafruit_ens160.ENS160(self.i2c)
            self.found_sensors.append('ENS160')
            print("✓ ENS160 air quality sensor ready")
        except Exception as e:
            print(f"✗ ENS160 init error: {e}")

        # Try to initialize AHT21
        try:
            self.sensors['aht21'] = adafruit_ahtx0.AHTx0(self.i2c)
            self.found_sensors.append('AHT21')
            print("✓ AHT21 temperature/humidity sensor ready")
        except Exception as e:
            print(f"✗ AHT21 init error: {e}")

        # Try to initialize BME680
        try:
            self.sensors['bme680'] = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
            self.found_sensors.append('BME680')
            print("✓ BME680 environmental sensor ready")
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

    def check_air_quality(self):
        """Check if air quality is good"""
        readings = self.get_readings()

        # Check CO2 levels (from ENS160 or mock)
        co2 = readings.get('eco2', 0)
        if co2 > CO2_WARNING_LEVEL:  # CO2 levels above threshold are concerning
            return False

        # Check VOC levels (from ENS160 or mock)
        tvoc = readings.get('tvoc', 0)
        if tvoc > TVOC_WARNING_LEVEL:  # VOC levels above threshold are concerning
            return False

        # Check AQI if available
        aqi = readings.get('aqi', 0)
        if aqi > AQI_WARNING_LEVEL:  # AQI above threshold is concerning
            return False

        return True

    def handle_button(self):
        """Handle button press"""
        current_time = time.monotonic()

        if not self.button.value:  # Button pressed
            if current_time - self.button_last_press > 0.2:  # Debounce
                # Change view on button press
                self.current_view = (self.current_view + 1) % 4  # Now 4 views total
                self.button_last_press = current_time

    def draw_bar(self, x, y, width, height, value, max_value, label=None):
        """Draw a nice looking progress bar"""
        # Draw the outline
        self.draw.rectangle((x, y, x+width, y+height), outline=1, fill=0)

        # Calculate fill width
        fill_width = int((value / max_value) * width)

        # Draw the fill
        self.draw.rectangle((x, y, x+fill_width, y+height), outline=0, fill=1)

        # Add label if provided
        if label:
            text_width = self.draw.textlength(label, font=self.font)
            text_x = x + (width - text_width) // 2
            self.draw.text((text_x, y+height+2), label, font=self.font, fill=255)

    def update_display(self):
        """Update display based on current view"""
        # Clear the display
        self.display.fill(0)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        if not self.is_running:
            # Draw a nice border
            self.draw.rectangle((2, 2, self.width-3, self.height-3), outline=1, fill=0)
            self.draw.text((20, 32), "Press to start", font=self.font, fill=255)
            self.display.image(self.image)
            self.display.show()
            return

        readings = self.get_readings()

        # Handle different views
        if self.current_view == 0:  # Bird view with air quality status
            self.bird.draw_bird()
            self.bird.draw_notes()

            # Add air quality status
            is_good = self.check_air_quality()
            status = "GOOD AIR" if is_good else "CHECK AIR"

            # Draw a nice box around the status
            text_width = self.draw.textlength(status, font=self.font)
            self.draw.rectangle((35, 53, 45+text_width, 63), outline=1, fill=0)
            self.draw.text((40, 55), status, font=self.font, fill=255)

        elif self.current_view == 1:  # Air Quality view
            # Draw a header with border
            self.draw.rectangle((0, 0, self.width, 12), outline=1, fill=1)
            self.draw.text((30, 2), "Air Quality", font=self.font, fill=0)

            # Show CO2 and TVOC with bar graphs
            co2 = readings.get('eco2', 0)
            tvoc = readings.get('tvoc', 0)
            aqi = readings.get('aqi', 0)

            self.draw.text((5, 16), f"CO2: {co2} ppm", font=self.font, fill=255)
            self.draw_bar(5, 25, self.width-10, 5, min(co2, 2000), 2000)

            self.draw.text((5, 35), f"TVOC: {tvoc} ppb", font=self.font, fill=255)
            self.draw_bar(5, 44, self.width-10, 5, min(tvoc, 1000), 1000)

            self.draw.text((5, 54), f"AQI: {aqi}", font=self.font, fill=255)

        elif self.current_view == 2:  # Environment view
            # Draw a header with border
            self.draw.rectangle((0, 0, self.width, 12), outline=1, fill=1)
            self.draw.text((25, 2), "Environment", font=self.font, fill=0)

            # Show temperature, humidity, pressure with nicer formatting
            temp = readings.get('temperature', 0)
            humidity = readings.get('humidity', 0)
            pressure = readings.get('pressure', 0)

            # Temperature with thermometer icon
            self.draw.text((5, 16), f"Temp: {temp:.1f}°C", font=self.font, fill=255)
            # Simple thermometer icon
            self.draw.rectangle((90, 16, 95, 24), outline=1, fill=0)
            self.draw.rectangle((92, 14, 93, 16), outline=1, fill=1)
            self.draw_bar(90, 16, 5, 8, min(temp, 40), 40, None)

            # Humidity with bar
            self.draw.text((5, 30), f"Humidity: {humidity:.1f}%", font=self.font, fill=255)
            self.draw_bar(5, 40, self.width-10, 6, humidity, 100)

            # Pressure
            if pressure > 0:
                self.draw.text((5, 50), f"Pressure: {pressure/100:.0f} hPa", font=self.font, fill=255)

        elif self.current_view == 3:  # Sensor Status view
            # Draw a header with border
            self.draw.rectangle((0, 0, self.width, 12), outline=1, fill=1)
            self.draw.text((25, 2), "Sensor Status", font=self.font, fill=0)

            # Draw sensor status with icons
            y = 16
            for i, sensor in enumerate(['ENS160', 'AHT21', 'BME680']):
                # Check if sensor is present
                has_sensor = sensor in self.found_sensors
                status = "✓" if has_sensor else "✗"
                icon_fill = 1 if has_sensor else 0

                # Draw a small icon
                self.draw.rectangle((5, y, 15, y+10), outline=1, fill=icon_fill)
                self.draw.text((20, y), f"{sensor}: {status}", font=self.font, fill=255)
                y += 15

            # Add humidity bar if available
            humidity = readings.get('humidity', 0)
            if humidity > 0:
                self.draw.text((5, y), f"Humidity: {humidity:.1f}%", font=self.font, fill=255)
                y += 10
                self.draw_bar(5, y, self.width-10, 6, humidity, 100, None)

        # Update the display
        self.display.image(self.image)
        self.display.show()

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
                self.display.fill(0)
                self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
                # Add a warning icon
                self.draw.rectangle((5, 20, 15, 30), outline=1, fill=1)
                self.draw.text((7, 22), "!", font=self.font, fill=0)
                self.draw.text((20, 22), "Error! Check sensors", font=self.font, fill=255)
                self.draw.text((5, 40), str(e)[:20], font=self.font, fill=255)
                self.display.image(self.image)
                self.display.show()
                time.sleep(5)

if __name__ == "__main__":
    monitor = AirMonitor()
    monitor.run()