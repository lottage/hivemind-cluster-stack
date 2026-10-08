import Toybox.Application;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Math;
import Toybox.System;
import Toybox.WatchUi;

// Dense, row-stacked layout (closer to commercial "data" watch faces like
// Geektime): every row is laid out with real measured font heights, never
// guessed fractions of screen height, so rows can't overlap regardless of
// content. All secondary text uses the custom Micro 5 font resource
// (Rez.Fonts.MicroFive, resources/fonts/) -- Connect IQ's smallest system
// font (FONT_XTINY) still wasn't small/thin enough; Micro 5 (Google Fonts,
// OFL) is purpose-built to stay legible at tiny sizes. Compiled into a real
// font resource via a generated BMFont atlas (resources/fonts/micro5.fnt +
// .png), not hand-drawn pixels -- see resources/fonts/ for how it was made.
// Fixed (never configurable): link status, battery, steps, HR, date, big
// time (kept on a system font -- it's the one thing meant to stay big and
// prominent). Configurable from the phone (Garmin Connect settings, same as
// any other watch face): the subscreen ring and a 2-metric data row -- any
// of the 16 metrics in Metrics.mc.
// Lower half, top: an agent/project/node glyph roster (auto-learned from
// whatever project names the bridge has ever sent), running = outline glyph,
// not currently running = "negative" (color-inverted, filled) glyph. Below
// that: the currently-focused agent's detail (rotates each minute if enabled).
class FaceView extends WatchUi.WatchFace {
    const CENTER = Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER;
    const LEFT_V = Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER;
    const NUMERIC = "0123456789:.";

    var _sub = null;
    var _tinyF = null;
    var _iconF = null;
    var _iconBigF = null;

    function initialize() {
        WatchFace.initialize();
    }

    function onLayout(dc) {
        _sub = (WatchUi has :getSubscreen) ? WatchUi.getSubscreen() : null;
        _tinyF = WatchUi.loadResource(Rez.Fonts.MicroFive);
        _iconF = WatchUi.loadResource(Rez.Fonts.Icons);
        _iconBigF = WatchUi.loadResource(Rez.Fonts.IconBig);
    }

    function onUpdate(dc) {
        var w = dc.getWidth();
        var h = dc.getHeight();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        var use = FaceData.use();
        var st = FaceData.st();
        var tinyF = _tinyF;
        var tinyH = Graphics.getFontHeight(tinyF);

        // Subscreen geometry (fallback: top-right third on devices without one).
        var sx = (_sub != null) ? _sub.x : (w * 0.64).toNumber();
        var sy = (_sub != null) ? _sub.y : 0;
        var sw = (_sub != null) ? _sub.width : w - sx;
        var shh = (_sub != null) ? _sub.height : (h * 0.36).toNumber();
        var leftCx = (sx + 8) / 2;
        var leftW = sx - 12;

        // Rows this close to the top edge sit inside the round bezel's curve,
        // which cuts into the left column more than the flat sx-based rect
        // above accounts for -- that flat leftW was clipping the last digits
        // of calories off the visible circle. Same halfWidthAt() used below
        // for the roster row, just applied here too.
        var y = 6;
        var topCy = y + tinyH / 2;
        drawTopRow(dc, leftColCx(w, h, sx, topCy), leftColWidth(w, h, sx, topCy), y, tinyF, tinyH);
        y += tinyH + 1;
        var healthCy = y + tinyH / 2;
        drawHealthRow(dc, leftColCx(w, h, sx, healthCy), leftColWidth(w, h, sx, healthCy), y, tinyF, tinyH);
        y += tinyH + 1;

        // Plain text, no icon -- just the date, directly above the time.
        dc.drawText(leftCx, y + tinyH / 2, tinyF, Metrics.value(Metrics.DATE, use, st), CENTER);
        y += tinyH + 1;

        var timeStr = Metrics.value(Metrics.TIME, use, st);
        var f = fit(dc, timeStr, leftW);
        var timeH = Graphics.getFontHeight(f);
        dc.drawText(leftCx, y + timeH / 2, f, timeStr, CENTER);
        y += timeH + 3;

        // Configurable: ring (slot 2), 2 data rows (slots 4/5, 6/7).
        drawSlot(dc, 2, sx + sw / 2, sy + shh / 2, sw - 6, use, st, true, tinyF);
        drawSlot(dc, 4, w * 0.29, y + tinyH / 2, w * 0.44, use, st, false, tinyF);
        drawSlot(dc, 5, w * 0.71, y + tinyH / 2, w * 0.44, use, st, false, tinyF);
        y += tinyH + 8;
        drawSlot(dc, 6, w * 0.29, y + tinyH / 2, w * 0.44, use, st, false, tinyF);
        drawSlot(dc, 7, w * 0.71, y + tinyH / 2, w * 0.44, use, st, false, tinyF);
        y += tinyH + 10;

        dc.drawLine(w * 0.08, y, w * 0.92, y);
        drawStatus(dc, w, h, y, st, tinyF, tinyH);
    }

