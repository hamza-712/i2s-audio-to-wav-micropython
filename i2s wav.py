from machine import Pin
from machine import I2S


#======= USER CONFIGURATION =======
RECORD_TIME_IN_SECONDS = 3
SAMPLE_RATE_IN_HZ = 16000
filename = 'mic.wav'
#======= USER CONFIGURATION =======

WAV_SAMPLE_SIZE_IN_BITS = 16
WAV_SAMPLE_SIZE_IN_BYTES = WAV_SAMPLE_SIZE_IN_BITS // 8
MIC_SAMPLE_BUFFER_SIZE_IN_BYTES = 4096
SDCARD_SAMPLE_BUFFER_SIZE_IN_BYTES = MIC_SAMPLE_BUFFER_SIZE_IN_BYTES // 2 # why divide by 2? only using 16-bits of 32-bit samples
NUM_SAMPLE_BYTES_TO_WRITE = int(RECORD_TIME_IN_SECONDS * SAMPLE_RATE_IN_HZ * WAV_SAMPLE_SIZE_IN_BYTES)
NUM_SAMPLES_IN_DMA_BUFFER = 256
NUM_CHANNELS = 1

#====== FUNCTIONS =========
def snip_16_mono(samples_in, samples_out):
    num_samples = len(samples_in) // 4
    for i in range(num_samples):
        samples_out[2*i] = samples_in[4*i + 2]
        samples_out[2*i + 1] = samples_in[4*i + 3]
            
    return num_samples * 2

def create_wav_header(sampleRate, bitsPerSample, num_channels, num_samples):
    datasize = int(num_samples * num_channels * bitsPerSample // 8)
    o = bytes("RIFF",'ascii')                                                   # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4,'little')                                   # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes("WAVE",'ascii')                                                  # (4byte) File type
    o += bytes("fmt ",'ascii')                                                  # (4byte) Format Chunk Marker
    o += (16).to_bytes(4,'little')                                              # (4byte) Length of above format data
    o += (1).to_bytes(2,'little')                                               # (2byte) Format type (1 - PCM)
    o += (num_channels).to_bytes(2,'little')                                    # (2byte)
    o += (sampleRate).to_bytes(4,'little')                                      # (4byte)
    o += (sampleRate * num_channels * bitsPerSample // 8).to_bytes(4,'little')  # (4byte)
    o += (num_channels * bitsPerSample // 8).to_bytes(2,'little')               # (2byte)
    o += (bitsPerSample).to_bytes(2,'little')                                   # (2byte)
    o += bytes("data",'ascii')                                                  # (4byte) Data Chunk Marker
    o += (datasize).to_bytes(4,'little')                                        # (4byte) Data size in bytes
    return o


################## MAIN #########################

#FOR ICS43434 only
PIN_I2S_LR = 3
Pin(PIN_I2S_LR, Pin.OUT, value=0)
###############
audio_in = I2S(1,
    sck=Pin(4), ws=Pin(5), sd=Pin(18),
    mode=I2S.RX,
    bits=32,
    format=I2S.MONO,
    rate=SAMPLE_RATE_IN_HZ,
    ibuf=20000,
               
)

wav = open(filename,'wb')

# create header for WAV file and write to SD card
wav_header = create_wav_header(
    SAMPLE_RATE_IN_HZ, 
    WAV_SAMPLE_SIZE_IN_BITS, 
    NUM_CHANNELS, 
    SAMPLE_RATE_IN_HZ * RECORD_TIME_IN_SECONDS
)
num_bytes_written = wav.write(wav_header)

# allocate sample arrays
#   memoryview used to reduce heap allocation in while loop
mic_samples = bytearray(MIC_SAMPLE_BUFFER_SIZE_IN_BYTES)
mic_samples_mv = memoryview(mic_samples)
wav_samples = bytearray(SDCARD_SAMPLE_BUFFER_SIZE_IN_BYTES)
wav_samples_mv = memoryview(wav_samples)

num_sample_bytes_written_to_wav = 0

print('Starting')
# read 32-bit samples from I2S microphone, snip upper 16-bits, write snipped samples to WAV file
while num_sample_bytes_written_to_wav < NUM_SAMPLE_BYTES_TO_WRITE:
        # try to read a block of samples from the I2S microphone
        # readinto() method returns 0 if no DMA buffer is full
        num_bytes_read_from_mic = audio_in.readinto(mic_samples_mv)
        if num_bytes_read_from_mic > 0:
            # snip upper 16-bits from each 32-bit microphone sample
            num_bytes_snipped = snip_16_mono(mic_samples_mv[:num_bytes_read_from_mic], wav_samples_mv)
            num_bytes_to_write = min(num_bytes_snipped, NUM_SAMPLE_BYTES_TO_WRITE - num_sample_bytes_written_to_wav)
            num_bytes_written = wav.write(wav_samples_mv[:num_bytes_to_write])
            num_sample_bytes_written_to_wav += num_bytes_written

wav.close()
audio_in.deinit()
print('Done')
print(f'{num_sample_bytes_written_to_wav} sample bytes written to WAV file')