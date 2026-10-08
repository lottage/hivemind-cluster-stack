import Toybox.Application;
import Toybox.Lang;
import Toybox.Time;

// Latest usage / status / layout from the bridge, persisted in Storage.
module FaceData {
    const ROSTER_MAX = 6;

    function ingest(data) {
        if (!(data instanceof Dictionary)) {
            return;
        }
        var k = data["k"];
        if (k == null) {                       // snapshot: {use, st, cfg?}
            if (data["use"] != null) { Application.Storage.setValue("use", data["use"]); }
            if (data["st"] != null) {
                Application.Storage.setValue("st", data["st"]);
                noteAgents(data["st"]["a"]);
            }
            if (data["cfg"] != null) { Application.Storage.setValue("cfg", data["cfg"]); }
        } else if ("use".equals(k)) {
            Application.Storage.setValue("use", data["m"]);
        } else if ("st".equals(k)) {
            Application.Storage.setValue("st", data);
            noteAgents(data["a"]);
        } else if ("cfg".equals(k)) {
            Application.Storage.setValue("cfg", data);
            return;                            // layout isn't data freshness
        } else {
            return;
        }
        Application.Storage.setValue("ts", Time.now().value());
    }

    // Every project/agent/node name ever seen in an `st` push, oldest dropped
    // first past ROSTER_MAX -- this is the glyph roster FaceView draws. Purely
    // client-side memory: the bridge/protocol don't need to know about it.
    function roster() {
        var r = Application.Storage.getValue("roster");
        return (r instanceof Array) ? r : [];
    }

    function noteAgents(agents) {
        if (!(agents instanceof Array)) {
            return;
        }
        var r = roster();
        var changed = false;
        for (var i = 0; i < agents.size(); i++) {
            var p = agents[i]["p"];
            if (p == null) {
                continue;
            }
            var found = false;
            for (var j = 0; j < r.size(); j++) {
                if (p.equals(r[j])) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                r.add(p);
                changed = true;
            }
        }
        while (r.size() > ROSTER_MAX) {
            r.remove(r[0]);
            changed = true;
        }
        if (changed) {
            Application.Storage.setValue("roster", r);
        }
    }

    function use() {
        var u = Application.Storage.getValue("use");
        return (u instanceof Dictionary) ? u : {};
    }

    function st() {
        var s = Application.Storage.getValue("st");
        return (s instanceof Dictionary) ? s : null;
    }

    // Minutes since last update, or null if never.
    function ageMin() {
        var ts = Application.Storage.getValue("ts");
        return (ts == null) ? null : (Time.now().value() - ts) / 60;
    }

    // Metric id for slot position i (2=ring, 4/5/6/7=data rows): StoneSage remote
    // layout (if allowed) else local phone settings (properties.xml).
    // The wire protocol fixes cfg.slots at exactly 5 elements (PROTOCOL.md), so
    // position i maps onto an index via CFG_POSITIONS, not i-1 directly -- there
    // are 5 configurable positions (2,4,5,6,7) since Phase 5, not a contiguous
    // 1..5, and a plain i-1 mapping left slots 6/7 permanently unaddressable
    // remotely (caught 2026-09-26, while adding slot 6/7 phone-settings support).
    const CFG_POSITIONS = [2, 4, 5, 6, 7];

    function slot(i) {
        if (Application.Properties.getValue("remoteLayout") == true) {
            var cfg = Application.Storage.getValue("cfg");
            if (cfg instanceof Dictionary) {
                var slots = cfg["slots"];
                var idx = -1;
                for (var j = 0; j < CFG_POSITIONS.size(); j++) {
                    if (CFG_POSITIONS[j] == i) {
                        idx = j;
                        break;
                    }
                }
                if (slots instanceof Array && idx >= 0 && slots.size() > idx && slots[idx] != null) {
                    return slots[idx];
                }
            }
        }
        var v = Application.Properties.getValue("slot" + i);
        return (v == null) ? 0 : v;
    }
}
