import Toybox.Application;
import Toybox.Background;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

// Entry point. Annotated (:background) so the service delegate can load it.
(:background)
class SageApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function getServiceDelegate() {
        return [new SageBg()];
    }

    function getInitialView() {
        // Wake us (via SageBg) whenever the phone sends a message while closed.
        Background.registerForPhoneAppMessageEvent();
        // While open, messages arrive here directly.
        Communications.registerForPhoneAppMessages(method(:onPhoneMsg));
        // Background.exit keeps only the latest message, so ask the bridge to
        // resend everything still pending.
        Inbox.requestSync();
        return [new InboxView(), new InboxDelegate()];
    }

    function onPhoneMsg(msg) {
        Inbox.ingest(msg.data, true);
        WatchUi.requestUpdate();
    }

    function onBackgroundData(data) {
        Inbox.ingest(data, false);
        WatchUi.requestUpdate();
    }
}
