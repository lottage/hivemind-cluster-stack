import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

module Ui {
    const CENTER = Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER;

    // Word-wrap into at most maxLines lines of width maxW.
    function wrap(dc, text, font, maxW, maxLines) {
        var lines = [];
        if (text == null) {
            return lines;
        }
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
                if (line.length() > 0) {
                    lines.add(line);
                }
                line = word;
            }
        }
        if (line.length() > 0 && lines.size() < maxLines) {
            lines.add(line);
        }
        return lines;
    }

    function clip(s, n) {
        if (s == null) {
            return "";
        }
        s = s.toString();
        return s.length() <= n ? s : s.substring(0, n);
    }

    // Instinct 2 round subscreen (top-right); null on devices without one.
    function subscreen() {
        return (WatchUi has :getSubscreen) ? WatchUi.getSubscreen() : null;
    }
}
