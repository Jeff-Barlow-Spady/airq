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

class AnimatedBird:
    def __init__(self, palette):
        self.palette = palette
        self.notes = []
        self.note_positions = [(95, 10), (105, 8), (115, 12)]
        self.note_directions = [1, -1, 1]  # Up/down movement

        # Create bird body parts
        self.body = vectorio.Circle(pixel_shader=palette, radius=20, x=60, y=32)
        self.head = vectorio.Circle(pixel_shader=palette, radius=8, x=82, y=22)
        self.beak = vectorio.Triangle(pixel_shader=palette, points=[(90,20), (98,23), (90,26)])
        self.tail = vectorio.Triangle(pixel_shader=palette, points=[(30,25), (40,30), (30,35)])
        self.leg = vectorio.Rectangle(pixel_shader=palette, width=2, height=10, x=60, y=45)

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

            # Reverse direction at boundaries
            if note.y > 15 or note.y < 5:
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
        self.i2c = busio.I2C(board.GP9, board.GP8)  # SCL, SDA

        # Initialize button
        self.button = DigitalInOut(board.GP7)
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
        self.is_running = False
        self.button_last_press = time.monotonic()
        self.press_count = 0

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
        if co2 > 1000:  # CO2 levels above 1000ppm are concerning
            return False

        # Check VOC levels (from ENS160 or mock)
        tvoc = readings.get('tvoc', 0)
        if tvoc > 300:  # VOC levels above 300ppb are concerning
            return False

        # Check AQI if available
        aqi = readings.get('aqi', 0)
        if aqi > 100:  # AQI above 100 is concerning
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
        while len(self.root_group) > 0:
            self.root_group.pop()

        if not self.is_running:
            text = label.Label(terminalio.FONT, text="Press 5x to start", x=20, y=32)
            self.root_group.append(text)
            return

        if self.current_view == 0:
            # Bird view with air quality status
            self.bird.add_to_group(self.root_group)
            self.bird.animate_notes()

            # Add air quality status
            is_good = self.check_air_quality()
            status = "GOOD AIR" if is_good else "CHECK AIR"
            status_text = label.Label(terminalio.FONT, text=status, x=40, y=55)
            self.root_group.append(status_text)

        elif self.current_view == 1:
            # Basic stats view - Air Quality
            readings = self.get_readings()

            title = label.Label(terminalio.FONT, text="Air Quality", x=30, y=10)
            self.root_group.append(title)

            # Show CO2 and TVOC
            co2 = readings.get('eco2', 'N/A')
            tvoc = readings.get('tvoc', 'N/A')
            aqi = readings.get('aqi', 'N/A')

            self.root_group.append(label.Label(terminalio.FONT,
                text=f"CO2: {co2} ppm", x=10, y=25))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"TVOC: {tvoc} ppb", x=10, y=40))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"AQI: {aqi}", x=10, y=55))

        else:  # current_view == 2
            # Environment view
            readings = self.get_readings()

            title = label.Label(terminalio.FONT, text="Environment", x=25, y=10)
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
                pressure = f"{pressure:.0f}"

            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Temp: {temp}°C", x=10, y=25))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Humidity: {humidity}%", x=10, y=40))
            self.root_group.append(label.Label(terminalio.FONT,
                text=f"Pressure: {pressure} hPa", x=10, y=55))

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