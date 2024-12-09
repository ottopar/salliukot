from machine import Pin, I2C, ADC
from piotimer import Piotimer
from ssd1306 import SSD1306_I2C
from fifo import Fifo
import time
import ujson
import gc
import micropython
import array
from umqtt.simple import MQTTClient
import network


micropython.alloc_emergency_exception_buf(200)

## Kehitykset ##
""" Display class?
    classeille funktiot, jotka tekee mitä pitää,,..!!
    no moikka jätkät <3<3<3
    Ongelmia:
    -fifo täyttyy jos kutsuu draw metodia liian usein hr measurementissa.
    -hr measurement on paskasti tehty, bpm heittelee aika paljon. Vaatii vähän vielä hiomista
    -Samuel syyttää paskaa mittariaan + ehkä skill issue, testatkaa emt
    
"""

SAMPLE_RATE = 250
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
        self.OLED.text("SALLIMONITOR", 16, 0, 1)
        for i, item in enumerate(self.menu_items): # Item in each iteration changes to the next list item string in self.menu_items and i is normal for loop iteration number starting from 0
            y_position = 20 + i * 10  # Space menu items 10 px apart ( First iteration 10 + i(0) * 10 = 10px from the top of the screen )
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
    def __init__(self, rotary_encoder, sample_rate):
        
        self.rotary_encoder = rotary_encoder
        self.adc = ADC(26)  
        self.sample_rate = sample_rate
        self.data_segment_duration = 4  # seconds
        self.min_peak_distance = 100 # 400ms, ~190 bpm
        self.max_peak_distance = 400 # 1600ms, ~30 bpm
        self.buffer_size = self.sample_rate * self.data_segment_duration
        self.buffer = array.array('H', [0] * self.buffer_size) 
        self.fifo = Fifo(30, typecode='i')
        self.buffer_index = 0 
        self.bpm = None
        self.start_up = True
        self.prev_filtered_value = 0

        # I2C and OLED setup
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
    
    def read_adc(self, timer):
        sample = self.adc.read_u16()
        self.fifo.put(sample)
        
    def low_pass_filter(self, sample, alpha=0.1):
        self.prev_filtered_value = alpha * sample + (1 - alpha) * self.prev_filtered_value
        return int(self.prev_filtered_value)
    
    def calculate_data(self):
        threshold = (sum(self.buffer) / len(self.buffer)) * 1.03
        bpm_list = []
        last_peak_index = 0
        for i in range(1, len(self.buffer) -1):
            if self.buffer[i] > self.buffer[i - 1] and self.buffer[i] > self.buffer[i + 1] and self.buffer[i] > threshold:
                if last_peak_index != 0:
                    index_diff = i - last_peak_index
                    if self.min_peak_distance < index_diff < self.max_peak_distance:
                        ppi_ms = index_diff * 4
                        
                        bpm = round(60/(ppi_ms/1000))
                        bpm_list.append(bpm) # appending bpm, because sample buffer has 1000 samples. There might be ~3-4 valid peaks in the data.
                                
                last_peak_index = i
                
        if bpm_list:  # Check if there are any valid BPMs in the list
            round_bpm = (round(sum(bpm_list) / len(bpm_list)))  # Calculate the average BPM for more accuracy
            if 30 < round_bpm < 200: # varmistus vielä vaikka filtteröi jo ppi perusteella
                self.bpm = round_bpm
                print("BPM: ", self.bpm)
        else:
            print("No relevant peaks detected")
    def draw(self):
        if self.start_up:
            
            self.OLED.fill(0)
            self.OLED.text(f"HR MEASUREMENT", 8, 0, 1)
            self.OLED.text(f"Calculating...", 10, 32, 1)
            self.OLED.show()
            self.start_up = False
        else:
            
            if self.bpm:
                self.OLED.fill(0)
                self.OLED.text(f"HR MEASUREMENT", 10, 0, 1)
                self.OLED.text(f"BPM: {self.bpm}", 30, 32, 1)
            self.OLED.show()  # Update the screen
    
    def execute(self):
        global state
        
        if self.fifo.has_data():
            #sample = self.fifo.get()
            sample = self.low_pass_filter(self.fifo.get())

            self.buffer[self.buffer_index] = sample
            self.buffer_index = (self.buffer_index + 1) % len(self.buffer)  # ring buffer

            if self.buffer_index == 0: # ring buffer full
                print("Buffer is full, processing data...")
                self.calculate_data()  
                self.buffer_index = 0
                self.draw() # Need to call draw here to limit draw calls, else the fifo fills up.
                
        if self.start_up: # First startup
            self.draw()
            
        if self.rotary_encoder.fifo.has_data(): # Rotary events
            event = self.rotary_encoder.fifo.get()
            if event == 2:
                self.bpm = None
                self.start_up = True
                state = 0
                
        
