import os
import time
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from directory_manager import get_scanned_images_dir

try:
    import twain
except ImportError:
    twain = None

class ScannerManager(QObject):
    image_scanned = pyqtSignal(str) # Emits the path of the scanned image
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def is_available(self):
        return twain is not None

    def scan_images(self, show_ui=False):
        if not self.is_available():
            self.error_occurred.emit("TWAIN library not installed.")
            return

        try:
            # Note: This usually requires a window handle on Windows.
            # In a GUI app, we might need to pass the parent window's handle.
            sm = twain.SourceManager(0) # 0 is often enough for a global SM
            source = sm.open_source()
            if not source:
                self.error_occurred.emit("No scanner source selected or found.")
                return

            # --- Capability Negotiation for Canon DR-240 and similar scanners ---
            try:
                # Enable ADF (Auto Document Feeder)
                source.set_capability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
                # Set to scan all pages in the feeder
                source.set_capability(twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1)
                # Optionally enable Duplex (double-sided) - can be made a setting later
                # source.set_capability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, True)
                
                self.logger.info("Scanner capabilities set: ADF Enabled, Batch Transfer Enabled.")
            except Exception as cap_e:
                self.logger.warning(f"Could not set some scanner capabilities: {cap_e}")

            output_dir = get_scanned_images_dir()
            if not output_dir:
                self.error_occurred.emit("Could not determine output directory.")
                return

            def on_image_info(info):
                # This callback might be needed depending on the pytwain version/implementation
                pass

            source.request_acquire(show_ui, False)
            
            # Pytwain acquisition loop
            handle, more = source.xfer_image_natively()
            while handle:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"scan_{timestamp}_{handle}.png"
                filepath = os.path.join(output_dir, filename)
                
                # Save the image
                twain.dib_to_bm_file(handle, filepath)
                self.image_scanned.emit(filepath)
                
                # Free memory
                twain.global_free(handle)
                
                # Check for more pages in ADF
                if more:
                    handle, more = source.xfer_image_natively()
                else:
                    handle = None

            source.close()
            sm.close()

        except Exception as e:
            self.logger.error(f"Scanner Error: {e}")
            self.error_occurred.emit(str(e))
