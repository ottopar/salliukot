from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
import time
import json

## Kehitykset ##
""" Display class?
    classeille funktiot, jotka tekee mitä pitää,,..!!
    no moikka jätkät <3<3<3
"""


state = 0

class RotaryEncoder:
    def __init__(self, btn_pin=12, a_pin=10, b_pin=11):
        self.sw = Pin(btn_pin, mode=Pin.IN, pull=Pin.PULL_UP)
        self.a = Pin(a_pin, mode=Pin.IN, pull=Pin.PULL_UP)
        self.b = Pin(b_pin, mode=Pin.IN, pull=Pin.PULL_UP)
        self.debounce_time = 100
        
        self.fifo = Fifo(30, typecode='i')
        
        # Interrupts for rotary encoder
        self.a.irq(handler=self.on_rotary_rotated, trigger=Pin.IRQ_RISING, hard=True)
        self.sw.irq(handler=self.on_rotary_pressed, trigger=Pin.IRQ_RISING, hard=True)
        
        self.last_press_time = 0
        self.last_rotate_time = 0
        
    def on_rotary_rotated(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_rotate_time) > self.debounce_time:
            self.last_rotate_time = current_time
            if self.b():  # Clockwise rotation
                self.fifo.put(-1)
            else:         # Counter-clockwise rotation
                self.fifo.put(1)

    def on_rotary_pressed(self, pin):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_press_time) > self.debounce_time:
            self.last_press_time = current_time
            self.fifo.put(2)  # Button press

    def get_event(self):
        if self.fifo.has_data():
            return self.fifo.get()
        return None
    
    
    

class MainMenu:
    def __init__(self, rotary_encoder):
        
        self.rotary_encoder = rotary_encoder

        # I2C and OLED setup
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)

        # Menu logic
        self.menu_items = ["Heart rate", "HRV analysis", "Kubios", "History"]
        self.selected_index = 0  # Initially select the first menu item


    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        for i, item in enumerate(self.menu_items): # Item in each iteration changes to the next list item string in self.menu_items and i is normal for loop iteration number starting from 0
            y_position = 10 + i * 10  # Space menu items 10 px apart ( First iteration 10 + i(0) * 10 = 10px from the top of the screen )
            if i == self.selected_index:
                self.OLED.text(f"{item} <=", 0, y_position, 1) # If current selected index value (0-2) == i, place select arror next to it.
            else:
                self.OLED.text(f"{item}", 0, y_position, 1)  # Regular text
        self.OLED.show()  # Update the screen

        
    def execute(self):
        global state
        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            if event == 1:  # Clockwise rotation event
                if self.selected_index < len(self.menu_items) - 1:
                    self.selected_index = (self.selected_index + 1)
                    print(self.selected_index)
            elif event == -1:  # Counter-clockwise rotation event
                if self.selected_index > 0:
                    self.selected_index = (self.selected_index - 1)
                    print(self.selected_index)
            elif event == 2:  # Button press event
                if self.selected_index == 0:
                    state = 1
                elif self.selected_index == 1:
                    state = 2
                elif self.selected_index == 2:
                    state = 3
                elif self.selected_index == 3:
                    state = 4
                    
            
            if self.selected_index > len(self.menu_items) - 1: # Making sure menu arrow doesn't go "out of bounds"
                self.selected_index = 0
            elif self.selected_index < 0:
                self.selected_index = len(self.menu_items) - 1
        self.draw()
        
        
class HrMeasurement:
    def __init__(self, rotary_encoder):
        
        self.rotary_encoder = rotary_encoder

        # I2C and OLED setup
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
    
    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        self.OLED.text("HR MEASUREMENT", 0, 0, 1)
        self.OLED.text("Press rotary", 0, 16, 1)
        self.OLED.text("to return", 0, 24, 1)
        self.OLED.show()  # Update the screen
    
    def execute(self):
        global state
        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            if event == 2:
                state = 0
        self.draw()
        
class HrvAnalysis:
    def __init__(self, rotary_encoder):
        
        self.rotary_encoder = rotary_encoder
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
    
    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        self.OLED.text("HRV analysis", 0, 0, 1)
        self.OLED.text("Press rotary", 0, 16, 1)
        self.OLED.text("to return", 0, 24, 1)
        self.OLED.show()  # Update the screen
    
    def execute(self):
        global state
        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            if event == 2:
                state = 0
        self.draw()
        
class Kubios:
    def __init__(self, rotary_encoder):
        self.rotary_encoder = rotary_encoder
        
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
    
    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        self.OLED.text("Kubios", 0, 0, 1)
        self.OLED.text("Press rotary", 0, 16, 1)
        self.OLED.text("to return", 0, 24, 1)
        self.OLED.show()  # Update the screen
        
    
    def execute(self):
        global state
        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            if event == 2:
                state = 0
        self.draw()
        
class History:
    def __init__(self, rotary_encoder):
            
        self.rotary_encoder = rotary_encoder
        
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
        
        self.save_data:list = [] # create empty save_data variable.
        self.initialize_json() #check if savedata.json exist. if not create new .json file inside root directory.
        
        self.save_measurement(69, 666, 81, 123) #[REMOVE THIS] just testing to append new data to json
        
    def initialize_json(self): 
        try:
            with open("savedata.json", "r") as f: #with open("PATH", "r=READ/w=WRITE") as VARIABLE
                #IF saveddata.json exists!
                self.save_data = json.load(f) #loads json data and adds it to our "save_data" variable. 
                print("savedata.json file found.")
        except:
            #IF savedata.json does not exist!
            new_data = json.dumps(self.save_data) 
            with open("savedata.json", "w") as f: #with open("PATH", "r=READ/w=WRITE") as VARIABLE
                f.write(new_data)
                
            print("Save data not found. Created new savedata.json file in to root dictionary.")
    
    def save_measurement(self, ppi, hr, rmssd, sdnn):
        new_entry = [ {
            "PPI" : ppi,
            "HR" : hr,
            "rmssd" : rmssd,
            "sdnn" : sdnn
            } ]
        
        self.save_data.append(new_entry)
        self.write_to_json(self.save_data)
        
    def write_to_json(self, dictionary):
        with open("savedata.json", "w") as f: #with open("PATH", "r=READ/w=WRITE") as VARIABLE
            json.dump(dictionary, f)
            print("new .json data saved.")
            
    def draw(self):
        self.OLED.fill(0)  # Fill screen with black
        self.OLED.text("History", 0, 0, 1)
        self.OLED.text("Press rotary", 0, 16, 1)
        self.OLED.text("to return", 0, 24, 1)
        self.OLED.show()  # Update the screen
        
    def execute(self):
        global state
        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            if event == 2:
                state = 0
        self.draw()


rotary_encoder = RotaryEncoder()
menu = MainMenu(rotary_encoder)
hr = HrMeasurement(rotary_encoder)
hrv = HrvAnalysis(rotary_encoder)
kubios = Kubios(rotary_encoder)
history = History(rotary_encoder)



# Main loop
while True:
    if state == 0:  # main menu
        menu.execute()
    elif state == 1: # HR measurement
        hr.execute()
    elif state == 2: # HRV analysis
        hrv.execute()
    elif state == 3: # Kubios
        kubios.execute()
    elif state == 4: # History
        history.execute()