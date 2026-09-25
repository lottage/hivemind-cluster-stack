import Toybox.Application;
import Toybox.Lang;
import Toybox.Time;

// Latest usage / status / layout from the bridge, persisted in Storage.
module FaceData {

    function ingest(data) {
        if (!(data instanceof Dictionary)) {
            return;
        }
        var k = data["k"];
        if (k == null) {                       // snapshot: {use, st, cfg?}
            if (data["use"] != null) { Application.Storage.setValue("use", data["use"]); }
            if (data["st"] != null) { Application.Storage.setValue("st", data["st"]); }
            if (data["cfg"] != null) { Application.Storage.setValue("cfg", data["cfg"]); }
        } else if ("use".equals(k)) {
            Application.Storage.setValue("use", data["m"]);
        } else if ("st".equals(k)) {
            Application.Storage.setValue("st", data);
        } else if ("cfg".equals(k)) {
            Application.Storage.setValue("cfg", data);
            return;                            // layout isn't data freshness
        } else {
            return;
        }
        Application.Storage.setValue("ts", Time.now().value());
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

    // Metric id for slot 1..5: StoneSage layout (if allowed) else phone settings.
    function slot(i) {
        if (Application.Properties.getValue("remoteLayout") == true) {
            var cfg = Application.Storage.getValue("cfg");
            if (cfg instanceof Dictionary) {
                var slots = cfg["slots"];
                if (slots instanceof Array && slots.size() >= i && slots[i - 1] != null) {
                    return slots[i - 1];
                }
            }
        }
        var v = Application.Properties.getValue("slot" + i);
        return (v == null) ? 0 : v;
    }
}
