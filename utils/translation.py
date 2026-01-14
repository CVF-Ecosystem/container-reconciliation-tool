# File: translation.py
import json
from pathlib import Path
from typing import Dict
import configparser

class Translator:
    def __init__(self, locales_dir: Path = Path("locales")):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.language = self._load_saved_language()  # V5.0: Load from settings
        self._load_languages()

    def _load_saved_language(self) -> str:
        """V5.0: Load language from gui_settings.ini."""
        try:
            config = configparser.ConfigParser()
            settings_file = Path("gui_settings.ini")
            if settings_file.exists():
                config.read(settings_file)
                return config.get('Appearance', 'language', fallback='vi')
        except:
            pass
        return "vi"

    def _load_languages(self):
        """Tải tất cả các file .json trong thư mục locales."""
        for lang_file in self.locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.translations[lang_code] = json.load(f)

    def set_language(self, language: str):
        """Thiết lập ngôn ngữ hiện tại."""
        if language in self.translations:
            self.language = language
        else:
            # Mặc định quay về tiếng Anh nếu không tìm thấy ngôn ngữ
            self.language = "en"

    def get_translator(self):
        """Trả về một hàm dịch (t) cho ngôn ngữ hiện tại."""
        lang_data = self.translations.get(self.language, {})
        
        def t(key: str) -> str:
            """Dịch một key sang ngôn ngữ hiện tại."""
            return lang_data.get(key, key) # Trả về chính key nếu không tìm thấy bản dịch
            
        return t

# Tạo một instance toàn cục để các module khác có thể sử dụng
translator_instance = Translator()