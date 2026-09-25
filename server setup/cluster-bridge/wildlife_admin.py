#!/usr/bin/env python3
"""
Presence corrections on VM 102 (called by StoneSage over SSH; deployed to /opt/cluster-bridge/wildlife_admin.py).

    echo '<json args>' | python3 wildlife_admin.py <command>     (args on stdin: nothing user-typed reaches a shell)

Commands (all print one JSON object):
  profiles                          -> known_entities.json
  profile-add  {name, kind, species?, role?, traits?}   kind = person | pet
  reject       {file}               snapshots/<file> -> rejected/<file> (reversible; kept as negative examples)
  relabel      {file, name}         snapshots/austin_<ts>.jpg -> snapshots/savannah_<ts>.jpg
  snapshot     {file}               the image, base64 (for training Frigate's face library from a correction)

Every change is appended to corrections.jsonl; known_entities.json is backed up before each write.
The sentry derives identity from the snapshot filename prefix, and the presence hub matches the activity log by
the timestamp part, so a rename keeps the camera and activity of the sighting.
"""

import base64
import json
import os
import re
import shutil
import sys
import time

BASE_DIR = os.environ.get("WILDLIFE_DIR", "/opt/cluster-bridge/wildlife")
ENTITIES = "known_entities.json"
SNAPSHOT = re.compile(r"^[a-z][a-z0-9-]{0,30}_\d{8}_\d{6}\.jpg$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 '-]{0,29}$")


def _path(*parts):
    return os.path.join(BASE_DIR, *parts)


def _log(entry):
    entry["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(_path("corrections.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _load_entities():
    try:
        with open(_path(ENTITIES), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"people": [], "pets": []}


def prefix(name):
    """File prefix for a profile name: 'Aunt May' -> 'aunt-may' (no '_': the hub splits filenames on it)."""
    return re.sub(r"[^a-z0-9-]", "", name.strip().lower().replace(" ", "-").replace("'", ""))


def known_names(entities):
    return {e["name"].lower(): e["name"] for group in ("people", "pets") for e in entities.get(group, [])}


def cmd_profiles(_args):
    return {"ok": True, "entities": _load_entities()}


def cmd_profile_add(args):
    name = (args.get("name") or "").strip()
    kind = args.get("kind")
    if not NAME.match(name):
        return {"ok": False, "error": "name: letters, digits, spaces, ' and - only (max 30)"}
    if kind not in ("person", "pet"):
        return {"ok": False, "error": "kind must be person or pet"}
    entities = _load_entities()
    if name.lower() in known_names(entities):
        return {"ok": False, "error": f"'{name}' already exists"}
    entry = {"id": f"{kind}-{prefix(name)}", "name": name, "traits": (args.get("traits") or "")[:300],
             "alert_level": "trusted_resident" if kind == "person" else "trusted_pet", "added_by": "stonesage"}
    if kind == "person":
        entry["role"] = (args.get("role") or "Visitor")[:60]
    else:
        entry["species"] = (args.get("species") or "")[:30]
    entities.setdefault("people" if kind == "person" else "pets", []).append(entry)
    if os.path.exists(_path(ENTITIES)):
        shutil.copy2(_path(ENTITIES), _path(f"{ENTITIES}.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    tmp = _path(ENTITIES + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2)
    os.replace(tmp, _path(ENTITIES))  # atomic: the sentry never reads a half-written file
    _log({"action": "profile-add", "name": name, "kind": kind})
    return {"ok": True, "profile": entry}


def _check_file(args):
    f = args.get("file") or ""
    if not SNAPSHOT.match(f):
        raise ValueError(f"not a snapshot name: {f!r}")
    if not os.path.isfile(_path("snapshots", f)):
        raise FileNotFoundError(f)
    return f


def cmd_reject(args):
    f = _check_file(args)
    os.makedirs(_path("rejected"), exist_ok=True)
    shutil.move(_path("snapshots", f), _path("rejected", f))
    _log({"action": "reject", "file": f})
    return {"ok": True, "moved_to": f"rejected/{f}"}


def cmd_relabel(args):
    f = _check_file(args)
    names = known_names(_load_entities())
    name = (args.get("name") or "").strip()
    if name.lower() not in names:
        return {"ok": False, "error": f"unknown profile '{name}' (add it first)"}
    new = f"{prefix(names[name.lower()])}_{f.split('_', 1)[1]}"
    if new == f:
        return {"ok": True, "file": f, "unchanged": True}
    if os.path.exists(_path("snapshots", new)):
        return {"ok": False, "error": f"{new} already exists"}
    os.rename(_path("snapshots", f), _path("snapshots", new))
    _log({"action": "relabel", "file": f, "new_file": new, "name": names[name.lower()]})
    return {"ok": True, "file": new}


def cmd_snapshot(args):
    f = args.get("file") or ""
    if not SNAPSHOT.match(f):
        raise ValueError(f"not a snapshot name: {f!r}")
    with open(_path("snapshots", f), "rb") as fh:
        return {"ok": True, "jpeg_b64": base64.b64encode(fh.read()).decode()}


COMMANDS = {"profiles": cmd_profiles, "profile-add": cmd_profile_add, "reject": cmd_reject,
            "relabel": cmd_relabel, "snapshot": cmd_snapshot}


def main(argv, stdin=sys.stdin):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(json.dumps({"ok": False, "error": f"usage: {argv[0]} {'|'.join(COMMANDS)}  (json args on stdin)"}))
        return 2
    try:
        args = json.loads(stdin.read() or "{}")
        print(json.dumps(COMMANDS[argv[1]](args)))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