    // Row 1: link status (device <-> bridge) + battery. Filled = connected/
    // fresh (<20m), outline (grayed) = stale or no link.
    function drawTopRow(dc, leftCx, leftW, y, font, fontH) {
        var cy = (y + fontH / 2).toNumber();
        var age = FaceData.ageMin();
        var linkOk = (age != null && age < 20);

        var r = 5;
        var iconGap = 3;
        var colGap = 8;
        var battVal = Metrics.value(Metrics.BATTERY, {}, null);

        var itemW0 = r * 2;
        var itemW1 = r * 2 + iconGap + dc.getTextWidthInPixels(battVal, font);
        var totalW = itemW0 + colGap + itemW1;

        var x = leftCx - totalW / 2;
        if (!linkOk) {
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        }
        dc.drawText(x + r, cy, _iconF, "l", CENTER);
        if (!linkOk) {
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        }
        x += itemW0 + colGap;
        drawIcon(dc, Metrics.BATTERY, x + r, cy, r, {});
        dc.drawText(x + r * 2 + iconGap, cy, font, battVal, LEFT_V);
    }

    // Row 2: steps, heart rate -- confined to the left column (leftCx/leftW),
    // same as everything else above the ring's height, since the subscreen
    // ring physically occupies the top-right corner up here. Calories was
    // dropped from this fixed row (2026-09-27, John: "looks a bit shit with
    // all the overlap") -- it's still pickable in a configurable data slot
    // via Metrics.CAL for anyone who wants it there instead.
    function drawHealthRow(dc, leftCx, leftW, y, font, fontH) {
        var cy = (y + fontH / 2).toNumber();
        var r = 5;
        var iconGap = 3;
        var colGap = 8;

        var ids = [Metrics.STEPS, Metrics.HR];
        var vals = [Metrics.value(Metrics.STEPS, {}, null), Metrics.value(Metrics.HR, {}, null)];

        var n = ids.size();
        var itemW = new [n];
        var contentW = 0;
        for (var i = 0; i < n; i++) {
            itemW[i] = r * 2 + iconGap + dc.getTextWidthInPixels(vals[i], font);
            contentW += itemW[i];
        }
        var totalW = contentW + colGap * (n - 1);

        if (totalW > leftW && n > 1) {
            colGap = ((leftW - contentW) / (n - 1)).toNumber();
            if (colGap < 2) { colGap = 2; }
            totalW = contentW + colGap * (n - 1);
        }

        var x = leftCx - totalW / 2;
        for (var i = 0; i < n; i++) {
            drawIcon(dc, ids[i], x + r, cy, r, {});
            dc.drawText(x + r * 2 + iconGap, cy, font, vals[i], LEFT_V);
            x += itemW[i] + colGap;
        }
    }

    function drawSlot(dc, i, cx, cy, maxW, use, st, stacked, font) {
        var id = FaceData.slot(i);
        var v = Metrics.value(id, use, st);
        drawMetric(dc, id, v, cx, cy, maxW, stacked, use, font);
    }

    function drawMetric(dc, id, v, cx, cy, maxW, stacked, use, font) {
        if (v == null) {
            return;
        }
        if (stacked) {
            // Center the icon+value stack around cy using real metrics --
            // this used to be hardcoded offsets tuned for a bigger font and
            // drifted off-center once the text shrank to the tiny font.
            var iconR = 8;
            var gap = 2;
            var fontH = Graphics.getFontHeight(font);
            var totalH = iconR * 2 + gap + fontH;
            var topY = cy - totalH / 2;
            drawIcon(dc, id, cx, topY + iconR, iconR, use);
            dc.drawText(cx, topY + iconR * 2 + gap + fontH / 2, font, v, CENTER);
            return;
        }

        var iconR = 6;
        var gap = 4;
        var tw = dc.getTextWidthInPixels(v, font);
        var totalW = iconR * 2 + gap + tw;
        var startX = cx - totalW / 2;
        drawIcon(dc, id, startX + iconR, cy, iconR, use);
        dc.drawText(startX + iconR * 2 + gap, cy, font, v, LEFT_V);
    }

