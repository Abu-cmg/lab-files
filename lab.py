import os
import sys
import threading

# VM / rendering safety: prefer CPU raster painting in VMs to avoid partial redraws
# Only enable these aggressive fallbacks when running on Linux VMs or when
# explicitly requested via RUNNING_IN_VM=1 or FORCE_RASTER=1 environment variable.
_force_raster = os.environ.get('FORCE_RASTER', os.environ.get('RUNNING_IN_VM', '0')) == '1' or (sys.platform.startswith('linux') and os.environ.get('RUNNING_IN_VM', '0') == '1')
if _force_raster:
	# HARD disable GPU paths and force raster composition
	os.environ['QT_QPA_PLATFORM'] = os.environ.get('QT_QPA_PLATFORM', 'xcb')
	os.environ['QT_OPENGL'] = 'software'
	os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
	os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
	os.environ['QT_QUICK_BACKEND'] = 'software'
	os.environ['QT_GRAPHICSSYSTEM'] = 'raster'

# --- Auto-start Xvfb when no DISPLAY is present (helps when launching via SSH)
# This will try to start Xvfb on :99 and set DISPLAY so Qt can initialize.
_xvfb_proc = None

# Prevent concurrent elevation attempts which can trigger PolicyKit conflicts
_elev_lock = threading.Lock()
def ensure_display_via_xvfb(width=1280, height=720, depth=24, display=':99'):
	"""Start Xvfb if DISPLAY is not set. Returns True if a DISPLAY is available."""
	global _xvfb_proc
	if os.environ.get('DISPLAY'):
		return True
	try:
		import shutil, subprocess, atexit, time
	except Exception:
		return False

	xvfb_bin = shutil.which('Xvfb') or shutil.which('Xvfb')
	if not xvfb_bin:
		sys.stderr.write('No DISPLAY and Xvfb not found; GUI may be headless.\n')
		return False

	cmd = [xvfb_bin, display, '-screen', '0', f'{width}x{height}x{depth}']
	try:
		_xvfb_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		# give Xvfb a moment to start
		time.sleep(0.25)
		os.environ['DISPLAY'] = display
		sys.stderr.write(f'Started Xvfb on {display} (pid={_xvfb_proc.pid})\n')

		def _cleanup():
			global _xvfb_proc
			try:
				if _xvfb_proc and _xvfb_proc.poll() is None:
					_xvfb_proc.terminate()
					time.sleep(0.2)
					if _xvfb_proc.poll() is None:
						_xvfb_proc.kill()
			except Exception:
				pass

		atexit.register(_cleanup)
		return True
	except Exception as e:
		sys.stderr.write(f'Failed to start Xvfb: {e}\n')
		return False

# Try to ensure a display when running over SSH or in headless environments
_headless_display_ok = ensure_display_via_xvfb()

# If running on Linux, prefer the system Qt6 plugin directory (helps when PyQt/Pip mixes exist)
if sys.platform.startswith('linux'):
	sys_plugin_dir = '/usr/lib/x86_64-linux-gnu/qt6/plugins'
	if os.path.isdir(sys_plugin_dir):
		# prepend system plugin dir to QT_PLUGIN_PATH if not already present
		cur = os.environ.get('QT_PLUGIN_PATH', '')
		if sys_plugin_dir not in cur.split(os.pathsep):
			if cur:
				os.environ['QT_PLUGIN_PATH'] = sys_plugin_dir + os.pathsep + cur
			else:
				os.environ['QT_PLUGIN_PATH'] = sys_plugin_dir
		# ensure platform plugin path is set as well
		os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', sys_plugin_dir)
	# if a display exists, prefer xcb platform
	if os.environ.get('DISPLAY'):
		os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
	QLabel, QTextEdit, QProgressBar, QScrollArea, QGridLayout, QFrame, QSizePolicy,
	QMenuBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QPixmap, QPainter, QLinearGradient, QColor, QAction, QActionGroup, QKeySequence, QImage
import subprocess
import shutil
import tempfile
import urllib.request
import shlex
import stat
import time


LABS = {
	"Web – SQL Injection": ("web_sqli", "Practise SQLi against a vulnerable app."),
	"Web – File Upload": ("web_upload", "Exploit insecure file upload handling."),
	"Linux – Sudo PrivEsc": ("sudo_privesc", "Gain root via sudo misconfiguration."),
	"Web – XSS": ("web_xss", "Learn about XSS (Cross-Site Scripting) and how to defend against it."),
}

# Default scripts (can be overridden by env vars)
INSTALL_SCRIPT = os.environ.get("INSTALL_SCRIPT", "/usr/local/bin/install_lab.sh")
RESET_SCRIPT = os.environ.get("RESET_SCRIPT", "/opt/lab/reset_lab.sh")

# If a root user/password is provided
ROOT_USER = os.environ.get("ROOT_USER", "antori")

# Per-lab installer sources. Keys are the lab codes from `LABS` values.
# Values may be a URL to a shell installer (http/https) or None to use
# the default `INSTALL_SCRIPT` mechanism. Add more entries here.
LAB_INSTALLERS = {
	'web_sqli': 'https://raw.githubusercontent.com/Abu-cmg/lab-files/main/lab_web.sh.sh',
	# Example: 'web_upload': 'https://example.com/labs/web_upload/install.sh',
	# 'sudo_privesc': None,  # uses INSTALL_SCRIPT with arg
}



from PyQt6.QtWidgets import QGraphicsDropShadowEffect


