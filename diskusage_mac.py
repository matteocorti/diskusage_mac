#!/usr/bin/env python3
"""
diskusage_mac.py — friendly disk usage for macOS (APFS/HFS)

Shows one line per *mounted* local filesystem (APFS/HFS), with:
Device | Volume name | Mount | Total | Used | Free | Use%

Now hides all mounts under /System (system helper volumes).
"""

import os
import re
import subprocess
import sys
import plistlib
from typing import List, Tuple

LINE_RE = re.compile(r'^(?P<dev>\S+)\s+on\s+(?P<mp>.+?)\s+\((?P<fstype>[^,]+)')
LOCAL_FS = {"apfs", "hfs", "hfs+"}


def human(bytes_: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    b = float(bytes_)
    for u in units:
        if b < 1024 or u == "PiB":
            return f"{int(b)} B" if u == "B" else f"{b:.1f} {u}"
        b /= 1024
    return f"{bytes_} B"


def volume_name(dev: str) -> str:
    try:
        out = subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", dev])
        info = plistlib.loads(out)
        return info.get("VolumeName") or ""
    except Exception:
        return ""


def statvfs_row(mp: str) -> Tuple[int, int, int, float]:
    s = os.statvfs(mp)
    bs = s.f_frsize or s.f_bsize
    size = s.f_blocks * bs
    used = (s.f_blocks - s.f_bfree) * bs
    avail = s.f_bavail * bs
    pct = (used / size * 100.0) if size else 0.0
    return size, used, avail, pct


def get_rows() -> List[Tuple[str, str, str, int, int, int, float]]:
    try:
        mount_output = subprocess.check_output(["/sbin/mount"], text=True)
    except FileNotFoundError:
        mount_output = subprocess.check_output(["mount"], text=True)

    rows = []
    seen_mps = set()

    for line in mount_output.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        dev = m.group("dev")
        mp = m.group("mp")
        fstype = (m.group("fstype") or "").lower()

        if fstype not in LOCAL_FS:
            continue
        if not mp.startswith("/"):
            continue
        if mp.startswith("/System/"):  # hide system helper volumes
            continue
        if mp.startswith("/Volumes/.time"):
            continue
        if not os.path.exists(mp):
            continue
        if mp in seen_mps:
            continue

        seen_mps.add(mp)

        try:
            size, used, avail, pct = statvfs_row(mp)
        except OSError:
            continue

        name = volume_name(dev)
        rows.append((dev, name, mp, size, used, avail, pct))

    rows.sort(key=lambda r: r[2].lower())
    return rows


def main() -> int:
    rows = get_rows()
    dev_w = max([len("Device")] + [len(r[0]) for r in rows])
    name_w = max([len("Volume name")] + [len(r[1]) for r in rows])
    mp_w = max([len("Mount")] + [len(r[2]) for r in rows])
    dev_w, name_w, mp_w = min(dev_w, 18), min(name_w, 24), min(mp_w, 40)

    header = (
        f"{'Device':{dev_w}}  {'Volume name':{name_w}}  {'Mount':{mp_w}}  "
        f"{'Total':>12}  {'Used':>12}  {'Free':>12}  {'Use%':>6}"
    )
    sep = (
        f"{'-'*dev_w:{dev_w}}  {'-'*name_w:{name_w}}  {'-'*mp_w:{mp_w}}  "
        f"{'-'*12:>12}  {'-'*12:>12}  {'-'*12:>12}  {'-'*6:>6}"
    )

    print(header)
    print(sep)
    for dev, name, mp, size, used, avail, pct in rows:
        print(
            f"{dev:{dev_w}}  {name[:name_w]:{name_w}}  {mp[:mp_w]:{mp_w}}  "
            f"{human(size):>12}  {human(used):>12}  {human(avail):>12}  {pct:6.1f}%"
        )

    if not rows:
        print("(no local APFS/HFS mounts found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
