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

# Pin definitions - easy to change
PIN_SCL = board.SCL  # I2C clock pin
PIN_SDA = board.SDA  # I2C data pin
PIN_BUTTON = board.D17  # Button pin (GPIO17 on Raspberry Pi)

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
        # Initialize I2C bus
        self.i2c = busio.I2C(PIN_SCL, PIN_SDA)

        # Initialize button
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
        self.current_view = 0  # 0: Bird, 1: Basic Stats, 2: Status
        self.is_running = False
        self.button_last_press = time.monotonic()
        self.press_count = 0

        self._init_sensors()

        # Show welcome message
        self._show_welcome()

    def _show_welcome(self):
        """Show a welcome message on startup"""
        self.display.fill(0)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        # Centered text for small display
        self.draw.text((10, 15), "Air Quality Monitor", font=self.font, fill=255)
        self.draw.text((30, 35), "Starting up...", font=self.font, fill=255)

        self.display.image(self.image)
        self.display.show()
        time.sleep(2)

    def _init_sensors(self):
        """Initialize sensors"""
        self.sensors = {}

        # Try to initialize ENS160
        try:
            self.sensors['ens160'] = adafruit_ens160.ENS160(self.i2c)
            print("✓ ENS160 air quality sensor ready")
        except Exception as e:
            print(f"✗ ENS160 init error: {e}")

        # Try to initialize AHT21
        try:
            self.sensors['aht21'] = adafruit_ahtx0.AHTx0(self.i2c)
            print("✓ AHT21 temperature/humidity sensor ready")
        except Exception as e:
            print(f"✗ AHT21 init error: {e}")

        # Try to initialize BME680
        try:
            self.sensors['bme680'] = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
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
        # Clear the display
        self.display.fill(0)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        if not self.is_running:
            self.draw.text((20, 32), "Press 5x to start", font=self.font, fill=255)
            self.display.image(self.image)
            self.display.show()
            return

        if self.current_view == 0:
            # Bird view with air quality status
            self.bird.draw_bird()
            self.bird.draw_notes()

            # Add air quality status
            is_good = self.check_air_quality()
            status = "GOOD AIR" if is_good else "CHECK AIR"
            self.draw.text((40, 55), status, font=self.font, fill=255)

        elif self.current_view == 1:
            # Basic stats view - Air Quality
            readings = self.get_readings()

            self.draw.text((30, 10), "Air Quality", font=self.font, fill=255)

            # Show CO2 and TVOC
            co2 = readings.get('eco2', 'N/A')
            tvoc = readings.get('tvoc', 'N/A')
            aqi = readings.get('aqi', 'N/A')

            self.draw.text((10, 25), f"CO2: {co2} ppm", font=self.font, fill=255)
            self.draw.text((10, 40), f"TVOC: {tvoc} ppb", font=self.font, fill=255)
            self.draw.text((10, 55), f"AQI: {aqi}", font=self.font, fill=255)

        else:  # current_view == 2
            # Environment view
            readings = self.get_readings()

            self.draw.text((25, 10), "Environment", font=self.font, fill=255)

            # Show temperature, humidity, pressure
            temp = readings.get('temperature', 'N/A')
            if temp != 'N/A':
                temp = f"{temp:.1f}"

            humidity = readings.get('humidity', 'N/A')
            if humidity != 'N/A':
                humidity = f"{humidity:.1f}"

            pressure = readings.get('pressure', 'N/A')
            if pressure != 'N/A':
                pressure = f"{pressure:.0f}"

            self.draw.text((10, 25), f"Temp: {temp}°C", font=self.font, fill=255)
            self.draw.text((10, 40), f"Humidity: {humidity}%", font=self.font, fill=255)
            self.draw.text((10, 55), f"Pressure: {pressure} hPa", font=self.font, fill=255)

        # Update the display
        self.display.image(self.image)
        self.display.show()

    def run(self):
        """Main loop"""
        print("Air Quality Monitor Starting...")

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
                self.draw.text((5, 32), "Error! Check sensors", font=self.font, fill=255)
                self.display.image(self.image)
                self.display.show()
                time.sleep(5)

if __name__ == "__main__":
    monitor = AirMonitor()
    monitor.run()