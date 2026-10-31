"""_sb_core.py - Core session, logging ring, dispatcher, and budgeting.

Pure Python 3.9 syntax with zero external dependencies.
"""

import collections
import contextlib
import sys
import time

try:
    from studiobridge.device.assets import _sb_api as api
    from studiobridge.device.assets import _sb_auth as auth
    from studiobridge.device.assets import _sb_json as json_codec
except ImportError:
    import _sb_api as api  # type: ignore
    import _sb_auth as auth  # type: ignore
    import _sb_json as json_codec  # type: ignore


def _now_ms():
    """Current timestamp in milliseconds."""
    try:
        return int(time.time() * 1000)
    except Exception:
        return 0


def _perf_now():
    """High-resolution monotonic timer."""
    try:
        return time.perf_counter()
    except Exception:
        return time.time()


class LogRing:
    """Bounded circular ring buffer of 256 entries with console rate limiting."""

    def __init__(self, capacity=256):
        self.capacity = capacity
        self.entries = []
        self.seq = 0
        self.dropped = 0
        self._print_timestamps = []

    def append(self, lvl, msg):
        """Append an entry to the log ring."""
        self.seq += 1
        entry = {
            "seq": self.seq,
            "t": _now_ms(),
            "lvl": str(lvl),
            "msg": str(msg)[:200],
        }
        if len(self.entries) >= self.capacity:
            self.entries.pop(0)
            self.dropped += 1
        self.entries.append(entry)

    def get_entries(self, since_seq=0, max_count=100):
        """Retrieve entries newer than since_seq up to max_count."""
        matching = [e for e in self.entries if e["seq"] > since_seq]
        if len(matching) > max_count:
            matching = matching[-max_count:]
        return {
            "entries": matching,
            "dropped": self.dropped,
            "total": self.seq,
        }

    def console_print(self, msg, force=False):
        """Rate-limited print to FL Script Output window (~20 lines per minute)."""
        now = _perf_now()
        self._print_timestamps = [t for t in self._print_timestamps if now - t < 60.0]
        if force or len(self._print_timestamps) < 20:
            self._print_timestamps.append(now)
            with contextlib.suppress(Exception):
                print(str(msg)[:240])


class Session:
    """Device session state manager with fingerprint rotation and idempotency cache."""

    def __init__(self, sid=None):
        if sid is None:
            # 14-bit random mix from time and object id
            sid = (int(_perf_now() * 1000) ^ id(self)) & 0x3FFF
        self.sid = int(sid) & 0x3FFF
        self.fp = ""
        self.last_mutating_mid = 0
        self.max_cache_size = 64
        self.idempotency_cache = collections.OrderedDict()
        self.rotate_fp()

    def rotate_fp(self):
        """Rotate session fingerprint on init or project load."""
        seed = int(_perf_now() * 1000000) ^ id(object())
        self.fp = f"{seed & 0xFFFFFFFF:08x}"
        self.idempotency_cache.clear()

    def get_cached_response(self, idem):
        """Look up cached response by idempotency key."""
        if not idem:
            return None
        return self.idempotency_cache.get(idem)

    def cache_response(self, idem, response):
        """Store response in LRU idempotency cache."""
        if not idem:
            return
        if len(self.idempotency_cache) >= self.max_cache_size:
            self.idempotency_cache.popitem(last=False)
        self.idempotency_cache[idem] = response


