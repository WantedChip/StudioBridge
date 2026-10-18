"""_sb_json.py - JSON parser and serializer for FL Studio sandbox.

Pure Python 3.9 syntax with graceful fallback if the standard library json
module is not present in the embedded Python environment.
"""

try:
    import json as _stdlib_json

    _HAS_JSON = True
except ImportError:
    _stdlib_json = None
    _HAS_JSON = False


def _dump_pure(obj):
    """Pure-Python fallback serializer."""
    if obj is None:
        return "null"
    elif obj is True:
        return "true"
    elif obj is False:
        return "false"
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, str):
        buf = ['"']
        for ch in obj:
            if ch == '"':
                buf.append('\\"')
            elif ch == "\\":
                buf.append("\\\\")
            elif ch == "\n":
                buf.append("\\n")
            elif ch == "\r":
                buf.append("\\r")
            elif ch == "\t":
                buf.append("\\t")
            elif ord(ch) < 32:
                buf.append(f"\\u{ord(ch):04x}")
            else:
                buf.append(ch)
        buf.append('"')
        return "".join(buf)
    elif isinstance(obj, (list, tuple)):
        pieces = [_dump_pure(x) for x in obj]
        return "[" + ",".join(pieces) + "]"
    elif isinstance(obj, dict):
        items = [_dump_pure(str(k)) + ":" + _dump_pure(v) for k, v in obj.items()]
        return "{" + ",".join(items) + "}"
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class _JsonParser:
    """Minimal recursive-descent JSON parser in pure Python."""

    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.len = len(text)

    def _skip_whitespace(self):
        while self.pos < self.len and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def parse(self):
        self._skip_whitespace()
        val = self._parse_value()
        self._skip_whitespace()
        return val

    def _parse_value(self):
        self._skip_whitespace()
        if self.pos >= self.len:
            raise ValueError("Unexpected end of JSON input")
        ch = self.text[self.pos]
        if ch == "{":
            return self._parse_object()
        elif ch == "[":
            return self._parse_array()
        elif ch == '"':
            return self._parse_string()
        elif ch == "t" and self.text.startswith("true", self.pos):
            self.pos += 4
            return True
        elif ch == "f" and self.text.startswith("false", self.pos):
            self.pos += 5
            return False
        elif ch == "n" and self.text.startswith("null", self.pos):
            self.pos += 4
            return None
        elif ch in "-0123456789":
            return self._parse_number()
        raise ValueError(f"Unexpected character '{ch}' at position {self.pos}")

    def _parse_object(self):
        self.pos += 1  # skip '{'
        res = {}
        self._skip_whitespace()
        if self.pos < self.len and self.text[self.pos] == "}":
            self.pos += 1
            return res

        while self.pos < self.len:
            self._skip_whitespace()
            if self.pos >= self.len or self.text[self.pos] != '"':
                raise ValueError(f"Expected string key in object at position {self.pos}")
            key = self._parse_string()
            self._skip_whitespace()
            if self.pos >= self.len or self.text[self.pos] != ":":
                raise ValueError(f"Expected ':' after object key at position {self.pos}")
            self.pos += 1  # skip ':'
            val = self._parse_value()
            res[key] = val
            self._skip_whitespace()
            if self.pos < self.len and self.text[self.pos] == "}":
                self.pos += 1
                return res
            elif self.pos < self.len and self.text[self.pos] == ",":
                self.pos += 1
            else:
                raise ValueError(f"Expected ',' or '}}' in object at position {self.pos}")
        raise ValueError("Unterminated object")

    def _parse_array(self):
        self.pos += 1  # skip '['
        res = []
        self._skip_whitespace()
        if self.pos < self.len and self.text[self.pos] == "]":
            self.pos += 1
            return res

        while self.pos < self.len:
            val = self._parse_value()
            res.append(val)
            self._skip_whitespace()
            if self.pos < self.len and self.text[self.pos] == "]":
                self.pos += 1
                return res
            elif self.pos < self.len and self.text[self.pos] == ",":
                self.pos += 1
            else:
                raise ValueError(f"Expected ',' or ']' in array at position {self.pos}")
        raise ValueError("Unterminated array")

    def _parse_string(self):
        self.pos += 1  # skip initial '"'
        chars = []
        while self.pos < self.len:
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1
                return "".join(chars)
            elif ch == "\\":
                self.pos += 1
                if self.pos >= self.len:
                    raise ValueError("Unterminated string escape")
                esc = self.text[self.pos]
                if esc == '"':
                    chars.append('"')
                elif esc == "\\":
                    chars.append("\\")
                elif esc == "/":
                    chars.append("/")
                elif esc == "b":
                    chars.append("\b")
                elif esc == "f":
                    chars.append("\f")
                elif esc == "n":
                    chars.append("\n")
                elif esc == "r":
                    chars.append("\r")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "u":
                    hex_digits = self.text[self.pos + 1 : self.pos + 5]
                    if len(hex_digits) < 4:
                        raise ValueError("Invalid unicode escape")
                    chars.append(chr(int(hex_digits, 16)))
                    self.pos += 4
                else:
                    chars.append(esc)
                self.pos += 1
            else:
                chars.append(ch)
                self.pos += 1
        raise ValueError("Unterminated string")

    def _parse_number(self):
        start = self.pos
        if self.pos < self.len and self.text[self.pos] == "-":
            self.pos += 1
        while self.pos < self.len and self.text[self.pos] in "0123456789":
            self.pos += 1
        is_float = False
        if self.pos < self.len and self.text[self.pos] == ".":
            is_float = True
            self.pos += 1
            while self.pos < self.len and self.text[self.pos] in "0123456789":
                self.pos += 1
        if self.pos < self.len and self.text[self.pos] in "eE":
            is_float = True
            self.pos += 1
            if self.pos < self.len and self.text[self.pos] in "+-":
                self.pos += 1
            while self.pos < self.len and self.text[self.pos] in "0123456789":
                self.pos += 1
        num_str = self.text[start : self.pos]
        return float(num_str) if is_float else int(num_str)


def dumps(obj):
    """Serialize object to compact 7-bit clean ASCII JSON string."""
    if _HAS_JSON and _stdlib_json is not None:
        return _stdlib_json.dumps(obj, ensure_ascii=True, separators=(",", ":"))
    return _dump_pure(obj)


def loads(s):
    """Deserialize JSON string or ASCII bytes into Python objects."""
    if isinstance(s, (bytes, bytearray)):
        s = s.decode("ascii")
    if _HAS_JSON and _stdlib_json is not None:
        return _stdlib_json.loads(s)
    parser = _JsonParser(s)
    return parser.parse()
