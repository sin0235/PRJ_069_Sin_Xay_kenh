import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sin_content_api"))

from src.modules.tao_video_noi_dung import planner

brief_data = {
    "pains": [
        {"id": "pain-1", "text": "Doanh nghiệp bận rộn cả ngày nhưng hiệu quả chưa như mong đợi, chi phí tăng mà doanh thu không tăng tương xứng.", "source": "content"},
        {"id": "pain-2", "text": "Khách hàng quan tâm sản phẩm nhưng không được chăm sóc kịp thời, dẫn đến mất đơn hàng.", "source": "content"},
        {"id": "pain-3", "text": "Chủ doanh nghiệp phải liên tục kiểm tra tiến độ, nhắc nhở nhân viên, xử lý việc lặp lại.", "source": "content"}
    ],
    "consequences": [
        {"id": "consequence-1", "text": "Chi phí vận hành tăng cao, lãng phí thời gian và cơ hội kinh doanh.", "source": "content"},
        {"id": "consequence-2", "text": "Điểm nghẽn vô hình tiếp tục kìm hãm sự bứt phá và phát triển của doanh nghiệp.", "source": "content"}
    ],
    "insights": [
        {"id": "insight-1", "text": "Vấn đề thực sự không phải do thiếu khách hàng, nhân sự hay nỗ lực.", "source": "content"},
        {"id": "insight-2", "text": "Điều doanh nghiệp thiếu là một hệ thống vận hành đủ thông minh để tận dụng nguồn lực đang có.", "source": "content"}
    ],
    "solutions": [
        {"id": "solution-1", "text": "Chương trình Khám sức khỏe doanh nghiệp hoàn toàn miễn phí cùng BAHA.", "source": "content"},
        {"id": "solution-2", "text": "Nhìn lại cách vận hành từ tìm kiếm khách hàng, bán hàng, chăm sóc khách đến quản lý công việc để nhận diện điểm nghẽn.", "source": "content"},
        {"id": "solution-3", "text": "Tư vấn lộ trình giải pháp công nghệ ứng dụng trí tuệ nhân tạo (AI) phù hợp thực tế.", "source": "content"},
        {"id": "solution-4", "text": "Khách hàng được tiếp nhận 24/7, bán hàng phân loại tự động, tiến độ tự động theo dõi.", "source": "content"}
    ],
    "outcomes": [
        {"id": "outcome-1", "text": "Quản lý nắm bắt tình hình mà không cần liên tục hỏi nhân viên, tiết kiệm chi phí và tăng tốc độ.", "source": "content"},
        {"id": "outcome-2", "text": "Giải pháp công nghệ thực tế tạo ra giá trị thực, không bắt buộc triển khai.", "source": "content"}
    ],
    "cta": {
        "id": "cta-1",
        "text": "Đăng ký chương trình khám sức khỏe doanh nghiệp miễn phí cùng BAHA ngay hôm nay.",
        "source": "content"
    },
    "needs_ui_demo": False
}

