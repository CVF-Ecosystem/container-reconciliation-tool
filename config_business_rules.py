# File: config_business_rules.py — @2026 v1.0
"""
Business Rules cho Rule Engine đối soát container.

Tách ra khỏi config.py để dễ bảo trì và mở rộng.
KHÔNG import từ config.py để tránh circular import.
Dùng string literals trực tiếp (các giá trị của Col class).

Mỗi rule có dạng:
    {
        'conditions': {column_name: [list_of_values]},
        'action': {'move_type': 'IN' | 'OUT'}
    }

Các rule được áp dụng theo thứ tự từ trên xuống.
Rule đầu tiên khớp sẽ được áp dụng (first-match wins).
"""

# Column name constants (mirror của config.Col để tránh circular import)
_SOURCE_KEY = 'SourceKey'
_PHUONG_AN = 'Phương án'
_VAO_RA = 'Vào/Ra'


# ============================================================
# BUSINESS RULES - Rule Engine chính
# Hỗ trợ cả tiếng Anh và tiếng Việt (có dấu và không dấu)
# ============================================================

BUSINESS_RULES = [
    # ===== THEO SOURCE KEY (Ưu tiên cao nhất) =====
    # Xác định hướng dựa trên nguồn file, không cần check Phương án
    {
        'conditions': {_SOURCE_KEY: ['xuat_tau', 'xuat_shifting', 'gate_out']},
        'action': {'move_type': 'OUT'}
    },
    {
        'conditions': {_SOURCE_KEY: ['nhap_tau', 'nhap_shifting', 'gate_in', 'ton_cu']},
        'action': {'move_type': 'IN'}
    },

    # ===== PHƯƠNG ÁN XUẤT (RA khỏi bãi) =====

    # Lấy Nguyên (Pick Up)
    {
        'conditions': {_PHUONG_AN: [
            'LAY NGUYEN', 'Lấy Nguyên', 'LẤY NGUYÊN', 'lay nguyen',
            'PICK UP', 'Pick Up', 'Pick up'
        ]},
        'action': {'move_type': 'OUT'}
    },

    # Cấp Rỗng (Empty Release)
    {
        'conditions': {_PHUONG_AN: [
            'CAP RONG', 'Cấp rỗng', 'CẤP RỖNG', 'cap rong',
            'EMPTY RELEASE', 'Empty Release'
        ]},
        'action': {'move_type': 'OUT'}
    },

    # Lưu Rỗng - Xuất (phụ thuộc Vào/Ra)
    {
        'conditions': {
            _PHUONG_AN: ['LUU RONG', 'Lưu rỗng', 'LƯU RỖNG', 'luu rong'],
            _VAO_RA: ['RA', 'Ra', 'OUT', 'Out']
        },
        'action': {'move_type': 'OUT'}
    },

    # Xuất tàu (Loading)
    {
        'conditions': {_PHUONG_AN: [
            'XUAT TAU', 'Xuất tàu', 'XUẤT TÀU', 'xuat tau',
            'LOADING', 'Loading', 'SHIP OUT', 'Ship Out'
        ]},
        'action': {'move_type': 'OUT'}
    },

    # Chuyển tàu - Xuất (phụ thuộc Vào/Ra)
    {
        'conditions': {
            _PHUONG_AN: [
                'CHUYEN TAU', 'Chuyển tàu', 'CHUYỂN TÀU', 'chuyen tau',
                'TRANSHIPMENT', 'Transhipment'
            ],
            _VAO_RA: ['RA', 'Ra', 'OUT', 'Out']
        },
        'action': {'move_type': 'OUT'}
    },

    # Shifting Loading (Bãi → Tàu)
    {
        'conditions': {_PHUONG_AN: [
            'SHIFTING LOADING', 'Shifting Loading', 'shifting loading',
            'SHIFTING XUẤT', 'Shifting xuất', 'X-RESTOW', 'RESTOW OUT',
            'Shifting xuất (Bãi→Tàu)'
        ]},
        'action': {'move_type': 'OUT'}
    },

    # ===== PHƯƠNG ÁN NHẬP (VÀO bãi) =====

    # Hạ Bãi (Drop Off)
    {
        'conditions': {_PHUONG_AN: [
            'HA BAI', 'Hạ bãi', 'HẠ BÃI', 'ha bai',
            'DROP OFF', 'Drop Off', 'Drop off', 'DROP'
        ]},
        'action': {'move_type': 'IN'}
    },

    # Trả Rỗng (Empty Return)
    {
        'conditions': {_PHUONG_AN: [
            'TRA RONG', 'Trả rỗng', 'TRẢ RỖNG', 'tra rong',
            'EMPTY RETURN', 'Empty Return', 'MTY RETURN'
        ]},
        'action': {'move_type': 'IN'}
    },

    # Lưu Rỗng - Nhập (phụ thuộc Vào/Ra)
    {
        'conditions': {
            _PHUONG_AN: ['LUU RONG', 'Lưu rỗng', 'LƯU RỖNG', 'luu rong'],
            _VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']
        },
        'action': {'move_type': 'IN'}
    },

    # Nhập tàu (Discharge)
    {
        'conditions': {_PHUONG_AN: [
            'NHAP TAU', 'Nhập tàu', 'NHẬP TÀU', 'nhap tau',
            'DISCHARGE', 'Discharge', 'SHIP IN', 'Ship In'
        ]},
        'action': {'move_type': 'IN'}
    },

    # Chuyển tàu - Nhập (phụ thuộc Vào/Ra)
    {
        'conditions': {
            _PHUONG_AN: [
                'CHUYEN TAU', 'Chuyển tàu', 'CHUYỂN TÀU', 'chuyen tau',
                'TRANSHIPMENT', 'Transhipment'
            ],
            _VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']
        },
        'action': {'move_type': 'IN'}
    },

    # Shifting Discharge (Tàu → Bãi)
    {
        'conditions': {_PHUONG_AN: [
            'SHIFTING DISCHARGE', 'Shifting Discharge', 'shifting discharge',
            'SHIFTING NHẬP', 'Shifting nhập', 'N-RESTOW', 'RESTOW IN',
            'Shifting nhập (Tàu→Bãi)'
        ]},
        'action': {'move_type': 'IN'}
    },

    # ===== ĐÓNG HÀNG / RÚT HÀNG (phụ thuộc Vào/Ra) =====

    {
        'conditions': {
            _PHUONG_AN: [
                'DONG HANG', 'RUT HANG', 'ĐÓNG HÀNG', 'RÚT HÀNG',
                'ĐÓNG HÀNG XE - CONT', 'ĐÓNG HÀNG GHE - CONT',
                'STUFFING', 'Stuffing', 'UNSTUFFING', 'Unstuffing'
            ],
            _VAO_RA: ['RA', 'Ra', 'OUT', 'Out']
        },
        'action': {'move_type': 'OUT'}
    },
    {
        'conditions': {
            _PHUONG_AN: [
                'DONG HANG', 'RUT HANG', 'ĐÓNG HÀNG', 'RÚT HÀNG',
                'ĐÓNG HÀNG XE - CONT', 'ĐÓNG HÀNG GHE - CONT',
                'STUFFING', 'Stuffing', 'UNSTUFFING', 'Unstuffing'
            ],
            _VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']
        },
        'action': {'move_type': 'IN'}
    },

    # ===== RÚT HÀNG TỪ XE / GHE (phụ thuộc Vào/Ra) =====

    {
        'conditions': {
            _PHUONG_AN: [
                'RÚT HÀNG TỪ XE - CONT', 'RÚT HÀNG TỪ GHE - CONT',
                'RUT HANG TU XE', 'RUT HANG TU GHE'
            ],
            _VAO_RA: ['RA', 'Ra', 'OUT', 'Out']
        },
        'action': {'move_type': 'OUT'}
    },
    {
        'conditions': {
            _PHUONG_AN: [
                'RÚT HÀNG TỪ XE - CONT', 'RÚT HÀNG TỪ GHE - CONT',
                'RUT HANG TU XE', 'RUT HANG TU GHE'
            ],
            _VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']
        },
        'action': {'move_type': 'IN'}
    },

    # ===== ĐÓNG HÀNG SANG CONTAINER (CFS) =====

    {
        'conditions': {
            _PHUONG_AN: [
                'Đóng hàng sang container sử dụng xe nâng',
                'DONG HANG SANG CONT', 'CFS STUFFING'
            ],
            _VAO_RA: ['RA', 'Ra', 'OUT', 'Out']
        },
        'action': {'move_type': 'OUT'}
    },
    {
        'conditions': {
            _PHUONG_AN: [
                'Đóng hàng sang container sử dụng xe nâng',
                'DONG HANG SANG CONT', 'CFS STUFFING'
            ],
            _VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']
        },
        'action': {'move_type': 'IN'}
    },
]
