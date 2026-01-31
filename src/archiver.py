# src/archiver.py
import json
import os
from pathlib import Path
from .schema import DailyBriefing

class DataArchiver:
    def __init__(self, base_dir: str = "data/archive"):
        """
        初始化归档器
        :param base_dir: 档案根目录，默认为 data/archive
        """
        self.base_dir = Path(base_dir)

    def save_daily_raw(self, data: DailyBriefing) -> str:
        """
        保存每日原始数据 (Raw Archive)
        路径格式: data/archive/{year}/{date}_raw.json
        """
        # 1. 解析日期 (YYYYMMDD) -> Year
        date_str = data.date
        year = date_str[:4]
        
        # 2. 构建目录路径
        year_dir = self.base_dir / year
        year_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 构建文件路径
        file_path = year_dir / f"{date_str}_raw.json"
        
        # 4. 序列化并写入 (使用 model_dump 以处理 Enum 等复杂类型)
        # ensure_ascii=False 保证中文可读
        with open(file_path, 'w', encoding='utf-8') as f:
            # Pydantic v2 推荐使用 model_dump(mode='json')
            # 如果是旧版 v1，可能需要 data.dict()
            json_data = data.model_dump(mode='json')
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        print(f"💾 [Archiver] 原始档案已保存: {file_path}")
        return str(file_path)

    def load_daily_raw(self, date_str: str) -> DailyBriefing:
        """
        读取历史档案 (用于回溯或重试)
        """
        year = date_str[:4]
        file_path = self.base_dir / year / f"{date_str}_raw.json"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Archive not found for date: {date_str}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
            
        return DailyBriefing(**data_dict)