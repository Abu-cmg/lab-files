
import os
import sys
import threading
import re
import html as _html

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
import json
import socket
import shlex
import stat
import time
import pprint


LABS = {'Linux – Sudo PrivEsc': ('sudo_privesc', 'Gain root via sudo misconfiguration.'),
 'Web – File Upload': ('web_upload', 'Exploit insecure file upload handling.'),
 'Web – SQL Injection': ('web_sqli', 'Practise SQLi against a vulnerable app.'),
 'Web – XSS': ('web_xss', 'Learn about XSS (Cross-Site Scripting) and how to defend against it.'),
 'Boot2root': ('ab', 'Get root_admin by exploiting various vulnerabilities in a  Linux environment .'),
 'Privelege Escaltion': ('fsdfd', 'try your privelege escalation skills'),
 'Red teams': ('net', 'Red team your way through a vulnerable network'),
 'IOT': ('asds', 'deep dive into IOT vulnerabilities'),
 'Cryto': ('sdW', 'Sharpen your crypto skills with rsa, aes, hashing and more'),
 'Enumertion': ('sd', 'enumerate network services and hosts') }


# Optional per-lab difficulty mapping (title -> 'Easy'|'Medium'|'Hard')
LAB_DIFFICULTY = {
	'Boot2root': 'Hard',
	'Linux – Sudo PrivEsc': 'Hard',
	'Web – File Upload': 'Medium',
	'Web – SQL Injection': 'Easy',
	'Web – XSS': 'Easy',
	'Privelege Escaltion': 'Medium',
	'Red teams': 'Hard',
	'IOT': 'Medium',
	'Cryto': 'Easy',
	'Enumertion': 'Easy',
}

# Default scripts (can be overridden by env vars)
INSTALL_SCRIPT = os.environ.get("INSTALL_SCRIPT", "/usr/local/bin/install_lab.sh")
RESET_SCRIPT = os.environ.get("RESET_SCRIPT", "/opt/lab/reset_lab.sh")

# If a root user/password is provided
ROOT_USER = os.environ.get("ROOT_USER", "antori")

# Per-lab installer sources. Keys are the lab codes from `LABS` values.
# Values may be a URL to a shell installer (http/https) or None to use
# the default `INSTALL_SCRIPT` mechanism. Add more entries here.
LAB_INSTALLERS = {'asda': 'asd',
 'asds': 'asdsa',
 'fsdfd': 'sdf',
 'net': 'https://github.com/Abu-cmg/lab-files/blob/main/red.sh',
 'ab': 'https://github.com/Abu-cmg/lab-files/blob/main/pen.sh',
 'web_sqli': 'https://raw.githubusercontent.com/Abu-cmg/lab-files/main/lab_web.sh.sh',
 'web_upload': 'https://raw.githubusercontent.com/Abu-cmg/lab-files/main/upload.sh',
 'sd': 'https://raw.githubusercontent.com/Abu-cmg/lab-files/main/upload.sh' }

# Persisted labs config paths: prefer system-wide '/opt/lab/labs.json'
# but fall back to the local `labs.json` beside this script when not writable.
_SYSTEM_LABS_DIR = '/opt/lab'
_SYSTEM_LABS_CONFIG = os.path.join(_SYSTEM_LABS_DIR, 'labs.json')
_LOCAL_LABS_CONFIG = os.path.join(os.path.dirname(__file__), 'labs.json')

def load_persisted_labs():
	"""Load persisted labs from system path first, then local fallback.
	Persisted entries will override defaults when keys/codes collide.
	"""
	try:
		path = None
		if os.path.exists(_SYSTEM_LABS_CONFIG):
			path = _SYSTEM_LABS_CONFIG
		elif os.path.exists(_LOCAL_LABS_CONFIG):
			path = _LOCAL_LABS_CONFIG
		if not path:
			return
		with open(path, 'r', encoding='utf-8') as f:
			data = json.load(f)
		labs = data.get('labs', {})
		installers = data.get('installers', {})
		difficulties = data.get('difficulties', {})
		# labs stored as title -> [code, desc]
		for title, val in labs.items():
			try:
				code, desc = val[0], val[1] if len(val) > 1 else ''
			except Exception:
				continue
			# replace or add
			LABS[title] = (code, desc)
		# installers: code -> url/path
		for k, v in installers.items():
			if v:
				LAB_INSTALLERS[k] = v
			else:
				LAB_INSTALLERS.pop(k, None)
		# difficulties: title -> difficulty
		for t, dv in difficulties.items():
			if dv:
				LAB_DIFFICULTY[t] = dv
			else:
				LAB_DIFFICULTY.pop(t, None)
	except Exception:
		# don't fail startup on corrupted config
		sys.stderr.write('[WARN] Failed to load persisted labs config\n')


