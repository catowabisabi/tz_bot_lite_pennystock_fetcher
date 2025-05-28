import subprocess
import time
import re
import logging
from typing import Optional, List
import pygetwindow as gw
import pyautogui
import psutil
import win32gui
import win32con
import win32api
import ctypes
import sys
import argparse

import os
from dotenv import load_dotenv

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '.env'))
load_dotenv(dotenv_path=env_path)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ZeroProAutomation")

zero_pro_path = r"C:\Program Files (x86)\TradeZero\ZeroPro v637\ZeroPro.exe"
class ZeroProAutomation:
    """ZeroPro software automation class"""
    
    def __init__(self, exe_path: str = zero_pro_path, username: str = None, password: str = None):
        self.exe_path = exe_path
        self.username = username or os.getenv("TZ_USERNAME")
        self.password = password or os.getenv("TZ_PASSWORD")
        if not self.username or not self.password:
            logger.error("ENV Cannot be empty: TZ_USERNAME 或 TZ_PASSWORD")
            return None
        self.process = None
        self.zeropro_pids = []
        self.last_found_hwnd = None
        
        # set process DPI awareness
        
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if not self._is_admin():
            logger.warning("Please run the script with admin privileges.")
            self._request_admin()
            sys.exit(1)

    # region 核心功能方法
    def run(self) -> bool:
        """main entry point"""
        try:
            if self.is_zeropro_running():
                logger.info("ZeroPro is already running, try to find main window...")
                hwnd = self.find_main_window()
                
                if not hwnd:
                    logger.error("main windows cannot be found, try to force restart...")
                    return self.force_restart()
                
                if not self.safe_activate(hwnd):
                    logger.warning("safe activate failed, try to execute emergency recovery...")
                    return self.emergency_recovery(hwnd)
                return True
                
            return self.start_new_instance()
            
        except Exception as e:
            logger.critical(f"failed to run: {e}")
            return False
        
        
    def initialize_zeropro(self):
        if not self.run():
            logger.warning("fail to initialize zeropro, try to force restart...")
            zp = self.force_run()
            if not zp:
                logger.error("fail to initialize zeropro")
                sys.exit(1)
                return False
        logger.info("ZeroPro initialized successfully.")
        return True





    def find_main_window(self) -> Optional[int]:
        """ find main window """
        logger.info("\n\nfind main window...")
        target_hwnd = None
        
        def enum_callback(hwnd, _):
            nonlocal target_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
                
            window_text = win32gui.GetWindowText(hwnd)
            window_class = win32gui.GetClassName(hwnd)
            
            # 使用之前成功的窗口匹配条件 use the previously successful window matching conditions
            if window_text == "" and re.match(r"WindowsForms10\.Window\.8\.app\.", window_class):
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top
                if width > 100 and height > 100:
                    logger.info(f"possible main window - class: {window_class}, size: {width}x{height}")
                    target_hwnd = hwnd
                    return False
            
            # 保留原來的匹配邏輯作為備選 retain the original matching logic as a backup
            try:
                # 檢查是否為ZeroPro相關窗口
                if (("ZeroPro" in window_text or "TradeZero" in window_text) or
                    ("GDI+" in window_text) or
                    (bool(re.match(r"WindowsForms10\.Window\.[0-9]+\.app", window_class)) and
                     width > 300 and height > 200)):
                    
                    # 如果進程ID匹配則更優先
                    if self.zeropro_pids:
                        _, pid = win32gui.GetWindowThreadProcessId(hwnd)
                        if pid in self.zeropro_pids:
                            logger.info(f"found ZeroPro window - title: {window_text}, class: {window_class}")
                            target_hwnd = hwnd
                            return False
                    else:
                        # 如果沒有記錄進程ID，僅通過窗口特徵匹配 if no process ID is recorded, match only by window features
                        logger.info(f"found possible ZeroPro window - title: {window_text}, class: {window_class}")
                        target_hwnd = hwnd
                        return False
            except Exception as e:
                logger.debug(f"error occurred finding main window: {e}")
                
            return True

        try:
            logger.info("starting window enumeration...")
            win32gui.EnumWindows(enum_callback, None)
            logger.info("done window enumeration")
            
            if target_hwnd:
                # 確保窗口真正可見
                if not win32gui.IsWindowVisible(target_hwnd):
                    logger.warning("window is not visible, trying to restore...")
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                    logger.info("restored window")
                self.last_found_hwnd = target_hwnd
            else:
                logger.warning("no main window found...")

        except Exception as e:
            logger.error(f"error occurred finding main window: {e}")
            
        return target_hwnd

    def safe_activate(self, hwnd: int) -> bool:
        """安全激活窗口流程 safe activation process"""
        try:
            # 1. 恢复窗口状态
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)
                
            # 2. 渐进式激活
            for attempt in range(3):
                try:
                    # 非侵入式提醒
                    win32gui.FlashWindow(hwnd, True)
                    
                    # 温和的窗口位置调整
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOP,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                    )
                    time.sleep(0.3)
                    
                    # 最终尝试置前
                    win32gui.SetForegroundWindow(hwnd)
                    
                    if win32gui.GetForegroundWindow() == hwnd:
                        # 渐进式最大化 gradual maximization
                        logger.info("radual maximization")
                        for i in range(1, 6):
                            width = int(win32api.GetSystemMetrics(0) * i // 5)
                            height = int(win32api.GetSystemMetrics(1) * i // 5)
                            win32gui.SetWindowPos(
                                hwnd, win32con.HWND_TOP,
                                0, 0, width, height,
                                win32con.SWP_ASYNCWINDOWPOS
                            )
                            time.sleep(0.1)
                            logger.info("最大化視窗")
                        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                        time.sleep(0.5)
                        return True
                        
                except Exception as e:
                    logger.warning(f"激活尝试{attempt+1}失败: {e}")
                    time.sleep(1)
                    
            return False
            
        except Exception as e:
            logger.error(f"激活过程出错: {e}")
            return False
    
    def force_run(self) -> bool:
        """强制重启ZeroPro的完整实现"""
        try:
            if self.is_zeropro_running():
                if not self.terminate_process():  # 修正: 使用terminate_process代替close_zeropro
                    logger.error("关闭进程失败")
                    return False
                time.sleep(3)  # 等待进程完全退出
            
            # 重新启动流程
            return self.start_new_instance()  # 修正: 使用start_new_instance代替_start_and_login
        except Exception as e:
            logger.error(f"强制重启失败: {e}")
            return False
        
    # endregion

    # region 辅助方法
    def _is_admin(self) -> bool:
        """检查管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
            
    def _request_admin(self):
        """请求管理员权限"""
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)

    def is_zeropro_running(self) -> bool:
        """检查进程是否运行"""
        self.zeropro_pids = [
            p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
            if p.info.get('name') == 'ZeroPro.exe'
        ]
        return bool(self.zeropro_pids)

    def start_new_instance(self) -> bool:
        """启动新实例流程"""
        logger.info("启动ZeroPro...")
        try:
            #si = subprocess.STARTUPINFO()
            #si.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # 隱藏視窗
            #si.wShowWindow = subprocess.SW_HIDE
            self.process = subprocess.Popen(
                            [self.exe_path], 
                            shell=True,
                            #startupinfo=si,
                            #stdout=subprocess.DEVNULL,
                            #stderr=subprocess.DEVNULL,
                            #creationflags=subprocess.CREATE_NO_WINDOW
                        )
            
            if not self._wait_for_process("ZeroPro.exe", 60):
                logger.error("启动超时")
                return False
                
            time.sleep(8)  # 等待初始化
            
            if not self._perform_login():
                return False

            logger.info(f"登录成功: {self.username}")  
            hwnd = self.find_main_window()
            return hwnd and self.safe_activate(hwnd)
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            return False

    def _wait_for_process(self, name: str, timeout: int) -> bool:
        """等待进程启动"""
        logger.info(f"等待 {name} 启动...")
        start = time.time()
        while time.time() - start < timeout:
            if any(name.lower() in p.info['name'].lower()
                  for p in psutil.process_iter(['name'])):
                logger.info(f"{name} 已启动")
                return True
            time.sleep(1)
        return False

    def _perform_login(self) -> bool:
        """执行登录操作"""
        login_window = self._find_login_window()
        if not login_window:
            logger.error("找不到登录窗口")
            return False
            
        try:
            login_window.activate()
            time.sleep(1)
            pyautogui.write(self.username)
            time.sleep(0.3)
            pyautogui.press('tab')
            time.sleep(0.3)
            pyautogui.write(self.password)
            time.sleep(0.3)
            pyautogui.press('enter')
            
            logger.info("凭证已提交，等待登录...")
            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"登录出错: {e}")
            return False

    def _find_login_window(self, retries=15, delay=1) -> Optional[gw.Window]:
        """查找登录窗口"""
        for i in range(retries):
            windows = gw.getWindowsWithTitle("Client Connection")
            if windows:
                logger.info("找到登录窗口")
                return windows[0]
            if i < retries - 1:
                logger.debug(f"未找到登录窗口，重试 {i+1}/{retries}...")
                time.sleep(delay)
        return None

    def terminate_process(self) -> bool:
        """终止进程"""
        success = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info.get('name') == 'ZeroPro.exe':
                    proc.terminate()
                    success = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if success:
            time.sleep(3)
            return not self.is_zeropro_running()
        return True

    def force_restart(self) -> bool:
        """强制重启流程"""
        try:
            if self.is_zeropro_running():
                if not self.terminate_process():
                    logger.error("终止进程失败")
                    return False
                time.sleep(3)
                
            return self.start_new_instance()
        except Exception as e:
            logger.error(f"强制重启失败: {e}")
            return False

    def emergency_recovery(self, hwnd: int) -> bool:
        """应急恢复方案"""
        try:
            logger.warning("执行应急恢复...")
            
            # 尝试温和关闭
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(3)
            
            # 检查是否关闭成功
            if self.is_zeropro_running():
                if not self.terminate_process():
                    logger.error("无法终止进程")
                    return False
                    
            return self.start_new_instance()
            
        except Exception as e:
            logger.critical(f"应急恢复失败: {e}")
            return False
    # endregion

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroPro自动化控制")
    parser.add_argument("--path", default=r"C:\Program Files (x86)\TradeZero\ZeroPro v637\ZeroPro.exe", 
                       help="ZeroPro执行路径 DEFAULT: C:\\Program Files (x86)\\TradeZero\\ZeroPro v637\\ZeroPro.exe")
    parser.add_argument("--username", required=True, help="登录用户名 TZ_USERNAME")
    parser.add_argument("--password", required=True, help="登录密码 TZ_PASSWORD")
    parser.add_argument("--force", action="store_true", help="强制重启 force restart")
    parser.add_argument("--close", action="store_true", help="仅关闭 close zeropro")
    parser.add_argument("--debug", action="store_true", help="调试模式 debug mode")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    zp = ZeroProAutomation(args.path, args.username, args.password)
    
    if args.close:
        success = zp.terminate_process()  # 修正: 使用terminate_process代替close_zeropro
        logger.info(f"关闭操作 {'成功' if success else '失败'}")
    else:
        success = zp.force_restart() if args.force else zp.run()
        logger.info(f"{'强制重启' if args.force else '启动'}操作 {'成功' if success else '失败'}")
    
    sys.exit(0 if success else 1)