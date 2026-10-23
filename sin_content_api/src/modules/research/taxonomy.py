"""
Audience Need Taxonomy & Intent Groups (P05 / P05-10)
Deterministic categorization for intent groups and search variant generation.
"""
from enum import Enum
from typing import Dict, List

class IntentGroup(str, Enum):
    PROBLEMS = "PROBLEMS"
    CONTEXTS = "CONTEXTS"
    COMPARISONS = "COMPARISONS"
    OBJECTIONS = "OBJECTIONS"
    QUESTIONS = "QUESTIONS"
    TRENDS = "TRENDS"

AUDIENCE_NEED_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    IntentGroup.PROBLEMS: {
        "description": "Nỗi đau, sự cố, bất tiện hoặc thất vọng mà người dùng gặp phải",
        "subcategories": [
            "PACKAGING_LEAKAGE",      # Rò rỉ, tràn nắp, hỏng khóa
            "THERMAL_RETENTION_LOSS", # Nhanh nguội, không giữ nhiệt tốt
            "CLEANING_DIFFICULTY",    # Khó rửa kẽ nắp, bám mùi thức ăn
            "SKIN_BREAKOUT",          # Kích ứng, lên mụn, châm chích
            "AUDIO_LATENCY",          # Trễ âm, rè mic khi đàm thoại
            "DURABILITY_ISSUE",       # Nhanh hỏng, bong tróc
        ],
        "templates": [
            "sự cố bất tiện khi dùng {topic}",
            "{topic} có thật sự hiệu quả tốt không",
            "cách xử lý vấn đề thường gặp với {topic}",
            "lưu ý quan trọng khi trải nghiệm {topic}",
            "lỗi phổ biến khi sử dụng {topic}",
        ]
    },
    IntentGroup.CONTEXTS: {
        "description": "Tình huống, không gian và môi trường sử dụng thực tế của khách hàng",
        "subcategories": [
            "OFFICE_COMMUTE",         # Mang đi làm văn phòng, đi xe máy
            "STUDENT_DORM",           # Sinh viên ký túc xá, bữa trưa tiết kiệm
            "GYM_WORKOUT",            # Tập thể thao, bổ sung nước/protein
            "REMOTE_MEETING",         # Đàm thoại họp online tại nhà
            "NIGHT_ROUTINE",          # Chu trình dưỡng da trước khi ngủ
        ],
        "templates": [
            "{topic} cho người đi làm",
            "{topic} tiện lợi mỗi ngày",
            "{topic} cho sinh viên và giới trẻ",
            "thói quen sử dụng {topic} hàng ngày",
        ]
    },
    IntentGroup.COMPARISONS: {
        "description": "So sánh, phân vân lựa chọn giữa các chất liệu, thương hiệu hoặc giải pháp",
        "subcategories": [
            "MATERIAL_DIFFERENCE",    # So sánh chất liệu / thành phần
            "BRAND_BENCHMARK",        # So sánh với đối thủ cạnh tranh trực tiếp
            "FEATURE_TRADE_OFF",      # Đánh đổi công năng
        ],
        "templates": [
            "so sánh {topic} với các dòng phổ biến",
            "nên chọn {topic} hay giải pháp thông thường",
            "review các loại {topic} hot nhất hiện nay",
            "đánh giá thật {topic} so với thị trường",
        ]
    },
    IntentGroup.OBJECTIONS: {
        "description": "Rào cản tâm lý, nghi ngại về giá thành, tính xác thực hoặc độ an toàn",
        "subcategories": [
            "PRICE_VALUE_DOUBT",      # Giá cao có đáng tiền không
            "SAFETY_AUTHENTICITY",    # Có an toàn vệ sinh không, có giả nhái không
            "MAINTENANCE_EFFORT",     # Dùng có phiền phức rườm rà không
        ],
        "templates": [
            "{topic} có đáng tiền không",
            "sự thật về {topic} quảng cáo",
            "nhược điểm của {topic} ít ai nói",
            "{topic} dùng lâu có bền không",
        ]
    },
    IntentGroup.QUESTIONS: {
        "description": "Các câu hỏi thắc mắc thường gặp cần hướng dẫn giải đáp",
        "subcategories": [
            "HOW_TO_USE",             # Cách sử dụng đúng
            "HOW_TO_CLEAN",           # Cách vệ sinh, bảo quản
            "TROUBLESHOOTING",        # Xử lý khi gặp lỗi
        ],
        "templates": [
            "cách dùng {topic} đúng cách",
            "mẹo bảo quản và sử dụng {topic} hiệu quả",
            "hướng dẫn chọn mua {topic} chuẩn nhất",
        ]
    },
    IntentGroup.TRENDS: {
        "description": "Xu hướng định dạng video, âm thanh hoặc bối cảnh viral đang thịnh hành",
        "subcategories": [
            "PACK_LUNCH_WITH_ME",     # Định dạng chuẩn bị đồ ăn mang đi làm
            "BEFORE_AFTER_PROOF",     # Thử nghiệm thực tế chứng minh
            "WHAT_I_EAT_IN_A_DAY",    # Thực đơn ngày làm việc
        ],
        "templates": [
            "trải nghiệm thực tế cùng {topic}",
            "thử thách kiểm chứng chất lượng {topic}",
            "một ngày trải nghiệm cùng {topic}",
        ]
    }
}
