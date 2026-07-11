#!/usr/bin/env python3
"""
decrypt_chiplist.py - Standalone decryptor for NeoProgrammer's chiplist.dat

Reverse-engineered from NeoProgrammer.exe (v2.2.0.10) using IDA Pro
(static analysis + live-memory verification via debugger). No IDA or the
original .exe is required to run this script - pure Python 3 stdlib only.

Algorithm (fully verified byte-for-byte against the real decrypted output):

  1. RC4-keystream is seeded with key = SHA1(PASSPHRASE), where PASSPHRASE
     is a fixed 21-byte string hardcoded/derived inside the exe:
         b'Eoa:S,$nf"LExge/L"N[3'
     (This passphrase itself is produced at runtime by RC4-decrypting an
     embedded blob using SHA1("chiplist.dat") as a bootstrap key - but
     since the result is a constant, we can hardcode it directly here.)

  2. The RC4 keystream is applied to the raw chiplist.dat bytes in 8192-byte
     chunks. IMPORTANT: this is a non-standard variant - the RC4 S-box
     (permutation table) persists/continues mutating across chunk
     boundaries, but the running (i, j) index counters are RESET to 0 at
     the start of EVERY 8192-byte chunk (this matches DCPcrypt2's
     TDCP_cipher.DecryptStream, which calls Decrypt() once per buffered
     chunk, and TDCP_rc4.Decrypt() declares i/j as local variables that
     reinitialize to 0 on every call).

  3. The resulting 17885-byte(*) buffer starts with an 8-byte little-endian
     uint64 header holding the uncompressed XML size, followed by a
     standard zlib-wrapped (RFC 1950, header bytes 0x78 0x9C) DEFLATE
     stream (compression level 6) containing the plaintext chiplist XML.

     (*) size depends on the specific chiplist.dat being decrypted.

Usage:
    python decrypt_chiplist.py chiplist.dat [output.xml]

If output.xml is omitted, it defaults to chiplist.dat with a .xml extension.
"""

import hashlib
import struct
import sys
import zlib

PASSPHRASE = b'Eoa:S,$nf"LExge/L"N[3'
CHUNK_SIZE = 8192


def rc4_chunked_decrypt(data: bytes, key: bytes, chunk_size: int = CHUNK_SIZE) -> bytes:
    """RC4 with a persistent S-box but i/j counters reset every chunk_size bytes."""
    # KSA (standard RC4 key scheduling, done once)
    S = list(range(256))
    j = 0
    klen = len(key)
    for i in range(256):
        j = (j + S[i] + key[i % klen]) % 256
        S[i], S[j] = S[j], S[i]

    out = bytearray(len(data))
    pos = 0
    while pos < len(data):
        chunk = data[pos:pos + chunk_size]
        i = j = 0  # reset per chunk; S continues from previous chunk
        for n, b in enumerate(chunk):
            i = (i + 1) & 0xFF
            j = (j + S[i]) & 0xFF
            S[i], S[j] = S[j], S[i]
            k = S[(S[i] + S[j]) & 0xFF]
            out[pos + n] = b ^ k
        pos += chunk_size
    return bytes(out)


def decrypt_chiplist_dat(raw_bytes: bytes) -> bytes:
    """Decrypt raw chiplist.dat bytes and return the plaintext XML bytes."""
    key = hashlib.sha1(PASSPHRASE).digest()
    decrypted = rc4_chunked_decrypt(raw_bytes, key)

    if len(decrypted) < 8:
        raise ValueError("File too short to contain the 8-byte size header")

    uncompressed_size = struct.unpack("<Q", decrypted[:8])[0]
    payload = decrypted[8:]

    xml = zlib.decompress(payload)

    if len(xml) != uncompressed_size:
        raise ValueError(
            "Decompressed size mismatch (got %d, header says %d) - "
            "wrong key/passphrase or corrupted/different file format?"
            % (len(xml), uncompressed_size)
        )
    return xml


def main(argv):
    if len(argv) < 2:
        print("Usage: python decrypt_chiplist.py <chiplist.dat> [output.xml]")
        return 1

    in_path = argv[1]
    out_path = argv[2] if len(argv) > 2 else (
        in_path[:-4] + ".xml" if in_path.lower().endswith(".dat") else in_path + ".xml"
    )

    with open(in_path, "rb") as f:
        raw_bytes = f.read()

    try:
        xml = decrypt_chiplist_dat(raw_bytes)
    except Exception as e:
        print("Decryption failed: %s" % e)
        return 1

    with open(out_path, "wb") as f:
        f.write(xml)

    print("OK: decrypted %d bytes -> %d bytes of XML" % (len(raw_bytes), len(xml)))
    print("Written to: %s" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
