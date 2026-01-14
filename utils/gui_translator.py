# File: utils/gui_translator.py
"""
GUI Translator - Provides translation support for desktop GUI with live switching.

V5.0 - Multi-language support
"""

import json
import configparser
from pathlib import Path
from typing import Dict, Callable, List
import tkinter as tk


class GUITranslator:
    """Singleton translator for GUI with live language switching."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.locales_dir = Path("locales")
        self.translations: Dict[str, Dict[str, str]] = {}
        self.language = "vi"
        self._callbacks: List[Callable] = []
        
        self._load_languages()
        self._load_saved_language()
    
    def _load_languages(self):
        """Load all language files."""
        for lang_file in self.locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
            except Exception:
                pass
    
    def _load_saved_language(self):
        """Load language setting from config file."""
        try:
            config = configparser.ConfigParser()
            settings_file = Path("gui_settings.ini")
            if settings_file.exists():
                config.read(settings_file)
                saved_lang = config.get('Appearance', 'language', fallback='vi')
                if saved_lang in self.translations:
                    self.language = saved_lang
        except Exception:
            pass
    
    def set_language(self, language: str):
        """Set language and trigger all registered callbacks to update UI."""
        if language in self.translations:
            self.language = language
            # Trigger all callbacks to update UI
            for callback in self._callbacks:
                try:
                    callback()
                except Exception:
                    pass
    
    def register_callback(self, callback: Callable):
        """Register a callback to be called when language changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def t(self, key: str, *args) -> str:
        """Translate a key to current language."""
        lang_data = self.translations.get(self.language, {})
        text = lang_data.get(key, key)
        
        # Handle format args like {0}, {1}
        if args:
            for i, arg in enumerate(args):
                text = text.replace(f"{{{i}}}", str(arg))
        
        return text
    
    def get_language(self) -> str:
        """Get current language code."""
        return self.language


# Global instance
gui_translator = GUITranslator()


def t(key: str, *args) -> str:
    """Convenience function to translate a key."""
    return gui_translator.t(key, *args)


def set_language(language: str):
    """Convenience function to set language."""
    gui_translator.set_language(language)


def register_language_callback(callback: Callable):
    """Register callback for language changes."""
    gui_translator.register_callback(callback)