    // Real icon glyphs (Material Icons subset, resources/fonts/icons.fnt) for
    // everything with a fixed meaning. BUD/LSH stay hand-drawn: an arc gauge
    // showing an actual live percentage isn't a fixed icon, it's a chart.
    function drawIcon(dc, id, cx, cy, r, use) {
        if (id == Metrics.BUD || id == Metrics.LSH) {
            var v = (id == Metrics.BUD) ? use["bud"] : use["lsh"];
            var frac = (v == null) ? 0.0 : (v.toFloat() / 100.0);
            dc.drawCircle(cx, cy, r);
            dc.setPenWidth(2);
            dc.drawArc(cx, cy, r, Graphics.ARC_CLOCKWISE, 90, (90 - frac * 360).toNumber());
            dc.setPenWidth(1);
            return;
        }
        var glyph = iconGlyph(id);
        if (glyph != null) {
            dc.drawText(cx, cy, _iconF, glyph, CENTER);
        }
        // TIME or anything unmapped: no icon, value speaks for itself.
    }

    function iconGlyph(id) {
        if (id == Metrics.DATE) { return "d"; }
        if (id == Metrics.BATTERY) { return "b"; }
        if (id == Metrics.HR) { return "h"; }
        if (id == Metrics.STEPS) { return "w"; }
        if (id == Metrics.CAL) { return "c"; }
        if (id == Metrics.TOK) { return "t"; }
        if (id == Metrics.LTK) { return "m"; }
        if (id == Metrics.USD || id == Metrics.MTD) { return "$"; }
        if (id == Metrics.ASKS || id == Metrics.NOTIF || id == Metrics.ALL_PENDING) { return "n"; }
        if (id == Metrics.AGE) { return "a"; }
        if (id == Metrics.TPS) { return "s"; }
        return null;
    }