def save_persisted_labs():
	"""Embed current LABS, LAB_INSTALLERS and LAB_DIFFICULTY into this
	Python source file. A timestamped backup of the file is written first.
	"""
	try:
		src = os.path.abspath(__file__)
		# create a backup copy
		bak = f"{src}.bak.{int(time.time())}"
		try:
			shutil.copy2(src, bak)
		except Exception:
			bak = None

		# Prepare Python literal representations
		labs_repr = pprint.pformat({k: (v[0], v[1]) for k, v in LABS.items()}, width=120)
		installers_repr = pprint.pformat(dict(LAB_INSTALLERS), width=120)
		difficulties_repr = pprint.pformat(dict(LAB_DIFFICULTY), width=120)

		with open(src, 'r', encoding='utf-8') as f:
			content = f.read()

		# Replace LABS block
		new_labs_block = f"LABS = {labs_repr}\n\n"
		content, n1 = re.subn(r"(?ms)^LABS\s*=\s*\{.*?\n\}\n", new_labs_block, content)

		# Replace LAB_INSTALLERS block
		new_inst_block = f"LAB_INSTALLERS = {installers_repr}\n\n"
		content, n2 = re.subn(r"(?ms)^LAB_INSTALLERS\s*=\s*\{.*?\n\}\n", new_inst_block, content)

		# Replace or insert LAB_DIFFICULTY
		new_diff_block = f"LAB_DIFFICULTY = {difficulties_repr}\n\n"
		if re.search(r"(?m)^LAB_DIFFICULTY\s*=", content):
			content, n3 = re.subn(r"(?ms)^LAB_DIFFICULTY\s*=\s*\{.*?\n\}\n", new_diff_block, content)
		else:
			# insert after LAB_INSTALLERS block if present, else after LABS
			if n2:
				content = re.sub(r"(?ms)(^LAB_INSTALLERS\s*=\s*\{.*?\n\}\n)", r"\1\n" + new_diff_block, content)
			else:
				content = re.sub(r"(?ms)(^LABS\s*=\s*\{.*?\n\}\n)", r"\1\n" + new_diff_block, content)

		# Write back
		with open(src, 'w', encoding='utf-8') as f:
			f.write(content)

		sys.stderr.write(f"[INFO] Embedded labs into source: {src} (backup: {bak})\n")
	except Exception as e:
		sys.stderr.write(f"[WARN] Failed to embed labs into source: {e}\n")

