import time
import board
import busio
import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import math

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

# For dual-color display - top 1/4 (16 pixels) is yellow, rest is blue
YELLOW_SECTION_HEIGHT = 16

class AnimatedBird:
    def __init__(self, draw, width, height):
        self.draw = draw
        self.width = width
        self.height = height
        self.notes = []
        # Moved notes further right to avoid overlap with beak
        self.note_positions = [(98, 30), (108, 28), (118, 32)]  # Below yellow section
        self.note_directions = [0.2, -0.2, 0.2]  # Greatly reduced movement speed
        # Track original positions to limit movement range
        self.original_y = [30, 28, 32]
        self.max_deviation = 2  # Maximum pixels to move up/down

    def draw_bird(self):
        """Draw the bird in the blue section"""
        # Base positioning
        base_x = 30  # Base x position
        base_y = YELLOW_SECTION_HEIGHT + 10  # Raised slightly to make room for leg

        # Draw body parts in a more structured way
        # Body - smaller and more oval to match other views
        self.draw.ellipse((base_x, base_y, base_x+30, base_y+25), outline=1, fill=1)

        # Head
        head_x = base_x + 25
        head_y = base_y - 5
        self.draw.ellipse((head_x, head_y, head_x+15, head_y+15), outline=1, fill=1)

        # Beak - shortened to avoid covering notes
        beak_x = head_x + 15
        beak_y = head_y + 7
        self.draw.polygon([(beak_x, beak_y), (beak_x+10, beak_y), (beak_x, beak_y+4)], outline=1, fill=1)
        self.draw.line([(beak_x, beak_y), (beak_x, beak_y+4)], fill=0, width=1)  # Beak detail

        # Tail
        tail_x = base_x - 10
        tail_y = base_y + 10
        self.draw.polygon([(tail_x, tail_y), (tail_x+10, tail_y+3), (tail_x, tail_y+6)], outline=1, fill=1)

        # Leg - clearly visible below the body
        leg_x = base_x + 15
        leg_y = base_y + 25  # Start at bottom of body
        self.draw.rectangle((leg_x, leg_y, leg_x+1, leg_y+10), outline=1, fill=1)

        # Add foot like in other views
        foot_y = leg_y + 10
        self.draw.line((leg_x-3, foot_y, leg_x+5, foot_y), fill=1, width=1)

        # Eye
        eye_x = head_x + 9
        eye_y = head_y + 5
        self.draw.ellipse((eye_x, eye_y, eye_x+3, eye_y+3), outline=0, fill=0)
        # Wing (curved line)
        for i in range(10):
            x = base_x + 8 + i*2
            y = base_y + 12 + int(5 * math.sin(i/2))
            self.draw.point((x, y), fill=0)

    def draw_notes(self):
        """Draw notes in the blue section"""
        for i, (x, y) in enumerate(self.note_positions):
            # Draw note head - smaller for better visibility
            self.draw.ellipse((x, y, x+3, y+3), outline=1, fill=1)
            # Draw note stem
            self.draw.rectangle((x+2, y-6, x+3, y), outline=1, fill=1)

            # Move note position for next frame
            new_y = y + self.note_directions[i]

            # Limit movement to max_deviation from original position
            if abs(new_y - self.original_y[i]) > self.max_deviation:
                self.note_directions[i] *= -1
                new_y = y + self.note_directions[i]

            self.note_positions[i] = (x, new_y)