class BannerWidget(QWidget):
	"""Widget that displays a banner image; supports zooming and a gradient fallback."""
	def __init__(self, image_path: str, height: int = 110, zoom: float = 1.0, parent=None):
		super().__init__(parent)
		self._image_path = image_path
		self._pixmap = None
		self._zoom = float(zoom) if zoom and zoom > 0 else 1.0
		try:
			if image_path:
				# attempt to load the pixmap and report failures to stderr for debugging
				if os.path.exists(image_path):
					pm = QPixmap(image_path)
					if pm and not pm.isNull():
						self._pixmap = pm
					else:
						# try explicit load and report
						pm2 = QPixmap()
						ok = pm2.load(image_path)
						if ok and not pm2.isNull():
							self._pixmap = pm2
						else:
							# QPixmap.load failed (likely missing imageformats plugin). Try Pillow fallback.
							try:
								from PIL import Image
								img = Image.open(image_path).convert('RGBA')
								w, h = img.size
								data = img.tobytes('raw', 'RGBA')
								# Create QImage from raw RGBA data and then QPixmap
								qimg = QImage(data, w, h, QImage.Format.Format_RGBA8888)
								if not qimg.isNull():
									self._pixmap = QPixmap.fromImage(qimg)
								else:
									sys.stderr.write(f"[WARN] Pillow produced QImage but it was null: {image_path}\n")
							except Exception as e:
								# Pillow fallback failed — report original warning
								sys.stderr.write(f"[WARN] Banner image found but failed to load via QPixmap and Pillow: {image_path} -> {e}\n")
				else:
					sys.stderr.write(f"[WARN] Banner image path does not exist: {image_path}\n")
		except Exception:
			self._pixmap = None
		# fixed height suitable for a banner strip; can be adjusted
		self.setFixedHeight(height)
		# create an internal label to display the pixmap (simpler and more reliable)
		try:
			from PyQt6.QtWidgets import QLabel
			self._label = QLabel(self)
			self._label.setScaledContents(False)
			self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
			# keep the label background transparent so our gradient shows through
			try:
				self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
			except Exception:
				pass
		except Exception:
			self._label = None
		# expand horizontally so it fills the window width
		try:
			from PyQt6.QtWidgets import QSizePolicy
			self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
		except Exception:
			pass

	def paintEvent(self, event):
		painter = QPainter(self)
		# Draw gradient background first
		try:
			grad = QLinearGradient(0, 0, self.width(), 0)
			grad.setColorAt(0.0, QColor(18,18,20))
			grad.setColorAt(1.0, QColor(28,28,32))
			painter.fillRect(self.rect(), grad)
		except Exception:
			pass
		# If a label has already painted the pixmap we don't need to draw it here.
		if not (hasattr(self, '_label') and self._label and self._label.pixmap()):
			# draw fallback title so banner is informative when no image present
			try:
				painter.setPen(QColor(200, 200, 210))
				title_font = QFont('Segoe UI', 18, QFont.Weight.DemiBold)
				painter.setFont(title_font)
				painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Vulnerable Lab Selector')
			except Exception:
				pass
		# subtle dark overlay to improve readability of UI elements below
		try:
			overlay = QColor(0, 0, 0, 64)  # ~25% opacity
			painter.fillRect(self.rect(), overlay)
		except Exception:
			pass
		painter.end()

	def resizeEvent(self, ev):
		super().resizeEvent(ev)
		# If we have a label and a loaded pixmap, scale it to the widget height
		try:
			if hasattr(self, '_label') and self._label and self._pixmap and not self._pixmap.isNull():
				target_h = max(8, self.height() - 8)
				scaled = self._pixmap.scaledToHeight(target_h, Qt.TransformationMode.SmoothTransformation)
				self._label.setPixmap(scaled)
				self._label.setGeometry(0, 0, self.width(), self.height())
			elif hasattr(self, '_label') and self._label:
				# ensure label is cleared when no pixmap to avoid covering fallback text
				self._label.clear()
		except Exception:
			pass


class CardWidget(QFrame):
	def __init__(self, name: str, desc: str, code: str, click_cb=None, parent=None):
		super().__init__(parent)
		self.name = name
		self.desc = desc
		self.code = code
		self.click_cb = click_cb
		self._selected = False

		# base/hover sizes for subtle scale-on-hover effect
		self._base_size = QSize(260, 140)
		self._hover_size = QSize(294, 150)
		# set sensible min/max so cards grow but do not stretch to fill the entire row
		self.setMinimumSize(self._base_size)
		# Prevent cards from stretching horizontally in fullscreen by using Preferred
		# horizontal policy and a modest maximum width.
		try:
			from PyQt6.QtWidgets import QSizePolicy as _SP
			self.setSizePolicy(_SP.Policy.Preferred, _SP.Policy.Fixed)
			self.setMaximumWidth(self._hover_size.width())
		except Exception:
			pass
		self.setCursor(Qt.CursorShape.PointingHandCursor)

		# Base style: rounded, subtle border
		# Dark card base and neon accent when selected
		self._base_style = (
			"QFrame{"
			"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #16151a, stop:1 #1e1b26);"
			"border-radius:12px;"
			"border:1px solid rgba(255,255,255,0.03);"
			"}")

		# Selected style: keep the same dark background, only change the outer border color
		self._selected_style = (
			"QFrame{"
			"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #16151a, stop:1 #1e1b26);"
			"border-radius:12px;"
			"border:2px solid #00ff99;"
			"}")

		self.setStyleSheet(self._base_style)

		# Shadow effect
		# Shadow effect: avoid using QGraphicsDropShadowEffect in VM / software GL modes
		_vm_safe_no_shadow = (os.environ.get('RUNNING_IN_VM', '0') == '1') or (os.environ.get('QT_OPENGL', '').lower() == 'software') or (os.environ.get('QT_QPA_PLATFORM') == 'offscreen')
		if _vm_safe_no_shadow:
			# fallback: emulate an outer border to keep a similar visual without GPU effects
			self.setStyleSheet(self._base_style + "border:1px solid rgba(0,0,0,0.2);")
		else:
			self._shadow = QGraphicsDropShadowEffect(self)
			self._shadow.setBlurRadius(8)
			self._shadow.setXOffset(0)
			self._shadow.setYOffset(2)
			self._shadow.setColor(Qt.GlobalColor.black)
			self.setGraphicsEffect(self._shadow)


		# Layout and polished contents
		v = QVBoxLayout()
		v.setContentsMargins(12, 10, 12, 10)
		v.setSpacing(6)

		# Top row: title + badge
		top_row = QHBoxLayout()
		top_row.setContentsMargins(0, 0, 0, 0)
		top_row.setSpacing(8)
		title = QLabel(self.name)
		title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
		title.setStyleSheet("color: #e6e6e6; border: none; background: transparent;")
		badge = QLabel("Easy")
		badge.setStyleSheet("background:#0b3b6f; color:#ffffff; padding:3px 6px; border-radius:6px; font-size:9px;")
		badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
		top_row.addWidget(title)
		top_row.addStretch()
		top_row.addWidget(badge)
		v.addLayout(top_row)

		# Description
		desc_lbl = QLabel(self.desc)
		desc_lbl.setWordWrap(True)
		desc_lbl.setStyleSheet("color: #cfcfcf; font-size:11px; border: none; background: transparent;")
		v.addWidget(desc_lbl)

		v.addStretch()

		# bottom-right progress pill
		self._prog = QLabel("0%")
		self._prog.setStyleSheet("background: rgba(0,255,153,0.08); color:#00ff99; padding:4px 6px; border-radius:6px; font-weight:700;")
		self._prog.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
		bottom_row = QHBoxLayout()
		bottom_row.addStretch()
		bottom_row.addWidget(self._prog)
		v.addLayout(bottom_row)

		self.setLayout(v)

	def enterEvent(self, ev):
		# increase shadow on hover
		try:
			self._shadow.setBlurRadius(20)
			self._shadow.setYOffset(6)
			# (no fixed-size changes here so layout can expand)
		except Exception:
			pass
		return super().enterEvent(ev)

	def leaveEvent(self, ev):
		try:
			if not self._selected:
				self._shadow.setBlurRadius(8)
				self._shadow.setYOffset(2)
				# keep minimum size; layout will handle spacing
		except Exception:
			pass
		return super().leaveEvent(ev)

	def mousePressEvent(self, ev):
		if callable(self.click_cb):
			self.click_cb(self.code, self)
		return super().mousePressEvent(ev)

	def set_selected(self, sel: bool):
		self._selected = bool(sel)
		if self._selected:
			self.setStyleSheet(self._selected_style)
			self._shadow.setBlurRadius(22)
			self._shadow.setYOffset(6)
		else:
			self.setStyleSheet(self._base_style)
			self._shadow.setBlurRadius(8)
			self._shadow.setYOffset(2)

