#LIBRARYS
from machine import Pin, PWM
from fifo import Fifo
import time

class RotaryKnob:
    def __init__(self, rotarybtn_pin, a_pin, b_pin, led_pin, frequency):
        self.sw = Pin(rotarybtn_pin, mode = Pin.IN, pull = Pin.PULL_UP)
        self.a = Pin(a_pin, mode = Pin.IN, pull = Pin.PULL_UP)
        self.b = Pin(b_pin, mode = Pin.IN, pull = Pin.PULL_UP)

        #LED
        self.led_pwm = PWM(Pin(led_pin, Pin.OUT))
        self.led_pwm.freq(frequency)
        self.brightness = 0
        self.is_led_on:bool = True

        #FIFO
        self.fifo = Fifo(100, typecode = 'i')
        
        #INTERRUPTS
        self.a.irq(handler = self.on_rotary_rotated, trigger = Pin.IRQ_RISING, hard = True)
        self.sw.irq(handler = self.on_rotary_pressed, trigger = Pin.IRQ_RISING, hard = True)
        
        #CANCEL BUTTON BOUNCE
        self.can_press:bool = True
        self.last_press = 0

    #ENCODER BUTTON PRESS INTERUPT (ON RELEASE)
    def on_rotary_pressed(self, pin):
         if self.sw():
                self.fifo.put(2) #2 = ROTARY PRESS
    #ENCODER ROTATION (CHECK ONLY INNER RING)
    def on_rotary_rotated(self, pin):
        if self.b():
            self.fifo.put(-1)
        else:
            self.fifo.put(1)
    #MAIN CODE
    def execute(self):
        if self.fifo.has_data(): #IF self.fifo has any values
            value = self.fifo.get()
            
            if(value == 2 and self.can_press):
                self.brightness = 0 #turn off the light what ever happens
                self.last_press = time.ticks_ms() #this sets the last pressed tick to current time tick in milliseconds to prevent button bounce
                self.can_press = False
                
                if(self.is_led_on):
                    self.is_led_on = False
                    print("Led off.")
                else:
                    self.is_led_on = True
                    print("Led on.")
            
            elif(self.is_led_on):
                self.brightness += value * 1500
                
        value = self.clamp(self.brightness, 0, 65535)
        self.brightness = value
        self.led_pwm.duty_u16(value)
        self.bounce_filter()
    #CLAMP FUNCTION (CLAMP GIVEN VALUE BETWEEN TWO GIVEN VALUE)
    def clamp(self, value, minimum, maximum):
        if(value > maximum):
            value = maximum
        elif(value < minimum):
            value = minimum
        return value
    #ADD DELAY BETWEEN ENCODERS BUTTON PRESS
    def bounce_filter(self):
        if(time.ticks_ms() - self.last_press > 250 and not self.can_press):
            self.can_press = True
#ASSIGN ONE ROTARY    
knob1 = RotaryKnob(12, 10, 11, 22, 1000) #(ROTARY_BTN_PIN, OUTER_ENCODER, INNER_ENCODER, FREQUENCY)
#MAIN LOOP
while True:
    knob1.execute() #RUN CODE