# Attempt to load persisted labs at startup
load_persisted_labs()



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

        # Top row: title (badge moved to bottom-right)
		top_row = QHBoxLayout()
		top_row.setContentsMargins(0, 0, 0, 0)
		top_row.setSpacing(8)
		title = QLabel(self.name)
		title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
		title.setStyleSheet("color: #e6e6e6; border: none; background: transparent;")
		top_row.addWidget(title)
		top_row.addStretch()
		v.addLayout(top_row)

		# Description
		desc_lbl = QLabel(self.desc)
		desc_lbl.setWordWrap(True)
		desc_lbl.setStyleSheet("color: #cfcfcf; font-size:11px; border: none; background: transparent;")
		v.addWidget(desc_lbl)

		v.addStretch()

		# keep bottom spacing and place difficulty pill at bottom-right
		v.addStretch()
		bottom_row = QHBoxLayout()
		bottom_row.addStretch()
		# difficulty badge (Easy/Medium/Hard)
		# Determine difficulty: prefer explicit mapping in LAB_DIFFICULTY, else fall back to description scanning
		diff = 'Easy'
		try:
			if self.name in LAB_DIFFICULTY:
				diff = LAB_DIFFICULTY.get(self.name, 'Easy')
			else:
				if isinstance(self.desc, str):
					d = self.desc.lower()
					if 'hard' in d:
						diff = 'Hard'
					elif 'medium' in d:
						diff = 'Medium'
					elif 'easy' in d:
						diff = 'Easy'
		except Exception:
			pass
		self._badge = QLabel(diff)
		# Color mapping: Easy = blue, Medium = yellow, Hard = red
		_badge_colors = {
			'Easy': '#0b3b6f',
			'Medium': '#c19a0b',
			'Hard': '#c0392b',
		}
		bg = _badge_colors.get(diff, '#0b3b6f')
		self._badge.setStyleSheet(f"background:{bg}; color:#ffffff; padding:6px 8px; border-radius:8px; font-size:10px; font-weight:700;")
		self._badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
		bottom_row.addWidget(self._badge)
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
	# signal emitted when an update completes (dest path)
	update_done_signal = pyqtSignal(str)

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
		# Track which lab has been installed; prevents installing another until reset
		self._installed_lab = None

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
		# increase height slightly for better visibility and ensure it expands horizontally
		banner = BannerWidget(banner_path, height=140, zoom=1.0)
		try:
			from PyQt6.QtWidgets import QSizePolicy as _SP
			banner.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Fixed)
		except Exception:
			pass

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
		self.restart_btn = QPushButton("Restart System")
		self.shell_btn = QPushButton("Open Shell")
		# Manage Labs button -- optional interface to add/edit lab cards at runtime
		# This whole section is easily comment-able. To disable at runtime set
		# the environment variable ENABLE_MANAGE_UI=0 or comment out the block
		# between the markers: MANAGE_UI_BLOCK START / END
		self.manage_btn = QPushButton("Manage Labs")
		left.addWidget(self.manage_btn)
		# Hide and disable Manage Labs button per user request
		try:
			self.manage_btn.setVisible(False)
			self.manage_btn.setEnabled(False)
		except Exception:
			pass

		self.cancel_btn.setEnabled(False)
		left.addWidget(QLabel("Actions", alignment=Qt.AlignmentFlag.AlignLeft))
		left.addWidget(self.install_btn)
		left.addWidget(self.reset_btn)
		left.addWidget(self.cancel_btn)
		# Restart button placed below Cancel
		left.addWidget(self.restart_btn)
		left.addWidget(self.shell_btn)
		left.addStretch()

		# Button styling: dark flat with neon-green accent on hover
		btn_style = (
			"QPushButton{background:#1e1b26; color:#e6e6e6; border:1px solid rgba(255,255,255,0.04);"
			"border-radius:8px; padding:8px 12px;}"
			"QPushButton:hover{border:1px solid #00ff99;}"
			"QPushButton:disabled{background:#2a2733; color:#6a6a6a;}"
		)
		# Give the Install button a purple -> pink gradient to stand out
		self.install_btn.setStyleSheet(
    "QPushButton{background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6a0dad, stop:1 #9d4edd);"
    " color:#ffffff; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:8px 12px;}"
    "QPushButton:hover{border:1px solid #ff8ed6;}"
    "QPushButton:disabled{background:#5a3a5a; color:#6a6a6a;}"
)
		# Reset and Cancel styled to match Install (purple -> pink gradient)
		self.reset_btn.setStyleSheet(
    "QPushButton{background:#7b2cbf;"
    " color:#ffffff; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:8px 12px;}"
    "QPushButton:hover{border:1px solid #ff8ed6;}"
    "QPushButton:disabled{background:#5a3a5a; color:#6a6a6a;}"
		)
		self.cancel_btn.setStyleSheet(
			 "QPushButton{background:#7b2cbf;"
    " color:#ffffff; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:8px 12px;}"
    "QPushButton:hover{border:1px solid #ff8ed6;}"
    "QPushButton:disabled{background:#5a3a5a; color:#6a6a6a;}"
		)
		# Restart button styled with cautionary red
		self.restart_btn.setStyleSheet(
			"QPushButton{background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff4d4f, stop:1 #c40000);"
			" color:#ffffff; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:8px 12px;}"
			"QPushButton:hover{border:1px solid #ffb3b3;}"
			"QPushButton:disabled{background:#8a2b2b; color:#6a6a6a;}"
		)
		self.shell_btn.setStyleSheet(btn_style)
		# connect restart handler
		try:
			self.restart_btn.clicked.connect(self.restart_system)
		except Exception:
			pass

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
		# add the banner at the very top (banner will center its content internally)
		wrapper.addWidget(banner)

		# Add an app title under the banner
		try:
			title_lbl = QLabel("HKQ's Practice Labs")
			title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
			title_lbl.setStyleSheet('color:#9370db; font-size:18px; font-weight:800; padding:6px 0;')
			wrapper.addWidget(title_lbl)
		except Exception:
			pass

		# Initialize installed-state display
		try:
			self._set_installed_lab(getattr(self, '_installed_lab', None))
		except Exception:
			pass

		# Top-right window controls (maximize/restore) - small, Kali-like button
		try:
			controls = QWidget()
			controls.setFixedHeight(34)
			ctrl_layout = QHBoxLayout()
			ctrl_layout.setContentsMargins(8, 4, 8, 4)
			# Current installed lab display (top-left)
			try:
				self.current_lab_lbl = QLabel("Current Lab: None")
				self.current_lab_lbl.setStyleSheet('color:#ffffff; font-weight:700; padding:6px 0;')
				ctrl_layout.addWidget(self.current_lab_lbl)
			except Exception:
				pass
			ctrl_layout.addStretch()
			# Target IP label (top-right). Shows detected IP or uses TARGET_IP env override.
			try:
				ip = os.environ.get('TARGET_IP') or '...'
			except Exception:
				ip = '...'
			# small grey card containing the target IP
			try:
				self._target_ip_text = QLabel(f"IP: {ip}")
				# larger red text for visibility
				self._target_ip_text.setStyleSheet('color:#ff3b3b; font-size:14px; font-weight:700;')
				self._target_ip_text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
				self._target_ip_card = QFrame()
				self._target_ip_card.setObjectName('target_ip_card')
				# dark rounded card with subtle border to match the application's theme
				self._target_ip_card.setStyleSheet(
					'QFrame#target_ip_card{background:#171718; border-radius:6px; border:1px solid rgba(255,255,255,0.04); padding:2px 6px;}'
				)
				from PyQt6.QtWidgets import QHBoxLayout as _HBL
				_hl = _HBL(self._target_ip_card)
				_hl.setContentsMargins(10,4,10,4)
				_hl.addWidget(self._target_ip_text)
				try:
					self._target_ip_card.setFixedHeight(36)
					self._target_ip_card.setMinimumWidth(180)
					# increase padding slightly for larger card
					_hl.setContentsMargins(14,6,14,6)
				except Exception:
					pass
				ctrl_layout.addWidget(self._target_ip_card)
				# Only show target IP when a lab is installed
				try:
					self._target_ip_card.setVisible(bool(getattr(self, '_installed_lab', None)))
				except Exception:
					pass
				try:
					ctrl_layout.setAlignment(self._target_ip_card, Qt.AlignmentFlag.AlignTop)
					self._target_ip_card.raise_()
				except Exception:
					pass
			except Exception:
				# fallback to plain label
				self.target_ip_lbl = QLabel(f"Target IP: {ip}")
				# fallback label should also be red
				self.target_ip_lbl.setStyleSheet('color:#ff3b3b; font-size:10px; padding-right:8px;')
				try:
					self.target_ip_lbl.setVisible(bool(getattr(self, '_installed_lab', None)))
				except Exception:
					pass
				ctrl_layout.addWidget(self.target_ip_lbl)
			# fullscreen toggle button removed per user request
			controls.setLayout(ctrl_layout)
			wrapper.addWidget(controls)
			# start IP detection timer (tries to detect primary outbound IP)
			try:
				def _update_ip():
					try:
						# env var override
						ip = os.environ.get('TARGET_IP')
						if ip:
							try:
								self._target_ip_text.setText(f'Target IP: {ip}')
							except Exception:
								try:
									self.target_ip_lbl.setText(f'Target IP: {ip}')
								except Exception:
									pass
							return
							return
						# detect primary outbound IP by creating a UDP socket
						s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
						try:
							s.connect(('8.8.8.8', 80))
							ip2 = s.getsockname()[0]
							try:
								self._target_ip_text.setText(f'Target IP: {ip2}')
							except Exception:
								try:
									self.target_ip_lbl.setText(f'Target IP: {ip2}')
								except Exception:
									pass
						finally:
							s.close()
					except Exception:
						# fallback: hostname lookup
						try:
							ip3 = socket.gethostbyname(socket.gethostname())
							try:
								self._target_ip_text.setText(f'Target IP: {ip3}')
							except Exception:
								try:
									self.target_ip_lbl.setText(f'Target IP: {ip3}')
								except Exception:
									pass
						except Exception:
							try:
								self._target_ip_text.setText('Target IP: unknown')
							except Exception:
								try:
									self.target_ip_lbl.setText('Target IP: unknown')
								except Exception:
									pass
				# run once now and then on timer
				_update_ip()
				self._ip_timer = QTimer()
				self._ip_timer.timeout.connect(_update_ip)
				self._ip_timer.start(30000)
			except Exception:
				pass
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
		self.update_done_signal.connect(self._on_update_done)
		self.install_btn.clicked.connect(self.install_lab)
		self.reset_btn.clicked.connect(self.reset_lab)
		# Open Shell button disabled and hidden per user request
		try:
			self.shell_btn.setVisible(False)
			self.shell_btn.setEnabled(False)
		except Exception:
			pass
		# Update button: download replacement script and notify user to restart
		try:
			self.update_btn = QPushButton("Update")
			left.addWidget(self.update_btn)
			# Give the Update button a purple -> pink gradient to match Install button
			try:
				self.update_btn.setStyleSheet(
					 "QPushButton{background:#7b2cbf;"
    " color:#ffffff; border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:8px 12px;}"
    "QPushButton:hover{border:1px solid #ff8ed6;}"
    "QPushButton:disabled{background:#5a3a5a; color:#6a6a6a;}"
)
			except Exception:
				pass
		except Exception:
			pass
		# fullscreen / maximize toggle
		try:
			# F11 shortcut to toggle maximize/restore. Use an application QAction as a reliable fallback.
			a = QAction(self)
			a.setShortcut(QKeySequence('F11'))
			a.triggered.connect(self.toggle_maximize)
			# ensure the action is active by adding it to the window
			self.addAction(a)
		except Exception:
			pass
		self.cancel_btn.clicked.connect(self.cancel_current)
		try:
			self.update_btn.clicked.connect(self.update_lab_script)
		except Exception:
			pass
		except Exception:
			pass

		# process handle for running scripts
		self.current_proc = None

		# application menu intentionally omitted (rendering toggle removed)

	def log(self, msg: str):
		import time
		t = time.strftime("%H:%M:%S")
		# Convert ANSI color sequences to HTML spans so QTextEdit shows colors
		def _ansi_to_html(s: str) -> str:
			# simple ANSI SGR to CSS color mapping
			ansi_map = {
				'30': '#000000', '31': '#c0392b', '32': '#27ae60', '33': '#c19a0b',
				'34': '#0b3b6f', '35': '#7b2cbf', '36': '#16a085', '37': '#bdc3c7',
				'90': '#7f8c8d', '91': '#ff3b3b', '92': '#2ecc71', '93': '#f1c40f',
				'94': '#5dade2', '95': '#ff66b3', '96': '#48c9b0', '97': '#ffffff',
			}
			out = ''
			open_tags = []
			pos = 0
			for m in re.finditer(r"\x1b\[([0-9;]+)m", s):
				start, end = m.span()
				if start > pos:
					out += _html.escape(s[pos:start])
				codes = m.group(1).split(';')
				for code in codes:
					if code == '0':
						# reset
						while open_tags:
							out += '</span>'
							open_tags.pop()
						continue
					# color codes
					if code in ansi_map:
						color = ansi_map[code]
						out += f"<span style='color:{color}'>"
						open_tags.append('span')
					elif code == '1':
						# bold -> use strong
						out += "<span style='font-weight:700'>"
						open_tags.append('span')
				pos = end
			# tail
			if pos < len(s):
				out += _html.escape(s[pos:])
			# close any remaining tags
			while open_tags:
				out += '</span>'
				open_tags.pop()
			# preserve line breaks
			out = out.replace('\n', '<br/>')
			return out

		try:
			html_msg = _ansi_to_html(str(msg))
		except Exception:
			html_msg = _html.escape(str(msg)).replace('\n', '<br/>')

		# Append as rich text so colors are visible
		try:
			self.output.append(f"[{t}] {html_msg}")
		except Exception:
			# fallback to plain text
			self.output.append(f"[{t}] {msg}")
		# update status bar with plain text
		try:
			self.status.setText(str(msg))
		except Exception:
			pass

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
		# Connect optional manage UI if enabled
		try:
			if os.environ.get('ENABLE_MANAGE_UI', '1') != '0':
				self.manage_btn.clicked.connect(self._open_manage_ui)
		except Exception:
			pass

	def _open_manage_ui(self):
		# convenience wrapper to open the manage dialog. The manage UI can be
		# commented out entirely by removing the MANAGE UI BLOCK in this file.
		# Manage UI intentionally disabled. Keep a no-op placeholder so callers
		# won't error; log for visibility.
		try:
			self.log('[!] Manage Labs UI disabled')
		except Exception:
			pass


	def _arrange_cards(self):
		"""Arrange `self.cards` into `self.grid` responsively based on available width.
		This computes how many columns fit and repositions card widgets so they
		fill rows left-to-right, wrapping to the next row as needed.
		"""
		if not hasattr(self, 'cards') or not self.cards:
			return
		# clear current grid items and detach widgets so they aren't left parented
		while self.grid.count():
			item = self.grid.takeAt(0)
			w = item.widget() if item is not None else None
			if w:
				# detach widget from layout/parent so re-adding doesn't duplicate
				try:
					w.setParent(None)
				except Exception:
					pass
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
					# Attempt to run the command under configured ROOT_USER if possible
					try:
						cmd = self._wrap_with_root_user(cmd)
					except Exception:
						pass
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
			def _mask(u: str) -> str:
				try:
					if not u:
						return ''
					lu = u.lower()
					if 'abu-cmg' in lu or 'abu_cmg' in lu or 'abu cmg' in lu:
						return '[github source redacted]'
					return u
				except Exception:
					return u

			self.output_signal.emit(f"[+] Downloading {_mask(url)} to {dest}")
			# Normalize known VCS URLs to raw content URLs (GitHub /blob/ -> raw.githubusercontent)
			raw = raw.strip()
			try:
				if 'github.com' in raw and '/blob/' in raw:
					raw = raw.replace('https://github.com/', 'https://raw.githubusercontent.com/').replace('http://github.com/', 'http://raw.githubusercontent.com/').replace('/blob/', '/')
					# Avoid printing full source links for Abu-cmg repositories
					if 'abu-cmg' in raw.lower() or 'abu_cmg' in raw.lower() or 'abu cmg' in raw.lower():
						self.output_signal.emit("[+] Normalized GitHub blob URL to raw (redacted)")
					else:
						self.output_signal.emit(f"[+] Normalized GitHub blob URL to raw: {raw}")
			except Exception:
				pass
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
					try:
						subprocess.check_call(['dos2unix', dest])
						self.output_signal.emit('[+] Line endings normalized (redacted)')
					except Exception:
						# Don't expose dos2unix stderr to console
						self.output_signal.emit('[+] Line endings normalized (redacted)')
				else:
					with open(dest, 'rb') as f:
						data = f.read()
					if b"\r\n" in data:
						data = data.replace(b"\r\n", b"\n")
						with open(dest, 'wb') as f:
							f.write(data)
						self.output_signal.emit('[+] Line endings normalized (redacted)')
			except Exception as e:
				self.output_signal.emit(f"[WARN] Failed to normalize line endings: {e}")

			# ensure executable
			try:
				if os.name != 'nt':
					st = os.stat(dest)
					os.chmod(dest, st.st_mode | stat.S_IEXEC)
					# Attempt to set ownership to antori:antori when available
					try:
						import pwd, grp
						uid = pwd.getpwnam('antori').pw_uid
						gid = grp.getgrnam('antori').gr_gid
						os.chown(dest, uid, gid)
						self.output_signal.emit('[+] Ownership set to antori:antori')
					except Exception:
						pass
			except Exception as e:
				self.output_signal.emit(f"[WARN] chmod failed: {e}")

			# run in background and stream
			self.output_signal.emit(f"[+] Executing downloaded script in background: {dest}")
			self._run_script_thread(dest, "")
		except Exception as e:
			self.output_signal.emit(f"[ERROR] Failed to download/execute {url}: {e}")
			self.set_busy(False)

	# Button actions (stubs that mirror behavior from tkinter)
	def _set_installed_lab(self, lab: str | None):
		"""Update internal installed-state and refresh UI status/button state."""
		try:
			self._installed_lab = lab
			if lab:
				try:
					self.install_btn.setEnabled(False)
				except Exception:
					pass
				# show installed lab in status label
				try:
					self.status.setText(f"Installed: {lab}")
				except Exception:
					pass
				# show target IP widgets when a lab is installed
				try:
					if hasattr(self, '_target_ip_card'):
						self._target_ip_card.setVisible(True)
					if hasattr(self, 'target_ip_lbl'):
						self.target_ip_lbl.setVisible(True)
				except Exception:
					pass
				# update current lab label
				try:
					if hasattr(self, 'current_lab_lbl'):
						self.current_lab_lbl.setText(f"Current Lab: {lab}")
				except Exception:
					pass
			else:
				try:
					self.install_btn.setEnabled(True)
				except Exception:
					pass
				try:
					self.status.setText("Installed: None")
				except Exception:
					pass
				# hide target IP widgets when nothing installed
				try:
					if hasattr(self, '_target_ip_card'):
						self._target_ip_card.setVisible(False)
					if hasattr(self, 'target_ip_lbl'):
						self.target_ip_lbl.setVisible(False)
				except Exception:
					pass
				# update current lab label to None
				try:
					if hasattr(self, 'current_lab_lbl'):
						self.current_lab_lbl.setText("Current Lab: None")
				except Exception:
					pass
		except Exception:
			pass


	def _wrap_with_root_user(self, cmd: list) -> list:
		"""If possible, wrap `cmd` so it runs as `ROOT_USER` using sudo.
		This returns the wrapped command list or the original on failure.
		Note: uses `sudo -n -u ROOT_USER` (non-interactive). Caller must ensure
		the configured `ROOT_USER` sudoers entry exists if elevation is required.
		"""
		try:
			# No-op on Windows
			if os.name == 'nt':
				return cmd
			# prefer explicit env override but fall back to module-level default
			ru = os.environ.get('ROOT_USER', ROOT_USER)
			if not ru:
				return cmd
			# require sudo available to perform the elevation
			if shutil.which('sudo'):
				# Use non-interactive sudo to execute the command as root. This
				# matches the application's existing guidance to add a sudoers
				# NOPASSWD rule for unattended installs. If the intent is to run
				# as a specific non-root user, set ROOT_USER to that name and the
				# caller can opt out of elevation.
				return ['sudo', '-n', '--'] + list(cmd)
			return cmd
		except Exception:
			return cmd

	def install_lab(self):
		# Prevent installing a new lab if one is already installed
		if getattr(self, '_installed_lab', None):
			QMessageBox.information(self, 'Reset required', 'A lab is already installed. Reset the lab before installing another.')
			return
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
				# mark as installed and disable further installs until reset
				try:
					self._set_installed_lab(lab)
				except Exception:
					pass
				return
			# otherwise fall back to running configured installer path directly
			try:
				threading.Thread(target=self._run_script_thread, args=(installer, lab), daemon=True).start()
				try:
					self._set_installed_lab(lab)
				except Exception:
					pass
				return
			except Exception:
				pass
		# For installs that require root, run elevation/install logic in background
		# to avoid blocking the UI and causing black screens.
		try:
			threading.Thread(target=self._run_as_admin, args=(INSTALL_SCRIPT, lab), daemon=True).start()
			try:
				self._set_installed_lab(lab)
			except Exception:
				pass
		except Exception:
			# fallback to non-interactive background thread
			threading.Thread(target=self._run_script_thread, args=(INSTALL_SCRIPT, lab), daemon=True).start()

	def update_lab_script(self):
		"""Download latest lab.py from the repository and place it under /opt/lab/lab.py.
		This runs in a background thread and emits `update_done_signal` when finished.
		"""
		def _worker():
			# Accept either raw or GitHub blob URLs and normalize to raw content URL
			src = 'https://github.com/Abu-cmg/lab-files/blob/main/lab.py'
			raw = src.strip()
			try:
				if 'github.com' in raw and '/blob/' in raw:
					raw = raw.replace('https://github.com/', 'https://raw.githubusercontent.com/').replace('http://github.com/', 'http://raw.githubusercontent.com/').replace('/blob/', '/')
			except Exception:
				pass
			out_dir = os.environ.get('LAB_INSTALL_DIR', '/opt/lab')
			try:
				os.makedirs(out_dir, exist_ok=True)
			except Exception:
				pass
			# atomic download to temp file then replace
			dest = os.path.join(out_dir, 'lab.py')
			tmpdest = None
			try:
				# create temp file in system tempdir (more likely writable than /opt)
				fd, tmpdest = tempfile.mkstemp(suffix='.tmp')
				os.close(fd)
			except Exception:
				# fallback: create a path in the system tempdir
				try:
					tmpdest = os.path.join(tempfile.gettempdir(), f"lab_update_{int(time.time())}.tmp")
				except Exception:
					tmpdest = dest
			# download (prefer curl, fall back to urllib). Clean up temp file on failure.
			download_ok = False
			if shutil.which('curl'):
				try:
					subprocess.check_call(['curl', '-fsSL', raw, '-o', tmpdest])
					download_ok = True
				except Exception as e:
					self.output_signal.emit(f"[WARN] curl download failed: {e}; falling back to urllib")
			if not download_ok:
				try:
					urllib.request.urlretrieve(raw, tmpdest)
					download_ok = True
				except Exception as e:
					try:
						if tmpdest and tmpdest != dest and os.path.exists(tmpdest):
							os.remove(tmpdest)
					except Exception:
						pass
					self.output_signal.emit(f"[ERROR] Update download failed: {e}")
					return
			# Instead of attempting to overwrite /opt (which may require root),
			# save the updated script into a per-user install location so the
			# update is non-interactive and reliable across environments.
			user_dir = os.path.join(os.path.expanduser('~'), '.local', 'opt', 'lab')
			try:
				os.makedirs(user_dir, exist_ok=True)
			except Exception:
				pass
			user_dest = os.path.join(user_dir, 'lab.py')
			try:
				# If an existing user copy exists, remove it first so we replace cleanly
				try:
					if os.path.exists(user_dest):
						os.remove(user_dest)
						self.output_signal.emit(f"[INFO] Removed existing {user_dest}")
				except Exception as e_rem:
					self.output_signal.emit(f"[WARN] Could not remove existing {user_dest}: {e_rem}")

				# If a system /opt target exists and is writable by this process, remove it too
				try:
					if os.path.exists(dest):
						try:
							os.remove(dest)
							self.output_signal.emit(f"[INFO] Removed existing system {dest}")
						except Exception as e_sys_rem:
							self.output_signal.emit(f"[WARN] Could not remove system {dest}: {e_sys_rem}")
				except Exception:
					pass

				shutil.copy2(tmpdest, user_dest)
				# Normalize line endings on the target copy if needed
				try:
					if shutil.which('dos2unix'):
						subprocess.check_call(['dos2unix', user_dest])
						self.output_signal.emit('[+] Ran dos2unix on updated script')
					else:
						with open(user_dest, 'rb') as f:
							data = f.read()
						if b"\r\n" in data:
							data = data.replace(b"\r\n", b"\n")
							with open(user_dest, 'wb') as f:
								f.write(data)
							self.output_signal.emit('[+] Converted CRLF -> LF on updated script')
				except Exception:
					pass
				# ensure executable
				try:
					if os.name != 'nt':
						st = os.stat(user_dest)
						os.chmod(user_dest, st.st_mode | stat.S_IEXEC)
						# Attempt to set ownership to antori:antori when available
						try:
							import pwd, grp
							uid = pwd.getpwnam('antori').pw_uid
							gid = grp.getgrnam('antori').gr_gid
							os.chown(user_dest, uid, gid)
							self.output_signal.emit('[+] Ownership set to antori:antori')
						except Exception:
							pass
				except Exception:
					pass
				try:
					if tmpdest and tmpdest != user_dest and os.path.exists(tmpdest):
						os.remove(tmpdest)
				except Exception:
					pass
				self.output_signal.emit(f"[+] Saved updated script to {user_dest}")
				# Attempt non-interactive system install immediately (no GUI prompts).
				installed_dest = None
				try:
					# If running as root, copy directly
					if os.name != 'nt':
						try:
							if os.geteuid() == 0:
								shutil.copy2(user_dest, dest)
								st = os.stat(dest)
								os.chmod(dest, st.st_mode | stat.S_IEXEC)
								# Attempt to set ownership to antori:antori on installed path
								try:
									import pwd, grp
									uid = pwd.getpwnam('antori').pw_uid
									gid = grp.getgrnam('antori').gr_gid
									os.chown(dest, uid, gid)
									self.output_signal.emit('[+] Ownership set to antori:antori')
								except Exception:
									pass
								installed_dest = dest
								self.output_signal.emit(f"[+] Installed updated script to {dest} (running as root)")
						except Exception:
							pass
				except Exception:
					pass
				# If not installed yet, try passwordless sudo (non-interactive)
				if not installed_dest and shutil.which('sudo'):
					try:
						r = subprocess.run(['sudo', '-n', 'cp', user_dest, dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
						if r.returncode == 0:
							# try chmod
							r2 = subprocess.run(['sudo', '-n', 'chmod', '+x', dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
							installed_dest = dest
							self.output_signal.emit(f"[+] Installed updated script to {dest} via sudo")
						else:
							self.output_signal.emit(f"[WARN] Non-interactive sudo copy failed: {r.stderr.decode(errors='ignore')}")
					except Exception as e:
						self.output_signal.emit(f"[WARN] sudo copy attempt failed: {e}")
				# Emit final result: system path if installed, otherwise user path
				if installed_dest:
					self.update_done_signal.emit(installed_dest)
				else:
					self.update_done_signal.emit(user_dest)
			except Exception as e2:
				self.output_signal.emit(f"[ERROR] Failed to save updated script to user directory: {e2}")
				try:
					if tmpdest and tmpdest != dest and os.path.exists(tmpdest):
						os.remove(tmpdest)
				except Exception:
					pass
				return
		threading.Thread(target=_worker, daemon=True).start()

	def _on_update_done(self, dest_path: str):
		"""Called when update_lab_script finishes downloading/replacing the file."""
		try:
			# remember last updated path for possible system install
			self._last_update_path = dest_path
			self.log(f"[+] Update completed: {dest_path}")
			# If the updated path is under /opt, advise restart; else provide manual install instructions
			if os.path.abspath(dest_path).startswith(os.path.sep + 'opt'):
				QMessageBox.information(self, 'Update complete', f'Updated: {dest_path}\n\nPlease restart the application for changes to take effect.')
			else:
				QMessageBox.information(self, 'Update saved (manual install required)',
					f'The updated script was saved to:\n\n{dest_path}\n\nTo install system-wide, run as root:\n\nsudo cp {dest_path} /opt/lab/lab.py && sudo chmod +x /opt/lab/lab.py')
		except Exception:
			pass

    

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
					# Even when running as root, prefer to execute under the configured
					# `ROOT_USER` where appropriate (wrap via sudo -u). Fall back to
					# direct execution if wrapping fails.
					cmdlist = [script_path] + ([arg] if arg else [])
					try:
						cmdlist = self._wrap_with_root_user(cmdlist)
					except Exception:
						pass
					subprocess.Popen(cmdlist, start_new_session=True)
					self.log(f"[+] Running as root, launched script: {script_path}")
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
		# Clear installed-state to allow new installs once reset is requested
		try:
			self._set_installed_lab(None)
		except Exception:
			pass
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

	def restart_system(self):
		"""Prompt and attempt to restart the host (Linux/Debian).
		Uses `systemctl reboot` then falls back to `shutdown -r now` or `reboot`.
		Logs progress to the UI output via `output_signal` so background attempts don't touch GUI widgets.
		"""
		# Confirm with user
		try:
			resp = QMessageBox.question(self, 'Confirm Restart', 'Restart the system now? This will reboot the host.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
		except Exception:
			# If QMessageBox unavailable for any reason, require explicit return
			return
		if resp != QMessageBox.StandardButton.Yes:
			return
		# Only attempt on Linux
		if not sys.platform.startswith('linux'):
			QMessageBox.warning(self, 'Unsupported', 'Restart is supported only on Linux (Debian).')
			return
		self.log('[!] Initiating system restart...')

		def _do_restart():
			# Use output_signal so background thread doesn't manipulate GUI directly
			try:
				self.output_signal.emit('[!] Attempting: systemctl reboot')
				subprocess.check_call(['systemctl', 'reboot'])
			except Exception:
				try:
					self.output_signal.emit('[!] Fallback: shutdown -r now')
					subprocess.check_call(['shutdown', '-r', 'now'])
				except Exception:
					try:
						self.output_signal.emit('[!] Fallback: reboot')
						subprocess.check_call(['reboot'])
					except Exception as e:
						self.output_signal.emit(f'[ERROR] Restart failed: {e}')

		threading.Thread(target=_do_restart, daemon=True).start()

	def open_shell(self):
		# Open Shell intentionally disabled. Keep a no-op placeholder so
		# any code that calls this method won't raise; log for visibility.
		try:
			self.log('[!] Open Shell disabled')
		except Exception:
			pass

	def toggle_maximize(self):
		"""Toggle between maximized and normal window states (acts like Kali maximize)."""
		try:
			if self.isMaximized():
				self.showNormal()
				# update button appearance if desired
				# fullscreen button removed; no UI text to update
			else:
				self.showMaximized()
				# fullscreen button removed; no UI text to update
		except Exception as e:
			self.log(f"[ERROR] Toggle maximize failed: {e}")


# ---------------------------- MANAGE UI BLOCK START ----------------------------
# This whole section (the ManageLabsDialog class and the wiring above) can be
# commented out by removing or commenting the block between the START/END markers
# or by setting the environment variable `ENABLE_MANAGE_UI=0` before launching.
class ManageLabsDialog(QMessageBox):
	"""Manage dialog allowing adding/editing lab entries at runtime.
	Provides a selector to load existing labs for editing and a simple form
	to add new labs. Persisted via `save_persisted_labs()` when saved.
	"""
	def __init__(self, parent: LabWindow):
		super().__init__(parent)
		self.setWindowTitle('Manage Labs')
		self.parent = parent
		self.setIcon(QMessageBox.Icon.Information)
		# Build a simple form using standard widgets inside the message box
		from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QWidget, QLabel
		self._w = QWidget()
		self._form = QFormLayout(self._w)

		# existing selector (index 0 = New...)
		self.selector = QComboBox()
		self.selector.addItem('New lab...')
		for t in sorted(LABS.keys()):
			self.selector.addItem(t)
		self.selector.currentIndexChanged.connect(self._on_select_existing)
		self._form.addRow(QLabel('Edit existing:'), self.selector)

		self.title_in = QLineEdit()
		self.code_in = QLineEdit()
		self.desc_in = QLineEdit()
		self.diff_in = QComboBox()
		self.diff_in.addItems(['Easy', 'Medium', 'Hard'])
		self.url_in = QLineEdit()
		self._form.addRow('Title:', self.title_in)
		self._form.addRow('Code (identifier):', self.code_in)
		self._form.addRow('Description:', self.desc_in)
		self._form.addRow('Difficulty:', self.diff_in)
		self._form.addRow('Installer URL (optional):', self.url_in)
		self.setInformativeText('Select an existing lab to edit or choose New lab... to add.')
		# embed widget
		self.layout().addWidget(self._w)
		# buttons
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		self.layout().addWidget(bb)
		bb.accepted.connect(self._on_accept)
		bb.rejected.connect(self.reject)
		# tracking selected original title/code when editing
		self._orig_title = None
		self._orig_code = None

	def _on_select_existing(self, idx: int):
		# idx 0 == New lab...
		if idx <= 0:
			self._orig_title = None
			self._orig_code = None
			self.title_in.clear()
			self.code_in.clear()
			self.desc_in.clear()
			self.url_in.clear()
			self.diff_in.setCurrentIndex(0)
			return
		title = self.selector.currentText()
		self._orig_title = title
		try:
			code, desc = LABS.get(title, ('', ''))
		except Exception:
			code, desc = ('', '')
		self._orig_code = code
		self.title_in.setText(title)
		self.code_in.setText(code)
		# Set difficulty from explicit mapping if present, else fall back to parsing
		diff_used = None
		try:
			if title in LAB_DIFFICULTY:
				diff_used = LAB_DIFFICULTY.get(title)
			else:
				# legacy: parse trailing marker from description
				if isinstance(desc, str):
					m = re.search(r"\(?\s*(easy|medium|hard)\s*\)?\s*$", desc, re.I)
					if m:
						diff_used = m.group(1).capitalize()
						# strip marker from visible description
						desc = re.sub(r"\(?\s*(easy|medium|hard)\s*\)?\s*$", '', desc, flags=re.I).strip()
		except Exception:
			diff_used = None
		if diff_used:
			try:
				self.diff_in.setCurrentText(diff_used)
			except Exception:
				# best-effort index mapping
				if diff_used.lower() == 'easy':
					self.diff_in.setCurrentIndex(1)
				elif diff_used.lower() == 'medium':
					self.diff_in.setCurrentIndex(2)
				elif diff_used.lower() == 'hard':
					self.diff_in.setCurrentIndex(3)
		self.desc_in.setText(desc)
		self.url_in.setText(LAB_INSTALLERS.get(code, ''))
		# difficulty may have been parsed from the description above

	def _on_accept(self):
		title = self.title_in.text().strip()
		code = self.code_in.text().strip()
		desc = self.desc_in.text().strip()
		diff = self.diff_in.currentText().strip()
		url = self.url_in.text().strip()
		if not title or not code:
			QMessageBox.information(self.parent, 'Validation', 'Title and Code are required')
			return
		# Update LABS and LAB_INSTALLERS in-memory
		try:
			# If editing an existing title and it changed, remove the old entry
			if self._orig_title and self._orig_title != title:
				try:
					del LABS[self._orig_title]
				except Exception:
					pass
			# Remove any other entry that uses the same code (avoid duplicates)
			for k, v in list(LABS.items()):
				if v and v[0] == code and k != title:
					try:
						del LABS[k]
					except Exception:
						pass
			# Persist description unchanged and store difficulty separately
			clean_desc = desc or ''
			clean_desc = re.sub(r"\(?\s*(easy|medium|hard)\s*\)?\s*$", '', clean_desc, flags=re.I).strip()
			LABS[title] = (code, clean_desc)
			# store difficulty mapping (use default 'Easy' if empty)
			try:
				if diff:
					LAB_DIFFICULTY[title] = diff
				else:
					LAB_DIFFICULTY.pop(title, None)
			except Exception:
				pass
			if url:
				LAB_INSTALLERS[code] = url
			else:
				LAB_INSTALLERS.pop(code, None)
			# rebuild cards: detach old widgets
			try:
				for w in list(self.parent.cards):
					try:
						w.setParent(None)
					except Exception:
						pass
			except Exception:
				pass
			self.parent.cards = []
			while self.parent.grid.count():
				item = self.parent.grid.takeAt(0)
				w = item.widget() if item is not None else None
				if w:
					try:
						w.setParent(None)
					except Exception:
						pass
			self.parent._make_cards()
			self.parent._arrange_cards()
			# persist changes to disk so added/edited labs survive restarts
			save_persisted_labs()
			# update selector contents to reflect changes
			try:
				self.selector.blockSignals(True)
				self.selector.clear()
				self.selector.addItem('New lab...')
				for t in sorted(LABS.keys()):
					self.selector.addItem(t)
			finally:
				try:
					self.selector.blockSignals(False)
				except Exception:
					pass
			self.accept()
			self.parent.log(f"[+] Added/updated lab: {title} ({code})")
		except Exception as e:
			QMessageBox.information(self.parent, 'Error', f'Failed to add lab: {e}')

# ----------------------------- MANAGE UI BLOCK END -----------------------------


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
		# Startup ASCII banner (emitted to UI console after window created)
		STARTUP_BANNER = r"""          
                        
    _     _ _______ _______ _     _  _____  _______  _____  _     _ _______ ______ 
    |_____| |_____| |       |____/  |     | |______ |   __| |     | |_____| |     \
    |     | |     | |_____  |    \_ |_____| ______| |____\| |_____| |     | |_____/
                                                                                
                                         - ATTACK BOX (beta 1.0)            
																     
																	 """
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
	# Emit startup banner into the application's log console where `output_signal` is handled
	try:
		for _ln in STARTUP_BANNER.splitlines():
			try:
				w.output_signal.emit(_ln)
			except Exception:
				pass
	except Exception:
		pass
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