class HrvAnalysis:
    def __init__(self, rotary_encoder, history_obj):
        
        self.rotary_encoder = rotary_encoder
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
        self.adc = ADC(Pin(26))
        self.history = history_obj
        
        self.samplerate = 250
        self.duration = 30
        self.capturelength = int(self.samplerate * self.duration)
        self.samples = Fifo(32)
        self.adcbuffer = array.array('H', [0] * self.capturelength)
        self.index = 0
        self.signal_threshold = 2500
        self.tmr = None
        self.analysis_done = False
        self.count = 30
        self.counter = 0
        
    def reset(self):
        self.index = 0
        self.count = 30
        self.counter = 0
        self.adcbuffer = array.array('H', [0] * self.capturelength)
        self.samples = Fifo(32)
        self.analysis_done = False
        if self.tmr:
            self.stop_timer()
        print("analysis reset")
        
    def adc_read(self, tid):
        x = self.adc.read_u16()
        self.samples.put(x)
        
    def low_pass_filter(self, data, a=0.2):
        last_value = data[0]
        for i in range(1, len(data)):
            filtered_value = a * data[i] + (1 - a) * last_value
            data[i] = int(round(filtered_value))
            last_value = data[i]
        return data
    
    def peak_to_peak_intervals(self, data):
        
        threshold = (sum(data) / len(data)) * 1.03
        peaks_ms_list = []
        lastpeak = 0
        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] > threshold:
                if lastpeak != 0:
                    indexdiff = i - lastpeak
                    if 100 < indexdiff < 400:
                        peak_ms = indexdiff * 4
                        peaks_ms_list.append(peak_ms)       
                lastpeak = i
        return peaks_ms_list
    
    def moving_average(self, data, window_size=3):
        return [int(sum(data[i:i+window_size]) / window_size) for i in range(len(data) - window_size + 1)]
    
    def rmssd_calc(self, data):
        total = 0
        for i in range(len(data) -1):
            total += (data[i+1] - data[i])**2
        rmssd_round = round((total / (len(data) - 1))**0.5, 0)
        return int(rmssd_round)
    
    def sdnn_calc(self, data, meanPPI):
        total = 0
        for i in data:
            total += (i - meanPPI)**2
        sdnn = (total / (len(data) - 1))**0.5
        sdnn_round = round(sdnn, 0)
        return int(sdnn_round) 
        
    def start_timer(self):
        self.tmr = Piotimer(freq=self.samplerate, mode=Piotimer.PERIODIC, callback=self.adc_read)
        
    def stop_timer(self):
        if self.tmr:
            self.tmr.deinit()
            self.tmr = None
    
    def execute(self):
        
        global state
        
        if self.analysis_done:
            if self.rotary_encoder.fifo.has_data():
                event = self.rotary_encoder.fifo.get() # Get the first event in fifo
                if event == 2:
                    self.reset()
                    state = 0
            return
        
        self.OLED.fill(0)
        self.OLED.text("Measuring for", 0, 0, 1)
        self.OLED.text(f"{self.count} seconds", 0, 16, 1)
        self.OLED.text("Please wait", 0, 32, 1)
        self.OLED.show()
        
        self.start_timer()
        
        while self.index < len(self.adcbuffer):
            if not self.samples.empty():
                x = self.samples.get()
                self.adcbuffer[self.index] = x
                self.index += 1
            # Handle the counter
                self.counter += 1
            
            if self.counter >= 250:
                self.counter = 0
                if self.count > 0:
                    self.count -= 1
                    self.OLED.fill(0)
                    self.OLED.text("Measuring for", 0, 0, 1)
                    self.OLED.text(f"{self.count} seconds", 0, 16, 1)
                    self.OLED.text("Please wait", 0, 32, 1)
                    self.OLED.show()
                    
        self.stop_timer()
        
        filtered_signal = self.low_pass_filter(self.adcbuffer)
        peak_to_peak = self.peak_to_peak_intervals(filtered_signal)
        smoothed_peaks = self.moving_average(peak_to_peak)
        print(peak_to_peak)
        print(smoothed_peaks)
        
        if len(smoothed_peaks) >= 3:
            meanPPI = sum(smoothed_peaks) / len(smoothed_peaks) if smoothed_peaks else 0# scaled to ms #
            meanHR = round(60 * 1000 / meanPPI, 0) if smoothed_peaks else 0
            rmssd_value = self.rmssd_calc(smoothed_peaks)
            sdnn_value = self.sdnn_calc(smoothed_peaks, meanPPI) # scaled to ms #
        
            print(f"mean PPI: {meanPPI}, mean hr: {meanHR}, rmssd: {rmssd_value}, sdnn: {sdnn_value}")
        
            self.OLED.fill(0)
            self.OLED.text(f"HRV Result:", 0, 0, 1)
            self.OLED.text(f"MEAN PPI:{round(meanPPI)} ms", 0, 10, 1)
            self.OLED.text(f"MEAN HR:{round(meanHR)} BPM", 0, 20, 1)
            self.OLED.text(f"RMSSD:{rmssd_value} ms", 0, 30, 1)
            self.OLED.text(f"SDNN:{sdnn_value} ms", 0, 40, 1)
            self.OLED.show()
            
            #SAVE DATA THROUGH HISTORY CLASS FUNCTION!
            self.history.save_measurement(meanPPI, meanHR, rmssd_value, sdnn_value)    
            
            gc.collect()
            
            self.analysis_done = True
        
        else:
            self.OLED.fill(0)
            self.OLED.text("Error", 0, 0, 1)
            self.OLED.text("Please try again", 0, 10, 1)
            self.OLED.show()
            gc.collect()
        
            self.analysis_done = True
        
