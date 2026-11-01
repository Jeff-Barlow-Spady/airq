
import time
import adafruit_ssd1306
import RPi.GPIO as GPIO
from board import SCL, SDA
import busio
from PIL import Image, ImageDraw, ImageFont

# Configure GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Initialize I2C bus
i2c = busio.I2C(SCL, SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
def draw_info_screen(co2, voc, humidity):
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    # Draw readings
    draw.text((0, 0), f"CO2: {co2}", font=font, fill=1)
    draw.text((0, 16), f"VOC: {voc}", font=font, fill=1)

    # Draw humidity bar
    bar_width = int((humidity / 100) * oled.width)
    draw.rectangle((0, 50, oled.width, 64), outline=1, fill=0)  # Bar outline
    draw.rectangle((0, 50, bar_width, 64), outline=1, fill=1)   # Fill based on humidity
    draw.text((0, 38), f"Humidity: {humidity}%", font=font, fill=1)

    oled.image(image)
    oled.show()

def draw_chirping_canary(frame_num):
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Draw basic canary
    draw.ellipse((40, 20, 80, 45), outline=1, fill=1)  # body
    draw.ellipse((75, 16, 90, 30), outline=1, fill=1)  # head
    # Draw Eye
    draw.ellipse((80, 18, 84, 22), outline=1, fill=0)
    draw.ellipse((86, 18, 90, 22), outline=1, fill=1)
    draw.polygon([(90, 20), (98, 23), (90, 26)], outline=1, fill=1)  # beak
    draw.line((86, 22, 86, 26), fill=0, width=1) # horizontal beak line - starting at tip of beak polygon

    draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)  # tail
    draw.line((60, 45, 60, 55), fill=1, width=2)  # leg
    draw.line((55, 55, 65, 55), fill=1, width=1)  # foot

    # Draw musical notes based on frame
    if frame_num >= 1:
        draw.ellipse((95, 10, 99, 14), outline=1, fill=1)
        draw.line((99, 12, 99, 4), fill=1, width=1)
    if frame_num >= 2:
        draw.ellipse((105, 8, 109, 12), outline=1, fill=1)
        draw.line((109, 10, 109, 2), fill=1, width=1)
    if frame_num >= 3:
        draw.ellipse((115, 12, 119, 15), outline=1, fill=1)
        draw.line((119, 14, 119, 6), fill=1, width=1)

    oled.image(image)
    oled.show()

def main():
    try:
        show_info = True
        frame = 0
        mock_humidity = 65  # For testing

        while True:
            if show_info:
                draw_info_screen(800, 200, mock_humidity)
                time.sleep(3)
            else:
                draw_chirping_canary(frame % 4)
                frame += 1
                time.sleep(0.5)
                if frame % 4 == 0:
                    time.sleep(0.3)

            # Toggle display every 3 seconds
            if frame % 6 == 0:
                show_info = not show_info
                oled.fill(0)
                oled.show()
                time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        oled.fill(0)
        oled.show()
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()