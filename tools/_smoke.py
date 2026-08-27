# -*- coding: utf-8 -*-
"""Arayuzu gorunmez sekilde ayaga kaldirip hata olup olmadigina bakar."""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cf_ui as ui  # noqa: E402
import ClearFast  # noqa: E402

errors = []
ui.enable_dpi_awareness()
app = ClearFast.ClearFastApp()
app.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a)))

deadline = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 6)
while time.time() < deadline:
    app.update()
    time.sleep(0.02)

print("secim ozeti:", app.cleaner_page.stat_found.value.cget("text"),
      "| satir:", len(app.cleaner_page.rows),
      "| secili:", len(app.cleaner_page.checked))
print("pencere:", app.winfo_width(), "x", app.winfo_height(), "| olcek:", round(ui.px(100) / 100, 2))
app.destroy()
if errors:
    print("HATA SAYISI:", len(errors))
    print(errors[0])
    sys.exit(1)
print("TAMAM - hata yok")
