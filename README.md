# Split Mechanical Keyboard — Hardware and Firmware

A hand-wired split ergonomic keyboard: custom laser-cut steel case, point-to-point wired switch
matrix, and firmware written from scratch in CircuitPython on two RP2040 microcontrollers.

No PCB was fabricated for this build — every switch in both halves is wired by hand.

<img width="1280" height="960" alt="TopView" src="https://github.com/user-attachments/assets/61a613c2-79dd-40fc-b57c-23af29321998" />
<img width="1280" height="960" alt="BottomView" src="https://github.com/user-attachments/assets/00fcb779-b77f-452f-952e-99e565c634bb" />

## What's interesting here

The keyboard works like any other. The part worth reading is **the link between the two halves.**

The halves talk over a single TRRS cable, and that cable turned out to be a genuinely hostile
channel: packets arrived fragmented across reads, and electrical noise corrupted bytes in
transit. A naive "send the keypress, hope it arrives" protocol drops keys and — worse — strands
the receiver holding a key down forever when a release packet goes missing.

Most of the design effort went into a protocol that degrades gracefully instead of failing.

## Hardware

| | |
|---|---|
| Microcontrollers | 2 × Raspberry Pi Pico (RP2040), one per half |
| Runtime | CircuitPython |
| Matrix | 5 rows × 7 columns per half, 60 keys populated |
| Wiring | Hand-soldered point to point, no fabricated PCB |
| Case | Custom laser-cut steel |
| Interconnect | TRRS cable, UART on `GP16` (TX) / `GP17` (RX), 9600 baud |
| Switches | Gateron Browns
| Layout | Ortholinear |

## Repository layout

```
firmware/
  right-master/code.py    the master half: scans its own matrix, receives the left half, owns USB
  left-slave/code.py      the slave half: scans its matrix and transmits key events over UART
```

Copy the contents of the relevant folder onto each half's `CIRCUITPY` drive.

**Not in this repository:**

- `lib/` — the CircuitPython libraries (`adafruit_hid`). Install these from the
  [Adafruit CircuitPython bundle](https://circuitpython.org/libraries) matching your
  CircuitPython version.
- The KMK/Pog files that live alongside `code.py` on the physical drives. Those are dead
  leftovers from an earlier attempt (see below) and are not used — CircuitPython runs `code.py`.

## How it works

### Roles

The **right half is the master**. It scans its own matrix, receives key events from the left half
over UART, and is the only half connected to the host over USB. The **left half is a slave**: it
scans its matrix and transmits events. The host sees one keyboard.

### Matrix scanning

Rows are outputs held high, columns are inputs with pull-ups. Each scan pass drives one row low
at a time and reads the columns; a pressed key pulls its column low. The scan compares against a
stored previous state and acts only on transitions, so a held key produces exactly one press and
one release. USB HID reports go out through `adafruit_hid`.

### The split protocol

Key events are sent as bracket-framed ASCII packets:

```
[P3,4,127]
 │ │ │  └── sequence ID
 │ │ └───── column
 │ └─────── row
 └───────── action: P = press, R = release
```

The receiver accumulates incoming bytes into a buffer and extracts complete `[...]` frames, which
means a packet split across several UART reads is reassembled rather than lost. Everything else
is about surviving a bad cable:

| Failure | Handling |
|---|---|
| Packet split across reads | Buffered and reassembled once the closing `]` arrives |
| Corrupted or partial frame | A `]` seen before a `[` discards the leading garbage and resynchronises |
| Whitespace injected mid-packet | Stripped before parsing |
| Packet lost in transit | Each event is transmitted redundantly |
| Duplicate from that redundancy | Rejected by sequence ID — a repeated ID is ignored |
| Malformed field | Parse failure drops that frame; the next valid one recovers |
| Buffer fills with garbage | Flushed past 100 characters rather than growing unbounded |
| **Press lost, release arrives** | **A release with no matching press emits a full tap instead** |

That last row is the one I'd point at. If a press packet is lost, the receiver later gets a
release for a key it never registered. Ignoring it silently swallows the keystroke; treating it
as a release sends a HID release for a key that was never pressed. Emitting a press-release pair
delivers the character the user actually typed, which is what they wanted in the first place.

## Why not KMK or QMK?

The build started on [Pog](https://github.com/JanLunge/pog), a configurator over the
[KMK](https://github.com/KMKfw/kmk_firmware) firmware framework. It worked, but the split
communication was unreliable in this build — which, given the hand-wired matrix and the noise on
the TRRS line, may well have been my hardware rather than KMK's fault.

Rather than debug someone else's stack through a configuration layer, I rewrote the firmware
directly against `digitalio`, `busio` and `adafruit_hid`. That made the failure modes visible
and gave me somewhere to put the protocol work above.

If you want a split keyboard that just works, use KMK or QMK. This exists because I wanted to
understand the whole path from switch contact to HID report.

## Known limitations

Being honest about what this does not do:

- **No debouncing.** Transitions are detected against the previous scan state, and in practice
  the scan interval has been sufficient for the switches in this build. It is not a substitute
  for real debouncing and would need addressing with chattier switches.
- **No layers.** One keymap per half, fixed at flash time. There is no layer state, so no
  function layer, no modifiers-as-layers.
- **Duplicate rejection compares against the last ID only.** Consecutive duplicates are caught,
  which is what the redundant transmission scheme produces. Out-of-order or delayed duplicates
  are not.
- **9600 baud** is conservative for this application, chosen for margin on a noisy line.
- **Sequence IDs are shared across all keys**, not tracked per key.
- **Master-only USB.** Plugging the slave half in on its own does nothing useful.

## License

MIT — see [LICENSE](LICENSE).
