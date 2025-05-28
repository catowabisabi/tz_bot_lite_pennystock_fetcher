"""The main function of the DynamicUIFinder class 
is to find and extract data from UI controls, 
expecially the top 10 gainers and losers."""

import uiautomation as auto
from dotenv import load_dotenv
load_dotenv()
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),  '..', '..')))

from typing import List, Dict, Optional
import time
import pandas as pd
import logging

logger = logging.getLogger(__name__)
from program_starter.class_zeropro_starter import ZeroProAutomation


# 抑制 comtypes 和 numexpr 的 INFO 日誌
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("numexpr").setLevel(logging.WARNING)

class DynamicUIFinder:

    
    def __init__(self):
        self.max_retry = 5  # 增加重試次數
        self.retry_delay = 2  # 增加延遲時間
        self.search_timeout = 30  # 全域查找超時

        logger.info("initializing DynamicUIFinder...\n functions of DynamicUIFinder:\n" \
        "sThe main function of the DynamicUIFinder class is to find and extract data from UI controls, expecially the top 10 gainers and losers.\n" )


        logger.info(f"max_retry: {self.max_retry}, retry_delay: {self.retry_delay}, search_timeout: {self.search_timeout}")

    def setup(self):
        """初始化設定"""
        auto.SetGlobalSearchTimeout(self.search_timeout)



    def search_element(
        self,
        parent,
        control_type: str,
        automation_id: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Optional[auto.Control]:
        """基礎控件查找函數"""
        for _ in range(self.max_retry):
            try:
                control_class = getattr(auto, control_type)
                search_conditions = {}
                if automation_id:
                    search_conditions['AutomationId'] = automation_id
                if name:
                    search_conditions['Name'] = name
                search_conditions.update(kwargs)
                
                element = control_class(parent=parent, **search_conditions)
                if element.Exists():
                    return element
            except Exception as e:
                logger.error(f"⚠️ 查找失敗: {e}")
            time.sleep(self.retry_delay)
        return None
    


    def search_element_force_parent(
        self,
        parent,
        control_type: str,
        automation_id: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Optional[auto.Control]:
        """只在 parent 的 Children 中查找符合條件的控件"""
        try:
            
            for child in parent.GetChildren():
                
                if child.ControlTypeName != control_type:
                    continue
                if automation_id and child.AutomationId != automation_id:
                    continue
                if name and child.Name != name:
                    continue
                return child  # 第一個符合條件的
            return None
        except Exception as e:
            logger.error(f"⚠️ 查找失敗: {e}")
            return None


    




    # region find_control_sequence
    def find_control_sequence(
        self,
        root_control: auto.Control,
        control_sequence: List[Dict],
    ) -> Optional[auto.Control]:
        """
        Finds a control based on a sequence of control definitions.
        Returns the found control or None if not found.
        """
        #print("Control Sequence:", control_sequence)
      
        current_control = root_control
        for level, control_def in enumerate(control_sequence, 1):
            control_type = control_def["type"]
            id_list = control_def.get("ids", [])
            name = control_def.get("name")
            found = False
            
            print("\n\n\n\n\n")
            print("="*150)
            print("\n")
            logger.info(f"🔍 Searching Level {level}, Control Type:({control_type})...")
            #children = root_control.GetChildren()
            #for c in children:
            #    print(f"Type: {c.ControlTypeName}, Name: {c.Name}, AutomationId: {c.AutomationId}")

            if control_type == "WindowControl":
                #print("WindowControl")
                #print("\n\n")
                for automation_id in id_list:
                    control = self.search_element(
                        parent=current_control,
                        control_type=control_type,
                        name=name,
                    )
                    #print("\n\n開始的Control: ", control)
                    if control:
                        #print(dir(control))
                        logger.info(f"✅ Level {level} Found Control: {control_type}({automation_id})")
                        
                        #print("current_control就係: ", control)
                        #print("length", len(control))  
                        #print("first", control[0])


                        ##############
                        #print ("\n\nControl:  \n\n", control)
                        current_control = control
                        #print("\n\ncurrent_control Children: ", current_control)
                        #print("\n\nlength", len(current_control))
                        
                        found = True
                        break
            else:
                print("not WindowControl")
                for automation_id in id_list:
                    
                    control = self.search_element_force_parent(
                        parent=current_control,
                        control_type=control_type,
                        automation_id=automation_id,
                        name=name,
                    )
                    if control:
                        print("control", control)
                        print(dir(control))
                        #print("Date", control.Date)
                        logger.info(f"\n\n✅ Level {level} Found Control and AutomationId0: \n{control_type}({automation_id})")
                        current_control = control
                        #current_control = control.GetChildren()
                        found = True
                        break

                if not found:
                    logger.error(f"❌ Level {level} Failed to find control...")
                    return None
            return current_control
       
    # end region 
    # endregion



    def extract_all_data(self, control: auto.Control) -> pd.DataFrame:
        """改進的數據提取方法"""
        data = []
        # 嘗試不同的方法獲取數據行
        data_items = []
        
        # 方法1: 嘗試通過TreeControl獲取
        try:
            tree = control.TreeControl()
            data_items = tree.GetChildren()
        except:
            # 方法2: 直接獲取子控件
            data_items = control.GetChildren()
        
        logger.info(f"🔍 找到 {len(data_items)} 行數據")
        logger.debug(data_items)
        logger.info("🔍 正在提取數據...")
        
        for item in data_items:
            if item.ControlTypeName != "DataItemControl":
                continue
                
            row = {}
            # 嘗試獲取所有子單元格
            for cell in item.GetChildren():
                try:
                    # 嘗試不同的方法獲取單元格值
                    value = None
                    
                    # 方法1: 嘗試獲取ValuePattern
                    try:
                        value = cell.GetValuePattern().Value
                    except:
                        pass
                    
                    # 方法2: 嘗試獲取Name屬性
                    if not value and cell.Name:
                        value = cell.Name
                    
                    # 方法3: 嘗試獲取LegacyIAccessiblePattern
                    if not value:
                        try:
                            value = cell.GetLegacyIAccessiblePattern().Value
                        except:
                            pass
                    
                    if value:
                        # 使用控件名稱作為列名，或自動生成列名
                        col_name = cell.Name if cell.Name else f"Column{len(row)}"
                        row[col_name] = str(value).strip()
                except Exception as e:
                    logger.error(f"⚠️ 獲取單元格值失敗: {e}")
            if row:
                data.append(row)
        
        return pd.DataFrame(data) if data else pd.DataFrame()

    def extract_symbols(self, control: auto.Control) -> List[str]:
        """提取Symbol列表（兼容舊版）"""
        symbols = []
        data_items = [item for item in control.GetChildren() 
                     if item.ControlTypeName == "DataItemControl"]
        
        for item in data_items:
            for cell in item.GetChildren():
                if cell.ControlTypeName == "ComboBoxControl" and "Symbol" in cell.Name:
                    edit = cell.EditControl(AutomationId="[Editor] Edit Area")
                    if edit:
                        try:
                            symbol = edit.GetValuePattern().Value or edit.Name
                            if symbol:
                                symbols.append(symbol.strip())
                        except:
                            if edit.Name:
                                symbols.append(edit.Name.strip())
        
        return list(dict.fromkeys(symbols))
    
    def _format_numeric_value(self, value, is_percent=False):
        """格式化數值，保留2位小數並添加適當單位"""
        try:
            # 處理百分比值
            if is_percent:
                return f"{float(value):.2f}%"
            
            num = float(value)
            
            # 根據數值大小添加單位
            if abs(num) >= 1_000_000_000:
                return f"{num/1_000_000_000:.2f}B"
            elif abs(num) >= 1_000_000:
                return f"{num/1_000_000:.2f}M"
            elif abs(num) >= 1_000:
                return f"{num/1_000:.2f}k"
            else:
                return f"{num:.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _clean_and_format_data(self, df):
        """清理並格式化數據框，處理佔位符值"""
        # 移除第一行（標題行）
        if not df.empty:
            df = df.iloc[1:].reset_index(drop=True)
        
        # 定義應包含數值的列
        numeric_cols = ['Last', '% Change', 'Volume', 'Mkt. Cap', 
                       'Free Float Mkt. Cap', 'Float']
        
        # 清理每個數值列
        for col in numeric_cols:
            if col in df.columns:
                # 替換佔位符文本為空字符串
                df[col] = df[col].replace(['Mkt. Cap', 'Free Float Mkt. Cap', 'Last Split Date','Float'], '', regex=True)
                
                # 轉換為數值，錯誤轉換為NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # 僅格式化有效數字
                is_percent = '%' in col
                df[col] = df[col].apply(
                    lambda x: self._format_numeric_value(x, is_percent) 
                    if pd.notna(x) else ''
                )
        
        return df 
    # region get_list_of_gainers_and_save_md
    def get_list_of_gainers_and_save_md(self):
        """獲取漲幅榜列表並保存為Markdown格式"""
        try:
            # 獲取主窗口
            hwnd = ZeroProAutomation().find_main_window()
            logger.info(f"✅ 主窗口句柄: {hwnd}")
            if not hwnd:
                logger.error("❌ 無法獲取主窗口")
                return

            main_window = auto.ControlFromHandle(hwnd)
            if not main_window:
                logger.error("❌ 無法從句柄獲取控件")
                return

            # 定義控件查找序列
            control_sequence = [
                {"type": "WindowControl", "ids": ["TopTenForm"], "name": "Top List - Percent Chg Up"},
                {"type": "CustomControl", "ids": ["ugrTopTen"]},
                {"type": "CustomControl", "ids": ["Data Area"]},
            ]

            # 查找控件
            target_control = self.find_control_sequence(main_window, control_sequence)
            if not target_control:
                logger.error("❌ 控件查找失敗")
                return

            logger.info("✅ 成功找到目標控件，開始提取數據...")
            
            # 提取並清理數據
            df = self.extract_all_data(target_control)
            #symbols = self.extract_symbols(target_control)
            if not df.empty:
                df = self._clean_and_format_data(df)
                
                os.makedirs("output", exist_ok=True)
                
                # 保存Markdown表格
                md_path = "output/toplist.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("# Top List Data\n\n")
                    f.write(df.to_markdown(index=False))
                logger.info(f"✅ 已保存格式化數據至 {md_path}")
                
                # 保存Symbols
                symbols = df["Symbol"].tolist()
                with open("output/symbols.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(symbols))
                
                # 打印格式化預覽
                logger.info("\n📋 格式化數據預覽:")
                logger.info(df.head())
                
                return symbols, df

        except PermissionError:
            logger.error("❌ 權限不足，請以管理員身份運行")
        except Exception as e:
            logger.error(f"❌ 發生錯誤: {str(e)}")

        # end region
        # endregion 
    
    def get_list_of_gainers_and_save_md_with_hwnd(self, hwnd, data_name="Percent Chg Up"):
        """Get the list of gainers and save the data as Markdown format"""
        try:

            main_window = auto.ControlFromHandle(hwnd)
            if not main_window:
                logger.error("❌ Cannot get control from handle...")
                return

            # define control sequence
            control_sequence = [
                {"type": "WindowControl", "ids": ["TopTenForm"], "name": f"Top List - {data_name}"},
                {"type": "CustomControl", "ids": ["ugrTopTen"]},
                {"type": "CustomControl", "ids": ["Data Area"]},
            ]

            # find control
            target_control = self.find_control_sequence(main_window, control_sequence)
            if not target_control:
                logger.error("❌ Failed to find control...")
                return

            logger.info("✅ 成功找到目標控件，開始提取數據...")
            
            # 提取並清理數據
            df = self.extract_all_data(target_control)
            #symbols = self.extract_symbols(target_control)
            if not df.empty:
                df = self._clean_and_format_data(df)
                
                os.makedirs("output", exist_ok=True)
                
                # 保存Markdown表格
                md_path = "output/toplist.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("# Top List Data\n\n")
                    f.write(df.to_markdown(index=False))
                logger.info(f"✅ 已保存格式化數據至 {md_path}")
                
                # 保存Symbols
                symbols = df["Symbol"].tolist()
                with open("output/symbols.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(symbols))
                
                # 打印格式化預覽
                logger.info("\n\n\n📋 格式化數據預覽:")
                logger.info(df.head())
                print("="*150)
                print("\n\n\n\n\n")
                
                return symbols, df

        except PermissionError:
            logger.error("❌ 權限不足，請以管理員身份運行")
        except Exception as e:
            logger.error(f"❌ 發生錯誤: {str(e)}")