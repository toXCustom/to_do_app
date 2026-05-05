"""
gui/ttkbs_compat.py
===================
Must be imported BEFORE ttkbootstrap to capture the original
ttk.Frame.__init__. Used by the Calendar shim in app.py to temporarily
bypass ttkbootstrap's monkey-patch when constructing tkcalendar widgets.
"""
 
import tkinter.ttk as ttk
 
# Capture BEFORE ttkbootstrap is imported and patches it
ORIG_FRAME_INIT = ttk.Frame.__init__