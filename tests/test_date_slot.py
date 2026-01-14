# File: tests/test_date_slot.py
# Unit tests for DateSlot extraction and grouping logic

import pytest
from datetime import date

from core.batch_processor import extract_date_slot_from_filename, DateSlot


class TestExtractDateSlotFromFilename:
    """Test cases for extract_date_slot_from_filename function"""
    
    def test_full_day_format(self):
        """Test: 8H N10.1 - 8H N12.1 -> Full day 12/1"""
        result = extract_date_slot_from_filename("8H N10.1 - 8H N12.1")
        assert result is not None
        assert result.date_value.day == 12
        assert result.date_value.month == 1
        assert result.slot is None  # Full day
    
    def test_morning_slot(self):
        """Test: 15H N11.1 - 8H N12.1 -> Slot 8H ngày 12/1"""
        result = extract_date_slot_from_filename("15H N11.1 - 8H N12.1")
        assert result is not None
        assert result.date_value.day == 12
        assert result.date_value.month == 1
        assert result.slot == '8H'
    
    def test_afternoon_slot(self):
        """Test: 8H N12.1 - 15H N12.1 -> Slot 15H ngày 12/1"""
        result = extract_date_slot_from_filename("8H N12.1 - 15H N12.1")
        assert result is not None
        assert result.date_value.day == 12
        assert result.date_value.month == 1
        assert result.slot == '15H'
    
    def test_folder_with_prefix(self):
        """Test folder with prefix: 2 - BDTB DEN 8H N7.1 - 15H N7.1"""
        result = extract_date_slot_from_filename("2 - BDTB DEN 8H N7.1 - 15H N7.1")
        assert result is not None
        assert result.date_value.day == 7
        assert result.date_value.month == 1
        assert result.slot == '15H'
    
    def test_file_with_type(self):
        """Test file with type: GATE IN OUT 8H N10.1 - 8H N12.1 (982C).xlsx"""
        result = extract_date_slot_from_filename("GATE IN OUT 8H N10.1 - 8H N12.1 (982C).xlsx")
        assert result is not None
        assert result.date_value.day == 12
        assert result.date_value.month == 1
    
    def test_ton_moi_format(self):
        """Test TON MOI: TON MOI N12.1.2026.xlsx"""
        result = extract_date_slot_from_filename("TON MOI N12.1.2026.xlsx")
        assert result is not None
        assert result.date_value.day == 12
        assert result.date_value.month == 1
        assert result.slot is None  # Full day
    
    def test_ton_cu_format(self):
        """Test TON CU: TON CU N10.1.2026.xlsx"""
        result = extract_date_slot_from_filename("TON CU N10.1.2026.xlsx")
        assert result is not None
        assert result.date_value.day == 10
        assert result.date_value.month == 1
    
    def test_invalid_format(self):
        """Test invalid format returns None"""
        result = extract_date_slot_from_filename("random_file.xlsx")
        assert result is None
    
    def test_date_with_year(self):
        """Test date with year: N12.1.2026"""
        result = extract_date_slot_from_filename("LIST BDTB 8H N10.1 - 8H N12.1.2026")
        assert result is not None
        assert result.date_value.year == 2026
        assert result.date_value.month == 1
        assert result.date_value.day == 12


class TestDateSlot:
    """Test cases for DateSlot dataclass"""
    
    def test_display_label_full_day(self):
        """Test display label for full day"""
        slot = DateSlot(date(2026, 1, 12), None)
        assert slot.display_label() == "12/01/2026"
    
    def test_display_label_with_slot(self):
        """Test display label with time slot"""
        slot = DateSlot(date(2026, 1, 12), "8H")
        label = slot.display_label()
        assert "12/01/2026" in label
        assert "8H" in label
    
    def test_comparison(self):
        """Test DateSlot comparison for sorting"""
        slot1 = DateSlot(date(2026, 1, 10), "8H")
        slot2 = DateSlot(date(2026, 1, 10), "15H")
        slot3 = DateSlot(date(2026, 1, 11), "8H")
        
        # Same date, 8H < 15H
        assert slot1 < slot2
        # Different dates
        assert slot1 < slot3
        assert slot2 < slot3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
