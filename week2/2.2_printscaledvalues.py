from filefifo import Filefifo
import time

# Function to read data and find min and max values
def read_data_and_find_min_max(data_fifo, num_samples):
    signal = []
    for _ in range(num_samples):
        try:
            signal.append(data_fifo.get())
        except Exception:
            break  # End of file reached
    return signal

# Function to scale the signal to the range 0-100
def scale_signal(signal, min_val, max_val):
    scaled = [(value - min_val) / (max_val - min_val) * 100 for value in signal]
    return scaled

# Main program
def main():
    filename = 'capture_250Hz_01.txt'  # Change this to the desired file
    sampling_rate = 250  # Samples per second (250 Hz)
    seconds_to_read = 2  # Read 2 seconds of data

    # Create Filefifo instance to read data from the file
    data_fifo = Filefifo(10, name=filename)

    # Read two seconds of data
    num_samples = seconds_to_read * sampling_rate
    signal = read_data_and_find_min_max(data_fifo, num_samples)

    # Find min and max values
    min_val = min(signal)
    max_val = max(signal)
    print("Minimum Value:", min_val)
    print("Maximum Value:", max_val)

    # Scale the data to the range 0-100
    scaled_signal = scale_signal(signal, min_val, max_val)

    # Print scaled values
    for value in scaled_signal:
        print(value)

    # Read 10 seconds of data for plotting
    seconds_to_plot = 10
    data_fifo = Filefifo(10, name=filename)  # Re-initialize to read from the beginning
    plot_signal = read_data_and_find_min_max(data_fifo, seconds_to_plot * sampling_rate)
    
    # Scale the plot data using the same min and max
    scaled_plot_signal = scale_signal(plot_signal, min_val, max_val)

    # Print scaled plot values (optional)
    for value in scaled_plot_signal:
        print(value)

# Run the program
main()
