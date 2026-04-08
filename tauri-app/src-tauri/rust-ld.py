"""
rust-ld.py — Linker wrapper for Voxarah Tauri build.

Rust's GNU toolchain emits response files with GNU ld escaping (backslash-space
for paths with spaces). We read that file, inject the correct MinGW CRT startup
object, add -L for the self-contained libs, and pass everything to ld.lld.
"""
import sys, subprocess, os, tempfile, re

SC      = r"C:\Users\Joshu\.rustup\toolchains\stable-x86_64-pc-windows-gnu\lib\rustlib\x86_64-pc-windows-gnu\lib\self-contained"
LLD     = r"C:\Program Files\LLVM\bin\ld.lld.exe"
CRT2    = SC + r"\crt2.o"
DLLCRT2 = SC + r"\dllcrt2.o"

# Flags that lld GNU flavor doesn't recognise in this version
_STRIP = {"--nxcompat"}


def read_rsp_lines(path):
    """Read a GNU ld response file (one arg per line, backslash escapes spaces)."""
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln:
            # Unescape backslash-space → actual space
            ln = ln.replace("\\ ", " ")
            lines.append(ln)
    return lines


def write_rsp(args):
    """Write a temp response file, quoting args that contain spaces."""
    fd, path = tempfile.mkstemp(suffix=".rsp", prefix="vld-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for a in args:
            if " " in a:
                fh.write('"' + a + '"\n')
            else:
                fh.write(a + "\n")
    return path


def main():
    raw = sys.argv[1:]

    # Expand a single @response-file if that's how Rust passed args
    if len(raw) == 1 and raw[0].startswith("@"):
        args = read_rsp_lines(raw[0][1:])
    else:
        args = list(raw)

    # Strip unsupported flags
    args = [a for a in args if a not in _STRIP]

    # Select CRT object based on crate type
    is_dll = any(a in ("--dll", "-shared", "--shared") for a in args)
    crt    = DLLCRT2 if is_dll else CRT2

    # Inject CRT before the first user object file (ends with .o, not a flag)
    if not any(crt.lower() in a.lower() for a in args):
        for i, a in enumerate(args):
            if a.endswith(".o") and not a.startswith("-"):
                args.insert(i, crt)
                break

    # Prepend self-contained library search path
    all_args = [f"-L{SC}"] + args

    # Write new response file and link
    rsp = write_rsp(all_args)
    try:
        result = subprocess.run([LLD, f"@{rsp}"])
        return result.returncode
    finally:
        try:
            os.unlink(rsp)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
