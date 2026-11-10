"""Application wire codec compatible with firmware/lib/Energy/Protocol.h.
This does NOT simulate ESP-NOW radio or MAC delivery.
"""
from dataclasses import dataclass
import struct

FORMATS = {1:'<iiiQB', 2:'<IBI', 3:'<IBI', 4:'<BII', 5:'<H'}

def crc(data):
    c = 0xffff
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xa001 if c & 1 else c >> 1
    return c

@dataclass(frozen=True)
class Frame:
    type: int
    device: int
    sequence: int
    uptime: int
    values: tuple

    def encode(self):
        if self.type not in FORMATS or not 1 <= self.device <= 65535:
            raise ValueError('Invalid type/device')
        if self.type == 1 and self.values[-1] not in (0,1,2):
            raise ValueError('Invalid sensor status')
        if self.type == 4 and self.values[0] not in (0,1,2):
            raise ValueError('Invalid sensor status')
        if self.type == 3 and self.values[1] not in (0,1,2,3):
            raise ValueError('Invalid ACK code')
        payload = struct.pack(FORMATS[self.type], *self.values)
        data = struct.pack('<BBHIHI', 1, self.type, self.device, self.sequence, len(payload), self.uptime) + payload
        return data + struct.pack('<H', crc(data))

    @classmethod
    def decode(cls, data):
        if len(data) < 16 or len(data) > 48:
            raise ValueError('Invalid frame length')
        version, kind, device, sequence, length, uptime = struct.unpack('<BBHIHI', data[:14])
        if version != 1 or kind not in FORMATS or length != struct.calcsize(FORMATS[kind]) or len(data) != 16 + length:
            raise ValueError('Invalid frame header')
        if crc(data[:-2]) != struct.unpack('<H',data[-2:])[0]:
            raise ValueError('CRC mismatch')
        frame = cls(kind, device, sequence, uptime, struct.unpack(FORMATS[kind], data[14:-2]))
        frame.encode()  # Same semantic checks in both directions.
        return frame

class Sequence:
    def __init__(self):
        self.last = None

    def accept(self, sequence):
        delta = None if self.last is None else (sequence-self.last) & 0xffffffff
        if delta is not None and not 0 < delta < 0x80000000:
            return False
        self.last = sequence
        return True

    def reset(self):
        self.last = None
