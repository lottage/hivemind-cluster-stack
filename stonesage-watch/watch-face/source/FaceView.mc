import Toybox.Application;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

// Upper half: 5 configurable metric slots. Lower half: agent/project status (fixed).
class FaceView extends WatchUi.WatchFace {
    const CENTER = Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER;
    const NUMERIC = "0123456789:.";

    var _sub = null;

    function initialize() {
        WatchFace.initialize();
    }

    function onLayout(dc) {
        _sub = (WatchUi has :getSubscreen) ? WatchUi.getSubscreen() : null;
    }

    function onUpdate(dc) {
        var w = dc.getWidth();
        var h = dc.getHeight();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        var use = FaceData.use();
        var st = FaceData.st();

        // Subscreen geometry (fallback: top-right third on devices without one).
        var sx = (_sub != null) ? _sub.x : (w * 0.64).toNumber();
        var sy = (_sub != null) ? _sub.y : 0;
        var sw = (_sub != null) ? _sub.width : w - sx;
        var shh = (_sub != null) ? _sub.height : (h * 0.36).toNumber();
        var leftCx = (sx + 8) / 2;

        // Slot 1: big, top-left
        var v1 = Metrics.value(FaceData.slot(1), use, st);
        if (v1 != null) {
            var f = fit(dc, v1, sx - 12);
            dc.drawText(leftCx, h * 0.17, f, v1, CENTER);
        }
        // Slot 2: subscreen circle
        drawSlot(dc, 2, sx + sw / 2, sy + shh / 2, sw - 6, use, st, true);
        // Slot 3: under the big slot, left of the subscreen
        drawSlot(dc, 3, leftCx, h * 0.31, sx - 12, use, st, false);
        // Slots 4 & 5: full-width row just above the divider
        drawSlot(dc, 4, w * 0.29, h * 0.42, w * 0.44, use, st, false);
        drawSlot(dc, 5, w * 0.71, h * 0.42, w * 0.44, use, st, false);

        dc.drawLine(w * 0.08, h / 2, w * 0.92, h / 2);
        drawStatus(dc, w, h, st);
    }

    function drawSlot(dc, i, cx, cy, maxW, use, st, stacked) {
        var id = FaceData.slot(i);
        var v = Metrics.value(id, use, st);
        if (v == null) {
            return;
        }
        var lbl = Metrics.label(id);
        if (stacked) {
            if (lbl.length() > 0) {
                dc.drawText(cx, cy - 13, Graphics.FONT_XTINY, lbl, CENTER);
                dc.drawText(cx, cy + 7, Graphics.FONT_TINY, v, CENTER);
            } else {
                dc.drawText(cx, cy, Graphics.FONT_TINY, v, CENTER);
            }
            return;
        }
        var text = (lbl.length() > 0) ? lbl + " " + v : v;
        var font = Graphics.FONT_TINY;
        if (dc.getTextWidthInPixels(text, font) > maxW) {
            font = Graphics.FONT_XTINY;
        }
        dc.drawText(cx, cy, font, text, CENTER);
    }

    // Largest font that fits; numeric fonts only for digit/colon strings.
    function fit(dc, s, maxW) {
        var fonts = isNumeric(s)
            ? [Graphics.FONT_NUMBER_MEDIUM, Graphics.FONT_LARGE, Graphics.FONT_MEDIUM, Graphics.FONT_SMALL]
            : [Graphics.FONT_LARGE, Graphics.FONT_MEDIUM, Graphics.FONT_SMALL, Graphics.FONT_TINY];
        for (var i = 0; i < fonts.size(); i++) {
            if (dc.getTextWidthInPixels(s, fonts[i]) <= maxW) {
                return fonts[i];
            }
        }
        return Graphics.FONT_XTINY;
    }

    function isNumeric(s) {
        var chars = s.toCharArray();
        for (var i = 0; i < chars.size(); i++) {
            if (NUMERIC.find(chars[i].toString()) == null) {
                return false;
            }
        }
        return true;
    }

    // Lower half: focused agent, its status text, progress, pending asks + freshness.
    function drawStatus(dc, w, h, st) {
        var age = FaceData.ageMin();
        var agents = (st != null && st["a"] instanceof Array) ? st["a"] : [];
        if (agents.size() == 0) {
            dc.drawText(w / 2, h * 0.64, Graphics.FONT_TINY, (st == null) ? "NO LINK" : "IDLE", CENTER);
            dc.drawText(w / 2, h * 0.82, Graphics.FONT_XTINY, freshness(age), CENTER);
            return;
        }

        var idx = 0;
        if (Application.Properties.getValue("rotateAgents") == true && agents.size() > 1) {
            idx = System.getClockTime().min % agents.size();
        }
        var a = agents[idx];

        var head = glyph(a["s"]) + " " + Ui2.clip(a["p"], 12);
        if (agents.size() > 1) {
            head = head + "  " + (idx + 1) + "/" + agents.size();
        }
        dc.drawText(w / 2, h * 0.57, Graphics.FONT_TINY, head, CENTER);

        var lines = Ui2.wrap(dc, a["t"], Graphics.FONT_XTINY, w * 0.8, 2);
        for (var i = 0; i < lines.size(); i++) {
            dc.drawText(w / 2, h * 0.67 + i * h * 0.075, Graphics.FONT_XTINY, lines[i], CENTER);
        }

        var pr = a["pr"];
        if (pr != null) {
            var bw = (w * 0.56).toNumber();
            var bx = (w - bw) / 2;
            var by = (h * 0.81).toNumber();
            dc.drawRectangle(bx, by, bw, 7);
            dc.fillRectangle(bx, by, (bw * pr.toNumber() / 100), 7);
        }

        var q = (st["q"] != null) ? st["q"] : 0;
        var foot = (q > 0) ? q + " ASK  " + freshness(age) : freshness(age);
        dc.drawText(w / 2, h * 0.9, Graphics.FONT_XTINY, foot, CENTER);
    }

    function glyph(s) {
        if ("wait".equals(s)) { return "?"; }
        if ("err".equals(s)) { return "!"; }
        if ("run".equals(s)) { return ">"; }
        if ("done".equals(s)) { return "="; }
        return "-";
    }

    function freshness(age) {
        if (age == null) { return "no data"; }
        if (age >= 20) { return "STALE " + (age < 60 ? age + "m" : (age / 60) + "h"); }
        return age + "m ago";
    }
}

// Small text helpers (the face is a separate app from watch-app, so no shared Ui module).
module Ui2 {
    function clip(s, n) {
        if (s == null) { return ""; }
        s = s.toString();
        return s.length() <= n ? s : s.substring(0, n);
    }

    function wrap(dc, text, font, maxW, maxLines) {
        var lines = [];
        if (text == null) { return lines; }
        var rest = text.toString();
        var line = "";
        while (rest.length() > 0 && lines.size() < maxLines) {
            var sp = rest.find(" ");
            var word = (sp == null) ? rest : rest.substring(0, sp);
            rest = (sp == null) ? "" : rest.substring(sp + 1, rest.length());
            var cand = (line.length() == 0) ? word : line + " " + word;
            if (dc.getTextWidthInPixels(cand, font) <= maxW) {
                line = cand;
            } else {
                if (line.length() > 0) { lines.add(line); }
                line = word;
            }
        }
        if (line.length() > 0 && lines.size() < maxLines) { lines.add(line); }
        return lines;
    }
}
