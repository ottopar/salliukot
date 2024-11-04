from filefifo import Filefifo

# Function to find peaks using slope inspection
def find_peaks(signal):
    peaks_indices = []
    for i in range(1, len(signal) - 1):
        # Check if the current point is a peak
        if signal[i - 1] < signal[i] > signal[i + 1]:
            peaks_indices.append(i)
    return peaks_indices

# Function to calculate peak-to-peak intervals
def calculate_intervals(peaks_indices, sampling_rate):
    intervals_samples = []
    intervals_seconds = []
    
    for i in range(1, len(peaks_indices)):
        interval_samples = peaks_indices[i] - peaks_indices[i - 1]
        intervals_samples.append(interval_samples)
        intervals_seconds.append(interval_samples / sampling_rate)
    
    return intervals_samples, intervals_seconds

# Main program
def main():
    filename = 'capture_250Hz_02.txt'  # Change this to other filenames as needed
    sampling_rate = 250  # Samples per second (250 Hz)

    # Create Filefifo instance to read data from the file
    data_fifo = Filefifo(10, name=filename)

    # Read the entire file data into a list
    signal = []
    while True:
        try:
            signal.append(data_fifo.get())
        except Exception:
            break  # End of file reached

    # Find peaks in the signal
    peaks_indices = find_peaks(signal)

    # Calculate peak-to-peak intervals
    intervals_samples, intervals_seconds = calculate_intervals(peaks_indices, sampling_rate)

    # Calculate frequency from the intervals
    if len(intervals_seconds) > 0:
        average_interval = sum(intervals_seconds) / len(intervals_seconds)
        signal_frequency = 1 / average_interval
    else:
        signal_frequency = 0

    # Print results
    print("First Peaks:", peaks_indices[:3])  # Show the first three peaks
    if len(intervals_samples) > 0:
        print("Peak-to-Peak Intervals (samples):", intervals_samples[:3])
        print("Peak-to-Peak Intervals (seconds):", intervals_seconds[:3])
    print("Calculated Frequency of the Signal (Hz):", signal_frequency)

# Run the program
main()
