import sys
from pathlib import Path

# Add sin_content_api to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sin_content_api"))

from src.modules.tao_video_noi_dung import planner

narrations = [
    (10, "Doanh nghiệp của bạn đang thực sự phát triển, hay chỉ đang ngày càng bận rộn hơn? Nhân viên làm việc cả ngày nhưng hiệu quả vẫn chưa như mong đợi."),
    (5, "Chi phí vận hành tăng đều mỗi tháng, trong khi doanh thu lại không tăng tương xứng."),
    (10, "Khách hàng quan tâm sản phẩm nhưng không được chăm sóc kịp thời, dẫn đến mất đơn hàng. Bạn liên tục phải kiểm tra, nhắc nhở những việc lặp đi lặp lại."),
    (6, "Hơn sáu mươi lăm phần trăm cơ hội kinh doanh trôi qua chỉ vì phản hồi chậm trễ."),
    (8, "Bạn có bao giờ tự hỏi: Vấn đề thực sự nằm ở đâu? Do nhân sự làm việc, hay do quy trình quản lý chưa phù hợp?"),
    (8, "Nhiều doanh nghiệp không thiếu khách hàng hay cơ hội. Điều họ thiếu là một hệ thống vận hành đủ thông minh để tận dụng nguồn lực."),
    (8, "Đó là lý do BAHA cùng bạn nhìn lại toàn bộ cách vận hành, nhận diện những điểm nghẽn đang làm lãng phí thời gian và chi phí."),
    (6, "Chúng tôi giúp bạn hiểu rõ vấn đề, định vị chính xác rò rỉ và đề xuất giải pháp phù hợp."),
    (10, "Khách hàng được tiếp nhận tức thì ngoài giờ, đội ngũ bán hàng được phân loại khách tự động, quản lý nắm bắt tiến độ mà không cần hỏi từng người."),
    (6, "Đó không còn là ý tưởng xa vời, mà là giải pháp hoàn toàn có thể triển khai ngay hôm nay."),
    (8, "Chương trình khám doanh nghiệp miễn phí của BAHA: khám toàn diện, nhận diện đúng vấn đề, đề xuất giải pháp, không bắt buộc triển khai."),
    (10, "Đừng để những điểm nghẽn vô hình tiếp tục kìm hãm sự phát triển. Hãy chủ động làm chủ vận hành thông minh và nâng tầm doanh nghiệp của bạn."),
    (5, "Đăng ký khám doanh nghiệp miễn phí cùng BAHA ngay hôm nay để tạo ra giá trị thực.")
]

total_syllables = 0
all_ok = True
for i, (sec, text) in enumerate(narrations, 1):
    count = planner.narration_syllables(text)
    rate = count / sec
    low, high = round(sec * planner.NARRATION_SYLLABLES_MIN_RATIO), round(sec * planner.NARRATION_SYLLABLES_MAX_RATIO)
    ok = low <= count <= high
    if not ok:
        all_ok = False
    total_syllables += count
    status = "OK" if ok else "FAIL"
    print(f"s{i:02d} ({sec:2d}s): {count:2d} syllables ({rate:.2f} syl/s) [{low:2d}-{high:2d}] -> {status}")

print(f"Total: {total_syllables} syllables across 100s ({total_syllables/100:.2f} syl/s)")
expected = 100 * planner.SPEECH_SYLLABLES_PER_SECOND
total_ok = 0.85 * expected <= total_syllables <= 1.05 * expected
print(f"Total range [{0.85 * expected:.0f} - {1.05 * expected:.0f}]: {'OK' if total_ok else 'FAIL'}")

tts_issues = []
for i, (sec, text) in enumerate(narrations, 1):
    unresolved = planner.unresolved_pronunciations(text)
    if unresolved:
        tts_issues.append((f"s{i:02d}", unresolved))

if tts_issues:
    print(f"TTS unresolved words: {tts_issues}")
else:
    print("All TTS pronunciations: CLEAN")
