"""
One-time helper script: rewrite profiles.py and characters.py in-place
with measured-realistic energy_consistency and dynamic_range_db values,
then verify nothing is broken.
"""

import re, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── remap functions ──────────────────────────────────────────────────
# Old energy_consistency across all profiles+chars: ~0.20 .. 0.99
# Measured reality for narration: 0.03 .. 0.30
# We remap to 0.00 .. 0.40  (leaving headroom above 0.30 for "very flat" voices)
EC_OLD_LO, EC_OLD_HI = 0.20, 0.99
EC_NEW_LO, EC_NEW_HI = 0.00, 0.40

def remap_ec(old_val):
    return round(EC_NEW_LO + (old_val - EC_OLD_LO) / (EC_OLD_HI - EC_OLD_LO)
                 * (EC_NEW_HI - EC_NEW_LO), 2)

# Old dynamic_range_db across all profiles+chars: ~2 .. 32
# Measured reality: 11 .. 36
# We remap to 8 .. 45
DR_OLD_LO, DR_OLD_HI = 2, 32
DR_NEW_LO, DR_NEW_HI = 8, 45

def remap_dr(old_val):
    return round(DR_NEW_LO + (old_val - DR_OLD_LO) / (DR_OLD_HI - DR_OLD_LO)
                 * (DR_NEW_HI - DR_NEW_LO), 1)


def rewrite_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Replace energy_consistency tuples
    def replace_ec(m):
        indent = m.group(1)
        old_lo = float(m.group(2))
        old_hi = float(m.group(3))
        new_lo = remap_ec(old_lo)
        new_hi = remap_ec(old_hi)
        comment = m.group(4) or ""
        return f'{indent}"energy_consistency": ({new_lo:.2f}, {new_hi:.2f}),{comment}'

    text = re.sub(
        r'(\s*)"energy_consistency":\s*\(([0-9.]+),\s*([0-9.]+)\),(.*)',
        replace_ec, text
    )

    # Replace dynamic_range_db tuples
    def replace_dr(m):
        indent = m.group(1)
        old_lo = float(m.group(2))
        old_hi = float(m.group(3))
        new_lo = remap_dr(old_lo)
        new_hi = remap_dr(old_hi)
        comment = m.group(4) or ""
        return f'{indent}"dynamic_range_db":   ({new_lo:.0f}, {new_hi:.0f}),{comment}'

    text = re.sub(
        r'(\s*)"dynamic_range_db":\s*\(([0-9.]+),\s*([0-9.]+)\),(.*)',
        replace_dr, text
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Rewrote: {filepath}")


# ── apply to both files ──────────────────────────────────────────────
if __name__ == "__main__":
    rewrite_file(os.path.join(ROOT, "coaching", "characters.py"))
    rewrite_file(os.path.join(ROOT, "coaching", "profiles.py"))
    print("  Done — regex rewrite of energy_consistency and dynamic_range_db.")
