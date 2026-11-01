import RPi.GPIO as GPIO
import time
from board import SCL, SDA
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import busio

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Initialize I2C bus
i2c = busio.I2C(SCL, SDA)

# Create the OLED class
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Create blank image for drawing
image = Image.new("1", (display.width, display.height))

# Get drawing object to draw on image
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()
# Draw a black filled box to clear the image
draw.rectangle((0, 0, display.width, display.height), outline=0, fill=1)
draw.text((10, 10), "Hello World!", font=font, fill=0)

# Display image
display.image(image)
display.show()

GPIO.cleanup()
