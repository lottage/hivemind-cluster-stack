import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

class InboxView extends WatchUi.View {

    function initialize() {
        View.initialize();
    }

    function onUpdate(dc) {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        Inbox.prune();

        var w = dc.getWidth();
        var h = dc.getHeight();
        var sub = Ui.subscreen();
        var leftW = (sub != null) ? sub.x : w;
        var asks = Inbox.countAsks();

        dc.drawText(leftW / 2 + 6, h * 0.14, Graphics.FONT_TINY, "SAGE", Ui.CENTER);

        // Ask count lives in the subscreen when there is one.
        if (sub != null) {
            dc.drawText(sub.x + sub.width / 2, sub.y + sub.height / 2, Graphics.FONT_MEDIUM,
                        asks.toString(), Ui.CENTER);
        } else {
            dc.drawText(w / 2, h * 0.26, Graphics.FONT_SMALL, asks + " asks", Ui.CENTER);
        }

        var top = Inbox.top();
        if (top == null) {
            dc.drawText(w / 2, h * 0.52, Graphics.FONT_SMALL, "All clear", Ui.CENTER);
            dc.drawText(w / 2, h * 0.86, Graphics.FONT_XTINY, "START: sync", Ui.CENTER);
            return;
        }

        var head = "ask".equals(top["k"]) ? "? " : ("err".equals(top["k"]) ? "! " : "OK ");
        if (top["p"] != null) {
            head = head + top["p"];
        }
        dc.drawText(w / 2, h * 0.42, Graphics.FONT_TINY, Ui.clip(head, 16), Ui.CENTER);

        var lines = Ui.wrap(dc, top["t"], Graphics.FONT_XTINY, w * 0.82, 3);
        for (var i = 0; i < lines.size(); i++) {
            dc.drawText(w / 2, h * 0.55 + i * h * 0.1, Graphics.FONT_XTINY, lines[i], Ui.CENTER);
        }
        dc.drawText(w / 2, h * 0.9, Graphics.FONT_XTINY, "START: open", Ui.CENTER);
    }
}

class InboxDelegate extends WatchUi.BehaviorDelegate {

    function initialize() {
        BehaviorDelegate.initialize();
    }

    function onSelect() {
        Inbox.prune();
        var list = Inbox.items();
        if (list.size() == 0) {
            Inbox.requestSync();
            return true;
        }
        var menu = new WatchUi.Menu2({:title => "Inbox"});
        for (var i = list.size() - 1; i >= 0; i--) {
            var it = list[i];
            var tag = "ask".equals(it["k"]) ? "? " : ("err".equals(it["k"]) ? "! " : "OK ");
            var label = tag + (it["p"] != null ? it["p"] : Ui.clip(it["t"], 10));
            menu.addItem(new WatchUi.MenuItem(Ui.clip(label, 14), Ui.clip(it["t"], 22), it["id"], null));
        }
        WatchUi.pushView(menu, new ItemsDelegate(), WatchUi.SLIDE_UP);
        return true;
    }

    function onMenu() {
        Inbox.requestSync();
        return true;
    }
}
