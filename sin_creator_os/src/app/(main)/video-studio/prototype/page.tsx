"use client";

import * as React from "react";
import Link from "next/navigation";
import {
  FileVideo,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Layers,
  ShieldCheck,
  Palette,
  Sliders,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import {
  NhapNoiDung,
  DuLieuNhapNoiDung,
} from "../[projectId]/_components/nhap_noi_dung";
import {
  DuyetPhanCanh,
  KeHoachMẫu,
} from "../[projectId]/_components/duyet_phan_canh";
import {
  TienDoSanXuat,
  TrangThaiSanXuat,
} from "../[projectId]/_components/tien_do_san_xuat";
import { DuyetThanhPham } from "../[projectId]/_components/duyet_thanh_pham";
import { BangPhongCachKenh } from "../[projectId]/_components/bang_phong_cach_kenh";

// Bộ Dữ Liệu Mẫu 60 Giây
const MAU_60_GIAY: KeHoachMẫu = {
  keHoachId: "plan_60s_demo_01",
  revision: 1,
  tongThoiLuongGiay: 60,
  tongFrame: 1800,
  fps: 30,
  tyLeKhungHinh: "9:16",
  styleSnapshotHash: "sha256:7f8e3d2a1b9c4f5e6a0b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f",
  uocTinhChiPhi: "$0.45 USD (Hạn ngạch đã cấp)",
  danhSachCanh: [
    {
      canhId: "c01",
      thuTu: 1,
      tieuDe: "Hook Mở Đầu",
      loaiCanh: "HOOK",
      thoiGianBatDau: 0,
      thoiGianKetThuc: 3,
      loiThoai: "Đừng nhầm Chatbot và AI Agent: Một bên chỉ trả lời, một bên trực tiếp hành động.",
      chuManHinh: "CHATBOT VS AI AGENT: KHÁC BIỆT THỰC SỰ LÀ GÌ?",
      shots: [
        {
          shotId: "s01",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 3,
          soFrame: 90,
          promptKyThuat: "Văn bản chữ động sắc nét tương phản cao trên nền xanh đen #0f172a, chuyển động kinetic typography nhịp nhanh.",
          promptPhuDinh: "không có logo giả, không có nhân vật hoạt họa, không hiệu ứng nhòe",
          tuLieuNguon: "Đồ họa vector SVG nội bộ BAHA",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c02",
      thuTu: 2,
      tieuDe: "Bản Chất Chatbot",
      loaiCanh: "DIAGRAM",
      thoiGianBatDau: 3,
      thoiGianKetThuc: 15,
      loiThoai: "Chatbot thông thường chỉ xử lý ngôn ngữ và đưa ra câu trả lời dựa trên ngữ cảnh tức thời trong ô chat.",
      chuManHinh: "Chatbot: Phản hồi 1 lần (Single-turn QA)",
      shots: [
        {
          shotId: "s02",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Sơ đồ luồng dữ liệu 2 chiều đơn giản giữa người dùng và ô chat, đường nối phát sáng nhã nhặn theo bảng màu BAHA.",
          promptPhuDinh: "không có chữ tiếng Anh sai chính tả, không rối mắt",
          tuLieuNguon: "Sơ đồ giải thích chuẩn BAHA",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c03",
      thuTu: 3,
      tieuDe: "Bản Chất AI Agent",
      loaiCanh: "SCREEN_RECORDING",
      thoiGianBatDau: 15,
      thoiGianKetThuc: 43,
      loiThoai: "AI Agent sở hữu bộ nhớ dài hạn, công cụ API bên ngoài và khả năng tự lập kế hoạch nhiều bước để hoàn thành mục tiêu.",
      chuManHinh: "AI Agent: Lập kế hoạch + Gọi công cụ + Bộ nhớ",
      shots: [
        {
          shotId: "s03a",
          loaiShot: "SCREEN_RECORDING",
          thoiLuongGiay: 14,
          soFrame: 420,
          promptKyThuat: "Quay màn hình thao tác công cụ tự động hóa gọi API trích xuất dữ liệu, khung hình crop 9:16 căn giữa.",
          promptPhuDinh: "không làm sai lệch giao diện thực tế",
          tuLieuNguon: "Tư liệu quay màn hình công cụ BAHA Agent OS",
          trangThaiTuLieu: "CHO_RECORDING",
        },
        {
          shotId: "s03b",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 14,
          soFrame: 420,
          promptKyThuat: "Sơ đồ vòng lặp ReAct: Suy nghĩ &rarr; Hành động &rarr; Quan sát kết quả.",
          promptPhuDinh: "không sinh chữ giả trong video",
          tuLieuNguon: "Sơ đồ luồng thuật toán BAHA",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c04",
      thuTu: 4,
      tieuDe: "Ứng Dụng Doanh Nghiệp",
      loaiCanh: "TEXT_MOTION",
      thoiGianBatDau: 43,
      thoiGianKetThuc: 55,
      loiThoai: "Trong doanh nghiệp, Agent tự động phân loại đơn hàng, trích xuất hóa đơn và gửi email xác nhận mà không cần con người trực tiếp thao tác.",
      chuManHinh: "Ứng Dụng: Tự Động Hóa Quy Trình Doanh Nghiệp",
      shots: [
        {
          shotId: "s04",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Đồ họa motion infographics hiển thị 3 chỉ số tự động hóa: Tốc độ x5, Tiết kiệm 70% thời gian, Độ chính xác 99.4%.",
          promptPhuDinh: "không hứa hẹn số liệu vô căn cứ",
          tuLieuNguon: "Infographics BAHA",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c05",
      thuTu: 5,
      tieuDe: "Brand Outro BAHA (O1)",
      loaiCanh: "BRAND_OUTRO",
      thoiGianBatDau: 55,
      thoiGianKetThuc: 60,
      loiThoai: "BAHA Group — Cung cấp giải pháp AI toàn diện.",
      chuManHinh: "BAHA GROUP &bull; GIẢI PHÁP AI TOÀN DIỆN",
      shots: [
        {
          shotId: "s05",
          loaiShot: "BRAND_OUTRO",
          thoiLuongGiay: 5,
          soFrame: 150,
          promptKyThuat: "Khung hình Outro nhận diện thương hiệu BAHA O1: Logo logo.png căn giữa, chuyển động tỏa sáng nhẹ, chữ slogan tiếng Việt chuẩn.",
          promptPhuDinh: "không lệch tỉ lệ logo, không đổi màu",
          tuLieuNguon: "Asset public/logo.png (822 KB)",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
  ],
};

// Bộ Dữ Liệu Mẫu 120 Giây (Bắt Buộc Nghiệm Thu)
const MAU_120_GIAY: KeHoachMẫu = {
  keHoachId: "plan_120s_rag_ft_01",
  revision: 1,
  tongThoiLuongGiay: 120,
  tongFrame: 3600,
  fps: 30,
  tyLeKhungHinh: "9:16",
  styleSnapshotHash: "sha256:7f8e3d2a1b9c4f5e6a0b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f",
  uocTinhChiPhi: "$0.85 USD (Hạn ngạch đã cấp)",
  danhSachCanh: [
    {
      canhId: "c01",
      thuTu: 1,
      tieuDe: "Hook Trực Diện",
      loaiCanh: "HOOK",
      thoiGianBatDau: 0,
      thoiGianKetThuc: 3,
      loiThoai: "Nhiều doanh nghiệp tốn tiền tỷ huấn luyện lại mô hình mà không biết RAG có thể giải quyết 80% bài toán.",
      chuManHinh: "RAG HAY FINE-TUNING? SAI LẦM HÀNG TỶ ĐỒNG CỦA DOANH NGHIỆP",
      shots: [
        {
          shotId: "s01",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 3,
          soFrame: 90,
          promptKyThuat: "Văn bản chữ động kinetic typography nhấn mạnh 'Tốn tiền tỷ' vs 'RAG 80%', phông chữ Arial chuẩn dấu tiếng Việt.",
          promptPhuDinh: "không có hiệu ứng giật lag, không che mép safe zone",
          tuLieuNguon: "Đồ họa vector SVG",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c02",
      thuTu: 2,
      tieuDe: "Bản Chất Của RAG",
      loaiCanh: "DIAGRAM",
      thoiGianBatDau: 3,
      thoiGianKetThuc: 13,
      loiThoai: "Bản chất RAG là cơ chế tìm kiếm và cấp ngữ cảnh tri thức nội bộ cho mô hình ngôn ngữ lớn tại thời điểm thực.",
      chuManHinh: "RAG = Retrieval + Augmented + Generation",
      shots: [
        {
          shotId: "s02",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 10,
          soFrame: 300,
          promptKyThuat: "Sơ đồ kiến trúc 3 bước: Tài liệu PDF &rarr; Vector Database &rarr; Đưa vào Prompt của LLM.",
          promptPhuDinh: "không có logo lạ, không có hình ảnh nhiễu",
          tuLieuNguon: "Sơ đồ Vector DB BAHA",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c03",
      thuTu: 3,
      tieuDe: "Bản Chất Của Fine-Tuning",
      loaiCanh: "DIAGRAM",
      thoiGianBatDau: 13,
      thoiGianKetThuc: 23,
      loiThoai: "Fine-tuning là quá trình cập nhật trực tiếp các trọng số mạng nơ-ron bằng tập dữ liệu huấn luyện chuyên ngành sâu.",
      chuManHinh: "Fine-Tuning: Thay đổi trọng số nơ-ron (Weights Update)",
      shots: [
        {
          shotId: "s03",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 10,
          soFrame: 300,
          promptKyThuat: "Sơ đồ mạng nơ-ron đa tầng với các liên kết phát sáng đổi màu khi nạp bộ dữ liệu huấn luyện domain.",
          promptPhuDinh: "không vẽ sai cấu trúc toán học",
          tuLieuNguon: "Đồ họa thuật toán AI BAHA",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c04",
      thuTu: 4,
      tieuDe: "So Sánh Khả Năng Cập Nhật Dữ Liệu",
      loaiCanh: "TEXT_MOTION",
      thoiGianBatDau: 23,
      thoiGianKetThuc: 35,
      loiThoai: "RAG thắng thế ở khả năng cập nhật tài liệu tức thì và trích dẫn chính xác nguồn dữ liệu kiểm chứng.",
      chuManHinh: "Cập nhật tài liệu: RAG mất 1 giây &bull; FT mất hàng tuần",
      shots: [
        {
          shotId: "s04",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Bảng so sánh 2 cột: Cập nhật tài liệu (RAG tức thì / FT cần train lại); Độ tin cậy (RAG có trích dẫn nguồn / FT có thể bịa đặt).",
          promptPhuDinh: "không viết tắt khó hiểu",
          tuLieuNguon: "Bảng đối chiếu BAHA",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c05",
      thuTu: 5,
      tieuDe: "Demo Tra Cứu Tài Liệu Thật",
      loaiCanh: "SCREEN_RECORDING",
      thoiGianBatDau: 35,
      thoiGianKetThuc: 47,
      loiThoai: "Thao tác thực tế: Tìm kiếm chính sách nhân sự nội bộ qua hệ thống Vector Database và LLM.",
      chuManHinh: "Thao Tác Thực Tế: Tra Cứu Quy Chế Nội Bộ",
      shots: [
        {
          shotId: "s05",
          loaiShot: "SCREEN_RECORDING",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Quay màn hình tìm kiếm tài liệu trên phần mềm quản trị nội bộ BAHA, hiển thị đoạn trích dẫn đúng trang tài liệu gốc.",
          promptPhuDinh: "không làm mờ thông tin quan trọng",
          tuLieuNguon: "Video quay màn hình hệ thống BAHA",
          trangThaiTuLieu: "CHO_RECORDING",
        },
      ],
    },
    {
      canhId: "c06",
      thuTu: 6,
      tieuDe: "Kiểm Soát Ranh Giới Dữ Liệu",
      loaiCanh: "SCREEN_RECORDING",
      thoiGianBatDau: 47,
      thoiGianKetThuc: 59,
      loiThoai: "Luồng kiểm soát thông tin: Hệ thống từ chối trả lời nếu tài liệu nội bộ không chứa dữ liệu được xác thực.",
      chuManHinh: "Chống Bịa Đặt: Từ Chối Trả Lời Khi Thiếu Căn Cứ",
      shots: [
        {
          shotId: "s06",
          loaiShot: "SCREEN_RECORDING",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Màn hình hiển thị câu hỏi không có trong dữ liệu nội bộ và AI phản hồi lịch sự 'Không có căn cứ trong tài liệu'.",
          promptPhuDinh: "không tạo ảo giác AI",
          tuLieuNguon: "Video kiểm thử BAHA Guardrails",
          trangThaiTuLieu: "CHO_RECORDING",
        },
      ],
    },
    {
      canhId: "c07",
      thuTu: 7,
      tieuDe: "Kiến Trúc Phân Quyền Doanh Nghiệp",
      loaiCanh: "DIAGRAM",
      thoiGianBatDau: 59,
      thoiGianKetThuc: 71,
      loiThoai: "Kiến trúc dữ liệu doanh nghiệp: Phân quyền truy cập tài liệu và cô lập đa khách thuê chặt chẽ.",
      chuManHinh: "Bảo Mật Cấp Doanh Nghiệp: Phân Quyền Đa Tầng",
      shots: [
        {
          shotId: "s07",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Sơ đồ phân quyền 3 tầng: Nhân viên thường &rarr; Quản lý &rarr; Lãnh đạo, các rào chắn truy cập dữ liệu bảo mật.",
          promptPhuDinh: "không sinh sơ đồ rác",
          tuLieuNguon: "Kiến trúc bảo mật BAHA-AUTHZ",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c08",
      thuTu: 8,
      tieuDe: "Bối Cảnh Ứng Dụng Thực Tiễn",
      loaiCanh: "AI_VIDEO",
      thoiGianBatDau: 71,
      thoiGianKetThuc: 83,
      loiThoai: "Minh họa bối cảnh vận hành hiện đại: Nhân sự tiết kiệm 70% thời gian tra cứu thủ tục nghiệp vụ hàng ngày.",
      chuManHinh: "Hiệu Quả Thực Tế: Giảm 70% Thời Gian Tra Cứu",
      shots: [
        {
          shotId: "s08",
          loaiShot: "AI_VIDEO",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Không gian làm việc văn phòng công nghệ hiện đại, đội ngũ nhân sự sử dụng tablet tương tác nhanh chóng, ánh sáng tự nhiên dịu mát.",
          promptPhuDinh: "không có logo giả mạo, không có khuôn mặt dị dạng, không biến dạng tay chân",
          tuLieuNguon: "Flow AI Video Adapter (Prompt chuẩn hóa có receipt)",
          trangThaiTuLieu: "CHO_FLOW",
        },
      ],
    },
    {
      canhId: "c09",
      thuTu: 9,
      tieuDe: "Khi Nào Bắt Buộc Dùng Fine-Tuning?",
      loaiCanh: "DIAGRAM",
      thoiGianBatDau: 83,
      thoiGianKetThuc: 95,
      loiThoai: "Khi nào bắt buộc dùng Fine-tuning? Khi cần mô hình học phong cách giao tiếp riêng hoặc kiến thức y khoa, pháp lý đặc thù.",
      chuManHinh: "Khi Nào Cần Fine-Tuning? Giọng Điệu & Miền Tri Thức Sâu",
      shots: [
        {
          shotId: "s09",
          loaiShot: "DIAGRAM",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Sơ đồ radar đánh giá 4 tiêu chí: Phong cách phản hồi, Thuật ngữ chuyên sâu, Định dạng đầu ra nghiêm ngặt.",
          promptPhuDinh: "không rối rắm, đúng bảng màu chuẩn",
          tuLieuNguon: "Sơ đồ radar BAHA",
          trangThaiTuLieu: "DO_HOA_SVG",
        },
      ],
    },
    {
      canhId: "c10",
      thuTu: 10,
      tieuDe: "So Sánh Chi Phí Triển Khai",
      loaiCanh: "TEXT_MOTION",
      thoiGianBatDau: 95,
      thoiGianKetThuc: 107,
      loiThoai: "Chi phí so sánh: RAG triển khai trong vài ngày với chi phí thấp; Fine-tuning đòi hỏi hạ tầng GPU và chuyên gia dữ liệu.",
      chuManHinh: "Chi Phí & Thời Gian: RAG 3-5 ngày &bull; Fine-Tuning vài tháng",
      shots: [
        {
          shotId: "s10",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 12,
          soFrame: 360,
          promptKyThuat: "Biểu đồ so sánh thời gian và chi phí đầu tư giữa RAG và Fine-Tuning, số liệu rõ ràng minh bạch.",
          promptPhuDinh: "không dùng hiệu ứng hoạt họa rẻ tiền",
          tuLieuNguon: "Biểu đồ so sánh ROI",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c11",
      thuTu: 11,
      tieuDe: "Giải Pháp Kết Hợp Hybrid",
      loaiCanh: "TEXT_MOTION",
      thoiGianBatDau: 107,
      thoiGianKetThuc: 115,
      loiThoai: "Mô hình kết hợp tối ưu: Dùng Fine-tuning để định hình phong cách phản hồi và RAG để cung cấp tri thức thời gian thực.",
      chuManHinh: "Giải Pháp Toàn Diện: RAG + Fine-Tuning Hybrid",
      shots: [
        {
          shotId: "s11",
          loaiShot: "TEXT_MOTION",
          thoiLuongGiay: 8,
          soFrame: 240,
          promptKyThuat: "Đồ họa 2 mảnh ghép RAG và Fine-tuning lồng vào nhau tạo thành khối giải pháp hoàn chỉnh.",
          promptPhuDinh: "không lòe loẹt",
          tuLieuNguon: "Đồ họa hybrid BAHA",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
    {
      canhId: "c12",
      thuTu: 12,
      tieuDe: "Brand Outro BAHA (O1 / O3)",
      loaiCanh: "BRAND_OUTRO",
      thoiGianBatDau: 115,
      thoiGianKetThuc: 120,
      loiThoai: "BAHA Group — Cung cấp giải pháp AI toàn diện. Liên hệ ngay để đánh giá bài toán của bạn.",
      chuManHinh: "BAHA GROUP &bull; CUNG CẤP GIẢI PHÁP AI TOÀN DIỆN",
      shots: [
        {
          shotId: "s12",
          loaiShot: "BRAND_OUTRO",
          thoiLuongGiay: 5,
          soFrame: 150,
          promptKyThuat: "Khung hình Outro thương hiệu BAHA O3: Logo logo.png + Slogan 'Cung cấp giải pháp AI toàn diện' + Lời mời trải nghiệm giải pháp doanh nghiệp.",
          promptPhuDinh: "không sai lệch tỉ lệ nhận diện",
          tuLieuNguon: "Asset public/logo.png (822 KB)",
          trangThaiTuLieu: "SAN_SANG",
        },
      ],
    },
  ],
};

export default function VideoCreatorPrototypePage() {
  const [buocHienTai, setBuocHienTai] = React.useState<"NHAP_NOI_DUNG" | "DUYET_CANH" | "TIEN_DO" | "DUYET_THANH_PHAM">("NHAP_NOI_DUNG");
  const [activeTab, setActiveTab] = React.useState<"quy_trinh" | "phong_cach">("quy_trinh");
  const [keHoachHienTai, setKeHoachHienTai] = React.useState<KeHoachMẫu>(MAU_120_GIAY);
  const [runId, setRunId] = React.useState<string>("run_20261023_g1_sample");
  const [trangThaiSanXuat, setTrangThaiSanXuat] = React.useState<TrangThaiSanXuat>("DANG_SAN_XUAT");

  const handleChonMau = (loai: "60s" | "120s") => {
    if (loai === "60s") {
      setKeHoachHienTai(MAU_60_GIAY);
    } else {
      setKeHoachHienTai(MAU_120_GIAY);
    }
  };

  const handleTiepTucNhapNoiDung = (data: DuLieuNhapNoiDung) => {
    if (data.thoiLuongGiay === 60) {
      setKeHoachHienTai(MAU_60_GIAY);
    } else {
      setKeHoachHienTai(MAU_120_GIAY);
    }
    setBuocHienTai("DUYET_CANH");
  };

  const handleDuyetKeHoach = (keHoachMoi: KeHoachMẫu) => {
    setKeHoachHienTai(keHoachMoi);
    setRunId(`run_${Date.now().toString(36)}`);
    setTrangThaiSanXuat("DANG_SAN_XUAT");
    setBuocHienTai("TIEN_DO");
  };

  const handleHoanThanhSanXuat = () => {
    setBuocHienTai("DUYET_THANH_PHAM");
  };

  const handleSuaMotCanh = (canhId: string, promptMoi: string) => {
    setKeHoachHienTai((prev) => ({
      ...prev,
      revision: prev.revision + 1,
      danhSachCanh: prev.danhSachCanh.map((c) => {
        if (c.canhId !== canhId) return c;
        return {
          ...c,
          shots: c.shots.map((s, i) => (i === 0 ? { ...s, promptKyThuat: promptMoi } : s)),
        };
      }),
    }));
  };

  const handleLamMoi = () => {
    setBuocHienTai("NHAP_NOI_DUNG");
  };

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 py-6 px-4">
      {/* Header Điều Hướng Của Bộ Tạo Video */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-xs uppercase tracking-wider text-primary bg-primary/10 px-2 py-0.5 rounded">
              Bản 2.0 &bull; Prototype Cổng G1
            </span>
            <Badge variant="outline" className="text-xs font-mono">
              Harness + LLM + Flow
            </Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            Bộ Tạo Video Hoàn Chỉnh Từ Nội Dung (Technology Explainer OS)
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quy trình sản xuất nội bộ BAHA: Nhập nội dung & thời lượng &rarr; LLM lập kịch bản &rarr; Khóa phong cách &rarr; Tạo tư liệu &rarr; FFmpeg Native render.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
            <TabsList>
              <TabsTrigger value="quy_trinh" className="text-xs">
                Quy Trình Tạo Video
              </TabsTrigger>
              <TabsTrigger value="phong_cach" className="text-xs">
                Phong Cách Kênh Đã Khóa
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </header>

      {/* Điều Hướng 4 Bước Quy Trình */}
      {activeTab === "quy_trinh" && (
        <div className="grid grid-cols-4 gap-2 text-xs font-medium border-b pb-3">
          {[
            { id: "NHAP_NOI_DUNG", label: "1. Nhập Nội Dung & Kênh" },
            { id: "DUYET_CANH", label: "2. Duyệt Storyboard & Prompt" },
            { id: "TIEN_DO", label: "3. Theo Dõi Sản Xuất (DAG)" },
            { id: "DUYET_THANH_PHAM", label: "4. QC & Tải Gói Video" },
          ].map((s) => {
            const isCurrent = buocHienTai === s.id;
            return (
              <div
                key={s.id}
                onClick={() => setBuocHienTai(s.id as any)}
                className={`p-2.5 rounded-lg border text-center cursor-pointer transition-colors ${
                  isCurrent
                    ? "bg-primary text-primary-foreground border-primary font-bold shadow-sm"
                    : "bg-card text-muted-foreground hover:bg-muted/40"
                }`}
              >
                {s.label}
              </div>
            );
          })}
        </div>
      )}

      {/* Nội Dung Theo Tab */}
      {activeTab === "phong_cach" ? (
        <BangPhongCachKenh />
      ) : (
        <>
          {buocHienTai === "NHAP_NOI_DUNG" && (
            <NhapNoiDung
              initialData={{
                noiDung:
                  keHoachHienTai.tongThoiLuongGiay === 60
                    ? "Phân biệt Chatbot và AI Agent: Chatbot chỉ đưa ra phản hồi bằng văn bản dựa trên câu hỏi trực tiếp, trong khi AI Agent sở hữu bộ nhớ, công cụ API bên ngoài và tự lập kế hoạch nhiều bước để giải quyết bài toán phức tạp cho doanh nghiệp."
                    : "So sánh kiến trúc RAG (Retrieval-Augmented Generation) và Fine-tuning trong ứng dụng doanh nghiệp: RAG giúp truy xuất tri thức nội bộ tức thì với chi phí thấp và trích dẫn rõ nguồn gốc, trong khi Fine-tuning cập nhật trọng số nơ-ron cho các bài toán đòi hỏi giọng điệu chuyên sâu hoặc miền tri thức hẹp.",
                thoiLuongGiay: keHoachHienTai.tongThoiLuongGiay,
                cheDoNoiDung: "BIEN_SOAN",
              }}
              onTiepTuc={handleTiepTucNhapNoiDung}
              onChonMau={handleChonMau}
            />
          )}

          {buocHienTai === "DUYET_CANH" && (
            <DuyetPhanCanh
              keHoach={keHoachHienTai}
              onDuyetKeHoach={handleDuyetKeHoach}
              onQuayLai={() => setBuocHienTai("NHAP_NOI_DUNG")}
            />
          )}

          {buocHienTai === "TIEN_DO" && (
            <TienDoSanXuat
              runId={runId}
              trangThaiHienTai={trangThaiSanXuat}
              onHoanThanh={handleHoanThanhSanXuat}
              onThuLai={() => setTrangThaiSanXuat("DANG_SAN_XUAT")}
              onHuy={() => setBuocHienTai("DUYET_CANH")}
            />
          )}

          {buocHienTai === "DUYET_THANH_PHAM" && (
            <DuyetThanhPham
              runId={runId}
              tongThoiLuongGiay={keHoachHienTai.tongThoiLuongGiay}
              onSuaMotCanh={handleSuaMotCanh}
              onLamMoi={handleLamMoi}
            />
          )}
        </>
      )}
    </main>
  );
}