class Dispatcher:
    """Core request dispatcher routing call, batch, probe, ping, log, and panic."""

    def __init__(
        self,
        build_id="1.0.0",
        secret="",
        auth_alg="sha256",
        port_root="StudioBridge",
        max_frame=512,
        budget_ms=15,
        budget_calls=150,
        unsafe=0,
    ):
        self.build_id = build_id
        self.secret = secret
        self.auth_alg = auth_alg
        self.port_root = port_root
        self.max_frame = max_frame
        self.budget_ms = budget_ms
        self.budget_calls = budget_calls
        self.unsafe = unsafe

        self.log_ring = LogRing(256)
        self.session = Session()
        self.idle_queue = []
        self.max_queue = 64
        self.max_inline_calls = 8

        # Cache of imported FL modules
        self._fl_modules = {}

    def _get_module(self, name):
        """Lazily import and cache FL Studio API module."""
        if name in self._fl_modules:
            return self._fl_modules[name]
        try:
            mod = __import__(name)
            self._fl_modules[name] = mod
            return mod
        except ImportError:
            return None

    def _execute_single_call(self, fn_name, raw_args, verify=None):
        """Execute a single allowlisted FL call, returning result or raising error."""
        if "." not in fn_name:
            return False, "E_ARGS", f"Malformed function name: {fn_name}", None, None

        mod_name, func_name = fn_name.split(".", 1)

        try:
            coerced_args = api.coerce_args(mod_name, func_name, raw_args)
        except KeyError as e:
            return False, "E_UNAVAILABLE", str(e), None, None
        except ValueError as e:
            return False, "E_ARGS", str(e), None, None

        mod = self._get_module(mod_name)
        if mod is None:
            return False, "E_UNAVAILABLE", f"FL module '{mod_name}' is not available", None, None

        func = getattr(mod, func_name, None)
        if func is None:
            return (
                False,
                "E_UNAVAILABLE",
                f"Function '{func_name}' not found on module '{mod_name}'",
                None,
                None,
            )

        try:
            raw_ret = func(*coerced_args)
        except Exception as exc:
            self.log_ring.append("ERROR", f"{fn_name} failed: {exc}")
            return False, "E_FL", f"{type(exc).__name__}: {str(exc)[:120]}", None, None

        spec = api.ALLOW.get(mod_name, {}).get(func_name, {})
        ret_val = api.normalize_ret(spec.get("ret", "none"), raw_ret)

        readback_val = None
        if verify == "readback":
            getter_spec, getter_args = api.get_verify_getter(mod_name, func_name, coerced_args)
            if getter_spec and "." in getter_spec:
                g_mod_name, g_func_name = getter_spec.split(".", 1)
                g_mod = self._get_module(g_mod_name)
                if g_mod:
                    g_func = getattr(g_mod, g_func_name, None)
                    if g_func:
                        try:
                            g_raw = g_func(*getter_args)
                            g_spec = api.ALLOW.get(g_mod_name, {}).get(g_func_name, {})
                            readback_val = api.normalize_ret(g_spec.get("ret", "none"), g_raw)
                        except Exception as e:
                            self.log_ring.append("WARN", f"Readback getter failed: {e}")

        return True, None, None, ret_val, readback_val

    def _eval_precondition(self, expect):
        """Evaluate opts.expect guard against FL state."""
        if not isinstance(expect, dict):
            return True
        getter = expect.get("getter") or expect.get("fn")
        if not getter or "." not in getter:
            return True
        args = expect.get("args") or expect.get("a") or []
        expected_val = expect.get("value") if "value" in expect else expect.get("val")

        ok, _code, _msg, actual_val, _ = self._execute_single_call(getter, args)
        if not ok:
            return False
        if isinstance(expected_val, float) and isinstance(actual_val, (int, float)):
            tol = float(expect.get("tol", 0.005))
            return abs(float(actual_val) - expected_val) <= tol
        return actual_val == expected_val

    def dispatch(self, frame, payload_bytes):
        """Dispatch incoming request payload bytes and return response dictionary.

        If work is queued for OnIdle ticks (e.g. large batch), returns None.
        """
        sid = frame.get("sid", 0)
        mid = frame.get("mid", 0)

        try:
            req = json_codec.loads(payload_bytes)
        except Exception as exc:
            self.log_ring.append("WARN", f"Malformed JSON payload: {exc}")
            return {"ok": False, "e": {"c": "E_PROTO", "m": f"Malformed JSON: {exc}"}}

        if not isinstance(req, dict):
            return {"ok": False, "e": {"c": "E_PROTO", "m": "Request must be a JSON object"}}

        op = req.get("op", "")
        idem = req.get("idem")
        auth_token = req.get("auth")
        args = req.get("args") or {}
        opts = req.get("opts") or {}

        # 1. Replay defense via idempotency cache
        if idem:
            cached = self.session.get_cached_response(idem)
            if cached is not None:
                return cached

        # 2. Authentication check
        if not auth.verify_auth(
            self.secret, auth_token, op, idem=idem, args=args, alg=self.auth_alg
        ):
            self.log_ring.append("WARN", f"Auth check failed for op '{op}'")
            return {"ok": False, "e": {"c": "E_AUTH", "m": "Authentication failed"}}

        # 3. Session fingerprint guard
        req_fp = opts.get("fp")
        if req_fp and req_fp != self.session.fp:
            return {
                "ok": False,
                "e": {
                    "c": "E_STALE",
                    "m": "Session fingerprint mismatch",
                    "d": {"expected": self.session.fp, "actual": req_fp},
                },
            }

        # 4. Precondition guard
        expect = opts.get("expect")
        if expect and not self._eval_precondition(expect):
            return {
                "ok": False,
                "e": {
                    "c": "E_PRECONDITION",
                    "m": "Precondition check failed",
                    "d": {"expect": expect},
                },
            }

        # 5. Route operation
        try:
            if op == "ping":
                res = {"ok": True, "r": {"pong": True, "t": _now_ms()}}
            elif op == "hello":
                res = self._handle_hello()
            elif op == "probe":
                res = self._handle_probe()
            elif op == "call":
                res = self._handle_call(args, opts)
            elif op == "batch":
                return self._handle_batch(sid, mid, args, opts, idem)
            elif op == "log":
                res = self._handle_log(args)
            elif op == "panic":
                res = self._handle_panic()
            else:
                res = {"ok": False, "e": {"c": "E_PROTO", "m": f"Unknown operation: {op}"}}
        except Exception as exc:
            self.log_ring.append("ERROR", f"Unhandled handler exception on op '{op}': {exc}")
            res = {
                "ok": False,
                "e": {
                    "c": "E_FL",
                    "m": f"{type(exc).__name__}: {str(exc)[:120]}",
                    "d": {"type": type(exc).__name__},
                },
            }

        if idem:
            self.session.cache_response(idem, res)
        return res

    def _handle_hello(self):
        """Handle hello handshake query."""
        general = self._get_module("general")
        api_ver = general.getVersion() if general and hasattr(general, "getVersion") else 0
        return {
            "ok": True,
            "r": {
                "device": {
                    "build": self.build_id,
                    "port_root": self.port_root,
                    "sid": self.session.sid,
                    "fp": self.session.fp,
                    "auth_alg": self.auth_alg,
                },
                "proto": 1,
                "sid": self.session.sid,
                "fp": self.session.fp,
                "fl": {"api_version": api_ver},
                "py": {"version": sys.version.split()[0]},
                "limits": {
                    "max_frame": self.max_frame,
                    "max_msg": 98304,
                    "budget_ms": self.budget_ms,
                    "budget_calls": self.budget_calls,
                    "out_burst": 8,
                },
                "caps": {"safe_mode": False},
            },
        }

    def _handle_probe(self):
        """Handle probe operation inspecting sandbox and runtime environment."""
        names = sorted(sys.builtin_module_names)
        import_tests = {}
        probe_mods = (
            "socket",
            "ctypes",
            "subprocess",
            "threading",
            "json",
            "_json",
            "struct",
            "binascii",
            "time",
        )
        for mod_name in probe_mods:
            try:
                __import__(mod_name)
                import_tests[mod_name] = True
            except Exception:
                import_tests[mod_name] = False

        general = self._get_module("general")
        api_ver = general.getVersion() if general and hasattr(general, "getVersion") else 0

        return {
            "ok": True,
            "r": {
                "py": {"version": sys.version.split()[0], "builtin": names},
                "imports": import_tests,
                "fl": {"api": api_ver},
                "limits": {
                    "budget_ms": self.budget_ms,
                    "budget_calls": self.budget_calls,
                },
                "ctx": "controller",
            },
        }

    def _handle_call(self, args, opts):
        """Handle single call operation."""
        fn = args.get("fn", "")
        a = args.get("a", [])
        verify = opts.get("verify")

        ok, code, msg, ret_val, readback_val = self._execute_single_call(fn, a, verify=verify)
        if not ok:
            return {"ok": False, "e": {"c": code, "m": msg}}

        resp = {"ok": True, "r": ret_val}
        if readback_val is not None:
            resp["rb"] = readback_val
        return resp

    def _handle_batch(self, sid, mid, args, opts, idem):
        """Handle batch calls, executing inline or queueing across OnIdle ticks."""
        calls = args.get("calls", [])
        stop_on_error = bool(args.get("stop_on_error", False))
        verify = opts.get("verify")

        if len(self.idle_queue) >= self.max_queue:
            return {"ok": False, "e": {"c": "E_BUSY", "m": "Idle queue full", "retry": True}}

        # If batch is small, attempt inline execution
        if len(calls) <= self.max_inline_calls:
            results = []
            for call_item in calls:
                fn = call_item.get("fn", "")
                a = call_item.get("a", [])
                ok, code, msg, ret_val, rb = self._execute_single_call(fn, a, verify=verify)
                if not ok:
                    results.append({"ok": False, "e": {"c": code, "m": msg}})
                    if stop_on_error:
                        break
                else:
                    item_res = {"ok": True, "r": ret_val}
                    if rb is not None:
                        item_res["rb"] = rb
                    results.append(item_res)
            res = {"ok": True, "r": {"results": results, "count": len(results)}}
            if idem:
                self.session.cache_response(idem, res)
            return res

        # Otherwise, queue into idle_queue
        job = {
            "sid": sid,
            "mid": mid,
            "calls": calls,
            "stop_on_error": stop_on_error,
            "verify": verify,
            "idem": idem,
            "idx": 0,
            "results": [],
        }
        self.idle_queue.append(job)
        return None  # Defer execution to OnIdle

    def _handle_log(self, args):
        """Handle log query operation."""
        since_seq = int(args.get("since_seq", 0))
        max_count = int(args.get("max", 100))
        entries_data = self.log_ring.get_entries(since_seq, max_count)
        return {"ok": True, "r": entries_data}

    def _handle_panic(self):
        """Handle panic operation clearing queues and active jobs."""
        cleared = len(self.idle_queue)
        self.idle_queue.clear()
        self.log_ring.append("WARN", f"Panic received: cleared {cleared} queued jobs")
        return {"ok": True, "r": {"cleared": cleared}}

    def on_idle(self, send_fn):
        """Process queued work in idle_queue within budget_ms and budget_calls."""
        if not self.idle_queue:
            return

        start_time = _perf_now()
        calls_done = 0

        while self.idle_queue:
            job = self.idle_queue[0]
            calls = job["calls"]
            verify = job.get("verify")
            stop_on_error = job.get("stop_on_error", False)

            while job["idx"] < len(calls):
                # Budget check
                elapsed_ms = (_perf_now() - start_time) * 1000.0
                if calls_done >= self.budget_calls or elapsed_ms >= self.budget_ms:
                    return  # Yield to next OnIdle tick

                call_item = calls[job["idx"]]
                fn = call_item.get("fn", "")
                a = call_item.get("a", [])

                ok, code, msg, ret_val, rb = self._execute_single_call(fn, a, verify=verify)
                calls_done += 1
                job["idx"] += 1

                if not ok:
                    job["results"].append({"ok": False, "e": {"c": code, "m": msg}})
                    if stop_on_error:
                        job["idx"] = len(calls)
                        break
                else:
                    item_res = {"ok": True, "r": ret_val}
                    if rb is not None:
                        item_res["rb"] = rb
                    job["results"].append(item_res)

            # Job completed
            self.idle_queue.pop(0)
            res = {
                "ok": True,
                "r": {"results": job["results"], "count": len(job["results"])},
            }
            if job.get("idem"):
                self.session.cache_response(job["idem"], res)
            if send_fn:
                send_fn(job["sid"], job["mid"], res)

    def on_project_load(self, status=0):
        """Handle FL Studio project load event."""
        self.session.rotate_fp()
        self.idle_queue.clear()
        self.log_ring.append(
            "INFO",
            f"Project loaded (status={status}), fp rotated to {self.session.fp}",
        )
