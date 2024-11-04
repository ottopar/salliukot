from machine import Pin, I2C
import ssd1306
import time

# Constants
WIDTH = 128
HEIGHT = 64

# Initialize I2C and OLED
i2c = I2C(1, sda=Pin(14), scl=Pin(15))
display = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)

# Initialize button pins
sw0 = Pin(7, Pin.IN, Pin.PULL_UP)  # Move Up
sw1 = Pin(8, Pin.IN, Pin.PULL_UP)  # Clear
sw2 = Pin(9, Pin.IN, Pin.PULL_UP)  # Move Down

# Initial position and speed
x = 0
y = HEIGHT // 2

# Main loop
while True:
    # Clear the screen if SW1 is pressed
    if not sw1.value():
        x = 0
        y = HEIGHT // 2
        display.fill(0)  # Clear the display
        display.show()
        time.sleep(0.2)  # Debounce delay

    # Move the line based on button presses
    if not sw0.value() and y > 0:  # Move up if SW0 is pressed
        y -= 1
        time.sleep_ms(40)  # Debounce delay
    if not sw2.value() and y < HEIGHT - 1:  # Move down if SW2 is pressed
        y += 1
        time.sleep_ms(40)  # Debounce delay

    # Draw the current pixel to create a line effect
    display.pixel(x, y, 1)  # Draw the current pixel
    display.show()

    # Move the line to the right
    x += 1
    if x >= WIDTH:  # Wrap around
        x = 0

    time.sleep(0.05)  # Control the drawing speed
