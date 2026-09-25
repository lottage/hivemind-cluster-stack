import Toybox.Application;
import Toybox.Background;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;

(:background)
class FaceBg extends System.ServiceDelegate {

    function initialize() {
        ServiceDelegate.initialize();
    }

    // Pushed st/use/cfg frames from the companion.
    function onPhoneAppMessage(msg) {
        Background.exit(msg.data);
    }

    // Fallback poll through the phone (needs Tailscale up on the phone).
    function onTemporalEvent() {
        var url = Application.Properties.getValue("bridgeUrl");
        var tok = Application.Properties.getValue("readToken");
        if (url == null || url.length() == 0) {
            Background.exit(null);
            return;
        }
        Communications.makeWebRequest(
            url + "/watch/snapshot",
            null,
            {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :headers => {"Authorization" => "Bearer " + tok},
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
            },
            method(:onSnapshot)
        );
    }

    function onSnapshot(code, data) {
        Background.exit(code == 200 ? data : null);
    }
}
