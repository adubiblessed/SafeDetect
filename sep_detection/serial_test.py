import time
try:
    import serial
except Exception as e:
    print('PySerial not installed or import failed:', e)
    raise

port = input('Enter serial port to test (e.g. COM4): ').strip()
if not port:
    print('No port provided; exiting.')
    raise SystemExit(1)

raw = input('Enter baud rate [9600]: ').strip()
baud = int(raw) if raw else 9600

print(f'Testing open on {port} at {baud} baud...')
try:
    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(2)
    print('Port opened successfully. Attempting write...')
    ser.write(b'PING\n')
    ser.flush()
    print('Write succeeded.')
    ser.close()
    print('Closed port.')
except Exception as e:
    print('Serial test failed:', e)
    raise