class Kubios:
    def __init__(self, rotary_encoder, history_obj, HrvAnalysis):
        self.rotary_encoder = rotary_encoder
        self.HrvAnalysis = HrvAnalysis
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
        self.adc = ADC(Pin(26))
        self.history = history_obj
        
        self.ssid = "KME751_Group_5"
        self.password = "Nakkivene1"
        self.broker_ip = "192.168.50.253"
        self.port = 21884
        self.tmr = None
        self.connect_wlan()
            
        
        # Function to connect to WLAN
    def connect_wlan(self):
        # Connecting to the group WLAN
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.ssid, self.password)

        # Attempt to connect once per second
        while wlan.isconnected() == False:
            print("Connecting... ")
            time.sleep(1)

        # Print the IP address of the Pico
        print("Connection successful. Pico IP:", wlan.ifconfig()[0])
        
    def sub_cb(self, topic, msg):
        data = ujson.loads(msg)
        
        self.OLED.fill(0)   
        self.OLED.text(f'MEAN HR: {str(round(data["data"]["analysis"]["mean_hr_bpm"]))}' , 0, 0, 1)
        self.OLED.text(f'MEAN PPI: {str(round(data["data"]["analysis"]["mean_rr_ms"]))}' , 0, 10, 1)
        self.OLED.text(f'RMSSD: {str(round(data["data"]["analysis"]["rmssd_ms"]))}' , 0, 20, 1)
        self.OLED.text(f'SDNN: {str(round(data["data"]["analysis"]["sdnn_ms"]))}' , 0, 30, 1)
        self.OLED.text(f'SNS: {data["data"]["analysis"]["sns_index"]:.2f}' , 0, 40, 1)
        self.OLED.text(f'PNS: {data["data"]["analysis"]["pns_index"]:.2f}' , 0, 50, 1)
        self.OLED.show()
        
        self.history.save_measurement(round(data["data"]["analysis"]["mean_rr_ms"]),
                                      round(data["data"]["analysis"]["mean_hr_bpm"]),
                                      round(data["data"]["analysis"]["rmssd_ms"]),
                                      round(data["data"]["analysis"]["sdnn_ms"]))    
            
                
    def connect_mqtt(self):
        mqtt_client=MQTTClient("", self.broker_ip, self.port)
        mqtt_client.set_callback(self.sub_cb)
        mqtt_client.connect(clean_session=True)
        mqtt_client.subscribe("kubios-response")
        print("Connected to mqtt broker")
        return mqtt_client
            
    
    def draw(self):
        self.OLED.fill(0)
        self.OLED.text("Measuring for", 0, 0, 1)
        self.OLED.text(f"{self.HrvAnalysis.count} seconds", 0, 16, 1)
        self.OLED.text("Please wait", 0, 32, 1)
        self.OLED.show()
        
    def execute(self):
        global state
        
        if self.HrvAnalysis.analysis_done:
            if self.rotary_encoder.fifo.has_data():
                event = self.rotary_encoder.fifo.get() # Get the first event in fifo
                if event == 2:
                    self.HrvAnalysis.reset()
                    state = 0
            return
        
        self.draw()
        
        self.HrvAnalysis.start_timer()
        
        while self.HrvAnalysis.index < len(self.HrvAnalysis.adcbuffer):
            if not self.HrvAnalysis.samples.empty():
                x = self.HrvAnalysis.samples.get()
                self.HrvAnalysis.adcbuffer[self.HrvAnalysis.index] = x
                self.HrvAnalysis.index += 1
                self.HrvAnalysis.counter += 1
                
            if self.HrvAnalysis.counter >= 250:
                self.HrvAnalysis.counter = 0
                if self.HrvAnalysis.count > 0:
                    self.HrvAnalysis.count -= 1
                    self.OLED.fill(0)
                    self.OLED.text("Measuring for", 0, 0, 1)
                    self.OLED.text(f"{self.HrvAnalysis.count} seconds", 0, 16, 1)
                    self.OLED.text("Please wait", 0, 32, 1)
                    self.OLED.show()
            
        self.HrvAnalysis.stop_timer()
        
        filtered_signal = self.HrvAnalysis.low_pass_filter(self.HrvAnalysis.adcbuffer)
        peak_to_peak = self.HrvAnalysis.peak_to_peak_intervals(filtered_signal)
        smoothed_peaks = self.HrvAnalysis.moving_average(peak_to_peak)
        print(smoothed_peaks)
        
        sendtokubios = {
            "id" : 123,
            "type" : "RRI",
            "data" : smoothed_peaks,
            "analysis": { "type": "readiness" }
            }
        
        try:
            mqtt_client=self.connect_mqtt()
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")
            self.OLED.fill(0)
            self.OLED.text("Error", 0, 0, 1)
            self.OLED.text("Please try again", 0, 10, 1)
            self.OLED.show()
        
        try:
            
            topic = "kubios-request"
            message = ujson.dumps(sendtokubios)
            mqtt_client.publish(topic, message)
            print(f"Sending to MQTT: {topic} -> {message}")
            
        except Exception as e:
            print(f"Failed to send MQTT message: {e}")
            self.OLED.fill(0)
            self.OLED.text("Error", 0, 0, 1)
            self.OLED.text("Please try again", 0, 10, 1)
            self.OLED.show()
        
        while True:
            try:
                mqtt_client.wait_msg()
            except Exception as e:
                print(f"Error during wait: {e}")
                self.OLED.fill(0)
                self.OLED.text("Error", 0, 0, 1)
                self.OLED.text("Please try again", 0, 10, 1)
                self.OLED.show()
                self.HrvAnalysis.analysis_done = True
                time.sleep(1)
            self.HrvAnalysis.analysis_done = True
            break
        
            if self.rotary_encoder.fifo.has_data():
                event = self.rotary_encoder.fifo.get()
                if event == 2:
                    gc.collect()
                    break
                    state = 0
        
        self.HrvAnalysis.analysis_done = True
        
