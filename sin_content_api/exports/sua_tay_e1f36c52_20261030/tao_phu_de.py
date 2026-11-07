import json, importlib.util, sys
spec = importlib.util.spec_from_file_location("vietsub", "/mnt/baha_smb/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/tao_video_noi_dung/vietsub.py")
vs = importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)

SCRIPT = ("Doanh nghiệp tăng nhân sự, thêm phần mềm, nhưng công việc vẫn chậm, chi phí tăng và doanh thu chưa như kỳ vọng. "
 "Vấn đề đôi khi không nằm ở nhân viên, mà ở cách vận hành. "
 "Khách hỏi sản phẩm nhưng thông tin không đến kịp bộ phận kinh doanh, báo giá đã gửi nhưng không có lịch chăm sóc tiếp theo, khách chờ lâu, cơ hội kinh doanh có thể rơi vào tay đối thủ. "
 "Nhân viên nhập dữ liệu thủ công, phòng ban thiếu kết nối, việc trễ hạn khó được phát hiện, báo cáo ghép từ nhiều nguồn khiến quản lý thiếu thông tin chính xác, khó xác định nguyên nhân doanh thu không đạt mục tiêu, "
 "vấn đề đôi khi không nằm ở nhân viên, mà ở cách vận hành. "
 "Baha khảo sát quy trình để tìm công đoạn gây lãng phí thời gian, chi phí và cơ hội, chuyển đổi số không chỉ là mua thêm phần mềm, mà là thay đổi cách vận hành. "
 "Baha xây dựng hệ thống tự động hóa phù hợp, tiếp nhận yêu cầu, phân tích nhu cầu, lưu thông tin và chuyển đến đúng bộ phận. "
 "Hệ thống nhắc nhân viên khi chưa phản hồi đúng hạn. Hệ thống cảnh báo quản lý khi việc có nguy cơ trễ. "
 "Thông tin hoạt động được tập trung để quản lý theo dõi. Không cần gom báo cáo rời từ từng phòng ban, con người vẫn kiểm soát quyết định quan trọng. "
 "AI hỗ trợ việc lặp lại và cung cấp thông tin kịp thời. Hiệu quả cần được đo bằng thời gian xử lý, phản hồi đúng hạn và cơ hội không bị bỏ sót. "
 "Quản lý theo dõi hoạt động tập trung, nhận cảnh báo sớm. Baha Group cung cấp giải pháp AI cho doanh nghiệp.")

asr = json.load(open("words.json", encoding="utf-8"))["words"]
asr_words = [{"text": w["text"], "start_ms": round(w["start"]*1000), "end_ms": max(round(w["end"]*1000), round(w["start"]*1000)+1)} for w in asr]
aligned = vs.align_script_words(SCRIPT.split(), asr_words)
print("script words", len(SCRIPT.split()), "aligned", len(aligned), file=sys.stderr)

# chia cụm 1 dòng: theo mệnh đề (dấu câu), mệnh đề dài thì chia đều; gộp mệnh đề ngắn
MAXC = 42
def clen(ws): return len(" ".join(x["text"] for x in ws))
clauses, cur = [], []
for w in aligned:
    cur.append(w)
    if w["text"].endswith((",", ";", ".", "!", "?")): clauses.append(cur); cur = []
if cur: clauses.append(cur)
COMPOUND = {tuple(x.split()) for x in ("nhân viên|quản lý|cung cấp|tự động|cơ hội|công đoạn|tập trung|doanh thu|doanh nghiệp|kinh doanh|thời gian|hệ thống|phản hồi|"
    "thông tin|bộ phận|quy trình|chuyển đổi|vận hành|phần mềm|đối thủ|chăm sóc|công việc|nguyên nhân|mục tiêu|phòng ban|kết nối|báo cáo|báo giá|cảnh báo|"
    "kiểm soát|quyết định|quan trọng|xử lý|hiệu quả|giải pháp|lãng phí|chi phí|tiếp nhận|phân tích|nhu cầu|thủ công|dữ liệu|con người|nhân sự|sản phẩm|phát hiện|"
    "chính xác|xác định|đúng hạn|bỏ sót|lặp lại|kịp thời|theo dõi|hoạt động|Baha Group|tiếp theo|chuyển đến|đối tác").replace("|", "\n").split("\n")}
def norm(w): return w["text"].strip(",.;!?").lower()
def is_compound(a, b): return (norm(a), norm(b)) in {(x.lower(), y.lower()) for x, y in COMPOUND}
pieces = []
for cl in clauses:
    n = -(-clen(cl) // MAXC)
    if n <= 1: pieces.append(cl); continue
    total = clen(cl); prev = 0
    for k in range(1, n):
        ideal = total * k / n
        best = min(range(prev + 1, len(cl)), key=lambda i: abs(clen(cl[:i]) - ideal) + (100 if is_compound(cl[i-1], cl[i]) else 0))
        pieces.append(cl[prev:best]); prev = best
    pieces.append(cl[prev:])
chunks = []
for p in pieces:
    if chunks and not chunks[-1][-1]["text"].endswith((".", "!", "?")) and clen(chunks[-1] + p) <= 30: chunks[-1] = chunks[-1] + p
    else: chunks.append(p)

def ts(ms):
    cs = round(ms/10); h, r = divmod(cs, 360000); m, r = divmod(r, 6000); s, c = divmod(r, 100)
    return f"{h}:{m:02}:{s:02}.{c:02}"

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Be Vietnam Pro SemiBold,63,&H0000D7FF,&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,5.7,2.5,2,115,115,86,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
lines = []
for i, ch in enumerate(chunks):
    start = ch[0]["start_ms"]
    end = ch[-1]["end_ms"] + 120
    if i + 1 < len(chunks): end = min(end, chunks[i+1][0]["start_ms"])
    parts = []
    t = start
    for w in ch:
        pre = max(0, w["start_ms"] - t)           # khoảng nghỉ trước từ (giữ nhịp)
        dur = max(1, w["end_ms"] - w["start_ms"])
        parts.append(f"{{\\k{round(pre/10)}}}{{\\k{round(dur/10)}}}{w['text']} " if pre >= 10 else f"{{\\k{round(dur/10)}}}{w['text']} ")
        t = w["end_ms"]
    lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Karaoke,,0,0,0,,{{\\fad(80,60)}}{''.join(parts).strip()}")
open("phu_de_moi.ass", "w", encoding="utf-8-sig").write(head + "\n".join(lines) + "\n")
print(len(chunks), "cum phu de; cuoi:", ts(chunks[-1][-1]["end_ms"]), file=sys.stderr)
for ch in chunks[:6]: print(f"{ch[0]['start_ms']/1000:6.2f} {' '.join(x['text'] for x in ch)}", file=sys.stderr)
