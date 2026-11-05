#!/usr/bin/env python3
"""Capture locally derived Linux WeChat database keys without printing them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from queue import Empty, Queue
import sys
import time

import frida

sys.path.insert(0, "/opt/wechat-decrypt")
from key_scan_common import collect_db_files, verify_enc_key
from linux_wechat_capture import locate_kdf_boundary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, help="Attach to an existing WeChat process")
    parser.add_argument("--spawn", action="store_true", help="Start WeChat under observation")
    parser.add_argument("--seconds", type=int, default=90)
    args = parser.parse_args()
    if bool(args.pid) == args.spawn:
        parser.error("Specify either --pid or --spawn")

    accounts = [p for p in Path("/config/xwechat_files").glob("*/db_storage") if p.is_dir()]
    if len(accounts) != 1:
        raise SystemExit("Cannot select a unique account database")
    db_dir = accounts[0]
    files, _ = collect_db_files(str(db_dir))
    boundary = locate_kdf_boundary(Path("/opt/wechat/wechat"))
    if not files or not boundary:
        raise SystemExit("Databases or a unique compatible KDF signature were not found")

    source = '''
    const site = Process.enumerateModules()[0].base.add(OFFSET);
    Interceptor.attach(site, {
      onEnter(args) {
        try {
          const c = this.context;
          if (c.rbx.add(4).readU32() !== 32 || c.r9.toUInt32() !== 16 ||
              c.r14.add(0x34).readU32() !== 2 || c.r14.add(4).readU32() !== 256000 ||
              c.r10.toUInt32() !== 32) return;
          send({event: 'candidate'}, c.rbx.add(0x18).readPointer().readByteArray(32));
        } catch (e) { send({event: 'error'}); }
      }
    });
    send({event: 'ready'});
    '''.replace("OFFSET", str(boundary.signature_address))
    device = frida.get_local_device()
    pid = device.spawn(["/opt/wechat/wechat"]) if args.spawn else args.pid
    session = device.attach(pid)
    script = session.create_script(source)
    candidates = Queue()
    errors = Queue()

    def message(msg, data):
        payload = msg.get("payload", {})
        if msg.get("type") == "error":
            errors.put("Observer could not be installed")
        elif isinstance(payload, dict) and payload.get("event") == "ready":
            print("Observer ready", flush=True)
        elif isinstance(payload, dict) and payload.get("event") == "error":
            errors.put("Observer could not read the derivation arguments")
        elif isinstance(payload, dict) and payload.get("event") == "candidate" and data and len(data) == 32:
            candidates.put(bytes(data))

    script.on("message", message)
    seen = set()
    resumed = not args.spawn
    try:
        script.load()
        if args.spawn:
            device.resume(pid)
            resumed = True
        deadline = time.monotonic() + max(1, args.seconds)
        while time.monotonic() < deadline:
            if not errors.empty():
                raise RuntimeError(errors.get())
            try:
                password = candidates.get(timeout=min(1, max(0.01, deadline - time.monotonic())))
            except Empty:
                continue
            if password in seen:
                continue
            seen.add(password)
            results = {}
            for rel, path, size, salt, page in files:
                key = hashlib.pbkdf2_hmac("sha512", password, page[:16], 256000, dklen=32)
                if verify_enc_key(key, page):
                    results[rel] = {"enc_key": key.hex(), "salt": salt, "size_mb": round(size / 1024 / 1024, 1)}
            print(f"Verified {len(results)} of {len(files)} databases", flush=True)
            if results:
                results["_db_dir"] = str(db_dir)
                target = Path("/config/.wechat-agent-keys.json")
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump(results, f)
                os.chmod(target, 0o600)
                return
        raise SystemExit("No verified key captured")
    finally:
        if not resumed:
            device.resume(pid)
        script.unload()
        session.detach()


if __name__ == "__main__":
    main()