storyboard_v4 = {
    "title": "Chuyển đổi vận hành doanh nghiệp cùng BAHA (V4)",
    "narration": "",
    "continuity_anchor": "Phong cách hoạt họa biên tập B2B cao cấp; nửa đầu ngà xám và san hô thể hiện sự thủ công rối rắm; nửa sau ngọc lam sáng và vàng kim trên nền navy sâu thể hiện tự động hoá thông minh. Đạo cụ origami như sổ sách, thẻ việc, băng chuyền và bảng số liệu.",
    "brief": brief_data,
    "shots": [
        {
            "shot_id": "s01",
            "scene": "Hook trạng thái hỗn loạn: bàn làm việc ngập trong chứng từ sổ sách.",
            "narration": "Doanh nghiệp của bạn đang thực sự phát triển, hay chỉ đang ngày càng bận rộn hơn? Nhân viên làm việc cả ngày nhưng hiệu quả vẫn chưa như mong đợi.",
            "prompt": "FLOW_ORIGAMI. Khung ngang 16:9, không chữ. Cận cảnh bàn làm việc origami bề bộn chứng từ hóa đơn; người quản lý bối rối lật giở từng trang tài liệu giữa tiếng chuông điện thoại reo liên hồi.",
            "negative_prompt": "Không chữ, số, logo, watermark; không biến hình, nhân đôi đạo cụ, giật hình, động tác vô lý hoặc giữ tư thế tĩnh.",
            "duration_seconds": 10,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "HOOK",
            "message_ids": ["pain-1"],
            "shot_kind": "FLOW_ORIGAMI",
            "action_beats": [
                {
                    "start_s": 0.0,
                    "end_s": 3.2,
                    "action": "Người quản lý ngồi giữa xấp tài liệu dày cộp, lúng túng tìm kiếm hóa đơn khách hàng cần gấp."
                },
                {
                    "start_s": 3.2,
                    "end_s": 6.8,
                    "action": "Nhân viên liên tục mang thêm phiếu yêu cầu đặt lên bàn làm việc đang quá tải nghiêm trọng."
                },
                {
                    "start_s": 6.8,
                    "end_s": 10.0,
                    "action": "Chuông điện thoại bàn reo vang trong khi báo cáo tài chính vẫn còn dang dở chưa hoàn thành."
                }
            ],
            "ui_scene": None
        },
        {
            "shot_id": "s02",
            "scene": "Tiêu đề chốt sự thật bận rộn hay phát triển.",
            "narration": "Chi phí vận hành tăng đều mỗi tháng, trong khi doanh thu lại không tăng tương xứng.",
            "prompt": "KINETIC_TITLE: câu chốt hiện chữ lớn BẬN RỘN HAY PHÁT TRIỂN.",
            "negative_prompt": "",
            "duration_seconds": 5,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "PAIN",
            "message_ids": ["pain-1"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "KINETIC_TITLE",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "BẬN RỘN HAY PHÁT TRIỂN",
                    "tag": "PHÁT TRIỂN",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s03",
            "scene": "Trước: Lật trang sổ sách thủ công bề bộn, đóng dấu chưa xử lý.",
            "narration": "Là chủ doanh nghiệp, bạn phải liên tục kiểm tra tiến độ, nhắc nhở nhân viên, xử lý những vấn đề lặp đi lặp lại mỗi ngày.",
            "prompt": "BOOK_FLIP: lật trang sổ sách chuyển đổi từ thủ công sang tự động.",
            "negative_prompt": "",
            "duration_seconds": 9,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "PAIN",
            "message_ids": ["pain-3"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "BOOK_FLIP",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Chuyển đổi sổ sách thủ công",
                    "docs": [
                        {"title": "Trước", "label": "Thủ công", "value": "Chậm trễ"},
                        {"title": "Sau", "label": "Tự động", "value": "Chính xác"}
                    ],
                    "steps": ["Sổ bán hàng", "Bảng theo dõi", "Phiếu thu chi"],
                    "diff_label": "CHƯA XỬ LÝ",
                    "caption": "Sổ sách thủ công",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s04",
            "scene": "Tiêu điểm chuyển từ quản lý sự vụ sang kiểm soát tiến độ.",
            "narration": "Khách hàng quan tâm sản phẩm nhưng không được chăm sóc kịp thời, dẫn đến mất đơn hàng.",
            "prompt": "CARD_SHIFT: chuyển đổi giữa chăm sóc khách và chốt đơn hàng.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "PAIN",
            "message_ids": ["pain-2"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "CARD_SHIFT",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Trễ phản hồi",
                    "steps": ["Chăm sóc chậm", "Mất đơn hàng"],
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s05",
            "scene": "Băng chuyền quy trình tắc nghẽn ở khâu tư vấn, thẻ hồ sơ rơi.",
            "narration": "Khách hàng quan tâm sản phẩm nhưng không được chăm sóc kịp thời, dẫn đến mất đơn hàng. Hơn sáu mươi lăm phần trăm cơ hội kinh doanh trôi qua vì thiếu quy trình theo dõi.",
            "prompt": "PIPELINE_RAIL: băng chuyền quy trình chăm sóc và bán hàng với thẻ kẹt.",
            "negative_prompt": "",
            "duration_seconds": 10,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "AGITATE",
            "message_ids": ["consequence-1"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "PIPELINE_RAIL",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Quy trình chăm sóc và bán hàng",
                    "steps": ["Tiếp nhận", "Tư vấn", "Chốt đơn"],
                    "block_step": 1,
                    "tag": "Khách quan tâm",
                    "value": "65%",
                    "caption": "Rò rỉ cơ hội",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s06",
            "scene": "Vòng tròn tỉ lệ thất thoát thời gian.",
            "narration": "Bạn có bao giờ tự hỏi: Vấn đề thực sự nằm ở đâu? Do nhân viên hay do quy trình quản lý?",
            "prompt": "STAT_RING: vòng tròn quét 75% lãng phí thời gian.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "INSIGHT",
            "message_ids": ["insight-1"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "STAT_RING",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Tỉ lệ lãng phí thời gian",
                    "to_value": 75,
                    "caption": "Vấn đề nằm ở đâu",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s07",
            "scene": "Bàn cờ đội ngũ chuyền việc, người duyệt vắng mặt khiến thẻ đỏ bật lên.",
            "narration": "Thực tế, nhiều doanh nghiệp không hề thiếu khách hàng hay nhân sự. Điều họ thực sự thiếu là một hệ thống vận hành đủ thông minh để tận dụng các nguồn lực đang có.",
            "prompt": "TEAM_BOARD: bàn giao việc giữa các nhân sự và điểm nghẽn thiếu người duyệt.",
            "negative_prompt": "",
            "duration_seconds": 10,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "INSIGHT",
            "message_ids": ["insight-2"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "TEAM_BOARD",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Người duyệt đơn",
                    "steps": ["Tiếp nhận", "Duyệt đơn", "Bàn giao"],
                    "pick": 1,
                    "tag": "Chờ duyệt",
                    "value": "15 đơn",
                    "caption": "Tắc nghẽn nhân sự",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s08",
            "scene": "Hoán đổi các bước lộ trình cải thiện.",
            "narration": "Đó là lý do BAHA cùng bạn nhận diện những điểm nghẽn đang làm lãng phí chi phí và cơ hội.",
            "prompt": "WORD_SWAP: các bước hiểu vấn đề, định vị rò rỉ, giải pháp AI.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "SOLUTION",
            "message_ids": ["solution-1", "solution-2"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "WORD_SWAP",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Lộ trình tháo gỡ",
                    "steps": ["Hiểu vấn đề", "Định vị rò rỉ", "Giải pháp AI"],
                    "caption": "không bắt buộc",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s09",
            "scene": "Sau: Bảng so sánh trước và sau chuyển đổi số.",
            "narration": "BAHA tư vấn giải pháp ứng dụng trí tuệ nhân tạo phù hợp với chính nguồn lực thực tế của doanh nghiệp.",
            "prompt": "BEFORE_AFTER: bảng đối chiếu trước thủ công sau tự động thông minh.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "SOLUTION",
            "message_ids": ["solution-3"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "BEFORE_AFTER",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Chuyển đổi vận hành bằng AI",
                    "docs": [
                        {"title": "Trước đây", "label": "Thủ công", "value": "Sự vụ"},
                        {"title": "Hiện nay", "label": "Hệ thống AI", "value": "Tự động"}
                    ],
                    "diff_label": "TĂNG TRƯỞNG",
                    "on": {
                        "before": "giải pháp ứng dụng",
                        "after": "trí tuệ nhân tạo",
                        "delta": "nguồn lực thực tế"
                    }
                }
            }
        },
        {
            "shot_id": "s10",
            "scene": "Bảng điều khiển trực tiếp với biểu đồ cột 3D và kim chỉ báo hiệu suất AI.",
            "narration": "Khách hàng được tiếp nhận tức thì ngay cả ngoài giờ làm việc, đội ngũ bán hàng được phân loại khách tự động, công việc được theo dõi sát sao.",
            "prompt": "LIVE_DASHBOARD: bảng điều khiển vận hành tự động hoá ứng dụng AI.",
            "negative_prompt": "",
            "duration_seconds": 10,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "DEMO",
            "message_ids": ["solution-4"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "LIVE_DASHBOARD",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Vận hành thông minh ứng dụng AI",
                    "labels": ["Tiếp nhận", "Phân loại", "Báo cáo"],
                    "series": [
                        {"name": "Hiện tại", "values": [30.0, 45.0, 40.0]},
                        {"name": "Tự động AI", "values": [90.0, 85.0, 95.0]}
                    ],
                    "to_value": 85,
                    "tag": "Tự động hoá",
                    "caption": "Hỗ trợ 24/7",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s11",
            "scene": "Chuyển ý mở ra lộ trình giải pháp công nghệ.",
            "narration": "Đó không còn là ý tưởng xa vời, mà là giải pháp hoàn toàn có thể triển khai ngay hôm nay.",
            "prompt": "KINETIC_TITLE: câu chốt công nghệ tạo giá trị thực.",
            "negative_prompt": "",
            "duration_seconds": 5,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "DEMO",
            "message_ids": ["solution-4"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "KINETIC_TITLE",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "CÔNG NGHỆ TẠO GIÁ TRỊ THỰC",
                    "tag": "GIÁ TRỊ THỰC",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s12",
            "scene": "Dòng nhận diện giá trị thực được khoanh tròn.",
            "narration": "Đừng để những điểm nghẽn vô hình tiếp tục kìm hãm sự bứt phá của doanh nghiệp bạn.",
            "prompt": "MARK_PHRASE: khoanh cụm then chốt giải pháp tạo giá trị thực.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "DEMO",
            "message_ids": ["outcome-1", "consequence-2"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "MARK_PHRASE",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Công nghệ tạo ra giá trị thực",
                    "tag": "tạo ra giá trị thực",
                    "caption": "Hiệu quả rõ rệt",
                    "on": {}
                }
            }
        },
        {
            "shot_id": "s13",
            "scene": "Bảng kiểm 3 nội dung của chương trình khám doanh nghiệp được tích xanh.",
            "narration": "Khám doanh nghiệp miễn phí, nhận diện đúng vấn đề, đề xuất giải pháp, không bắt buộc triển khai.",
            "prompt": "CHECKLIST: 3 bước khám toàn diện, nhận diện vấn đề, đề xuất giải pháp.",
            "negative_prompt": "",
            "duration_seconds": 6,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "SOLUTION",
            "message_ids": ["solution-1", "outcome-2"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "CHECKLIST",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "Khám sức khỏe doanh nghiệp",
                    "steps": ["Khám toàn diện miễn phí", "Nhận diện đúng vấn đề", "Đề xuất giải pháp thực"],
                    "on": {
                        "c0": "Khám doanh nghiệp",
                        "c1": "đúng vấn đề",
                        "c2": "không bắt buộc"
                    }
                }
            }
        },
        {
            "shot_id": "s14",
            "scene": "Thẻ kêu gọi hành động đăng ký khám doanh nghiệp miễn phí cùng BAHA.",
            "narration": "Đăng ký khám doanh nghiệp miễn phí cùng BAHA ngay hôm nay để tạo ra giá trị thực.",
            "prompt": "CTA_CLOSE: thẻ kết thương hiệu BAHA Group với lời mời khám doanh nghiệp miễn phí.",
            "negative_prompt": "",
            "duration_seconds": 5,
            "continues_previous": False,
            "prompt_contract_version": 4,
            "beat": "CTA",
            "message_ids": ["cta-1"],
            "shot_kind": "UI_SIM",
            "action_beats": [],
            "ui_scene": {
                "layout": "CTA_CLOSE",
                "messages": [],
                "highlight": None,
                "diagram": {
                    "title": "BAHA Group",
                    "caption": "Đăng ký khám doanh nghiệp miễn phí",
                    "tag": "Giá trị thực",
                    "value": "baha.vn",
                    "on": {}
                }
            }
        }
    ]
}

storyboard_v4["narration"] = " ".join(s["narration"] for s in storyboard_v4["shots"])
total_sec = sum(s["duration_seconds"] for s in storyboard_v4["shots"])
print(f"Total duration V4: {total_sec}s")

storyboard = planner.Storyboard.model_validate(storyboard_v4)
print("Storyboard V4 Pydantic: SUCCESS!")

richness = planner._richness_problems(storyboard)
print(f"Richness problems V4: {richness}")

score = planner.score_storyboard(storyboard, storyboard.brief)
print(f"Coverage: {score.coverage}, issues: {score.issues}")

soft = planner._soft_problems(storyboard, aspect_ratio="16:9")
print(f"Soft problems V4: {soft}")

out_path = Path(__file__).resolve().parents[2] / "mau_video" / "v4" / "storyboard_baha_v4.json"
out_path.write_text(json.dumps(storyboard_v4, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved verified storyboard to {out_path}")
