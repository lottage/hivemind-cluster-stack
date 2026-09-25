import Toybox.Activity;
import Toybox.ActivityMonitor;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;

// Every metric the slots can show. IDs are the contract with settings + PROTOCOL.md.
module Metrics {
    const NONE = 0;
    const TIME = 1;
    const DATE = 2;
    const BATTERY = 3;
    const STEPS = 4;
    const HR = 5;
    const TOK = 6;
    const USD = 7;
    const BUD = 8;
    const LTK = 9;
    const LSH = 10;
    const ASKS = 11;
    const NOTIF = 12;
    const AGE = 13;
    const MTD = 14;

    function label(id) {
        switch (id) {
            case BATTERY: return "BAT";
            case STEPS: return "STP";
            case HR: return "HR";
            case TOK: return "TOK";
            case USD: return "DAY";
            case BUD: return "BUD";
            case LTK: return "LOC";
            case LSH: return "L%";
            case ASKS: return "ASK";
            case NOTIF: return "MSG";
            case AGE: return "UPD";
            case MTD: return "MTD";
            default: return "";
        }
    }

    function value(id, use, st) {
        if (id == TIME) { return timeStr(); }
        if (id == DATE) {
            var info = Gregorian.info(Time.now(), Time.FORMAT_MEDIUM);
            return info.day_of_week.toString().toUpper() + " " + info.day;
        }
        if (id == BATTERY) { return System.getSystemStats().battery.toNumber() + "%"; }
        if (id == STEPS) {
            var am = ActivityMonitor.getInfo();
            return (am.steps == null) ? "--" : am.steps.toString();
        }
        if (id == HR) {
            var ai = Activity.getActivityInfo();
            var hr = (ai != null) ? ai.currentHeartRate : null;
            return (hr == null) ? "--" : hr.toString();
        }
        if (id == TOK) { return big(use["tok"]); }
        if (id == USD) { return money(use["usd"]); }
        if (id == MTD) { return money(use["mtd"]); }
        if (id == BUD) { return pct(use["bud"]); }
        if (id == LTK) { return big(use["ltk"]); }
        if (id == LSH) { return pct(use["lsh"]); }
        if (id == ASKS) { return (st == null || st["q"] == null) ? "--" : st["q"].toString(); }
        if (id == NOTIF) { return System.getDeviceSettings().notificationCount.toString(); }
        if (id == AGE) {
            var a = FaceData.ageMin();
            return (a == null) ? "--" : (a < 60 ? a + "m" : (a / 60) + "h");
        }
        return null;   // NONE or unknown
    }

    function timeStr() {
        var ct = System.getClockTime();
        var h = ct.hour;
        if (!System.getDeviceSettings().is24Hour) {
            h = h % 12;
            if (h == 0) { h = 12; }
        }
        return h + ":" + ct.min.format("%02d");
    }

    function big(v) {
        if (v == null) { return "--"; }
        var n = v.toFloat();
        if (n >= 1000000.0) { return (n / 1000000.0).format("%.1f") + "M"; }
        if (n >= 10000.0) { return (n / 1000.0).toNumber() + "k"; }
        if (n >= 1000.0) { return (n / 1000.0).format("%.1f") + "k"; }
        return n.toNumber().toString();
    }

    function money(v) {
        if (v == null) { return "--"; }
        var n = v.toFloat();
        return "$" + (n < 100.0 ? n.format("%.2f") : n.toNumber().toString());
    }

    function pct(v) {
        return (v == null) ? "--" : v.toNumber() + "%";
    }
}
