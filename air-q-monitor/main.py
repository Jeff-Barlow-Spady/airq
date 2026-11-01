import time
import RPi.GPIO as GPIO
from board import SCL, SDA
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# Configure GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Initialize I2C bus
i2c = busio.I2C(SCL, SDA)

# Create the OLED class
# Most 128x64 displays use address 0x3C
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

try:
    # Clear display
    display.fill(0)
    display.show()

    # Create blank image for drawing
    width = display.width
    height = display.height
    image = Image.new("1", (width, height))

    # Get drawing object to draw on image
    draw = ImageDraw.Draw(image)

    # Draw a filled rectangle for each half
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    draw.rectangle((0, 0, width-1, height//2-1), outline=1, fill=1)  # Top half (Yellow)
    draw.rectangle((0, height//2, width-1, height-1), outline=1, fill=1)  # Bottom half (Yellow)

    # Add some text
    font = ImageFont.load_default()
    draw.text((10, 10), "Yellow Section", font=font, fill=0)
    draw.text((10, 40), "Blue Section", font=font, fill=0)

    # Display image
    display.image(image)
    display.show()

    # Keep the display on for a while
    print("Display test running. Press CTRL+C to exit.")
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nExiting gracefully...")
except Exception as e:
    print(f"Error occurred: {e}")
finally:
    GPIO.cleanup()
