import Toybox.Background;
import Toybox.Lang;
import Toybox.System;

// Runs when a phone message arrives while the app is closed.
(:background)
class SageBg extends System.ServiceDelegate {

    function initialize() {
        ServiceDelegate.initialize();
    }

    function onPhoneAppMessage(msg) {
        var d = msg.data;
        if (d instanceof Dictionary) {
            var k = d["k"];
            if ("ask".equals(k) || "err".equals(k)) {
                var t = d["t"];
                var s = (t instanceof String) ? t : "StoneSage";
                if (s.length() > 60) {
                    s = s.substring(0, 60);
                }
                // Prompt limit is 255 bytes; the dialog shows after exit().
                Background.requestApplicationWake(("ask".equals(k) ? "Ask: " : "Error: ") + s);
            }
        }
        Background.exit(d);
    }
}
