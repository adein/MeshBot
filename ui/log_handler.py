import logging
from textual.widgets import RichLog

class TextualLogHandler(logging.Handler):
    """
    Redirects python logs to a Textual RichLog widget.
    """
    def __init__(self, rich_log_widget: RichLog):
        super().__init__()
        self.widget = rich_log_widget
        self.setLevel(logging.INFO)

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.widget.app is None:
                return
            self.widget.app.call_from_thread(self.widget.write, msg)
            
        except Exception:
            # If the app is closing/closed, accessing .app might raise an error.
            # We swallow this error to prevent the shutdown traceback.
            pass