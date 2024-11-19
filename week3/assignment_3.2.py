from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from led import Led
import time

class MainMenu:
    def __init__(self, rotary_btn, a_pin, b_pin, led_pins):
        # Rotary encoder pins
        self.sw = Pin(rotary_btn, mode=Pin.IN, pull=Pin.PULL_UP)
        self.a = Pin(a_pin, mode=Pin.IN, pull=Pin.PULL_UP)
        self.b = Pin(b_pin, mode=Pin.IN, pull=Pin.PULL_UP)

        # LED pins and states
        self.leds = [Led(pin) for pin in led_pins] # Assign pins 22, 21, 20 to LEDs
        self.led_states = [False, False, False]  # All LEDs off initially

        # I2C and OLED setup
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)

        # Menu logic
        self.menu_items = ["LED1", "LED2", "LED3"]
        self.selected_index = 0  # Initially select the first menu item

        # FIFO for rotary events
        self.fifo = Fifo(50, typecode='i')

        # Interrupts
        self.a.irq(handler=self.on_rotary_rotated, trigger=Pin.IRQ_RISING, hard=True)
        self.sw.irq(handler=self.on_rotary_pressed, trigger=Pin.IRQ_RISING, hard=True)

        # Debounce variables
        self.last_press_time = 0
        self.last_rotate_time = 0
        self.debounce_time = 100  # ms

    def on_rotary_rotated(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_press_time) > self.debounce_time: # Calculate that it has been atleast 100ms from last rotation
            self.last_press_time = current_time
            if self.b():  # Clockwise rotation
                self.fifo.put(-1)
            else:         # Counter-clockwise rotation
                self.fifo.put(1)

    def on_rotary_pressed(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_press_time) > self.debounce_time: # Calculate if it has been atleast 100ms from last button press
            self.last_press_time = current_time
            self.fifo.put(2)  # Button press

    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        for i, item in enumerate(self.menu_items): # Item in each iteration changes to the next list item string in self.menu_items and i is normal for loop iteration number starting from 0
            y_position = 10 + i * 10  # Space menu items 10 px apart ( First iteration 10 + i(0) * 10 = 10px from the top of the screen )
            if i == self.selected_index:
                self.OLED.text(f"{item} <=", 0, y_position, 1) # If current selected index value (0-2) == i, place select arror next to it.
            else:
                self.OLED.text(f"{item}", 0, y_position, 1)  # Regular text
        self.OLED.show()  # Update the screen

    def toggle_led(self, index):
        self.led_states[index] = not self.led_states[index]  # LED state from False => True
        self.leds[index].value(self.led_states[index])  # Turn the LED physically on
        
    def execute(self):
        if self.fifo.has_data():
            event = self.fifo.get() # Get the first event in fifo
            if event == 1:  # Clockwise rotation event
                self.selected_index = (self.selected_index + 1) 
            elif event == -1:  # Counter-clockwise rotation event
                self.selected_index = (self.selected_index - 1)
            elif event == 2:  # Button press event
                self.toggle_led(self.selected_index) # Toggle the LED corresponding to the main menu select index value
            
            if self.selected_index >= len(self.menu_items): # Making sure menu arrow doesn't go "out of bounds"
                self.selected_index = 0
            elif self.selected_index < 0:
                self.selected_index = len(self.menu_items) - 1
        self.draw()
        

# Create an instance of the MainMenu class
menu = MainMenu(
    12,  # Rotary button pin
    10,       # Rotary A pin
    11,       # Rotary B pin
    [22, 21, 20]  # Pins for LED1, LED2, LED3
)

# Main loop
while True:
    menu.execute()
    time.sleep(0.1) # Tried with Piotimer, but didn't get it to work
