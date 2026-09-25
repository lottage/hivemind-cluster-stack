import Toybox.Application;
import Toybox.Background;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.WatchUi;

(:background)
class FaceApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        if (Toybox has :Background) {
            // Push path: companion -> phone message -> FaceBg.
            if (Background has :registerForPhoneAppMessageEvent) {
                Background.registerForPhoneAppMessageEvent();
            }
            // Fallback: poll the bridge snapshot every 5 min (the platform minimum).
            Background.registerForTemporalEvent(new Time.Duration(5 * 60));
        }
        return [new FaceView()];
    }

    function getServiceDelegate() {
        return [new FaceBg()];
    }

    function onBackgroundData(data) {
        FaceData.ingest(data);
        WatchUi.requestUpdate();
    }

    function onSettingsChanged() {
        WatchUi.requestUpdate();
    }
}
