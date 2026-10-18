# name=SBProbe
# FL controller-script probe. Python 3.9-compatible. Prints ~70 lines once at init.
"""Hardware probe script for FL Studio embedded Python sub-interpreter.

Investigates Python version, builtin modules, restricted import sandbox,
filesystem read/write permissions, and host API version numbers.
"""

import sys


def _try(label, fn):
    try:
        r = fn()
        print(f"[SBP] {label}: OK {'' if r is None else r}")
    except Exception as e:
        print(f"[SBP] {label}: FAIL {type(e).__name__}: {str(e)[:90]}")


def _imp(m):
    __import__(m)


def OnInit():
    try:
        print("[SBP] version:", sys.version.replace("\n", " ")[:100])
        names = sorted(sys.builtin_module_names)
        print(f"[SBP] builtin({len(names)}): {','.join(names)}")
        for m in (
            "socket",
            "_socket",
            "select",
            "threading",
            "_thread",
            "os",
            "nt",
            "posix",
            "subprocess",
            "ctypes",
            "json",
            "_json",
            "hmac",
            "hashlib",
            "_hashlib",
            "_sha256",
            "_sha1",
            "_md5",
            "_blake2",
            "struct",
            "binascii",
            "zlib",
            "base64",
            "re",
            "time",
            "datetime",
            "itertools",
            "collections",
            "functools",
            "random",
            "math",
            "array",
            "io",
            "_io",
            "pathlib",
            "traceback",
            "contextlib",
            "enum",
            "dataclasses",
            "typing",
            "_sbp_dummy",
        ):
            _try("import " + m, lambda m=m: _imp(m))
        _try("sys.path[:6]", lambda: sys.path[:6])
        _try("__file__", lambda: globals().get("__file__"))
        _try("len(sys.modules)", lambda: len(sys.modules))
        for label, path in (("rel", "sbp_rel.txt"), ("public", "C:\\Users\\Public\\sbp_pub.txt")):

            def w(path=path):
                with open(path, "w") as f:
                    f.write("x")
                with open(path) as f:
                    d = f.read()
                return f"wrote+read={d!r}"

            _try("file " + label, w)

        def api():
            import general

            return f"general.getVersion()={general.getVersion()}"

        _try("api", api)

        def ver():
            import ui

            return f"ui.getVersion()={ui.getVersion()}"

        _try("ui.getVersion", ver)
        print("[SBP] done")
    except Exception as e:
        print("[SBP] FATAL", type(e).__name__, str(e)[:90])


if __name__ == "__main__":
    OnInit()
