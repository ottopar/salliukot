from machine import Pin, I2C
import ssd1306
import time

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
display = ssd1306.SSD1306_I2C(128, 64, i2c)

lines = []
max_lines = 8
line_height = 8

while True:
    
    user_input = input("Type something: ")  # Read input from the user

    # Add new input to the list of lines
    lines.append(user_input)

    # If we exceed the maximum number of lines, remove the first line
    if len(lines) > max_lines:
        lines.pop(0)

    # Clear the display
    display.fill(0)

    # Draw each line on the OLED display
    for i, line in enumerate(lines):
        display.text(line, 0, i * line_height)

    # Update the display
    display.show()


    

    