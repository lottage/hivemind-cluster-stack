import Toybox.Application;
import Toybox.Attention;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.Time;

// Pending asks + recent done/err events, persisted in Storage.
module Inbox {
    const MAX_ITEMS = 8;
    var _items = null;

    function items() {
        if (_items == null) {
            var s = Application.Storage.getValue("inbox");
            _items = (s instanceof Array) ? s : [];
        }
        return _items;
    }

    function save() {
        Application.Storage.setValue("inbox", _items);
    }

    function ingest(data, live) {
        if (!(data instanceof Dictionary)) {
            return;
        }
        var k = data["k"];
        if ("clr".equals(k)) {
            removeId(data["id"]);
            save();
            return;
        }
        if (!("ask".equals(k) || "done".equals(k) || "err".equals(k))) {
            return;
        }
        items();
        var isNew = find(data["id"]) == null;
        removeId(data["id"]);
        data.put("rx", Time.now().value());
        _items.add(data);
        while (_items.size() > MAX_ITEMS) {
            dropOne();
        }
        save();
        if (live && isNew && "ask".equals(k) && (Attention has :vibrate)) {
            Attention.vibrate([new Attention.VibeProfile(60, 250), new Attention.VibeProfile(0, 150),
                               new Attention.VibeProfile(60, 250)]);
        }
    }

    // Drop the oldest non-ask first; asks only go if nothing else is left.
    function dropOne() {
        for (var i = 0; i < _items.size(); i++) {
            if (!"ask".equals(_items[i]["k"])) {
                _items.remove(_items[i]);
                return;
            }
        }
        _items.remove(_items[0]);
    }

    function prune() {
        items();
        var now = Time.now().value();
        var keep = [];
        for (var i = 0; i < _items.size(); i++) {
            var it = _items[i];
            var ttl = it["x"];
            var rx = it["rx"];
            if ("ask".equals(it["k"]) && ttl != null && rx != null && now > rx + ttl) {
                continue;
            }
            keep.add(it);
        }
        if (keep.size() != _items.size()) {
            _items = keep;
            save();
        }
    }

    function find(id) {
        if (id == null) {
            return null;
        }
        var list = items();
        for (var i = 0; i < list.size(); i++) {
            if (id.equals(list[i]["id"])) {
                return list[i];
            }
        }
        return null;
    }

    function removeId(id) {
        var it = find(id);
        if (it != null) {
            _items.remove(it);
        }
    }

    function countAsks() {
        var n = 0;
        var list = items();
        for (var i = 0; i < list.size(); i++) {
            if ("ask".equals(list[i]["k"])) {
                n++;
            }
        }
        return n;
    }

    // Newest ask if any, else newest item.
    function top() {
        var list = items();
        for (var i = list.size() - 1; i >= 0; i--) {
            if ("ask".equals(list[i]["k"])) {
                return list[i];
            }
        }
        return list.size() > 0 ? list[list.size() - 1] : null;
    }

    function reply(ask, idx) {
        Communications.transmit({"id" => ask["id"], "r" => idx}, null, new TxListener());
        removeId(ask["id"]);
        save();
    }

    function dismiss(item) {
        removeId(item["id"]);
        save();
    }

    function requestSync() {
        Communications.transmit({"k" => "sync"}, null, new TxListener());
    }
}

class TxListener extends Communications.ConnectionListener {
    function initialize() {
        ConnectionListener.initialize();
    }
    function onComplete() {
    }
    function onError() {
        // Phone unreachable; bridge keeps the ask pending, so nothing is lost.
    }
}
