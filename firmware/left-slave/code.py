import time
import board
import digitalio
import busio

# Setup UART (TX=GP0, RX=GP1)
uart = busio.UART(board.GP16, board.GP17, baudrate=9600, timeout=0.001)
# Matrix Setup - Left Side
row_pins = [board.GP2, board.GP3, board.GP4, board.GP5, board.GP6]
# Reversed column order for the left hand wiring
col_pins = [board.GP13, board.GP12, board.GP11, board.GP10, board.GP9, board.GP8, board.GP7]

rows = [digitalio.DigitalInOut(p) for p in row_pins]
for r in rows:
    r.direction = digitalio.Direction.OUTPUT
    r.value = True

cols = [digitalio.DigitalInOut(p) for p in col_pins]
for c in cols:
    c.direction = digitalio.Direction.INPUT
    c.pull = digitalio.Pull.UP

last_state = [[False for _ in range(7)] for _ in range(5)]

# Slave Loop (Left Side)
# --- SLAVE (LEFT) SIDE ---
message_counter = 0

while True:
    for r_idx, r_pin in enumerate(rows):
        r_pin.value = False
        for c_idx, c_pin in enumerate(cols):
            is_pressed = not c_pin.value
            if is_pressed != last_state[r_idx][c_idx]:
                
                # Increment counter (0-255)
                message_counter = (message_counter + 1) % 256
                
                # New format: [Action Row, Col, ID]
                msg = f"[{'P' if is_pressed else 'R'}{r_idx},{c_idx},{message_counter}]\n"
                
                # SEND TWICE for redundancy
                uart.write(msg.encode())
                uart.write(msg.encode())
                
                last_state[r_idx][c_idx] = is_pressed
        r_pin.value = True
    time.sleep(0.005)