    // Largest font that fits; numeric fonts only for digit/colon strings.
    // Kept on system fonts deliberately -- the big clock is the one thing
    // meant to stay large and prominent, not shrunk to the tiny font.
    function fit(dc, s, maxW) {
        var fonts = isNumeric(s)
            ? [Graphics.FONT_NUMBER_MEDIUM, Graphics.FONT_LARGE, Graphics.FONT_MEDIUM, Graphics.FONT_SMALL]
            : [Graphics.FONT_LARGE, Graphics.FONT_MEDIUM, Graphics.FONT_SMALL, Graphics.FONT_XTINY];
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

    // Lower half, top: glyph roster (every known project, at a glance).
    // Below: the currently-focused agent's name + state + progress only --
    // no task-description text (it overlapped everything below it; the
    // glyph + name already says what's running).
    // Laid out with real measured font heights, not guessed fractions of h,
    // so lines can't overlap regardless of how much content is present, and
    // starting from the divider's actual (dynamic) y, not a fixed h/2.
    function drawStatus(dc, w, h, dividerY, st, font, fontH) {
        var age = FaceData.ageMin();
        var agents = (st != null && st["a"] instanceof Array) ? st["a"] : [];

        var y = dividerY + 12;
        var rosterR = 15;
        var rosterCy = y + rosterR;
        drawRoster(dc, w, h, rosterCy, agents, font);
        y = rosterCy + rosterR + 14;

        if (agents.size() == 0) {
            dc.drawText(w / 2, y + fontH / 2, font, (st == null) ? "NO LINK" : "IDLE", CENTER);
            y += fontH + 8;
            drawFreshness(dc, w / 2, y + fontH / 2, age, font);
            return;
        }

        var idx = 0;
        if (Application.Properties.getValue("rotateAgents") == true && agents.size() > 1) {
            idx = System.getClockTime().min % agents.size();
        }
        var a = agents[idx];

        var name = Ui2.clip(a["p"], 12);
        if (agents.size() > 1) {
            name = name + " " + (idx + 1) + "/" + agents.size();
        }
        var glyphR = 5;
        var nameY = y + fontH / 2;
        var nameW = dc.getTextWidthInPixels(name, font);
        var headStartX = w / 2 - (glyphR * 2 + 3 + nameW) / 2;
        drawAgentGlyph(dc, a["s"], headStartX + glyphR, nameY, glyphR, font);
        dc.drawText(headStartX + glyphR * 2 + 3, nameY, font, name, LEFT_V);
        y += fontH + 10;

        var pr = a["pr"];
        if (pr != null) {
            var bw = (w * 0.6).toNumber();
            var bx = (w - bw) / 2;
            dc.drawRectangle(bx, y, bw, 6);
            dc.fillRectangle(bx, y, (bw * pr.toNumber() / 100), 6);
            y += 6 + 10;
        }

        var q = (st["q"] != null) ? st["q"] : 0;
        if (q > 0) {
            dc.drawText(w / 2, y + fontH / 2, font, q + " ASK", CENTER);
        } else {
            drawFreshness(dc, w / 2, y + fontH / 2, age, font);
        }
    }

    // Max half-width of content centered at (w/2, y) that stays inside the round
    // bezel -- the display is a circle, so a row near the top/bottom edge has far
    // less usable width than one at vertical center. Never lay out with flat w/N
    // column math without checking this first.
    function halfWidthAt(w, h, y) {
        var r = w / 2.0;
        var dy = (y - h / 2.0).abs();
        if (dy >= r) { return 0; }
        return Math.sqrt(r * r - dy * dy);
    }

    // Left column (left of the subscreen) clamped to the bezel's actual curve
    // at height y, not just "everything left of sx" -- near the top/bottom
    // edge the circle pulls in from the left well before x=0.
    function leftEdgeAt(w, h, y) {
        var edge = w / 2.0 - halfWidthAt(w, h, y);
        return (edge > 0) ? edge : 0;
    }

    function leftColWidth(w, h, sx, y) {
        var width = (sx - 6) - leftEdgeAt(w, h, y);
        return (width > 0) ? width.toNumber() : 0;
    }

    function leftColCx(w, h, sx, y) {
        return ((leftEdgeAt(w, h, y) + (sx - 6)) / 2).toNumber();
    }

    // One glyph per project/agent/node name the bridge has ever reported
    // (FaceData.roster(), learned automatically -- see FaceData.noteAgents).
    // Running right now = normal outline glyph, matching the rest of the
    // face. Not in the latest status push (or idle) = "negative" glyph:
    // colors inverted (solid fill, punched-out letter) so it visually
    // recedes instead of competing with what's actually running.
    function drawRoster(dc, w, h, cy, agents, font) {
        var names = FaceData.roster();
        if (names.size() == 0) {
            return;
        }

        var activeNames = {};
        for (var i = 0; i < agents.size(); i++) {
            var p = agents[i]["p"];
            var s = agents[i]["s"];
            if (p != null && !"idle".equals(s)) {
                activeNames[p] = true;
            }
        }

        var r = 13;
        var gap = 6;
        var n = names.size();
        var totalW = n * (r * 2) + (n - 1) * gap;
        var maxW = (2 * halfWidthAt(w, h, cy) * 0.92).toNumber();
        if (totalW > maxW && n > 1) {
            gap = ((maxW - n * r * 2) / (n - 1)).toNumber();
            if (gap < 2) { gap = 2; }
            totalW = n * (r * 2) + (n - 1) * gap;
        }

        var x = w / 2 - totalW / 2;
        for (var i = 0; i < n; i++) {
            var name = names[i];
            var active = activeNames[name] == true;
            drawGlyph(dc, x + r, cy, r, active);
            x += r * 2 + gap;
        }
    }

    // One generic "agent" icon (robot head) per known project/node -- running
    // = the real Material Icons filled glyph, not running = the real Material
    // Icons Outlined variant of the same glyph (hollow, black infill) -- two
    // actual icon styles, not a color-invert trick.
    function drawGlyph(dc, cx, cy, r, active) {
        dc.drawCircle(cx, cy, r);
        dc.drawText(cx, cy, _iconBigF, active ? "r" : "R", CENTER);
    }

    // Small filled/hollow dot before the freshness text: filled = fresh (<20m), hollow = stale/no data.
    function drawFreshness(dc, cx, cy, age, font) {
        var text = (age == null) ? "no data" : (age >= 20 ? "STALE " + freshAge(age) : freshAge(age) + " ago");
        var tw = dc.getTextWidthInPixels(text, font);
        var r = 3;
        var startX = cx - (r * 2 + 3 + tw) / 2;
        if (age != null && age < 20) {
            dc.fillCircle(startX + r, cy, r);
        } else {
            dc.drawCircle(startX + r, cy, r);
        }
        dc.drawText(startX + r * 2 + 3, cy, font, text, LEFT_V);
    }

    function freshAge(age) {
        return age < 60 ? age + "m" : (age / 60) + "h";
    }

    // Icon glyph per agent state ("idle" has no icon in the set -- a plain
    // dash reads fine for "nothing to report" and doesn't need an icon).
    function drawAgentGlyph(dc, s, cx, cy, r, font) {
        if ("run".equals(s)) {
            dc.drawText(cx, cy, _iconF, "p", CENTER);
        } else if ("wait".equals(s)) {
            dc.drawText(cx, cy, _iconF, "o", CENTER);
        } else if ("err".equals(s)) {
            dc.drawText(cx, cy, _iconF, "e", CENTER);
        } else if ("done".equals(s)) {
            dc.drawText(cx, cy, _iconF, "k", CENTER);
        } else {
            dc.drawLine(cx - r, cy, cx + r, cy);
        }
    }
}

// Small text helpers (the face is a separate app from watch-app, so no shared Ui module).
module Ui2 {
    function clip(s, n) {
        if (s == null) { return ""; }
        s = s.toString();
        return s.length() <= n ? s : s.substring(0, n);
    }
}
