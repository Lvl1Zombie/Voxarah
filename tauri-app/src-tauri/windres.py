"""
windres.py — Shim for tauri-winres when no MinGW windres is available.

Uses llvm-rc.exe to compile the .rc resource file, then packages it into
a GNU ar archive that the linker can consume. Version info won't appear
in Explorer's file properties, but the build succeeds and the app runs.

Called by tauri-winres (via build.rs) as:
    windres [--target pe-x86-64] [-I include...] input.rc output.a
"""
import sys, subprocess, os, tempfile, struct
from pathlib import Path

LLVM_BIN  = r"C:\Program Files\LLVM\bin"
LLVM_RC   = os.path.join(LLVM_BIN, "llvm-rc.exe")
LLVM_AR   = os.path.join(LLVM_BIN, "llvm-ar.exe")


def parse_args(argv):
    """
    Extract rc_input, output_archive, and include dirs from a windres arg list.

    embed-resource calls windres like:
        windres --input foo.rc --output-format=coff --target pe-x86-64
                -c 65001 --output libresource.a --include-dir outdir
    """
    rc_file  = None
    out_file = None
    includes = []
    i = 0
    while i < len(argv):
        a = argv[i]
        # --input / -i
        if a in ("--input", "-i") and i + 1 < len(argv):
            rc_file = argv[i + 1]; i += 2
        elif a.startswith("--input="):
            rc_file = a.split("=", 1)[1]; i += 1
        # --output / -o
        elif a in ("--output", "-o") and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a.startswith("--output="):
            out_file = a.split("=", 1)[1]; i += 1
        # -I / --include-dir
        elif a in ("-I", "--include-dir") and i + 1 < len(argv):
            includes.append(argv[i + 1]); i += 2
        elif a.startswith("-I") and len(a) > 2:
            includes.append(a[2:]); i += 1
        elif a.startswith("--include-dir="):
            includes.append(a.split("=", 1)[1]); i += 1
        # Skip all other flags (--output-format, --target, -c, etc.)
        else:
            i += 1

    return rc_file, out_file, includes


def write_empty_archive(path):
    """Write a valid (empty) GNU ar archive."""
    with open(path, "wb") as f:
        f.write(b"!<arch>\n")


def compile_rc(rc_file, includes):
    """Use llvm-rc to compile rc_file → .res, return path to .res or None."""
    res_fd, res_path = tempfile.mkstemp(suffix=".res")
    os.close(res_fd)
    cmd = [LLVM_RC]
    for inc in includes:
        cmd += ["/I", inc]
    cmd += ["/FO", res_path, rc_file]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode(errors="replace"))
        os.unlink(res_path)
        return None
    return res_path


def res_to_coff_obj(res_path):
    """
    Wrap a .res binary as a bare COFF object with a .rsrc section.
    This is a minimal stub — enough for the linker to accept it without
    errors; proper .rsrc merging would require full COFF .rsrc layout.
    We use llvm-objcopy --input-target binary --output-target pe-x86-64-coff
    if available; otherwise fall back to an empty object.
    """
    obj_fd, obj_path = tempfile.mkstemp(suffix=".o")
    os.close(obj_fd)
    objcopy = os.path.join(LLVM_BIN, "llvm-objcopy.exe")
    r = subprocess.run(
        [objcopy,
         "--input-target=binary",
         "--output-target=pe-x86-64-coff",
         "--rename-section=.data=.rsrc",
         res_path, obj_path],
        capture_output=True,
    )
    if r.returncode != 0:
        # objcopy failed; write a minimal empty COFF stub
        # COFF header: machine=0x8664 (AMD64), 0 sections, no symbols
        with open(obj_path, "wb") as f:
            f.write(struct.pack("<HHIIIHH",
                0x8664,  # Machine: IMAGE_FILE_MACHINE_AMD64
                0,       # NumberOfSections
                0,       # TimeDateStamp
                0,       # PointerToSymbolTable
                0,       # NumberOfSymbols
                0,       # SizeOfOptionalHeader
                0,       # Characteristics
            ))
    return obj_path


def main():
    argv = sys.argv[1:]
    rc_file, out_file, includes = parse_args(argv)

    if not out_file:
        sys.stderr.write("windres shim: could not determine output file\n")
        return 1

    if not rc_file or not os.path.exists(rc_file):
        # No input or missing file — write empty archive and succeed
        write_empty_archive(out_file)
        return 0

    # Compile .rc → .res
    res_path = compile_rc(rc_file, includes)
    if res_path is None:
        # llvm-rc failed; write empty archive so build continues
        write_empty_archive(out_file)
        return 0

    try:
        obj_path = res_to_coff_obj(res_path)
        try:
            # ar rcs output.a object.o
            r = subprocess.run([LLVM_AR, "rcs", out_file, obj_path])
            return r.returncode
        finally:
            try: os.unlink(obj_path)
            except OSError: pass
    finally:
        try: os.unlink(res_path)
        except OSError: pass


if __name__ == "__main__":
    sys.exit(main())
