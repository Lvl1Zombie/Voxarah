/*
 * windres_stub.c — Minimal windres shim (no Windows SDK required).
 * Uses only POSIX/C-runtime functions.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define PY_EXE    "C:\\Windows\\py.exe"
#define WR_SCRIPT "C:\\Coding Projects\\Voxarah\\tauri-app\\src-tauri\\windres.py"

int main(int argc, char *argv[])
{
    char cmd[32768];
    int pos = snprintf(cmd, sizeof(cmd), "\"%s\" \"%s\"", PY_EXE, WR_SCRIPT);

    for (int i = 1; i < argc && pos < (int)sizeof(cmd) - 4; i++) {
        int has_space = (strchr(argv[i], ' ') != NULL);
        if (has_space)
            pos += snprintf(cmd + pos, sizeof(cmd) - pos, " \"%s\"", argv[i]);
        else
            pos += snprintf(cmd + pos, sizeof(cmd) - pos, " %s", argv[i]);
    }

    return system(cmd);
}