class LabWindow(QMainWindow):
	# signal used by background threads to send output to the UI thread
	output_signal = pyqtSignal(str)

	def __init__(self):
		super().__init__()
		# Optional frameless window (useful for kiosk/overlay modes). Set env USE_FRAMELESS=1 to enable.
		try:
			if os.environ.get('USE_FRAMELESS', '0') == '1':
				# Prefer using setWindowFlag where available to preserve existing flags
				try:
					self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
				except Exception:
					# fallback to replacing flags if setWindowFlag not present
					self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
		except Exception:
			pass
		self.setWindowTitle("Vulnerable Lab Selector")
		self.resize(1000, 700)
		self.selected_lab = None

		# Central widget and main layout
		# central widget should be a member and allowed to expand
		self.central = QWidget(self)
		self.setCentralWidget(self.central)
		# ensure central widget expands to fill the QMainWindow
		try:
			from PyQt6.QtWidgets import QSizePolicy as _SP
			self.central.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Expanding)
		except Exception:
			pass
		# Dark CTF-style background (HTB / TryHackMe vibe)
		self.central.setStyleSheet(
			"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0f0f12, stop:1 #16161a);"
			"color: #e6e6e6;"
		)
		main_h = QHBoxLayout()
		# remove outer gaps in main horizontal layout so contents sit flush when fullscreen
		try:
			main_h.setContentsMargins(0, 0, 0, 0)
			main_h.setSpacing(12)
		except Exception:
			pass
		# Banner image tiled across the top
		# Prefer a system-provided banner if present, otherwise fall back to a
		# banner next to this script. This allows packaging the banner at
		# `/opt/lab/banner.png` while keeping a local fallback for development.
		# Candidate banner locations (prefer system path, then user desktop, then local)
		candidates = [
			'/opt/lab/banner.png',
			r'C:\Users\saiya\OneDrive\Desktop\hki\banner.png',
			os.path.join(os.path.dirname(__file__), "banner.png"),
		]
		banner_path = None
		for p in candidates:
			try:
				if os.path.exists(p):
					banner_path = p
					break
			except Exception:
				continue
		# final fallback: local banner next to script
		if not banner_path:
			banner_path = os.path.join(os.path.dirname(__file__), "banner.png")
		# Debug: print which banner path we are using
		sys.stderr.write(f"[INFO] Banner path chosen: {banner_path} (exists={os.path.exists(banner_path)})\n")
		# banner size tuned for balanced logo + text readability
		banner = BannerWidget(banner_path, height=110, zoom=1.0)

		# Left column: Actions
		left = QVBoxLayout()
		left.setSpacing(8)
		# tighten left column margins so it stays flush with window edges
		try:
			left.setContentsMargins(8, 8, 8, 8)
		except Exception:
			pass
		self.install_btn = QPushButton("Install Selected ▶")
		self.reset_btn = QPushButton("Reset / Cleanup")
		self.cancel_btn = QPushButton("Cancel")
		self.shell_btn = QPushButton("Open Shell")
		self.cancel_btn.setEnabled(False)
		left.addWidget(QLabel("Actions", alignment=Qt.AlignmentFlag.AlignLeft))
		left.addWidget(self.install_btn)
		left.addWidget(self.reset_btn)
		left.addWidget(self.cancel_btn)
		left.addWidget(self.shell_btn)
		left.addStretch()

		# Button styling: dark flat with neon-green accent on hover
		btn_style = (
			"QPushButton{background:#1e1b26; color:#e6e6e6; border:1px solid rgba(255,255,255,0.04);"
			"border-radius:8px; padding:8px 12px;}"
			"QPushButton:hover{border:1px solid #00ff99;}"
			"QPushButton:disabled{background:#2a2733; color:#6a6a6a;}"
		)
		self.install_btn.setStyleSheet(btn_style)
		self.reset_btn.setStyleSheet(btn_style)
		self.cancel_btn.setStyleSheet(btn_style)
		self.shell_btn.setStyleSheet(btn_style)

		self.left_container = QWidget()
		self.left_container.setLayout(left)
		# prefer a minimum width for the left panel instead of fixed width so layouts can expand
		try:
			self.left_container.setMinimumWidth(220)
			from PyQt6.QtWidgets import QSizePolicy as _SP
			self.left_container.setSizePolicy(_SP.Policy.Fixed, _SP.Policy.Expanding)
			self.left_container.setContentsMargins(0, 0, 0, 0)
		except Exception:
			pass

		# Right column: Shell / Labs
		right_v = QVBoxLayout()
		# keep right column tight to edges
		try:
			right_v.setContentsMargins(0, 0, 0, 0)
			right_v.setSpacing(8)
		except Exception:
			pass

		# Shell output and embedded loader
		shell_label = QLabel("Shell Output")
		shell_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
		shell_label.setStyleSheet("color: #111111")
		right_v.addWidget(shell_label)

		self.output = QTextEdit()
		self.output.setReadOnly(True)
		# Dark monospace shell-like output with neon green text
		self.output.setStyleSheet(
			"background:#070709; color:#a6ffb0; font-family: Consolas; padding:8px; border-radius:6px;"
		)
		# Allow overriding the shell output height via environment for different displays
		try:
			height = int(os.environ.get('SHELL_OUTPUT_HEIGHT', '240'))
		except Exception:
			height = 240
		self.output.setFixedHeight(height)
		right_v.addWidget(self.output)

		# Embedded loader area
		self.embed_progress = QProgressBar()
		self.embed_progress.setValue(0)
		self.embed_progress.setVisible(False)
		self.embed_status = QLabel("")
		self.embed_status.setStyleSheet("color:#a6ffb0")
		right_v.addWidget(self.embed_progress)
		right_v.addWidget(self.embed_status)

		# scrollable labs grid
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		labs_widget = QWidget()
		self.grid = QGridLayout()
		self.grid.setSpacing(10)
		# reduce outer margins so cards sit closer to each other and reduce gaps at fullscreen
		self.grid.setContentsMargins(6, 6, 6, 6)
		# ensure cards stick to the top-left and columns expand to fill available width
		try:
			self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
			# Prevent columns from stretching to fill the entire row. Use a sensible
			# minimum width per column so cards cluster on the left like a tiled grid.
			col_min_w = 280
			for ci in range(3):
				try:
					self.grid.setColumnMinimumWidth(ci, col_min_w)
					self.grid.setColumnStretch(ci, 0)
				except Exception:
					pass
		except Exception:
			pass
		labs_widget.setLayout(self.grid)
		scroll.setWidget(labs_widget)
		# VM workaround: ensure scroll area and its viewport paint properly
		try:
			scroll.setStyleSheet("QScrollArea { background: transparent; }")
			scroll.viewport().setStyleSheet("background: transparent;")
		except Exception:
			pass
		# prefer no horizontal scrollbar; cards should flow vertically and stretch
		try:
			scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		except Exception:
			pass
		right_v.addWidget(scroll)

		# assemble main layout inside an explicit container so Qt can stretch it properly
		main_h.addWidget(self.left_container)
		self.main_right_container = QWidget()
		self.main_right_container.setLayout(right_v)
		# allow the right container to expand and take available space
		try:
			from PyQt6.QtWidgets import QSizePolicy as _SP
			self.main_right_container.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Expanding)
		except Exception:
			pass
		main_h.addWidget(self.main_right_container, 1)

		# bottom status
		bottom = QHBoxLayout()
		try:
			bottom.setContentsMargins(6, 6, 6, 6)
		except Exception:
			pass
		self.status = QLabel("Ready")
		self.status.setStyleSheet("color:#a6ffb0")
		self.global_progress = QProgressBar()
		self.global_progress.setMaximumHeight(14)
		bottom.addWidget(self.status)
		bottom.addStretch()
		bottom.addWidget(self.global_progress)

		wrapper = QVBoxLayout(self.central)
		# make the banner sit flush at the top with no gaps
		try:
			wrapper.setContentsMargins(0, 0, 0, 0)
			wrapper.setSpacing(0)
		except Exception:
			pass
		# add the banner at the very top
		wrapper.addWidget(banner)

		# Top-right window controls (maximize/restore) - small, Kali-like button
		try:
			controls = QWidget()
			controls.setFixedHeight(34)
			ctrl_layout = QHBoxLayout()
			ctrl_layout.setContentsMargins(8, 4, 8, 4)
			ctrl_layout.addStretch()
			self.fullscreen_btn = QPushButton('\u26F6')
			self.fullscreen_btn.setFixedSize(32, 28)
			self.fullscreen_btn.setToolTip('Toggle maximize/restore (F11)')
			self.fullscreen_btn.setStyleSheet('QPushButton{background:transparent; color:#e6e6e6; border:1px solid rgba(255,255,255,0.04); border-radius:6px;} QPushButton:hover{border:1px solid #00ff99;}')
			ctrl_layout.addWidget(self.fullscreen_btn)
			controls.setLayout(ctrl_layout)
			wrapper.addWidget(controls)
		except Exception:
			pass
		# wrap the main horizontal layout in a widget so the root layout can stretch it reliably
		try:
			main_container = QWidget()
			main_container.setLayout(main_h)
			from PyQt6.QtWidgets import QSizePolicy as _SP
			main_container.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Expanding)
			wrapper.addWidget(main_container, 1)
		except Exception:
			# fallback: add layout directly
			wrapper.addLayout(main_h, 1)
		wrapper.addLayout(bottom)

		# build lab cards (create widgets but arrange responsively)
		self.cards = []
		self._make_cards()
		# arrange cards into grid based on available width
		try:
			self._arrange_cards()
		except Exception:
			pass
		# ensure bottom stretch so cards remain at top when window grows
		try:
			self.grid.setRowStretch(100, 1)
		except Exception:
			pass

		# Connect signals and buttons
		self.output_signal.connect(self.log)
		self.install_btn.clicked.connect(self.install_lab)
		self.reset_btn.clicked.connect(self.reset_lab)
		self.shell_btn.clicked.connect(self.open_shell)
		# fullscreen / maximize toggle
		try:
			self.fullscreen_btn.clicked.connect(self.toggle_maximize)
			# F11 shortcut to toggle maximize/restore. Some PyQt builds may not expose QShortcut,
			# so use an application QAction as a reliable fallback for a global shortcut.
			a = QAction(self)
			a.setShortcut(QKeySequence('F11'))
			a.triggered.connect(self.toggle_maximize)
			# ensure the action is active by adding it to the window
			self.addAction(a)
		except Exception:
			pass
		self.cancel_btn.clicked.connect(self.cancel_current)

		# process handle for running scripts
		self.current_proc = None

		# application menu intentionally omitted (rendering toggle removed)

	def log(self, msg: str):
		import time
		t = time.strftime("%H:%M:%S")
		self.output.append(f"[{t}] {msg}")
		self.status.setText(msg)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		# Force full repaint to avoid partial repaint/black areas on buggy GL backends
		try:
			self.repaint()
		except Exception:
			pass
		# Re-layout cards responsively when window resizes
		try:
			self._arrange_cards()
		except Exception:
			pass

	def changeEvent(self, event):
		# Restore fullscreen if the window is minimized (works even with Openbox)
		try:
			if event.type() == QEvent.Type.WindowStateChange:
				# If some window managers minimize the window (Openbox), immediately
				# restore fullscreen and re-activate the window.
				if self.isMinimized():
					try:
						self.showFullScreen()
						self.raise_()
						self.activateWindow()
					except Exception:
						pass
		except Exception:
			pass
		super().changeEvent(event)




	def show_startup_diagnostics(self, diag: dict):
		# Diagnostics banner removed per user request — no UI shown when plugins missing.
		return

	def _make_cards(self):
		# Create CardWidget instances and store them; actual placement is handled
		# by `_arrange_cards()` so layout can adapt to the window width.
		for i, (name, (code, desc)) in enumerate(LABS.items()):
			card = CardWidget(name, desc, code, click_cb=self._on_card_click)
			self.cards.append(card)

		# After creating cards, arrange them into the grid
		try:
			self._arrange_cards()
		except Exception:
			pass


	def _arrange_cards(self):
		"""Arrange `self.cards` into `self.grid` responsively based on available width.
		This computes how many columns fit and repositions card widgets so they
		fill rows left-to-right, wrapping to the next row as needed.
		"""
		if not hasattr(self, 'cards') or not self.cards:
			return
		# clear current grid items without destroying widgets
		while self.grid.count():
			item = self.grid.takeAt(0)
			# no need to delete widgets; they will be re-added
		# Determine available width inside the main right container
		try:
			avail = max(200, self.main_right_container.width() - 24)
		except Exception:
			avail = 840
		spacing = max(8, self.grid.spacing())
		col_min_w = 280
		# compute columns that fit; at least 1, at most number of cards
		cols = max(1, min(len(self.cards), avail // (col_min_w + spacing) or 1))
		# fallback to 3 if computation yields 0
		if cols <= 0:
			cols = min(3, max(1, len(self.cards)))
		# add widgets into grid row/col
		for idx, card in enumerate(self.cards):
			r = idx // cols
			c = idx % cols
			self.grid.addWidget(card, r, c)
		# set sensible column minimum widths so cards cluster left
		for ci in range(cols):
			try:
				self.grid.setColumnMinimumWidth(ci, col_min_w)
				self.grid.setColumnStretch(ci, 0)
			except Exception:
				pass
		# ensure remaining columns (if any) don't stretch
		for ci in range(cols, 6):
			try:
				self.grid.setColumnStretch(ci, 0)
			except Exception:
				pass

	def _on_card_click(self, code, frame: 'CardWidget'):
		# clear previous selections
		for c in self.cards:
			try:
				c.set_selected(False)
			except Exception:
				pass
		# mark selected
		try:
			frame.set_selected(True)
		except Exception:
			pass
		self.selected_lab = code
		self.log(f"Selected: {code}")

	def set_busy(self, busy: bool):
		if busy:
			self.install_btn.setDisabled(True)
			self.reset_btn.setDisabled(True)
			self.cancel_btn.setDisabled(False)
			try:
				self.global_progress.setRange(0, 0)  # indeterminate
			except Exception:
				pass
		else:
			self.install_btn.setDisabled(False)
			self.reset_btn.setDisabled(False)
			self.cancel_btn.setDisabled(True)
			try:
				self.global_progress.setRange(0, 100)
				self.global_progress.setValue(0)
			except Exception:
				pass


	def _run_script_thread(self, script_path: str, arg: str = ""):
		"""Run a script in a background thread, stream output to UI via signal."""
		def _worker():
			with threading.Lock():
				self.set_busy(True)
				cmd = []
				# if script_path looks like a shell script on unix, run directly; otherwise try as executable
				if os.name != 'nt' and script_path.endswith('.sh'):
					cmd = ["/bin/bash", script_path]
				else:
					cmd = [script_path]
				if arg:
					cmd.append(arg)
				try:
					proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
					self.current_proc = proc
					for line in proc.stdout:
						self.output_signal.emit(line.rstrip())
					proc.wait()
					rc = proc.returncode
					self.output_signal.emit(f"[+] Finished (exit code {rc})")
				except FileNotFoundError:
					self.output_signal.emit(f"[ERROR] Script not found: {script_path}")
				except Exception as e:
					self.output_signal.emit(f"[ERROR] Execution failed: {e}")
				finally:
					self.current_proc = None
					self.set_busy(False)
		# run worker thread
		threading.Thread(target=_worker, daemon=True).start()


	def _download_and_execute_web(self):
		"""Download the web_sqli install script and execute it."""
		# Delegate to generic downloader+executor for web scripts
		try:
			self._download_and_execute_url('https://raw.githubusercontent.com/Abu-cmg/lab-files/main/lab_web.sh.sh', 'web_sqli')
		except Exception as e:
			self.output_signal.emit(f"[ERROR] Failed to start web installer: {e}")

	def _download_and_execute_url(self, url: str, lab_code: str = None):
		"""Generic downloader + executor for lab installer URLs.
		Downloads `url` to a temp file and runs it in a background thread,
		streaming output to the UI using `_run_script_thread`.
		"""
		self.set_busy(True)
		try:
			tmp = tempfile.gettempdir()
			name = f"lab_{lab_code}.sh" if lab_code else f"lab_download_{int(time.time())}.sh"
			dest = os.path.join(tmp, name)
			raw = url
			self.output_signal.emit(f"[+] Downloading {url} to {dest}")
			# prefer curl for robust downloads
			if shutil.which('curl'):
				try:
					subprocess.check_call(['curl', '-fsSL', raw, '-o', dest])
					self.output_signal.emit('[+] Downloaded via curl')
				except Exception as e:
					self.output_signal.emit(f"[WARN] curl download failed: {e}; falling back to urllib")
					try:
						urllib.request.urlretrieve(raw, dest)
					except Exception as e2:
						self.output_signal.emit(f"[ERROR] urllib download also failed: {e2}")
			else:
				# urllib fallback
				try:
					urllib.request.urlretrieve(raw, dest)
				except Exception as e:
					self.output_signal.emit(f"[ERROR] urllib download failed: {e}")

			# Normalize line endings
			try:
				if shutil.which('dos2unix'):
					self.output_signal.emit('[+] Running dos2unix on script')
					subprocess.check_call(['dos2unix', dest])
				else:
					with open(dest, 'rb') as f:
						data = f.read()
					if b"\r\n" in data:
						self.output_signal.emit('[+] Converting CRLF -> LF')
						data = data.replace(b"\r\n", b"\n")
						with open(dest, 'wb') as f:
							f.write(data)
			except Exception as e:
				self.output_signal.emit(f"[WARN] Failed to normalize line endings: {e}")

			# ensure executable
			try:
				if os.name != 'nt':
					st = os.stat(dest)
					os.chmod(dest, st.st_mode | stat.S_IEXEC)
			except Exception as e:
				self.output_signal.emit(f"[WARN] chmod failed: {e}")

			# run in background and stream
			self.output_signal.emit(f"[+] Executing downloaded script in background: {dest}")
			self._run_script_thread(dest, "")
		except Exception as e:
			self.output_signal.emit(f"[ERROR] Failed to download/execute {url}: {e}")
			self.set_busy(False)

	# Button actions (stubs that mirror behavior from tkinter)
	def install_lab(self):
		if not self.selected_lab:
			self.log("[!] No lab selected")
			return
		lab = self.selected_lab
		self.log(f"[+] Installing lab: {lab}")
		# Per-lab installers: if a URL is configured for this lab, download and run it
		installer = LAB_INSTALLERS.get(lab)
		if installer:
			# If installer looks like a URL, download and execute in background
			if installer.startswith('http://') or installer.startswith('https://'):
				threading.Thread(target=self._download_and_execute_url, args=(installer, lab), daemon=True).start()
				return
			# otherwise fall back to running configured installer path directly
			try:
				threading.Thread(target=self._run_script_thread, args=(installer, lab), daemon=True).start()
				return
			except Exception:
				pass
		# For installs that require root, run elevation/install logic in background
		# to avoid blocking the UI and causing black screens.
		try:
			threading.Thread(target=self._run_as_admin, args=(INSTALL_SCRIPT, lab), daemon=True).start()
		except Exception:
			# fallback to non-interactive background thread
			threading.Thread(target=self._run_script_thread, args=(INSTALL_SCRIPT, lab), daemon=True).start()

	def _run_as_admin(self, script_path: str, arg: str = ""):
		"""Try to run `script_path` with elevation. Prefer `pkexec`, else open a terminal
		so the user can enter their password for `sudo` interactively. Falls back to
		attempting to run the script directly if no elevation mechanism is available.
		"""
		if not script_path:
			self.log(f"[!] No script specified to run as admin")
			return

		# serialize elevation attempts to avoid races
		acquired = _elev_lock.acquire(blocking=False)
		if not acquired:
			QMessageBox.information(self, 'Busy', 'An elevation is already in progress. Please wait and try again.')
			return
		try:
			# If already root, run directly
			is_root = False
			try:
				is_root = (os.name != 'nt' and os.geteuid() == 0)
			except Exception:
				pass
			if is_root:
				try:
					subprocess.Popen([script_path] + ([arg] if arg else []), start_new_session=True)
					self.log(f"[+] Running as root, launched script directly: {script_path}")
					return
				except Exception as e:
					self.log(f"[WARN] direct run as root failed: {e}")

			# If sudo is not present, try direct exec and inform the user
			if not shutil.which('sudo'):
				self.log("[!] 'sudo' not found; attempting to run script directly")
				try:
					subprocess.Popen([script_path] + ([arg] if arg else []), start_new_session=True)
					self.log(f"[+] Launched script directly: {script_path}")
				except Exception as e:
					self.log(f"[ERROR] Could not launch installer: {e}")
					QMessageBox.information(self, 'Install failed', f'Unable to elevate privileges. Please run:\n\nsudo {script_path} {arg}')
				return

			# Detect passwordless sudo (recommended). DO NOT handle passwords in the GUI.
			pwless = False
			try:
				r = subprocess.run(['sudo', '-n', 'true'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				pwless = (r.returncode == 0)
			except Exception:
				pwless = False

			# Prepare a logfile for background runs
			logf = os.path.join(tempfile.gettempdir(), f"lab_install_{int(time.time())}.log")

			if pwless:
				# Prefer detached tmux session for persistent background installs
				if shutil.which('tmux'):
					try:
						sess = f"lab_{int(time.time())}"
						cmd = ['sudo', 'tmux', 'new-session', '-d', '-s', sess, script_path]
						if arg:
							cmd.append(arg)
						subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True)
						self.log(f"[+] Launched passwordless tmux session: {sess} (script: {script_path})")
						return
					except Exception as e:
						self.log(f"[WARN] tmux launch failed: {e}")
				# Fallback to nohup (detached, log to file)
				try:
					with open(logf, 'a') as outf:
						cmd = ['sudo', 'nohup', script_path]
						if arg:
							cmd.append(arg)
						subprocess.Popen(cmd, stdout=outf, stderr=subprocess.STDOUT, start_new_session=True)
					self.log(f"[+] Launched passwordless nohup install (log: {logf})")
					return
				except Exception as e:
					self.log(f"[WARN] nohup launch failed: {e}")

			# Passwordless sudo not available or background methods failed.
			# Do NOT prompt for or pipe passwords from the GUI. Instruct user to
			# create a scoped NOPASSWD sudoers entry instead (one-time, secure).
			try:
				msg = (
					"This installer requires root privileges. For unattended installs, configure a sudoers\n"
					"entry for the lab user (run once as root):\n\n"
					f'echo "{ROOT_USER} ALL=(ALL) NOPASSWD:{script_path}" | sudo tee /etc/sudoers.d/lab\n'
					"sudo chmod 440 /etc/sudoers.d/lab\n\n"
					"After creating this entry, retry the install.\n\n"
					"If you prefer to run manually, open a terminal and run:\n\n"
					f"sudo {script_path} {arg}\n"
				)
				QMessageBox.information(self, 'Elevation required', msg)
			except Exception:
				pass

		except Exception as e:
			self.log(f"[ERROR] Could not launch installer: {e}")
		finally:
			try:
				_elev_lock.release()
			except Exception:
				pass

	def _start_embedded_progress(self):
		self._embedded_goal = 85
		self._embedded_current = 0.0
		self._embedded_timer = QTimer()
		self._embedded_timer.timeout.connect(self._embedded_advance)
		self._embedded_timer.start(200)

	def _embedded_advance(self):
		if self._embedded_current >= self._embedded_goal:
			self._embedded_timer.stop()
			self.embed_progress.setValue(100)
			self.embed_status.setText("Completed")
			QTimer.singleShot(900, lambda: self.embed_progress.setVisible(False))
			return
		step = max(0.4, (self._embedded_goal - self._embedded_current) / 30.0)
		self._embedded_current += step
		self.embed_progress.setValue(int(self._embedded_current))
		self.embed_status.setText(f"{int(self._embedded_current)}%")

	def reset_lab(self):
		self.log("[+] Resetting lab environment")
		# Prefer a packaged reset script under /opt/lab/reset.sh run non-interactively
		opt_reset = '/opt/lab/reset.sh'
		# If packaged reset exists, run it in background and stream output to UI
		if os.path.exists(opt_reset):
			# ensure executable bit on unix
			try:
				if os.name != 'nt':
					st = os.stat(opt_reset)
					os.chmod(opt_reset, st.st_mode | stat.S_IEXEC)
			except Exception:
				pass
			threading.Thread(target=self._run_script_thread, args=(opt_reset, ""), daemon=True).start()
			return
		# Fallback: use configured RESET_SCRIPT (may require elevation)
		try:
			self._run_as_admin(RESET_SCRIPT, "")
		except Exception:
			# fallback to background thread
			threading.Thread(target=self._run_script_thread, args=(RESET_SCRIPT, ""), daemon=True).start()

	def cancel_current(self):
		if not getattr(self, 'current_proc', None):
			self.log("[!] No running process to cancel")
			return
		self.log("[!] Terminating current process...")
		try:
			proc = self.current_proc
			proc.terminate()
			threading.Timer(3.0, lambda: proc.kill() if proc.poll() is None else None).start()
		except Exception as e:
			self.log(f"[ERROR] Failed to terminate: {e}")

	def open_shell(self):
		"""Try to launch a terminal emulator for interactive debugging.
		Falls back to a user-visible message if no terminal found.
		"""
		# common terminal emulator launch commands (command, args...)
		# Try common terminal emulators, prefer launching /bin/bash directly.
		candidates = [
			['gnome-terminal','--','/bin/bash','-i'],
			['lxterminal','-e','/bin/bash'],
			['x-terminal-emulator','-e','/bin/bash'],
			['xterm','-e','/bin/bash'],
			['konsole','-e','/bin/bash'],
			['urxvt','-e','/bin/bash'],
		]
		# Windows fallbacks (Windows Terminal, PowerShell, cmd)
		win_candidates = [
			['wt','-w','0','new-tab','pwsh'],
			['powershell.exe'],
			['cmd.exe'],
		]
		for cmd in candidates:
			if shutil.which(cmd[0]):
				try:
					# start in new session so GUI isn't blocked and terminal persists
					subprocess.Popen(cmd, start_new_session=True)
					self.log(f"[+] Launched terminal: {cmd[0]}")
					return
				except Exception as e:
					self.log(f"[ERROR] Failed to launch {cmd[0]}: {e}")
		# Try Windows candidates if on Windows
		if sys.platform.startswith('win'):
			for cmd in win_candidates:
				if shutil.which(cmd[0]):
					try:
						subprocess.Popen(cmd, shell=False)
						self.log(f"[+] Launched terminal: {cmd[0]}")
						return
					except Exception as e:
						self.log(f"[ERROR] Failed to launch {cmd[0]}: {e}")
		# no terminal emulator found
		QMessageBox.information(self, 'No terminal', 'No terminal emulator found on system. Please install xterm or run a shell via SSH for debugging.')

	def toggle_maximize(self):
		"""Toggle between maximized and normal window states (acts like Kali maximize)."""
		try:
			if self.isMaximized():
				self.showNormal()
				# update button appearance if desired
				try:
					self.fullscreen_btn.setText('\u26F6')
				except Exception:
					pass
			else:
				self.showMaximized()
				try:
					self.fullscreen_btn.setText('\u2752')
				except Exception:
					pass
		except Exception as e:
			self.log(f"[ERROR] Toggle maximize failed: {e}")


def main():
	# Ensure Qt can find its platform plugins (helpful when using PyQt from pip)
	def ensure_qt_on_linux():
		if not sys.platform.startswith('linux'):
			return
		# try to set PyQt6 plugin path
		try:
			import PyQt6 as _pqt
			p = os.path.join(os.path.dirname(_pqt.__file__), 'Qt', 'plugins')
			if os.path.isdir(p):
				os.environ.setdefault('QT_PLUGIN_PATH', p)
				os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', p)
				platforms_dir = os.path.join(p, 'platforms')
				xcb_path = os.path.join(platforms_dir, 'libqxcb.so') if platforms_dir else None
				# if xcb plugin exists, prefer xcb when DISPLAY available
				if xcb_path and os.path.exists(xcb_path) and 'DISPLAY' in os.environ:
					os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
					return
		except Exception:
			pass

		# fallback: if Wayland session, use wayland platform
		if 'WAYLAND_DISPLAY' in os.environ:
			os.environ.setdefault('QT_QPA_PLATFORM', 'wayland')
			return

		# if no display (headless), use offscreen
		if 'DISPLAY' not in os.environ:
			os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
			return

		# On some virtual machines (VirtualBox, VMware) GPU drivers cause black/blank
		# widget areas. Prefer software GL rendering in that case unless overridden.
		# Allow users to override by setting FORCE_QT_SOFTWARE=0 in env.
		try:
			force_software = os.environ.get('FORCE_QT_SOFTWARE', '1')
			if force_software != '0':
				os.environ.setdefault('QT_OPENGL', 'software')
				os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
				# disable xcb GL integration which can cause black areas
				os.environ.setdefault('QT_XCB_GL_INTEGRATION', 'none')
		except Exception:
			pass

		# If we reach here, we couldn't verify a working platform plugin; print helpful Ubuntu steps
		sys.stderr.write('\n*** Qt platform plugin troubleshooting ***\n')
		sys.stderr.write('Detected Linux; if you get the "Could not load the Qt platform plugin \"xcb\"" error on Ubuntu, run:\n')
		sys.stderr.write('  sudo apt update\n')
		sys.stderr.write('  sudo apt install -y libxcb1 libx11-xcb1 libxcb-xinerama0 libxcb-xfixes0 libxcb-render0 libxcb-shm0 libxkbcommon-x11-0 \\n')
		sys.stderr.write('    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-util1 libxcb-ewmh1 libxcb-randr0\n')
		sys.stderr.write('Also ensure the PyQt6 plugin path is exported, for example:\n')
		sys.stderr.write('  export QT_PLUGIN_PATH=$(python3 -c "import PyQt6, os; print(os.path.join(os.path.dirname(PyQt6.__file__), \'Qt\', \'plugins\'))")\n')
		sys.stderr.write('  export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_PATH"\n')
		sys.stderr.write('Or run with headless/offscreen: export QT_QPA_PLATFORM=offscreen\n')
		sys.stderr.write('******************************************\n\n')

	ensure_qt_on_linux()

	# Debug: print environment and plugin info before QApplication
	def debug_pre_app():
		# Return structured diagnostics in addition to printing
		d = {
			'environ': {},
			'plugin_dir': None,
			'platforms_exist': False,
			'platforms_files': None,
			'raw': None,
		}
		out = []
		out.append('\n*** Qt pre-app diagnostics ***')
		for k in ('DISPLAY', 'WAYLAND_DISPLAY', 'QT_QPA_PLATFORM', 'QT_OPENGL', 'LIBGL_ALWAYS_SOFTWARE', 'QT_XCB_GL_INTEGRATION', 'FORCE_QT_SOFTWARE'):
			v = os.environ.get(k)
			d['environ'][k] = v
			out.append(f"{k}={v!r}")
		# locate PyQt6 plugin path if possible
		try:
			import PyQt6 as _pqt
			p = os.path.join(os.path.dirname(_pqt.__file__), 'Qt', 'plugins')
			d['plugin_dir'] = p
			out.append(f"PyQt6 plugin dir: {p}")
			platforms_dir = os.path.join(p, 'platforms')
			if os.path.isdir(platforms_dir):
				files = os.listdir(platforms_dir)
				d['platforms_exist'] = True
				d['platforms_files'] = files
				out.append(f"platforms: {files}")
			else:
				out.append('platforms: <missing>')
		except Exception as e:
			d['platforms_exist'] = False
			d['platforms_files'] = None
			out.append(f"PyQt6 plugin path detection failed: {e}")
		out.append('*** end diagnostics ***\n')
		# print to stderr so terminal captures it when running
		raw = '\n'.join(out) + '\n'
		sys.stderr.write(raw)
		d['raw'] = raw
		return d

	# Debug: print screen/DPI info after QApplication created
	def debug_post_app(app):
		out = []
		out.append('\n*** Qt post-app diagnostics ***')
		try:
			screen = app.primaryScreen()
			if screen:
				out.append(f"screen name: {screen.name()}")
				out.append(f"logical DPI: {screen.logicalDotsPerInch():.1f}")
				out.append(f"physical DPI: {screen.physicalDotsPerInch():.1f}")
				out.append(f"devicePixelRatio: {screen.devicePixelRatio():.2f}")
				sz = screen.size()
				out.append(f"screen size: {sz.width()}x{sz.height()}")
			else:
				out.append('no primary screen detected')
		except Exception as e:
			out.append(f"post-app screen info failed: {e}")
		out.append('*** end diagnostics ***\n')
		sys.stderr.write('\n'.join(out) + '\n')

	pre_diag = debug_pre_app()

	# Improve HiDPI and VM scaling behavior (use safe fallbacks for attribute names)
	try:
		# PyQt versions expose these attributes differently; try common variants
		try:
			if hasattr(Qt, 'ApplicationAttribute') and hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
				QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
			elif hasattr(Qt, 'AA_EnableHighDpiScaling'):
				QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

			if hasattr(Qt, 'ApplicationAttribute') and hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
				QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
			elif hasattr(Qt, 'AA_UseHighDpiPixmaps'):
				QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
		except Exception:
			# ignore if attributes not present on this PyQt build
			pass
		app = QApplication(sys.argv)
		# after QApplication is created, print post-app diagnostics
		try:
			debug_post_app(app)
		except Exception:
			pass
	except Exception as e:
		sys.stderr.write('Failed to initialize QApplication: ' + str(e) + '\n')
		sys.stderr.write('See above troubleshooting hints for Ubuntu (xcb) or try running with QT_QPA_PLATFORM=offscreen for headless systems.\n')
		raise
	# (software OpenGL attribute is set earlier, before QApplication creation)
	w = LabWindow()
	# If requested, enable frameless/topmost/customized flags and force fullscreen.
	# Otherwise, honor USE_FULL_SCREEN or default to maximized.
	try:
		# import QEvent locally (QApplication is imported at module scope)
		from PyQt6.QtCore import QEvent
	except Exception:
		pass

	# If USE_FRAMELESS=1, apply strict frameless/topmost flags and go fullscreen.
	if os.environ.get('USE_FRAMELESS', '0') == '1':
		try:
			w.setWindowFlags(
				Qt.WindowType.FramelessWindowHint |
				Qt.WindowType.WindowStaysOnTopHint |
				Qt.WindowType.CustomizeWindowHint
			)
			# Disable minimize/maximize completely
			try:
				w.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
			except Exception:
				pass
			try:
				w.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
			except Exception:
				pass
			# show fullscreen for kiosk-like behavior
			w.showFullScreen()
		except Exception:
			try:
				w.showMaximized()
			except Exception:
				pass
	else:
		# Respect USE_FULL_SCREEN if set, otherwise maximize
		try:
			if os.environ.get('USE_FULL_SCREEN', '0') == '1':
				w.showFullScreen()
			else:
				w.showMaximized()
		except Exception:
			try:
				w.showMaximized()
			except Exception:
				pass
	# show startup diagnostics banner if needed
	try:
		if isinstance(pre_diag, dict) and not pre_diag.get('platforms_exist'):
			# pass diagnostics to the window so it can render a helpful banner
			try:
				w.show_startup_diagnostics(pre_diag)
			except Exception:
				pass
	except Exception:
		pass
	sys.exit(app.exec())


if __name__ == '__main__':
	main()
