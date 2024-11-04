from machine import Pin, I2C
import ssd1306
import time

i2c = I2C(1, sda=Pin(14), scl=Pin(15))
display = ssd1306.SSD1306_I2C(128, 64, i2c)

btn0 = Pin(9, Pin.IN, Pin.PULL_UP)
btn2 = Pin(7, Pin.IN, Pin.PULL_UP)
loc = 50

while True:
    
    if btn0.value() == 0:
        if loc >= 100:
            loc = 100
        else:
            loc += 10
        display.fill(0)
        
    if btn2.value() == 0:
        if loc <= 0:
            loc = 0
        else:
            loc -= 10
        display.fill(0)
        
        
    display.contrast(255)
    display.invert(0)
    display.rotate(True)
    display.text('<=>', loc, 0, 1)
    display.show()
