
import time
from PIL import Image, ImageDraw
import adafruit_ssd1306
import RPi.GPIO as GPIO
from board import SCL, SDA
import busio

# Configure GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Initialize I2C bus
i2c = busio.I2C(SCL, SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

def test_display():
    # Clear display
    oled.fill(0)
    oled.show()

    # Create blank image for drawing
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Draw a test pattern
    draw.rectangle((0, 0, oled.width-1, oled.height-1), outline=1, fill=0)
    draw.line((0, 0, oled.width-1, oled.height-1), fill=1)

    # Display image
    oled.image(image)
    oled.show()
    time.sleep(2)
    return image, draw

def draw_canary():
    # Create blank image for drawing
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Clear display
    draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

    # Draw body (oval)
    draw.ellipse((40, 20, 80, 45), outline=1, fill=1)

    # Draw head (circle)
    draw.ellipse((75, 15, 90, 30), outline=1, fill=1)

    # Draw beak (triangle)
    draw.polygon([(90, 20), (98, 23), (90, 26)], outline=1, fill=1)

    # Draw tail feathers (triangles)
    draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)

    # Draw leg (line)
    draw.line((60, 45, 60, 55), fill=1, width=2)

    # Draw foot
    draw.line((55, 55, 65, 55), fill=1, width=1)

    # Display image
    oled.image(image)
    oled.show()

def main():
    try:
        print("Testing display...")
        test_display()  # Test the display first

        while True:
            print("Drawing canary...")
            draw_canary()
            time.sleep(5)

            # Clear display
            oled.fill(0)
            oled.show()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        oled.fill(0)
        oled.show()
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()

def draw_chirping_canary():
    # Create blank image for drawing
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Clear display
    draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

    # Draw basic canary (same as before)
    draw.ellipse((40, 20, 75, 45), outline=1, fill=1)  # body
    draw.ellipse((75, 15, 90, 30), outline=1, fill=1)  # head
    draw.polygon([(90, 20), (98, 23), (90, 26)], outline=1, fill=1)  # beak
    draw.polygon([(30, 25), (40, 30), (30, 35)], outline=1, fill=1)  # tail
    draw.line((60, 45, 60, 55), fill=1, width=2)  # leg
    draw.line((55, 55, 65, 55), fill=1, width=1)  # foot

    # Draw musical notes for chirping
    def draw_note(x, y):
        draw.ellipse((x, y, x+4, y+4), outline=1, fill=1)  # note head
        draw.line((x+4, y+2, x+4, y-6), fill=1, width=1)  # note stem

    # Animate different note positions
    return image, draw, draw_note

def chirp_animation():
    try:
        print("Drawing chirping canary animation...")
        image, draw, draw_note = draw_chirping_canary()

        while True:
            # Frame 1: One note
            draw_note(95, 10)
            oled.image(image)
            oled.show()
            time.sleep(0.5)

            # Frame 2: Two notes
            draw_note(100, 5)
            oled.image(image)
            oled.show()
            time.sleep(0.5)

            # Frame 3: Three notes
            draw_note(105, 8)
            oled.image(image)
            oled.show()
            time.sleep(0.5)

            # Clear notes for next animation
            draw.rectangle((90, 0, 128, 20), outline=0, fill=0)
            oled.image(image)
            oled.show()
            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        oled.fill(0)
        oled.show()

# Add new option to main function
def main():
    try:
        while True:
            print("\nChoose animation:")
            print("1. Static Canary")
            print("2. Chirping Canary")
            choice = input("Enter choice (1 or 2, CTRL+C to exit): ")

            if choice == "1":
                draw_canary()
                time.sleep(5)
            elif choice == "2":
                chirp_animation()
            else:
                print("Invalid choice. Please try again.")

            # Clear display between animations
            oled.fill(0)
            oled.show()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        oled.fill(0)
        oled.show()

if __name__ == "__main__":
    main()
