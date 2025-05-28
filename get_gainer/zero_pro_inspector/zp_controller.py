import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '..')))

from program_starter.class_zeropro_starter import logger 
from program_starter.class_zeropro_starter import ZeroProAutomation


class ZeroProController:
    """
    Responsible for launching or attaching to the ZeroPro trading platform window.
    """

    def initialize(self):
        zp = ZeroProAutomation()
        hwnd = zp.find_main_window()

        if not hwnd:
            logger.error("Main window not found. Starting ZeroPro...")
            zp.force_run()
            hwnd = zp.find_main_window()

        logger.info(f"✅ Found ZeroPro main window: HWND={hwnd}")
        return hwnd