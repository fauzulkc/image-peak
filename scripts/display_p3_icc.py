"""Build ICC v4 matrix/TRC profiles with the sRGB transfer curve and D65 white: Display P3 and sRGB.

Byte-for-byte deterministic (a fixed header date), so rebuilding an image never changes its file.
Pillow's built-in sRGB profile stamps the current time, which made every rebuild a new file.

Usage: python display_p3_icc.py <out.icc>   (importable: display_p3_profile(), srgb_profile() -> bytes)
"""
import struct, sys
import numpy as np

P3_TO_XYZ_D65 = np.array([[0.4865709, 0.2656677, 0.1982173], [0.2289746, 0.6917385, 0.0792869], [0.0000000, 0.0451134, 1.0439444]])
SRGB_TO_XYZ_D65 = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
D65 = np.array([0.95047, 1.0, 1.08883])
D50 = np.array([0.9642, 1.0, 0.8249])
BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])


def s15_fixed16(value):
    return struct.pack(">i", int(round(value * 65536)))


def xyz_tag(xyz):
    return b"XYZ " + b"\0" * 4 + b"".join(s15_fixed16(v) for v in xyz)


def mluc_tag(text):
    encoded = text.encode("utf-16-be")
    return b"mluc" + b"\0" * 4 + struct.pack(">II", 1, 12) + b"enUS" + struct.pack(">II", len(encoded), 28) + encoded


def display_p3_profile():
    return matrix_profile("Display P3", P3_TO_XYZ_D65)


def srgb_profile():
    return matrix_profile("sRGB", SRGB_TO_XYZ_D65)


def matrix_profile(description, rgb_to_xyz_d65):
    cone_scale = np.diag((BRADFORD @ D50) / (BRADFORD @ D65))
    chromatic_adaptation = np.linalg.inv(BRADFORD) @ cone_scale @ BRADFORD
    colorants = chromatic_adaptation @ rgb_to_xyz_d65  # columns: red, green, blue in D50 PCS
    # sRGB curve as parametric type 3: Y = (aX + b)^g for X >= d, else cX
    srgb_curve = b"para" + b"\0" * 4 + struct.pack(">HH", 3, 0) + b"".join(
        s15_fixed16(v) for v in (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045))
    tags = [
        (b"desc", mluc_tag(description)),
        (b"cprt", mluc_tag("No copyright, use freely")),
        (b"wtpt", xyz_tag(D50)),
        (b"chad", b"sf32" + b"\0" * 4 + b"".join(s15_fixed16(v) for v in chromatic_adaptation.ravel())),
        (b"rXYZ", xyz_tag(colorants[:, 0])),
        (b"gXYZ", xyz_tag(colorants[:, 1])),
        (b"bXYZ", xyz_tag(colorants[:, 2])),
        (b"rTRC", srgb_curve), (b"gTRC", srgb_curve), (b"bTRC", srgb_curve),
    ]
    table_size = 4 + 12 * len(tags)
    offset = 128 + table_size
    table, data, seen = struct.pack(">I", len(tags)), b"", {}
    for signature, body in tags:
        if body not in seen:  # the three TRC tags share one curve
            seen[body] = offset + len(data)
            data += body + b"\0" * (-len(body) % 4)
        table += signature + struct.pack(">II", seen[body], len(body))
    size = 128 + table_size + len(data)
    header = (struct.pack(">I", size) + b"\0" * 4 + struct.pack(">I", 0x04300000) + b"mntr" + b"RGB " + b"XYZ "
              + struct.pack(">6H", 2026, 1, 1, 0, 0, 0) + b"acsp" + b"\0" * 4 + struct.pack(">I", 0) + b"\0" * 8
              + b"\0" * 8 + struct.pack(">I", 0) + b"".join(s15_fixed16(v) for v in D50) + b"\0" * 4 + b"\0" * 16 + b"\0" * 28)
    assert len(header) == 128
    return header + table + data


if __name__ == "__main__":
    open(sys.argv[1], "wb").write(display_p3_profile())