class History:
    def __init__(self, rotary_encoder):
        """
        TO-DO:
            - Save actual data from measurements. 	[]
            - Display the data.					 	[X]
            - Erase data history 					[]
            - Add more TO-DO's...					[]
        """
        
        self.rotary_encoder = rotary_encoder
        
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.OLED = SSD1306_I2C(128, 64, self.i2c)
        
        self.max_save_data = 25
        self.current_page:int = 0
        self.last_page:int = 0
        
        self.save_data:list = [] # create empty save_data variable.
        self.initialize_json() #check if savedata.json exist. if not create new .json file inside root directory.
            
    def clamp(self, i, min, max): 
        if i < min: 
            return max
        elif i > max: 
            return 0
        else: 
            return i 
        
    def initialize_json(self): 
        try:
            #IF savedata.json EXISTS => load it to our self.save_data!
            with open("savedata.json", "r") as f: #with open("PATH", "r=READ") as VARIABLE
                self.save_data = ujson.load(f) #loads json data and adds it to "save_data" -variable to keep it in sync for new entries. 
                print("savedata.json file found.")
        except:
            #IF savedata.json does NOT exist => create new savedata.json in root!
            new_data = ujson.dumps(self.save_data) #dump empty
            with open("savedata.json", "w") as f: #with open("PATH", "w=WRITE") as VARIABLE
                f.write(new_data)    
            print("Save data not found. Created new savedata.json file in to root directory.")
    
    def erase_history(self):
        self.save_data.clear()
        
        with open("savedata.json", "w") as f: #with open("PATH", "w=WRITE") as VARIABLE
            ujson.dump(self.save_data, f)
            print("Erased all history data.")
    
    #creates a array obj of dictionary and appends it to our save_data variable and adds it to our savedata.json file.
    def save_measurement(self, ppi, hr, rmssd, sdnn):
        measurement_time = time.localtime()
        date = f"{measurement_time[2]}/{measurement_time[1]}/{measurement_time[0]}"
        
        new_entry = {
            "Date" 	: date,
            "PPI" 	: ppi,
            "HR" 	: hr,
            "rmssd" : rmssd,
            "sdnn" 	: sdnn
            } 
        
        self.save_data.append(new_entry)
        
        #if maximum list dictionaries is reached, remove oldest data.
        if(len(self.save_data) > self.max_save_data):
            self.save_data.pop(0) #remove first data from json.

        with open("savedata.json", "w") as f: #with open("PATH", "w=WRITE") as VARIABLE
            ujson.dump(self.save_data, f)
    
        print(f"new .json data saved. slots: { len(self.save_data) }/{ self.max_save_data }")
        
    def display_history(self, i):
        self.OLED.text(str( self.save_data[i]["Date"] ) , 0, 12, 1)
        self.OLED.text(f"HR: {str( self.save_data[i]['HR'] )}" , 0, 20, 1)
        self.OLED.text(f"PPI: {str( self.save_data[i]['PPI'] )}" , 0, 28, 1)
        self.OLED.text(f"rmssd: {str( self.save_data[i]['rmssd'] )}" , 0, 36, 1)
        self.OLED.text(f"sdnn: {str( self.save_data[i]['sdnn'] )}" , 0, 44, 1)
        
    def draw(self, page):
        self.OLED.fill(0)  # turn off all leds
        
        if len(self.save_data) > 0:
            self.OLED.text("History (" + str(self.current_page+1) + "/" + str(len(self.save_data))  + ")", 0, 0, 1)
            self.display_history(page)
        else:
            self.OLED.text("History", 0, 0, 1)
            self.OLED.text("No data.", 36, 28, 1)
        
        self.OLED.text("Press to return", 0, 56, 1)
        self.OLED.show()  # Update the screen
        
    def execute(self):
        global state

        if self.rotary_encoder.fifo.has_data():
            event = self.rotary_encoder.fifo.get() # Get the first event in fifo
            
            if event == 1 or event == -1:  #check if is rotation
                self.last_page = self.current_page
                self.current_page += event
                
                self.current_page = self.clamp(
                    self.current_page,
                    0,
                    len(self.save_data)-1)
                
            if event == 2:
                self.current_page = 0
                state = 0
                
        self.draw(self.current_page)
        
rotary_encoder = RotaryEncoder()
history = History(rotary_encoder)
hrv = HrvAnalysis(rotary_encoder, history)
kubios = Kubios(rotary_encoder, history, hrv)
menu = MainMenu(rotary_encoder)
hr = HrMeasurement(rotary_encoder, SAMPLE_RATE)

timer_on = False
# Main loop


if __name__ == "__main__":
    while True:
        if state == 0:  # main menu
            if timer_on:
                tmr.deinit() # sample timer off
                timer_on = False
            menu.execute()
        elif state == 1: # HR measurement
            if not timer_on:
                tmr = Piotimer(mode=Piotimer.PERIODIC, freq=SAMPLE_RATE, callback=hr.read_adc) # sample timer on
                timer_on = True
            hr.execute()
        elif state == 2: # HRV analysis
            hrv.execute()
        elif state == 3: # Kubios
            kubios.execute()
        elif state == 4: # History
            history.execute()
