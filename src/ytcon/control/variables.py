
class VariablesStorage:
	def __init__(self):
		self.queue_list = {}
		self.ydl_opts = {}

		self.temp = {}
		self.temp["autopaste_button_color"] = "" # some kind of cache, see tick_handler

		self.last_error = ""
		self.error_countdown = 0
		self.prev_last_error = ""
		self.prev_error_countdown = 0

		self.delete_after_download = False

		self.log = ["", "", "", "", "", "Logs will appear there.."]
		self.exit = False
		self.auto_update_safe_gui_stop = False
		self.exception = ""
		self.clipboard_checker_state_launched = False

		# See InputHandlerClass.InputBox
		self.alt_plus_arrow_multiline_message_sended = False

variables = VariablesStorage()