class DisplayHandler:
    def __init__(self, oled):
        self.oled = oled
        self.current_page = 0
        self.total_pages = 3  # Three focused pages
        print("Display handler initialized with simplified design")

    def draw_readings_page(self, readings, page):
        """Draw sensor readings based on current page"""
        print(f"Drawing readings page {page}")

        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Clear display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        if page == 0:  # Air Quality Focus
            # Title
            draw.rectangle((0, 0, self.oled.width, 10), outline=1, fill=1)
            draw.text((5, 1), "AIR QUALITY", font=font, fill=0)

            # Get air quality values
            co2 = readings.get('eco2') or readings.get('ens_eco2')
            tvoc = readings.get('tvoc') or readings.get('ens_tvoc')
            aqi = readings.get('ens_aqi')

            # CO2 - Large and prominent
            y_pos = 15
            if co2:
                draw.text((5, y_pos), "CO2:", font=font, fill=1)
                draw.text((40, y_pos), f"{co2} ppm", font=font, fill=1)

                # Add simple quality indicator
                if co2 < 800:
                    quality = "GOOD"
                elif co2 < 1000:
                    quality = "FAIR"
                else:
                    quality = "POOR"
                draw.text((90, y_pos), quality, font=font, fill=1)
                y_pos += 12

            # TVOC - Below CO2
            if tvoc:
                draw.text((5, y_pos), "TVOC:", font=font, fill=1)
                draw.text((40, y_pos), f"{tvoc} ppb", font=font, fill=1)
                y_pos += 12

            # AQI if available
            if aqi:
                draw.text((5, y_pos), "AQI:", font=font, fill=1)
                draw.text((40, y_pos), str(aqi), font=font, fill=1)
                y_pos += 12

            # Draw recommendation based on readings
            if co2 and co2 > 1000:
                draw.text((5, 50), "Recommendation:", font=font, fill=1)
                draw.text((5, 60), "Open a window for fresh air", font=font, fill=1)

            print(f"Air Quality - CO2: {co2}, TVOC: {tvoc}, AQI: {aqi}")

        elif page == 1:  # Climate Focus
            # Title
            draw.rectangle((0, 0, self.oled.width, 10), outline=1, fill=1)
            draw.text((5, 1), "CLIMATE", font=font, fill=0)

            # Get climate values
            temp = (readings.get('temperature') or
                   readings.get('aht_temperature') or
                   readings.get('bmp_temperature'))

            humidity = (readings.get('humidity') or
                       readings.get('aht_humidity'))

            # Temperature
            y_pos = 15
            if temp:
                draw.text((5, y_pos), "Temp:", font=font, fill=1)
                draw.text((40, y_pos), f"{temp:.1f} C", font=font, fill=1)

                # Add comfort indicator
                if 20 <= temp <= 25:
                    comfort = "COMFORTABLE"
                elif 18 <= temp <= 27:
                    comfort = "ACCEPTABLE"
                else:
                    comfort = "UNCOMFORTABLE"
                draw.text((90, y_pos), comfort[:8], font=font, fill=1)
                y_pos += 12

            # Humidity
            if humidity:
                draw.text((5, y_pos), "Humidity:", font=font, fill=1)
                draw.text((60, y_pos), f"{humidity:.1f}%", font=font, fill=1)
                y_pos += 12

                # Humidity bar
                draw.rectangle((5, y_pos, 123, y_pos+4), outline=1, fill=0)
                bar_width = int((humidity / 100) * 118)
                draw.rectangle((5, y_pos, 5 + bar_width, y_pos+4), outline=1, fill=1)
                y_pos += 8

                # Humidity comfort
                if 40 <= humidity <= 60:
                    hum_comfort = "IDEAL HUMIDITY"
                elif 30 <= humidity <= 70:
                    hum_comfort = "ACCEPTABLE HUMIDITY"
                else:
                    hum_comfort = "POOR HUMIDITY"
                draw.text((5, y_pos), hum_comfort, font=font, fill=1)

            print(f"Climate - Temperature: {temp:.1f if temp else 'N/A'}°C, Humidity: {humidity:.1f if humidity else 'N/A'}%")

        elif page == 2:  # Pressure and Sensors
            # Title
            draw.rectangle((0, 0, self.oled.width, 10), outline=1, fill=1)
            draw.text((5, 1), "PRESSURE & SENSORS", font=font, fill=0)

            # Get pressure and altitude
            pressure = (readings.get('pressure') or
                       readings.get('bmp_pressure'))

            altitude = (readings.get('altitude') or
                       readings.get('bmp_altitude'))

            gas = readings.get('gas')

            # Pressure
            y_pos = 15
            if pressure:
                draw.text((5, y_pos), "Pressure:", font=font, fill=1)
                draw.text((60, y_pos), f"{pressure/100:.1f} hPa", font=font, fill=1)
                y_pos += 12

            # Gas resistance
            if gas:
                draw.text((5, y_pos), "Gas:", font=font, fill=1)
                draw.text((60, y_pos), f"{gas/1000:.1f} kOhm", font=font, fill=1)
                y_pos += 12

            # Altitude if available
            if altitude:
                draw.text((5, y_pos), "Altitude:", font=font, fill=1)
                draw.text((60, y_pos), f"{altitude:.1f} m", font=font, fill=1)
                y_pos += 12

            # Active sensors
            sensors_found = []
            if 'eco2' in readings or 'tvoc' in readings:
                sensors_found.append("SGP30")
            if 'temperature' in readings or 'humidity' in readings or 'pressure' in readings:
                sensors_found.append("BME680")
            if 'aht_temperature' in readings or 'aht_humidity' in readings:
                sensors_found.append("AHT21")
            if 'bmp_temperature' in readings or 'bmp_pressure' in readings:
                sensors_found.append("BMP280")
            if 'ens_aqi' in readings or 'ens_tvoc' in readings:
                sensors_found.append("ENS160")

            # Display active sensors
            draw.text((5, 50), "Active sensors:", font=font, fill=1)
            if sensors_found:
                sensor_text = ", ".join(sensors_found)
                # Wrap text if needed
                if len(sensor_text) > 20:
                    draw.text((5, 60), sensor_text[:20], font=font, fill=1)
                    if len(sensor_text) > 20:
                        draw.text((5, 60), "..." + sensor_text[20:], font=font, fill=1)
                else:
                    draw.text((5, 60), sensor_text, font=font, fill=1)
            else:
                draw.text((5, 60), "None detected", font=font, fill=1)

            print(f"Pressure & Sensors - Pressure: {pressure/100:.1f if pressure else 'N/A'} hPa, " +
                  f"Altitude: {altitude:.1f if altitude else 'N/A'} m, " +
                  f"Active sensors: {', '.join(sensors_found) if sensors_found else 'None'}")

        # Display the image
        self.oled.image(image)
        self.oled.show()
        print(f"Page {page} displayed")

    def draw_canary_state(self, state, readings):
        """Draw the canary with air quality state"""
        print(f"Drawing canary with state: {state}")

        # Create blank image for drawing
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Clear display
        draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)

        # Draw header with state
        draw.rectangle((0, 0, self.oled.width, 10), outline=1, fill=1)

        # Set title based on state with clear meaning
        if state == "warning":
            title = "POOR AIR QUALITY"
            message = "Open windows or use air purifier"
        elif state == "good":
            title = "EXCELLENT AIR"
            message = "Air quality is optimal"
        elif state == "medium":
            title = "FAIR AIR QUALITY"
            message = "Consider ventilation"
        elif state == "caution":
            title = "DECLINING AIR"
            message = "Monitor and ventilate soon"
        else:
            title = "UNKNOWN STATUS"
            message = "Check sensor readings"

        # Draw title - centered if possible
        title_width = len(title) * 6  # Approximate width
        title_x = max(5, (self.oled.width - title_width) // 2)
        draw.text((title_x, 1), title, font=font, fill=0)

        # Draw the bird
        self.draw_bird(draw, state)

        # Draw message below bird
        message_width = len(message) * 6  # Approximate width
        message_x = max(5, (self.oled.width - message_width) // 2)
        draw.text((message_x, 45), message, font=font, fill=1)

        # Show key readings at bottom
        co2 = readings.get('eco2') or readings.get('ens_eco2')
        tvoc = readings.get('tvoc') or readings.get('ens_tvoc')

        if co2 and tvoc:
            reading_text = f"CO2: {co2} ppm   TVOC: {tvoc} ppb"
            draw.line((0, 55, self.oled.width, 55), fill=1)
            draw.text((2, 57), reading_text, font=font, fill=1)

        # Display the image
        self.oled.image(image)
        self.oled.show()
        print(f"Canary state displayed: {title}")

    def draw_bird(self, draw, state):
        """Draw the bird in the blue section"""
        # Base positioning
        base_x = 30  # Base x position
        base_y = 20  # Base y position for canary view

        # Draw body parts in a more structured way
        # Body - smaller and more oval to match other views
        draw.ellipse((base_x, base_y, base_x+30, base_y+25), outline=1, fill=1)

        # Head
        head_x = base_x + 25
        head_y = base_y - 5
        draw.ellipse((head_x, head_y, head_x+15, head_y+15), outline=1, fill=1)

        # Beak - shortened to avoid covering notes
        beak_x = head_x + 15
        beak_y = head_y + 7
        draw.polygon([(beak_x, beak_y), (beak_x+10, beak_y), (beak_x, beak_y+4)], outline=1, fill=1)

        # Tail
        tail_x = base_x - 10
        tail_y = base_y + 10
        draw.polygon([(tail_x, tail_y), (tail_x+10, tail_y+3), (tail_x, tail_y+6)], outline=1, fill=1)

        # Leg
        leg_x = base_x + 15
        leg_y = base_y + 25
        draw.line((leg_x, leg_y, leg_x, leg_y+10), fill=1, width=2)

        # Add foot
        foot_y = leg_y + 10
        draw.line((leg_x-3, foot_y, leg_x+5, foot_y), fill=1, width=1)

        # Eye
        eye_x = head_x + 8
        eye_y = head_y + 6

        # Draw state-specific elements
        if state == "warning":
            # X eyes for warning (replace the normal eye)
            draw.ellipse((eye_x, eye_y, eye_x+3, eye_y+3), outline=1, fill=1)  # Cover normal eye
            draw.line((head_x+5, head_y+5, head_x+10, head_y+10), fill=0, width=1)
            draw.line((head_x+10, head_y+5, head_x+5, head_y+10), fill=0, width=1)
        elif state == "good":
            # Draw musical notes for happy canary
            for i, (x, y) in enumerate([(90, 25), (100, 23), (110, 27)]):
                # Draw note head
                draw.ellipse((x, y, x+3, y+3), outline=1, fill=1)
                # Draw note stem
                draw.rectangle((x+2, y-6, x+3, y), outline=1, fill=1)
        elif state == "medium" or state == "caution":
            # Add straight line for mouth
            draw.line((head_x+5, head_y+12, head_x+10, head_y+12), fill=0, width=1)


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
        self.current_view = 0  # 0: Bird, 1: Air Quality, 2: Environment, 3: Sensor Status
        self.is_running = True  # Start immediately
        self.button_last_press = time.monotonic()
        self.press_count = 0
        self.found_sensors = []

        self._init_sensors()

        # Show welcome message
        self._show_welcome()

        # Initialize DisplayHandler
        self.display_handler = DisplayHandler(self.display)

    def _show_welcome(self):
        """Show a welcome message on startup"""
        self.display.fill(0)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        # Draw a decorative border
        self.draw.rectangle((2, 2, self.width-3, self.height-3), outline=1, fill=0)

        # Put title in yellow section
        self.draw.text((10, 5), "Air Quality Monitor", font=self.font, fill=255)

        # Put startup message in blue section
        self.draw.text((30, 30), "Starting up...", font=self.font, fill=255)

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
            self.sensors['aht'] = adafruit_ahtx0.AHTx0(self.i2c)
            self.found_sensors.append('AHT21')
            print("✓ AHT21 temperature/humidity sensor ready")
        except Exception as e:
            print(f"✗ AHT21 init error: {e}")

        # Try to initialize BME680
        try:
            self.sensors['bme'] = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)
            self.found_sensors.append('BME680')
            print("✓ BME680 environmental sensor ready")
        except Exception as e:
            print(f"✗ BME680 init error: {e}")

    def get_readings(self):
        """Get readings from all available sensors"""
        readings = {}

        # Get ENS160 readings if available
        if 'ens160' in self.sensors:
            try:
                ens = self.sensors['ens160']
                readings['eco2'] = ens.eCO2
                readings['tvoc'] = ens.TVOC
                readings['aqi'] = ens.AQI
            except Exception as e:
                print(f"ENS160 reading error: {e}")

        # Get AHT21 readings if available
        if 'aht' in self.sensors:
            try:
                aht = self.sensors['aht']
                readings['temperature'] = aht.temperature
                readings['humidity'] = aht.relative_humidity
            except Exception as e:
                print(f"AHT21 reading error: {e}")

        # Get BME680 readings if available
        if 'bme' in self.sensors:
            try:
                bme = self.sensors['bme']
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
                self.current_view = (self.current_view + 1) % 6  # Now 6 views total
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

        # Determine air quality status text
        is_good = self.check_air_quality()
        air_quality_text = "GOOD" if is_good else "CHECK"

        # Handle different views
        match self.current_view:
            case 0:  # Bird view with air quality status
                # Add air quality status in yellow section
                self.draw.text((5, 5), f"Air Quality: {air_quality_text}", font=self.font, fill=255)

                # Draw bird in blue section
                self.bird.draw_bird()
                self.bird.draw_notes()

                # No status text at the bottom - removed as requested

            case 1:  # Air Quality view
                # Title in yellow section
                self.draw.text((5, 5), "Air Quality", font=self.font, fill=255)

                # Show CO2 with bar graph
                co2 = readings.get('eco2', 0)
                self.draw.text((5, YELLOW_SECTION_HEIGHT + 5), f"CO2: {co2} ppm", font=self.font, fill=255)
                self.draw_bar(5, YELLOW_SECTION_HEIGHT + 14, self.width-10, 5, min(co2, 2000), 2000)

            case 2:  # TVOC view
                # Title in yellow section
                self.draw.text((5, 5), "Air Quality", font=self.font, fill=255)

                # Show TVOC with bar graph
                tvoc = readings.get('tvoc', 0)
                self.draw.text((5, YELLOW_SECTION_HEIGHT + 5), f"TVOC: {tvoc} ppb", font=self.font, fill=255)
                self.draw_bar(5, YELLOW_SECTION_HEIGHT + 14, self.width-10, 5, min(tvoc, 1000), 1000)

                # Show AQI if available
                aqi = readings.get('aqi', 0)
                if aqi:
                    self.draw.text((5, YELLOW_SECTION_HEIGHT + 24), f"AQI: {aqi}", font=self.font, fill=255)
                    self.draw_bar(5, YELLOW_SECTION_HEIGHT + 33, self.width-10, 5, min(aqi, 300), 300)

            case 3:  # Temperature/Humidity view
                # Title in yellow section
                self.draw.text((5, 5), "Environment", font=self.font, fill=255)

                # Show temperature and humidity
                temp = readings.get('temperature', 0)
                humidity = readings.get('humidity', 0)

                self.draw.text((5, YELLOW_SECTION_HEIGHT + 5), f"Temp: {temp:.1f}°C", font=self.font, fill=255)
                self.draw_bar(5, YELLOW_SECTION_HEIGHT + 14, self.width-10, 5, min(temp, 40), 40)

                self.draw.text((5, YELLOW_SECTION_HEIGHT + 24), f"Humidity: {humidity:.1f}%", font=self.font, fill=255)
                self.draw_bar(5, YELLOW_SECTION_HEIGHT + 33, self.width-10, 5, humidity, 100)

            case 4:  # Pressure/Gas view
                # Title in yellow section
                self.draw.text((5, 5), "Environment", font=self.font, fill=255)

                # Show pressure and gas resistance if available
                pressure = readings.get('pressure', 0)
                gas = readings.get('gas', 0)

                if pressure > 0:
                    self.draw.text((5, YELLOW_SECTION_HEIGHT + 5), f"Press: {pressure/100:.1f} hPa", font=self.font, fill=255)
                    # Normalize around 1013 hPa
                    norm_pressure = min(max((pressure/100 - 950) / 100, 0), 1)
                    self.draw_bar(5, YELLOW_SECTION_HEIGHT + 14, self.width-10, 5, norm_pressure * 100, 100)

                if gas > 0:
                    self.draw.text((5, YELLOW_SECTION_HEIGHT + 24), f"Gas: {gas/1000:.1f} kΩ", font=self.font, fill=255)
                    # Normalize gas resistance (higher is better)
                    norm_gas = min(gas / 300000, 1)
                    self.draw_bar(5, YELLOW_SECTION_HEIGHT + 33, self.width-10, 5, norm_gas * 100, 100)

            case 5:  # Sensor Status view
                # Title in yellow section
                self.draw.text((5, 5), "Sensor Status", font=self.font, fill=255)

                # Draw sensor status with icons
                y = YELLOW_SECTION_HEIGHT + 5
                for i, sensor in enumerate(['ENS160', 'AHT21', 'BME680']):
                    # Check if sensor is present
                    has_sensor = sensor in self.found_sensors
                    status = "✓" if has_sensor else "✗"
                    icon_fill = 1 if has_sensor else 0

                    # Draw a small icon
                    self.draw.rectangle((5, y, 15, y+10), outline=1, fill=icon_fill)
                    self.draw.text((20, y), f"{sensor}: {status}", font=self.font, fill=255)
                    y += 15  # More spacing between sensors

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
                # Add a warning icon in blue section
                self.draw.rectangle((5, YELLOW_SECTION_HEIGHT + 10, 15, YELLOW_SECTION_HEIGHT + 20), outline=1, fill=1)
                self.draw.text((7, YELLOW_SECTION_HEIGHT + 12), "!", font=self.font, fill=0)
                self.draw.text((20, YELLOW_SECTION_HEIGHT + 12), "Error! Check sensors", font=self.font, fill=255)
                self.draw.text((5, YELLOW_SECTION_HEIGHT + 25), str(e)[:20], font=self.font, fill=255)
                self.display.image(self.image)
                self.display.show()
                time.sleep(5)

if __name__ == "__main__":
    monitor = AirMonitor()
    monitor.run()