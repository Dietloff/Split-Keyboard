import time
import board
import digitalio
import busio
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
import re 


# Initialize Keyboard
kbd = Keyboard(usb_hid.devices)


# Initialize UART with a shorter timeout to prevent hanging
try:
    uart = busio.UART(board.GP16, board.GP17, baudrate=9600, timeout=0.001, receiver_buffer_size=512)
    print("UART Initiali zed")
except Exception as e:
    print(f"UART Error: {e}")
    uart = None

# Matrix Setup - Right Side
row_pins = [board.GP2, board.GP3, board.GP4, board.GP5, board.GP6]
col_pins = [board.GP7, board.GP8, board.GP9, board.GP10, board.GP11, board.GP12, board.GP13]


rows = [digitalio.DigitalInOut(p) for p in row_pins]
for r in rows:
    r.direction = digitalio.Direction.OUTPUT
    r.value = True

cols = [digitalio.DigitalInOut(p) for p in col_pins]
for c in cols:
    c.direction = digitalio.Direction.INPUT
    c.pull = digitalio.Pull.UP

# Keymaps (Ortho 5x7)
right_map = [
    [None, Keycode.SIX, Keycode.SEVEN, Keycode.EIGHT, Keycode.NINE, Keycode.ZERO, Keycode.BACKSPACE],
    [None, Keycode.Y, Keycode.U, Keycode.I, Keycode.O, Keycode.P, Keycode.EQUALS],
    [Keycode.RIGHT_BRACKET, Keycode.H, Keycode.J, Keycode.K, Keycode.L, Keycode.SEMICOLON, Keycode.ENTER],
    [None, Keycode.N, Keycode.M, Keycode.COMMA, Keycode.UP_ARROW, Keycode.FORWARD_SLASH, Keycode.QUOTE ],
    [Keycode.SPACE, Keycode.PERIOD, Keycode.LEFT_ARROW, Keycode.DOWN_ARROW, None, Keycode.RIGHT_ARROW, None]
]

left_map = [
    [Keycode.ESCAPE, Keycode.ONE, Keycode.TWO, Keycode.THREE, Keycode.FOUR, Keycode.FIVE, None],
    [Keycode.TAB, Keycode.Q, Keycode.W, Keycode.E, Keycode.R, Keycode.T, None],
    [Keycode.CAPS_LOCK, Keycode.A, Keycode.S, Keycode.D, Keycode.F, Keycode.G, Keycode.LEFT_BRACKET],
    [Keycode.LEFT_SHIFT, Keycode.Z, Keycode.X, Keycode.C, Keycode.V, Keycode.B, None],
    [None, Keycode.LEFT_CONTROL, None, Keycode.ALT, Keycode.GUI, Keycode.MINUS, Keycode.SPACE]
]

last_state_right = [[False for _ in range(7)] for _ in range(5)]

print("Right Master Loop Starting...")

# --- Add this above your 'while True' loop ---
left_buffer = ""

# Track both sides to be safe
pressed_keys_left = set()
pressed_keys_right = set()
last_msg_id = -1
while True:
    # 1. SCAN LOCAL (RIGHT) KEYS
    for r_idx, r_pin in enumerate(rows):
        r_pin.value = False
        for c_idx, c_pin in enumerate(cols):
            is_pressed = not c_pin.value
            if is_pressed != last_state_right[r_idx][c_idx]:
                key = right_map[r_idx][c_idx]
                if key:
                    if is_pressed:
                        kbd.press(key)
                        pressed_keys_right.add((r_idx, c_idx))
                    else:
                        if (r_idx, c_idx) in pressed_keys_right:
                            kbd.release(key)
                            pressed_keys_right.remove((r_idx, c_idx))
                last_state_right[r_idx][c_idx] = is_pressed
        r_pin.value = True

    # 2. RECEIVE SLAVE (LEFT) KEYS
    if uart and uart.in_waiting > 0:
        try:
            chunk = uart.read(uart.in_waiting).decode()
            left_buffer += chunk
            
            while "[" in left_buffer and "]" in left_buffer:
                start = left_buffer.find("[")
                end = left_buffer.find("]")
                if end < start:
                    left_buffer = left_buffer[end + 1:]
                    continue
                
                raw_packet = left_buffer[start + 1 : end]
                packet = "".join(raw_packet.split())
                
                if len(packet) >= 5 and "," in packet: # Increased length check for ID
                    try:
                        action = packet[0] 
                        parts = packet[1:].split(",")
                        
                        # Extract all three values
                        r = int(parts[0])
                        c = int(parts[1])
                        m_id = int(parts[2]) # This is the Counter ID
                        
                        # ONLY proceed if the message ID is different from the last one
                        if m_id != last_msg_id:
                            last_msg_id = m_id
                            
                            if r < len(left_map) and c < len(left_map[0]):
                                key = left_map[r][c]
                                key_id = (r, c)
                                
                                if key:
                                    if action == 'P':
                                        kbd.press(key)
                                        pressed_keys_left.add(key_id)
                                    elif action == 'R':
                                        if key_id in pressed_keys_left:
                                            kbd.release(key)
                                            pressed_keys_left.remove(key_id)
                                        else:
                                            # Sync Fix tap
                                            kbd.press(key)
                                            time.sleep(0.005)
                                            kbd.release(key)
                        else:
                            # This was a redundant packet, we ignore it!
                            pass 
                                
                    except Exception as e:
                        # This catches errors if parts[2] doesn't exist yet
                        pass 
                
                left_buffer = left_buffer[end + 1:]

            if len(left_buffer) > 100:
                left_buffer = ""

        except Exception as e:
            left_buffer = ""

    time.sleep(0.001)
