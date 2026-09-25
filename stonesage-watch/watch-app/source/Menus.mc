import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

class ItemsDelegate extends WatchUi.Menu2InputDelegate {

    function initialize() {
        Menu2InputDelegate.initialize();
    }

    function onSelect(item) {
        var it = Inbox.find(item.getId());
        if (it == null) {
            return;
        }
        if ("ask".equals(it["k"])) {
            var menu = new WatchUi.Menu2({:title => Ui.clip(it["p"] != null ? it["p"] : "Ask", 12)});
            menu.addItem(new WatchUi.MenuItem("Read", Ui.clip(it["t"], 22), -1, null));
            var opts = it["o"];
            for (var i = 0; i < opts.size(); i++) {
                menu.addItem(new WatchUi.MenuItem(Ui.clip(opts[i], 14), null, i, null));
            }
            WatchUi.pushView(menu, new OptionsDelegate(it), WatchUi.SLIDE_LEFT);
        } else {
            WatchUi.pushView(new DetailView(it), new DetailDelegate(it, true), WatchUi.SLIDE_LEFT);
        }
    }
}

class OptionsDelegate extends WatchUi.Menu2InputDelegate {
    var _ask;

    function initialize(ask) {
        Menu2InputDelegate.initialize();
        _ask = ask;
    }

    function onSelect(item) {
        var id = item.getId();
        if (id == -1) {
            WatchUi.pushView(new DetailView(_ask), new DetailDelegate(_ask, false), WatchUi.SLIDE_LEFT);
            return;
        }
        Inbox.reply(_ask, id);
        WatchUi.popView(WatchUi.SLIDE_RIGHT);   // options
        WatchUi.popView(WatchUi.SLIDE_RIGHT);   // inbox list
    }
}

class DetailView extends WatchUi.View {
    var _item;

    function initialize(item) {
        View.initialize();
        _item = item;
    }

    function onUpdate(dc) {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var w = dc.getWidth();
        var h = dc.getHeight();
        var lines = Ui.wrap(dc, _item["t"], Graphics.FONT_XTINY, w * 0.8, 6);
        var y = h * 0.28;
        for (var i = 0; i < lines.size(); i++) {
            dc.drawText(w / 2, y + i * h * 0.1, Graphics.FONT_XTINY, lines[i], Ui.CENTER);
        }
    }
}

class DetailDelegate extends WatchUi.BehaviorDelegate {
    var _item;
    var _dismissable;

    function initialize(item, dismissable) {
        BehaviorDelegate.initialize();
        _item = item;
        _dismissable = dismissable;
    }

    // START on a done/err item dismisses it; on an ask it just goes back.
    function onSelect() {
        if (_dismissable) {
            Inbox.dismiss(_item);
            WatchUi.popView(WatchUi.SLIDE_RIGHT);
        }
        WatchUi.popView(WatchUi.SLIDE_RIGHT);
        return true;
    }
}
