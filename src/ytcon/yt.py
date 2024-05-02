# - = Standart modules = -
import os
import re
import sys
import time
import pickle
import pprint
import threading
import traceback
import subprocess
from pathlib import Path
# - = - = - = - = - = - = -
import urwid
import ffmpeg # | !!!! "ffmpeg-python", NOT "ffmpeg" !!! | # https://kkroening.github.io/ffmpeg-python/ # python310-ffmpeg-python

import clipman

import yt_dlp
#import notify2

debug_that_will_be_saved_later = []
logs_that_will_be_printed_later = []

# - = - Check ffmpeg installed in system - = - = - = -
try:
	# Try to launch it
	subprocess.run("ffmpeg -version", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	subprocess.run("ffprobe -version", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except subprocess.CalledProcessError as e:
	# If there was a command execution error, ffmpeg is not installed
	print("\n[!!] FFMPEG and FFPROBE is not installed in your system. Install it using system package manager:\n - sudo apt install ffmpeg\n - sudo dnf install ffmpeg\n - sudo zypper install ffmpeg\n - sudo pacman -S ffmpeg.\n\nProgram execution cannot be continued. YTCON will be exit now.\n")
	sys.exit(1)
# - = - = - = - = - = - = - = - = - = - = - = - = - = -

# - = CHECK SYSTEM PATHS - = - = - = - = - = - = - = - =
# Check if it is android termux emulator and change dir to user-reachable internal storage
this_is_android_device = False
if os.getcwd().find("com.termux") != -1:
	print("[YTCON] Termux not user-reachable directory detected. Changing to /storage/emulated/0...")
	logs_that_will_be_printed_later.append("[YTCON] Termux not user-reachable directory detected.")
	logs_that_will_be_printed_later.append("[YTCON] Changing to /storage/emulated/0...")
	os.chdir("/storage/emulated/0")
	this_is_android_device = True
# - - - - - - - - - - - - -
# Current folder permissions check
try:
	with open("write_test", "wb") as filee:
		pass
	os.remove("write_test")
except:
	print(os.getcwd())
	print("[!!] Current folder is unwritable!")
	if this_is_android_device:
		print("Maybe Termux doesn't have storage permissions?")
	sys.exit(1)
# - - - - - - - - - - - - -
# /tmp folder check (For android and windows compability)
try:
	with open("/tmp/write_test", "wb") as filee:
		pass
	os.remove("/tmp/write_test")
	log_folder = "/tmp/"
except:
	logs_that_will_be_printed_later.append("[YTCON] /tmp folder is unavalible (windows, android?). setting current dir for logs..")
	log_folder = ""
# - - - - - - - - - - - - -
# Save file folder check
if "XDG_CONFIG_HOME" in os.environ:
	configpath = os.path.expanduser(os.environ["XDG_CONFIG_HOME"] + "/ytcon/")
else:
	configpath = os.path.expanduser("~/.config/ytcon/")

try:
	Path(configpath).mkdir(parents=True, exist_ok=True)
	with open(configpath + "write_test", "wb") as filee:
		pass
	os.remove(configpath + "write_test")
except:
	print(traceback.format_exc())
	print("= = =\n[!!] An error was occurred!\n")
	print("Save file folder check failed. Maybe XDG_CONFIG_HOME env or dir permissions broken?")
	print("The following path has problems: " + configpath)
	sys.exit(1)
# - = - = - = - = - = - = - = - = - = - = - = - = - = - =

class SettingsClass:
	""" Сontains settings data and methods for them """
	def __init__(self):

		# Default settings
		self.settings = {
			"special_mode": False,
			"clipboard_autopaste": True,
			"no_check_certificate": False,
			"ignoreerrors": False,
			"progressbar_appearance": "detailed",
			}

	class SettingNotFoundError(Exception):
		""" Called if the specified setting is not found (see def get_setting) """

	def show_settings_call(self, _=None):
		""" Settings display state switch, made for urwid.Button(on_press=show_settings_call) """
		RenderClass.settings_show = not RenderClass.settings_show

	def get_setting(self, setting_name):
		""" Get setting, if it not found, calls SettingNotFoundError """
		try:
			return self.settings[setting_name]
		except KeyError as exc:
			raise self.SettingNotFoundError from exc

	def write_setting(self, setting_name, setting_content):
		""" Writes the settings to the memory. Made for the possible use of some "hooks" in the future """
		self.settings[setting_name] = setting_content

	def save(self, button=None): # in the second argument urwid puts the button of which the function was called
		""" Uses pickle for saving settings from memory to ~/.config/settings.db"""
		logger.debug(Path(configpath).mkdir(parents=True, exist_ok=True)) # Create dirs if they don't already exist
		with open(configpath + "settings.db", "wb") as filee:
			pickle.dump(self.settings, filee)
		journal.info(f"[YTCON] {configpath}settings.db saved")
		RenderClass.flash_button_text(button, colors.green)

	def load(self, button=None): # in the second argument urwid puts the button of which the function was called
		""" Uses pickle for loading settings from ~/.config/settings.db to memory """
		try:
			with open(configpath + "settings.db", "rb") as filee:
				self.settings.update(pickle.load(filee))
			journal.info(f"[YTCON] {configpath}settings.db loaded")
			update_checkboxes()
			self.update_ydl_opts()
			RenderClass.flash_button_text(button, colors.green)
		except FileNotFoundError:
			# If file not found
			journal.warning(f"[YTCON] Saved settings load failed: FileNotFoundError: {configpath}settings.db")
			RenderClass.flash_button_text(button, colors.red)
		except EOFError as exc:
			# If save file is corrupted
			logger.debug(traceback.format_exc())
			journal.warning(f"[YTCON] Saved settings load FAILED: EOFError: {exc}: {configpath}settings.db")
			journal.error("[YTCON] YOUR SETTINGS FILE IS CORRUPTED. Default settings restored and corrupted save file removed.")
			self.write_setting("clipboard_autopaste", False)
			update_checkboxes()
			journal.warning("[YTCON] Clipboard autopaste has been turned off for security reasons. You can it enable it in settings")
			logger.debug(os.remove(f"{configpath}settings.db"))

	def clipboard_autopaste_switch(self, _=None, _1=None):
		""" Clipboard autopaste switch function for urwid.Button's. FOR BACK COMPABILITY """
		self.setting_switch(None, None, name="clipboard_autopaste")

	def setting_switch(self, _=None, state=None, name=None):
		""" Switches state to negative current state or to state set by state argument. Made for for urwid.Button's """
		if name is None:
			raise TypeError

		if state is None:
			state = not self.get_setting(name)

		journal.info("")
		journal.info(f"[YTCON] {name}: {self.get_setting(name)} -> {state}")
		self.write_setting(name, state)
		self.update_ydl_opts()
		sett.settings_soft_update_scheduled = True

	def setting_change_content(self, _=None, _1=None, data=None):
		"""
		Change content in setting where negative state cannot be determined.
		Made for for urwid.Button's with pre-writed arguments
		"""
		if data is None:
			raise TypeError

		name = data[0]
		set_data = data[1]

		journal.info("")
		journal.info(f"[YTCON] {name}: {self.get_setting(name)} -> {set_data}")
		self.write_setting(name, set_data)
		self.update_ydl_opts()
		sett.settings_soft_update_scheduled = True

	def update_ydl_opts(self):
		""" Updates some setting-related ydl_opts. Maybe something like post-change scripts? """
		#journal.info(pprint.pformat(variables.ydl_opts))
		#journal.info("updated ydl_opts")

		# - = Special mode cookie extractor activator = -
		if settings.get_setting("special_mode") is True and "cookiesfrombrowser" not in variables.ydl_opts:
			variables.ydl_opts["cookiesfrombrowser"] = ('chromium', ) # needed for some sites with login only access. you may need to replace it with the correct one
		elif settings.get_setting("special_mode") is False and "cookiesfrombrowser" in variables.ydl_opts:
			del variables.ydl_opts["cookiesfrombrowser"]
		# - = - = - = - = - = - = - = - = - = - = - = - =

		# - = Certificates ignore activator = -
		if settings.get_setting("no_check_certificate") is True and "nocheckcertificate" not in variables.ydl_opts:
			variables.ydl_opts["nocheckcertificate"] = True
		elif settings.get_setting("no_check_certificate") is False and "nocheckcertificate" in variables.ydl_opts:
			del variables.ydl_opts["nocheckcertificate"]
		# - = - = - = - = - = - = - = - = - = - = - = - =

		# - = Certificates ignore activator = -
		if settings.get_setting("ignoreerrors") is True and "ignoreerrors" not in variables.ydl_opts:
			variables.ydl_opts["ignoreerrors"] = True
		elif settings.get_setting("ignoreerrors") is False and "ignoreerrors" in variables.ydl_opts:
			del variables.ydl_opts["ignoreerrors"]
		# - = - = - = - = - = - = - = - = - = - = - = - =

		#journal.info(pprint.pformat(variables.ydl_opts))

from log import journal, logger

from control.variables import variables
from control.exit import exit_with_exception, traceback

from render.colors import colors
from render.progressbar_defs import progressbar_defs

from app_update import app_updates

settings = SettingsClass()

class RenderClass_base:
	""" It stores some information about rendering, screen, some functions for working with widgets and some functions that are related to rendering. """
	def __init__(self):
		self.settings_show = False
		self.settings_showed = False

		self.errorprinter_animation = 3

		# Variables that cannot have initial values but need to be declared
		self.width = None
		self.height = None
		self.loop = None

	def add_row(self, text):
		""" Add an additional widget to top_pile for drawing a new task """
		top_pile.contents = top_pile.contents + [[urwid.Text(text), top_pile.options()],]

	def edit_or_add_row(self, text, pos):
		""" Edit a widget with a specific serial number, and if there is none, then create a new one """
		if pos > self.calculate_widget_height(top_pile) - 1:
			self.add_row(text)
		else:
			top_pile.contents[pos][0].set_text(text)

	def remove_all_widgets(self):
		"""
		If there are obsolete widgets in top_pile that will not be changed, they are considered garbage,
		for this you need to call remove_all_widgets, all widgets, including unnecessary old ones, 
		will be removed, but will be recreated if needed
		"""
		top_pile.contents = []

	def calculate_widget_height(self, widget):
		""" (recursively) Counts how many rows the widget occupies in height """
		if isinstance(widget, urwid.Text):
			# Returns the number of lines of text in the widget
			return len(widget.text.split('\n'))
		if isinstance(widget, urwid.Pile):
			# Recursively sums the heights of widgets inside a urwid.Pile container
			return sum(self.calculate_widget_height(item[0]) for item in widget.contents)
		return 0 # Return 0 for unsupported widget types (?)

	def flash_button_text(self, button, color, times=4):
		""" Makes the button to blink in the specified color """
		if button is None:
			return None
		temp1 = button.get_label()
		for _ in range(1, times+1):
			button.set_label((color, temp1))
			RenderClass.loop.draw_screen()
			time.sleep(0.1)
			button.set_label(temp1)
			RenderClass.loop.draw_screen()
			time.sleep(0.1)
		return None

RenderClass = RenderClass_base()

def hook(d):
	""" A hook that is called every time by yt-dlp when the state of the task changes (example percent changed),
	and the hook writes the necessary information to the class in order to draw it later """
	try:
		# - = - = - log spam filter - = - = - = - =
		if "automatic_captions" in d["info_dict"]:
			del d["info_dict"]["automatic_captions"]
		if "formats" in d["info_dict"]:
			del d["info_dict"]["formats"]
		if "thumbnails" in d["info_dict"]:
			del d["info_dict"]["thumbnails"]
		if "heatmap" in d["info_dict"]:
			del d["info_dict"]["heatmap"]
		# - = - = - = - = - = - = - = - = - = - = -

		logger.debug(pprint.pformat(d))
		if "multiple_formats" in variables.queue_list[d["info_dict"]["original_url"]]:
			indexx = d["info_dict"]["original_url"] + ":" + d["info_dict"]["format_id"]
		else:
			indexx = d["info_dict"]["original_url"]

		# - = - resolution detector - = - = - = - = - = - = - = - = - = -
		if variables.queue_list[indexx]["resolution"].find("???") > -1 and (variables.queue_list[indexx].get("resolution_detection_tried_on_byte", 0) + 4000000) < int(d.get("downloaded_bytes", 0)) and variables.queue_list[indexx].get("resolution_detection_tries", 0) < 5:
			# int(d["downloaded_bytes"]) > 4000000 # if the file size is too smol, it does not have the needed metadata and ffprobe gives an error
			logger.debug("DOWNBYTES: %s", str(d["downloaded_bytes"]))
			temp1 = get_resolution_ffprobe(d["tmpfilename"])
			temp2 = str(variables.queue_list[indexx].get("resolution_detection_tries", 0)+1)

			if temp1 is not None:
				variables.queue_list[indexx]["resolution"] = temp1
				journal.info(f"[YTCON] Detected resolution: {temp1} (on try {temp2})" )
			else:
				journal.warning(f'[YTCON] Resolution detection failed: ffprobe gave an error (try {temp2})')
			variables.queue_list[indexx]["resolution_detection_tried_on_byte"] = int(d["downloaded_bytes"])
			variables.queue_list[indexx]["resolution_detection_tries"] = variables.queue_list[indexx].get("resolution_detection_tries", 0) + 1
		# - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = -

		variables.queue_list[indexx]["file"] = d["info_dict"]['_filename']
		if variables.queue_list[indexx]["status"] == "exists" and d["status"] == "finished":
			raise InputHandler.InputProcessed
		variables.queue_list[indexx]["status"] = d["status"]

		if int(d["_percent_str"].strip().split(".")[0]) > 100:
			journal.warning("[YTCON] yt-dlp returned percent more than 100%: \"" + d["_percent_str"].strip() + "\". Values remain unchanged...")
		else:
			variables.queue_list[indexx]["status_short_display"] = d["_percent_str"].strip()
			variables.queue_list[indexx]["percent"] = d["_percent_str"].strip()
		variables.queue_list[indexx]["speed"] = d["_speed_str"].strip()

		try:
			if variables.queue_list[indexx]["eta"].count(":") > 1:
				variables.queue_list[indexx]["eta"] = d["_eta_str"].strip()
			else:
				variables.queue_list[indexx]["eta"] = "ETA " + d["_eta_str"].strip()
		except KeyError:
			if d["status"] == "finished":
				variables.queue_list[indexx]["eta"] = "ETA 00:00"

		try:
			if d["_total_bytes_estimate_str"].strip() == "N/A":
				variables.queue_list[indexx]["size"] = d["_total_bytes_str"].strip()
			else:
				variables.queue_list[indexx]["size"] = d["_total_bytes_estimate_str"].strip()
		except KeyError:
			pass

		try:
			variables.queue_list[indexx]["downloaded"] = d["_downloaded_bytes_str"].strip()
		except:
			pass

		d["info_dict"]["formats"] = []
		d["info_dict"]["thumbnails"] = []
		d["info_dict"]["subtitles"] = []
		d["info_dict"]["fragments"] = []

		logger.debug(pprint.pformat(variables.queue_list))
	except InputHandler.InputProcessed:
		pass
	except:
		exit_with_exception(traceback.format_exc())

def downloadd(url): # pylint: disable=too-many-return-statements
	"""
	The main component of ytcon, this class sets the basic parameters for the video,
	composes the title and starts downloading.

	For each link one thread (exception: playlists)
	"""
	try:
		if url in variables.queue_list:
			if variables.queue_list[url]["status"] not in ("exists", "finished"):
				journal.error(f"[YTCON] Video link \"{progressbar_defs.name_shortener(url, 40)}\" is already downloading!")
				return None

		with yt_dlp.YoutubeDL(variables.ydl_opts) as ydl:
			# needed for some sites. you may need to replace it with the correct one
			if settings.get_setting("special_mode") is True:
				ydl.params["http_headers"]["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
				# "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
			# - = - = - = Get downloading formats (yt) and generate filename (global) = -
			infolist = ydl.extract_info(url, download=False)

			# - = - = - log spam filter - = - = - = - =
			if infolist is None: # yt-dlp returns videos with errors as None :|| # TODO?
				journal.warning("ydl.extract_info RETURNED NONE", show=False)
				return None
			if "automatic_captions" in infolist:
				del infolist["automatic_captions"]
			if "formats" in infolist:
				del infolist["formats"]
			if "thumbnails" in infolist:
				del infolist["thumbnails"]
			if "heatmap" in infolist:
				del infolist["heatmap"]
			logger.debug(pprint.pformat(infolist))
			# - = - = - = - = - = - = - = - = - = - = -

			# - Playlists support - = - = - = - = - = - = - = - = - = - = -
			if "entries" in infolist:
				for i in infolist["entries"]:
					if i is None: # yt-dlp returns videos with errors as None :||
						continue
					threading.Thread(target=downloadd, args=(i["webpage_url"],), daemon=True).start()
				return None
			# - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = -

			# - Name fiter + assemble - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = -
			temp1 = re.sub(r"[^A-Za-z0-9А-Яа-я \-_.,]", "", infolist["title"].replace("&", "and")) # get title, remove all characters except allowed # >"|" -> "｜" yt-dlp, wtf?
			temp1 = " ".join(temp1.removesuffix(" 1").split()) # remove space duplicates and remove 1 in the end because for some reason yt-dlp adds it on its own
			id_in_filename = infolist["id"].removesuffix("-1")
			filename = f'{temp1} [{id_in_filename}].{infolist["ext"]}'

			# Name too long handler (https://github.com/ytdl-org/youtube-dl/issues/29912 and more more more issues)
			if len(filename.encode('utf-8')) > 190:
				# ^^^^^^^^^^^^^^^^^^^^^^^ counting bytes in filename
				logger.debug("ERROR: FILENAME MORE THAN 190 BYTES. SHORTING...")
				while len(filename.encode('utf-8')) > 190:
					temp1 = " ".join(temp1.split()[:-1]) # remove 1 last word
					filename = f'{temp1} [{id_in_filename}].{infolist["ext"]}'
					logger.debug(filename)
					logger.debug(len(filename.encode('utf-8')))
			# - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = -

			# Check if file exists
			exists = os.path.exists(filename)
			if exists:
				journal.warning(f'[YTCON] FILE "{filename}" EXISTS')

			# - = - = - = Set parameters = -
			multiple_formats = False
			if infolist["extractor"] == "youtube" and "requested_formats" in infolist:
				multiple_formats = True

			temp1_index = map_variables.main(multiple_formats, infolist, filename)

			if exists:
				variables.queue_list[infolist["original_url"]]["status"] = "exists"
				if multiple_formats:
					for i in infolist["requested_formats"]:
						temp1_index = infolist["original_url"] + ":" + i["format_id"]
						variables.queue_list[temp1_index]["status"] = "exists"
						variables.queue_list[temp1_index]["downloaded"] = variables.queue_list[temp1_index]["size"]
						variables.queue_list[temp1_index]["status_short_display"] = "Exist"
						variables.queue_list[temp1_index]["percent"] = "100.0%"
				else:
					variables.queue_list[temp1_index]["downloaded"] = variables.queue_list[temp1_index]["size"]
					variables.queue_list[temp1_index]["status_short_display"] = "Exist"
					variables.queue_list[temp1_index]["percent"] = "100.0%"
			# - = - = - = - = - = - = - = - = - = - = - = - =
			logger.debug(pprint.pformat(variables.queue_list))

			with yt_dlp.YoutubeDL(variables.ydl_opts | {"outtmpl": filename}) as ydl2:
				logger.debug(ydl2.download(url))
				if variables.last_error.find("[Errno 36] File name too long") > -1:
					raise yt_dlp.utils.DownloadError(variables.last_error)
			# - = Mark meta as finished = -
			if "meta_index" in variables.queue_list[infolist["original_url"]]:
				variables.queue_list[infolist["original_url"]]["status"] = "finished"

	except yt_dlp.utils.DownloadError as e:
		journal.error(str(e), show=False)
		map_variables.mark_as_error(url)
		return None
	except:
		exit_with_exception(traceback.format_exc())
		return None

	# - = - = - = [Post-processing] = - = - = - #
	try:
		if variables.queue_list[temp1_index]["status"] == "exists":
			return None # skip post-process if file already exists

		# = - = -
		if variables.queue_list[temp1_index]["status"] != "finished":
			# IF DOWNLOAD THREAD EXITS WITHOUT ERROR (this usually occurs due to the "ignoreerrors" flag)
			journal.debug("DOWNLOAD THREAD EXITED WITHOUT ERROR")
			map_variables.mark_as_error(url)
			return None
		# = - = -

		# Removes Last-modified header. Repeats --no-mtime functionality which is not present in yt-dlp embeded version
		os.utime(variables.queue_list[temp1_index]["file"])

		# Remove file after downloading
		if variables.delete_after_download is True:
			journal.warning(f"[YTCON] REMOVING {variables.queue_list[temp1_index]['file']}...")
			os.remove(variables.queue_list[temp1_index]["file"])
	except:
		exit_with_exception(traceback.format_exc())

	return None

class MapVariablesClass:
	""" Created to simplify the distribution of parameters, work is organized here with playlists and requesting several formats on youtube """

	def main(self, multiple_formats, infolist, filename):
		""" Finding some specific parameters and using a loop assign if there are several files """
		if multiple_formats:
			variables.queue_list[infolist["original_url"]] = {}
			variables.queue_list[infolist["original_url"]]["meta_index"] = True
			variables.queue_list[infolist["original_url"]]["multiple_formats"] = True
			variables.queue_list[infolist["original_url"]]["formats"] = []
			variables.queue_list[infolist["original_url"]]["status"] = "waiting"
			for i in infolist["requested_formats"]:
				temp1_index = infolist["original_url"] + ":" + i["format_id"]
				variables.queue_list[infolist["original_url"]]["formats"].append(i["format_id"])
				self.map_variables(temp1_index, infolist, i, filename)
			return temp1_index
		# else:
		temp1_index = infolist["original_url"]
		self.map_variables(temp1_index, infolist, infolist, filename)
		return temp1_index

	def map_variables(self, temp1_index, infolist, i, filename):
		""" Main parameter assigner. In some cases, it can be used in a loop """
		variables.queue_list[temp1_index] = {}
		variables.queue_list[temp1_index]["status"] = "waiting"
		variables.queue_list[temp1_index]["status_short_display"] = "Wait"
		variables.queue_list[temp1_index]["percent"] = "0.0%"
		variables.queue_list[temp1_index]["speed"] = "0KiB/s"
		try:
			variables.queue_list[temp1_index]["size"] = str(round(i["filesize"]/1e+6)) + "MiB"
		except KeyError:
			variables.queue_list[temp1_index]["size"] = "???MiB"
		variables.queue_list[temp1_index]["downloaded"] = "0MiB"
		variables.queue_list[temp1_index]["eta"] = "ETA ??:??"
		variables.queue_list[temp1_index]["name"] = infolist["fulltitle"]
		if i["resolution"] == "audio only":
			variables.queue_list[temp1_index]["resolution"] = "audio"
		else:
			if i.get("width", None) is None and i.get("height", None) is None:
				variables.queue_list[temp1_index]["resolution"] = "???х???"
			else:
				variables.queue_list[temp1_index]["resolution"] = (str(i.get("width", None)) + "x" + str(i.get("height", None))).replace("None", "???")
		variables.queue_list[temp1_index]["site"] = infolist["extractor"].lower()
		variables.queue_list[temp1_index]["file"] = filename

	def mark_as_error(self, url):
		""" Change the status of the downloaded link to Error if such link exists """
		if url in variables.queue_list:
			variables.queue_list[url]["status"] = "error"
			if "multiple_formats" in variables.queue_list[url]:
				for i in url["formats"]:
					temp1_index = url + ":" + i
					variables.queue_list[temp1_index]["status"] = "error"
					variables.queue_list[temp1_index]["status_short_display"] = "Error"
			else:
				variables.queue_list[url]["status_short_display"] = "Error"

map_variables = MapVariablesClass()

def render_tasks(loop, _):
	"""
	Graphic part of ytcon - draws a colored video queue from variables.queue_list
	Shows names, extractors, ETAs, generates progress bars, etc.
	"""
	try:
		if not variables.queue_list: # if variables.queue_list == {}
			RenderClass.edit_or_add_row((colors.cyan, "No tasks"), 0)
		else:
			r = 0
			for _, i in variables.queue_list.items():
				if "meta_index" in i:
					continue # just ignore meta-downloads

				rcm = progressbar_defs
				ws = rcm.whitespace_stabilization

				errorr = i["status"] == "error"

				temp1 = f'{ws(i["status_short_display"], 7)}{rcm.progressbar_generator(i["percent"], errorr)}{ws(i["speed"], 13)}|{ws(rcm.bettersize(i["downloaded"])+"/"+rcm.bettersize(i["size"]), 15)}| {ws(i["eta"], 9)} | {ws(i["site"], 7)} | {ws(i["resolution"], 9)} | '
				fileshortname = rcm.name_shortener(i["name"], RenderClass.width - len(temp1))
				temp1 = temp1 + fileshortname

				if i["status"] == "waiting":
					RenderClass.edit_or_add_row((colors.cyan, temp1), r)
				elif i["status"] == "error":
					RenderClass.edit_or_add_row((colors.red, temp1), r)
				elif i["status"] == "exists":
					RenderClass.edit_or_add_row((colors.yellow, temp1), r)
				elif i["status"] == "finished":
					RenderClass.edit_or_add_row((colors.green, temp1), r)
				else:
					RenderClass.edit_or_add_row(temp1, r)

				r = r+1
		loop.set_alarm_in(0.3, render_tasks)
	except:
		exit_with_exception(traceback.format_exc())


class InputHandlerClass:
	"""
		Class for processing user input.
		Contains a modified Urwid.edit widget and functions for processing commands and URLs
	"""
	class InputBox(urwid.Edit):
		""" 
			A modified urwid.Edit Widget.
			If the user presses Enter, it collects text and sent text to input_handler,
			and after that is it cleans the input field
		"""
		def is_skipable(self, inp):
			"""
				Determines whether this character can be skipped.
				Used in ALT key handlers to determine whether a character is part of a word
			"""
			if inp.isalpha() or inp.isdigit():# or inp == "%":
				return True
			return False

		def get_cords(self, size):
			""" 
				Takes the cursor coordinates from the InputBox to determine which character the cursor is currently on.
				Doesn't work well if the text is muiti-line
			"""
			tmp1 = self.get_cursor_coords(size)[0]
			if len(self.get_cursor_coords(size)) > 1 and self.get_cursor_coords(size)[1] > 0:
				if variables.alt_plus_arrow_multiline_message_sended is False:
					journal.error("[YTCON] Navigation using Alt+Arrow in a multi-line input field does not work as expected, this is a known problem, and we cannot solve it due to the peculiarities of the engine.\n\nNavigation will be inaccurate and skip some characters for no reason.\nWe apologize for the inconvenience caused.")
					variables.alt_plus_arrow_multiline_message_sended = True
				tmp1 = tmp1 * self.get_cursor_coords(size)[1]
				return tmp1
			return tmp1 - 12

		def get_safe_text(self):
			""" Limits the end of the text to avoid infinite recursion """
			return self.get_edit_text() + "??"

		def keypress(self, size, key):
			""" Overrides a regular class. """
			#journal.info(key)

			if key in ('meta left', 'ctrl left'):
				# Alt + Left and Ctrl + Left key handler. Moves left one word
				super().keypress(size, "left")
				temp1 = ""
				# Moves one letter at a time until it finds a special symbol that cannot an part of word
				while self.is_skipable(self.get_safe_text()[self.get_cords(size)-1]):# and self.get_cords(size) > 0:
					endless_loop_detector_first = self.get_cords(size)
					temp1 = temp1 + self.get_safe_text()[self.get_cords(size)-1]
					super().keypress(size, "left")

					# If the coordinates have not changed since the last cursor movement, then the border has been reached
					endless_loop_detector_two = self.get_cords(size)
					if endless_loop_detector_first == endless_loop_detector_two:
						logger.debug("meta left: loop detected")
						break
				return None

			if key in ('meta right', 'ctrl right'):
				# Alt + Right and Ctrl + Right key handler. Moves right one word
				super().keypress(size, "right")
				temp1 = ""
				# Moves one letter at a time until it finds a special symbol that cannot an part of word
				while self.is_skipable(self.get_safe_text()[self.get_cords(size)]):# and self.get_cords(size) > 0:
					endless_loop_detector_first = self.get_cords(size)
					temp1 = temp1 + self.get_safe_text()[self.get_cords(size)]
					super().keypress(size, "right")

					# If the coordinates have not changed since the last cursor movement, then the border has been reached
					endless_loop_detector_two = self.get_cords(size)
					if endless_loop_detector_first == endless_loop_detector_two:
						logger.debug("meta right: loop detected")
						break
				return None

			if key == 'meta backspace':
				# Alt + Backspace key handler. Removes last word in inputbox
				if len(self.get_edit_text()) < 3:
					super().keypress(size, "backspace")
					return None

				temp1 = list(self.get_edit_text())
				temp2 = False
				if self.is_skipable(temp1[-1]):
					temp2 = True
				else:
					if self.is_skipable(temp1[-2]):
						temp2 = True
					del temp1[-1]

				while self.is_skipable(temp1[-1]) and temp2 is True:
					del temp1[-1]
					if len(temp1) == 0:
						break

				self.set_edit_text("".join(temp1))
				return None

			if key == 'enter':
				# If enter pressed, send URL to input_handler and clear inputbox
				InputHandler.input_handler(self.get_edit_text())
				self.set_edit_text("")
				return None

			# If the conditions do not work and the key is not assigned
			return super().keypress(size, key)

	class InputProcessed(Exception):
		""" Dummy exception, when called means that the processing of this request is completed. """

	def input_handler(self, text):
		""" Main input handler logic """
		try:
			original_text = text
			text = text.lower()

			if text == "":
				# Force refreshing screen...
				loop.draw_screen()
				raise self.InputProcessed

			journal.info("")
			journal.info("[YTCON] [INPUT] " + original_text)

			# - = Clipboard auto-paste = -
			if text in ("cb", "clipboard", "clip"):
				settings.clipboard_autopaste_switch()
				raise self.InputProcessed
			# - = - = - = - = - = - = - =

			# - = Delete after download = -
			if text in ("dad", "delete after download"):
				ControlClass.delete_after_download_switch()
				raise self.InputProcessed
			# - = - = - = - = - = - = - =

			if text in ("clear", "cls"):
				ControlClass.clear()

			elif text == "logtest":
				logger.debug("[TEST] 1")
				journal.info("[TEST] 2")
				journal.warning("[TEST] 3")
				journal.error("[TEST] 4")
				journal.error("[TEST] 5", show=False)
				journal.info("😘😘😘😘 6") # can break something, emojis have problems calculating sizes

			elif text == "crash":
				try:
					0/0
				except:
					exit_with_exception(traceback.format_exc())

			elif text == "s":
				RenderClass.settings_show = True

			elif text == "flags":
				journal.info(pprint.pformat(variables.ydl_opts))

			elif text == "s ls":
				journal.info(settings.settings)

			elif text == "save":
				settings.save()
				#journal.info(settings.settings)
			elif text == "load":
				settings.load()
				#journal.info(settings.settings)

			elif text == "update":
				#app_updates.update_run_and_restart()
				app_updates.update_thread = threading.Thread(target=app_updates.update_run_and_restart, daemon=True)
				app_updates.update_thread.start()

			elif text == "fake update":
				app_updates.pypi_version = "0.0.99"

			else:
				threading.Thread(target=downloadd, args=(original_text,), daemon=True).start()

		except self.InputProcessed:
			pass
		except:
			exit_with_exception(traceback.format_exc())

InputHandler = InputHandlerClass()

def errorprinter(loop, _):
	""" Draws errors in error_widget in red, after some time (specified in the timer) removes error messages """
	try:
		# - = skip, do not re-render if there is no errors - = - = - = - = -
		# if variables.prev_last_error == variables.last_error and variables.prev_error_countdown == variables.error_countdown:
		#	time.sleep(0.6)
		#	continue
		# - = - = - = - = - = - = - = - = - = - = - = - = - - = - = - = -
		to_render = []
		to_render.append("- - -\n")

		if variables.error_countdown != 0:
			error_text_generator = "[" + progressbar_defs.whitespace_stabilization(str(variables.error_countdown), 2) + "] " + str(variables.last_error)
		else:
			error_text_generator = str(variables.last_error)

		error_text_generator = error_text_generator.replace("; please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U", "")

		if variables.last_error == "":
			to_render.append((colors.cyan, error_text_generator))
		else:
			to_render.append((colors.red, error_text_generator))

		to_render.append("\n")

		# - = - = - = - = - = - unfold animation - = - = - = - = - = -
		if RenderClass.errorprinter_animation == 0:
			error_widget.set_text(to_render)
		elif RenderClass.errorprinter_animation == 1:
			error_widget.set_text(to_render[:-1])
		elif RenderClass.errorprinter_animation == 2:
			if to_render[:-2] == ["- - -\n"]:
				error_widget.set_text("- - -")
			else:
				error_widget.set_text(to_render[:-2])
		elif RenderClass.errorprinter_animation == 3:
			if not to_render[:-3]:
				error_widget.set_text("")
			else:
				error_widget.set_text(to_render[:-3])

		if variables.last_error == "":
			if RenderClass.errorprinter_animation < 3 and RenderClass.errorprinter_animation >= 0:
				RenderClass.errorprinter_animation += 1
		else:
			if RenderClass.errorprinter_animation <= 3 and RenderClass.errorprinter_animation > 0:
				RenderClass.errorprinter_animation = RenderClass.errorprinter_animation - 1
		# - = - = - = - = - = - = - = - = - = - = - = - = - = - = -

		variables.prev_last_error = variables.last_error
		variables.prev_error_countdown = variables.error_countdown

		if variables.error_countdown != 0:
			variables.error_countdown = variables.error_countdown - 1
			if variables.error_countdown == 0:
				journal.clear_errors()

		#error_widget.set_text(to_render)
		loop.set_alarm_in(0.3, errorprinter)
	except:
		exit_with_exception(str(traceback.format_exc()))

def logprinter(loop, _):
	""" Prints the last 6 lines of logs in log_widget """
	try:
		# - = skip, do not re-render if it doesn't change - = - = - =
		# if ControlClass.oldlog == variables.log:
		#	time.sleep(0.5)
		#	continue
		# else:
		#	ControlClass.oldlog = variables.log.copy()
		#
		# controlclass snippet:
		# self.oldlog = ["", "", "", "", "", ""]
		# - = - = - = - = - = - = - = - = - = - = - = - = - - = - = - =

		to_render = variables.log[0] + "\n"
		to_render += variables.log[1] + "\n"
		to_render += variables.log[2] + "\n"
		to_render += variables.log[3] + "\n"
		to_render += variables.log[4] + "\n"
		to_render += variables.log[5]
		log_widget.set_text(to_render)

		loop.set_alarm_in(0.3, logprinter)
	except:
		exit_with_exception(traceback.format_exc())

def tick_handler(loop, _):
	""" It just checks some conditions every few seconds and executes them. Directly not responsible for rendering, but changes some buttons color """

	# - = - = - = - = - = - = - = - = -
	# Autopaste button color changer
	if (settings.get_setting("clipboard_autopaste") is True and variables.clipboard_checker_state_launched is not True) or (settings.get_setting("clipboard_autopaste") is False and variables.clipboard_checker_state_launched is not False):
		main_footer_buttons.contents[2] = (urwid.AttrMap(main_footer_clipboard_autopaste_button, "yellow"), main_footer_buttons.contents[2][1])
		variables.temp["autopaste_button_color"] = "yellow" # some kind of cache
	elif variables.clipboard_checker_state_launched is not True and variables.temp["autopaste_button_color"] != "light_red":
		main_footer_buttons.contents[2] = (urwid.AttrMap(main_footer_clipboard_autopaste_button, "light_red"), main_footer_buttons.contents[2][1])
		variables.temp["autopaste_button_color"] = "light_red" # some kind of cache
	elif variables.clipboard_checker_state_launched is True and variables.temp["autopaste_button_color"] != "buttons_footer":
		main_footer_buttons.contents[2] = (urwid.AttrMap(main_footer_clipboard_autopaste_button, "buttons_footer"), main_footer_buttons.contents[2][1])
		variables.temp["autopaste_button_color"] = "buttons_footer" # some kind of cache
	# - = - = - = - = - = - = - = - = -

	# - = Clipboard thread activator = -
	if settings.get_setting("clipboard_autopaste") and variables.clipboard_checker_state_launched is False:
		threading.Thread(target=clipboard_checker, daemon=True).start()
	# - = - = - = - = - = - = - = - = -

	# - = - = - = - = - = - = - = - = -
	# The error handler, if it sees variables.exit = True,
	# then exits the program commenting this with the text from variables.exception.
	# The parent function of such actions: exit_with_exception()
	if variables.exit is True:
		loop.stop()
		print("An unknown error has occurred!\n")
		time.sleep(0.5)
		print(variables.exception)
		sys.exit(1)

	if variables.auto_update_safe_gui_stop is True:
		try:
			loop.stop()
		except:
			journal.debug(traceback.format_exc())

		try:
			app_updates.update_thread.join()
		except KeyboardInterrupt:
			print(" - Okay, canceled")
		sys.exit()
	# - = - = - = - = - = - = - = - = -

	# Prevent focus from remaining on footer buttons after pressing them
	main_footer.set_focus(input_widget)

	# - =
	loop.set_alarm_in(0.3, tick_handler)

def tick_handler_big_delay(loop, _):
	""" Same as tick_handler, but with bigger delay. Made for optimization purposes. """

	# - = - = - = - = - = - = - = - = -
	# Draw version in settings
	app_updates.update_settings_version_text()

	# New-update-avalible notificator
	if app_updates.auto_update_avalible is True:
		auto_update_avalible_text_indicator.set_text((colors.cyan, f"- - -\nAuto update {app_updates.version} -> {app_updates.pypi_version} is avalible! Write \"update\" to easy update right now!"))
	# - = - = - = - = - = - = - = - = -

	# - =
	loop.set_alarm_in(4, tick_handler_big_delay)

url_regex = r"^(https?:\/\/)?([\w-]{1,32}\.[\w-]{1,32})[^\s@]*$"
def clipboard_checker():
	"""
	Checks the clipboard for new entries against old ones.
	If it sees new content on the clipboard, it will check whether this is a site, if it detects site, download starts
	"""

	# Set the button yellow and DO NOT start daemon
	variables.clipboard_checker_state_launched = "Do not start"

	if clipman.dataclass.init_called is False:
		try:
			clipman.init()
		except:
			logger.info(traceback.format_exc())
			journal.error("[YTCON] An error occurred while initializing the clipboard. You can see the error in info.log. Or save the Auto-paste option enabled in the config file, restart ytcon, and after that you will see an error with detailed instructions.")

			# Keep setting ON for "save to config file" ability
			time.sleep(60)
			settings.write_setting("clipboard_autopaste", False)
			update_checkboxes()
			variables.clipboard_checker_state_launched = False
			return None

	try:
		variables.clipboard_checker_state_launched = True
		journal.info("[YTCON] Clipboard auto-paste is ON.")

		old_clip = ""

		while True:
			if settings.get_setting("clipboard_autopaste") is False:
				variables.clipboard_checker_state_launched = False
				journal.info("[YTCON] Clipboard auto-paste turned off.")
				return None

			new_clip = clipman.paste()
			if new_clip != old_clip:
				if re.fullmatch(url_regex, new_clip):
					journal.info("[CLIP] New URL detected: " + new_clip)
					threading.Thread(target=downloadd, args=(new_clip,), daemon=True).start()
				else:
					logger.debug("clipboard content: %s", new_clip)
					journal.info("[CLIP] New clipboard content detected. But this is not URL. Ignoring..")
			old_clip = new_clip
			time.sleep(1)
	except:
		exit_with_exception(str(traceback.format_exc()))
		return None

def get_resolution_ffprobe(file):
	""" Uses ffprobe to get video (even not fully downloaded) resolution """
	try:
		probe = ffmpeg.probe(file)
	except ffmpeg.Error as e:
		logger.debug("ffprobe error:")
		logger.debug(e.stderr)
		return None
	logger.debug("ffprobe response:")
	logger.debug(pprint.pformat(probe))
	for i in probe["streams"]:
		if "width" in i and "height" in i:
			return str(i["width"]) + "x" + str(i["height"])
	return None

# - = - = -
from control.control import ControlClass

variables.ydl_opts = {
	'logger': journal,
	'progress_hooks': [hook],
	'color': 'no_color',
	#'outtmpl': '%(title)s [%(id)s].%(ext)s', # REALIZED IN own file handler
	'socket_timeout': 15,
	'retries': 20,
	'fragment_retries': 40,
	'retry_sleep': 'http,fragment:exp',
	#'download_archive': 'downloaded_videos.txt', # !!! DANGEROUS OPTION !!! # TODO?
	}

top_pile = urwid.Pile([])

#logger.debug(pprint.pformat(top_pile.contents))
#logger.debug(pprint.pformat(calculate_widget_height(top_pile)))

log_widget = urwid.Text("Initializing, please wait")
error_widget = urwid.Text("Initializing, please wait")
input_widget = InputHandler.InputBox("Enter URL > ")

main_settings_button = urwid.Button("Settings", on_press=settings.show_settings_call)
main_clear_button = urwid.Button("Clear", on_press=ControlClass.clear)
main_footer_clipboard_autopaste_button = urwid.Button("Autopaste", on_press=settings.clipboard_autopaste_switch)

main_footer_buttons = urwid.GridFlow([main_settings_button, main_clear_button, main_footer_clipboard_autopaste_button], cell_width=13, h_sep=2, v_sep=1, align="left")
logger.debug(main_footer_buttons.contents)
main_footer_buttons_with_attrmap = urwid.AttrMap(main_footer_buttons, "buttons_footer")

auto_update_avalible_text_indicator = urwid.Text("- - -")

main_footer = urwid.Pile(
		[
		error_widget,
		urwid.Text("- - -"),
		log_widget,
		urwid.Text("- - -"),
		input_widget,
		urwid.Divider(),
		auto_update_avalible_text_indicator,
		main_footer_buttons_with_attrmap,
		])
main_widget = urwid.Frame(
	urwid.Filler(top_pile, "top"),
	footer=main_footer,
	focus_part='footer')

loop = urwid.MainLoop(main_widget, palette=colors.custom_palette)

RenderClass.width, RenderClass.height = loop.screen.get_cols_rows()
RenderClass.loop = loop

# - = - = - = - = - = - = -
# Some debug info writer
logger.debug("width: %s", RenderClass.width)
logger.debug("height: %s", RenderClass.height)
logger.debug("config path: %s", configpath)

# Output collected to-later-print logs
for i in logs_that_will_be_printed_later:
	journal.info(i)
for i in debug_that_will_be_saved_later:
	logger.debug(i)
# - = - = - = - = - = - = -

# - = SETTINGS - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - = - =
class SettingsSections:
	"""
	The class in which the settings category classes are placed.

	They will be automatically found and placed in a special dynamic list (self.settings_sections)
	that will be shown to the user
	"""
	def __init__(self):
		# Get all class attributes (sections)
		class_attributes = vars(SettingsSections)

		# Filter only classes
		self.settings_sections = [cls for cls in class_attributes.values() if isinstance(cls, type)]

		#print(self.settings_sections)

	class General_SECTION: # pylint: disable=attribute-defined-outside-init # because get() initializes a class
		""" General settings section """
		name = "General"

		def get(self):
			""" Get content of section """
			self.settings_checkbox_clipboard = urwid.CheckBox("Clipboard auto-paste", on_state_change=settings.setting_switch, user_data="clipboard_autopaste")

			# UPDATE CHECKBOXES
			self.update()

			settings_pile = urwid.Pile([
				urwid.Divider(),
				self.settings_checkbox_clipboard,
				urwid.Divider(),
				])
			return settings_pile

		def update(self):
			""" Update checkbox states for they don't lie """
			self.settings_checkbox_clipboard.set_state(settings.get_setting("clipboard_autopaste"), do_callback=False)

	class Appearance_SECTION: # pylint: disable=attribute-defined-outside-init # because get() initializes a class
		""" settings section related to appearance """
		name = "Appearance"
		def get(self):
			""" Get content of section """
			self.settings_checkbox_progresstype_detailed = urwid.CheckBox([
				(colors.cyan, "46% |███▍   | - Detailed"),
				"\nUse some unicode characters (▏;▍;▋;▉;█)\nto display the percentage more accurately.\nDoesn't fully work in tty",
				], on_state_change=settings.setting_change_content, user_data=("progressbar_appearance", "detailed"))
			self.settings_checkbox_progresstype_simple = urwid.CheckBox([
				(colors.cyan, "46% |████   | - Simple"),
				"\nUse only ACSII squares (█) to show percentage"
				], on_state_change=settings.setting_change_content, user_data=("progressbar_appearance", "simple"))
			self.settings_checkbox_progresstype_arrow = urwid.CheckBox([
				(colors.cyan, "46% |===>   | - Arrow"),
				"\nLet's just add some oldfag style 😎"
				], on_state_change=settings.setting_change_content, user_data=("progressbar_appearance", "arrow"))
			self.settings_checkbox_progresstype_pacman = urwid.CheckBox([
				(colors.cyan, "46% |--C o | - Pacman"),
				"\nPacman game"
				], on_state_change=settings.setting_change_content, user_data=("progressbar_appearance", "pacman"))

			# UPDATE CHECKBOXES
			self.update()

			settings_pile = urwid.Pile([
				urwid.Divider(),
				urwid.Text((colors.light_yellow, "Progress bar type")),
				self.settings_checkbox_progresstype_detailed,
				urwid.Divider(),
				self.settings_checkbox_progresstype_simple,
				urwid.Divider(),
				self.settings_checkbox_progresstype_arrow,
				urwid.Divider(),
				self.settings_checkbox_progresstype_pacman,
				urwid.Divider(),
				])

			return settings_pile

		def update(self):
			""" Update checkbox states for they don't lie """
			self.settings_checkbox_progresstype_detailed.set_state(settings.get_setting("progressbar_appearance") == "detailed", do_callback=False)
			self.settings_checkbox_progresstype_simple.set_state(settings.get_setting("progressbar_appearance") == "simple", do_callback=False)
			self.settings_checkbox_progresstype_arrow.set_state(settings.get_setting("progressbar_appearance") == "arrow", do_callback=False)
			self.settings_checkbox_progresstype_pacman.set_state(settings.get_setting("progressbar_appearance") == "pacman", do_callback=False)


	class Fetching_SECTION: # pylint: disable=attribute-defined-outside-init # because get() initializes a class
		""" Fetching settings section - related to yt-dlp downloding """
		name = "Fetching"
		def get(self):
			""" Get content of section """
			self.settings_checkbox_sp = urwid.CheckBox([(colors.light_yellow, "\"Special mode\""), "\nUse different user-agent and extract cookies from chromium"], on_state_change=settings.setting_switch, user_data="special_mode")
			self.settings_checkbox_nocert = urwid.CheckBox([(colors.light_yellow, "Do not check website certificates"), "\nEnable this if \"SSL: CERTIFICATE_VERIFY_FAILED\" error occurs"], on_state_change=settings.setting_switch, user_data="no_check_certificate")

			# UPDATE CHECKBOXES
			self.update()

			settings_pile = urwid.Pile([
				urwid.Divider(),
				self.settings_checkbox_sp,
				urwid.Divider(),
				self.settings_checkbox_nocert,
				urwid.Divider(),
				])

			return settings_pile

		def update(self):
			""" Update checkbox states for they don't lie """
			self.settings_checkbox_sp.set_state(settings.get_setting("special_mode"), do_callback=False)
			self.settings_checkbox_nocert.set_state(settings.get_setting("no_check_certificate"), do_callback=False)

	class Playlists_SECTION: # pylint: disable=attribute-defined-outside-init # because get() initializes a class
		""" Playlist settings section """
		name = "Playlists"
		def get(self):
			""" Get content of section """
			self.settings_checkbox_ignerr = urwid.CheckBox([
				(colors.light_yellow, "Ignore downloading errors"),
				(colors.light_red, "\n<!!> Dangerous option - makes ytcon a little unstable\nPlease use only if necessary <!!>"),
				"\nUse this so as not to interrupt the download if\none of the video in the playlist is not available"
				], on_state_change=settings.setting_switch, user_data="ignoreerrors")

			# UPDATE CHECKBOXES
			self.update()

			settings_pile = urwid.Pile([
				urwid.Divider(),
				self.settings_checkbox_ignerr,
				urwid.Divider(),
				])

			return settings_pile

		def update(self):
			""" Update checkbox states for they don't lie """
			self.settings_checkbox_ignerr.set_state(settings.get_setting("ignoreerrors"), do_callback=False)

	class Debug_SECTION: # pylint: disable=attribute-defined-outside-init # because get() initializes a class
		""" DEBUG settings section """
		name = "Debug"
		def get(self):
			""" Get content of section """
			self.settings_checkbox_delete_af = urwid.CheckBox("Delete after download", on_state_change=ControlClass.delete_after_download_switch)

			# UPDATE CHECKBOXES
			self.update()

			settings_pile = urwid.Pile([
				urwid.Divider(),
				urwid.Text((colors.light_red, "The settings found here are made for testing purposes!")),
				urwid.Text((colors.light_red, "Changing these settings is not recommended.")),
				urwid.Divider(),
				urwid.Text((colors.light_red, "Also, Debug settings WILL NOT be saved when you click on the \"Save to config file\" button")),
				urwid.Divider(),
				urwid.Text("- = -"),
				urwid.Divider(),
				self.settings_checkbox_delete_af,
				urwid.Divider(),
				])

			return settings_pile

		def update(self):
			""" Update checkbox states for they don't lie """
			self.settings_checkbox_delete_af.set_state(variables.delete_after_download, do_callback=False)

	# = - E X A M P L E - =
	#class Three_SECTION:
	#	# Test section
	#	name = "3"
	#	def get(self):
	#		# Get content of section
	#		return urwid.Text('helo3')

settings_sections = SettingsSections()

def update_checkboxes():
	"""
	!LEGACY!: update the checkboxes so that their status is not a lie 
	"""
	if RenderClass.settings_show is True:
		sett.update()

def gen_SimpleFocusListWalker_with_footer(contents, footer, width=20):
	"""
	Some analogue of urwid.Frame, it contains a body (contents) and footer,
	but at the same time we CAN switch the focus between them
	"""
	# Count body (contents) rows
	contents_rows = 0
	for i in contents:
		contents_rows = contents_rows + i.rows((width,))

	# Count footer rows
	footer_rows = 0
	for i in footer:
		footer_rows = footer_rows + i.rows((width,))

	filler_height = RenderClass.height - contents_rows - footer_rows
	filler_list = []

	# Filling the empty space between widgets using a urwid.Divider
	for i in range(0, filler_height):
		filler_list.append(urwid.Divider())
	return urwid.Pile(contents + filler_list + footer)

class SettingsRenderClass:
	""" The class that is responsible for rendering the settings menu """
	def __init__(self):
		self.settings_soft_update_scheduled = False

		self.exit_settings_button = urwid.Button("Exit from settings", on_press=settings.show_settings_call)
		self.save_settings_button = urwid.Button("Save to config file", on_press=settings.save)
		self.load_settings_button = urwid.Button("Load from config file", on_press=settings.load)

		self.footer_widget = urwid.Pile([
			error_widget,
			urwid.Text("- - -"),
			log_widget,
		])

		# - =
		# just placeholders. nevermind
		self.columns = None
		self.right_widget = None
		# - =

		# - = - Section buttons mapping - = - = - = - = - = - = -
		self.connected_sections = settings_sections.settings_sections

		self.section_buttons = [
				urwid.AttrMap(urwid.Text(" - = Categories = -"), "green_background", ""),
				]

		for i in self.connected_sections:
			self.section_buttons.append(
				urwid.AttrMap(
					urwid.Button(i.name, on_press=self.set_right_section, user_data=i),
					"", "reversed"
				)
			)
		# - = - = - = - = - = - = - = - = - = - = - = - = - = - =

		self.left_widget_sflw = gen_SimpleFocusListWalker_with_footer(
			self.section_buttons,
			[
				urwid.AttrMap(self.load_settings_button, "cyan", "reversed"),
				urwid.AttrMap(self.save_settings_button, "cyan", "reversed"),
				urwid.Divider(),
				urwid.AttrMap(self.exit_settings_button, "light_cyan", "cyan_background"),
			]
			)

		self.left_widget = urwid.Filler(self.left_widget_sflw, valign="top")

		self.vertical_divider = urwid.Filler(urwid.Text(" " * 100))
		self.set_right_section(None, self.connected_sections[0], update=False)

	def set_right_section(self, _, section, update=True):
		""" A function that puts the specified section class on the right visible part of the interface """
		self.current_section = section
		if update:
			self.update()

	def soft_update(self):
		""" Update current section flags states without re-rendering it """
		try:
			self.current_section_initialized.update()
		except AttributeError:
			logger.debug("soft_update unsucceful because SettingsRenderClass doesn't have initialized settings section")

	def update(self):
		""" re-generate + re-render right visible part of the interface """
		self.current_section_initialized = self.current_section()
		self.right_widget = urwid.Frame(
			urwid.Padding(urwid.Filler(self.current_section_initialized.get(), valign='top'), left=2, right=2, align='center'),

			footer = urwid.Pile([
				app_updates.settings_version_text,
				urwid.LineBox(
					self.footer_widget,
					tlcorner='╭', trcorner='╮', # Rounding corners
					blcorner='', bline='', brcorner='' # Remove bottom line
					),
				]),

			header = urwid.AttrMap(urwid.Text(" - = " + self.current_section.name), "reversed", "") )

		# Create Columns for split screen
		self.columns = urwid.Columns(
			[
			# ALL INCOMING WIDGETS MUST BE BOX
			("fixed", 20, self.left_widget),
			("fixed", 1, self.vertical_divider),
			#("fixed", 1, urwid.AttrMap(self.vertical_divider, "reversed")),
			self.right_widget
			])

		loop.widget = self.columns

	def tick_handler_settings(self, _, _1):
		""" Same as tick_handler, but responsible only for settings menu """
		if RenderClass.settings_show is True:
			lol = sett.left_widget_sflw.focus_position - 1 # -1 because header is widget too
			if not lol > len(self.connected_sections)-1: # prevent crash on bottom buttons selection, -1 because len makes +1
				if self.current_section != self.connected_sections[lol]:
					self.set_right_section(None, self.connected_sections[lol])

		# - = - = - = - = - = - = - = - = -
		# Settings page show handler
		if RenderClass.settings_show is True and RenderClass.settings_showed is False:
			try:
				# - = - = -
				# Return to default position
				self.left_widget_sflw.set_focus(1)
				self.set_right_section(None, self.connected_sections[0], update=False)
				# - = - = -
				self.update()
				RenderClass.settings_showed = True
			except:
				exit_with_exception(traceback.format_exc())
		if RenderClass.settings_show is False and RenderClass.settings_showed is True:
			try:
				loop.widget = main_widget
				RenderClass.settings_showed = False
			except:
				exit_with_exception(traceback.format_exc())
		# - = - = - = - = - = - = - = - = -

		# - = - = - = - = - = - = - = - = -
		# Soft checkbox updater
		if self.settings_soft_update_scheduled is True:
			self.soft_update()
			self.settings_soft_update_scheduled = False
		# - = - = - = - = - = - = - = - = -

		loop.set_alarm_in(0.1, self.tick_handler_settings)

sett = SettingsRenderClass()
# - = - = - = - Late initialize - = - = - = - =
settings.load()

if settings.get_setting("clipboard_autopaste") is True:
	try:
		clipman.init()
	except Exception as e: # pylint: disable=broad-except
		logger.info(traceback.format_exc())
		print("[!!] An Clipboard error occurred!\n")
		print(f"- {type(e).__name__}: {e}")
		print("\nYou can follow instructions in this error message, or ignore it")
		print("BUT, if you ignore it, clipboard auto-paste will be unavalible.\n")
		print("Also, if this error message doesn't contain instructions,")
		print("and does not contain any understandable text for your human language, please make an issue")
		print("https://github.com/NikitaBeloglazov/clipman/issues/new")
		print("Full traceback can be found in info.log\n")

		try:
			user_answer = input("Ignore it? [yes/NO] > ")
		except KeyboardInterrupt:
			print("Exiting..")
			sys.exit(1)

		if user_answer.lower() in ("yes", "y"):
			journal.error("[YTCON] If you don't want answer \"yes\" every time, solve the problem, or disable auto-paste in settings and PRESS \"Save to config file\"")
			settings.write_setting("clipboard_autopaste", False)
		else:
			print("Exiting..")
			sys.exit(1)
# - = - = - = - = - = - = - = - = - = - = - = -

loop.set_alarm_in(0, render_tasks)
loop.set_alarm_in(0, logprinter)
loop.set_alarm_in(0, errorprinter)
loop.set_alarm_in(0, tick_handler)
loop.set_alarm_in(1, tick_handler_big_delay)
loop.set_alarm_in(1, sett.tick_handler_settings)

# for testing purposes?
# threading.Thread(target=downloadd, args=("https://www.youtube.com/watch?v=Kek5Inz-wjQ",), daemon=True).start()

loop.run()
