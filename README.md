# DFTrader

Theo dõi toàn bộ nhóm đạn Delta Force từ [DFLoadout](https://dfloadout.gg/cho-dau-gia?category=5&sort=listed-desc), so sánh lịch sử giá, xuất báo cáo tiếng Việt và cảnh báo email cho chủ app. Python + GitHub Actions + GitHub Pages, không cần máy cá nhân bật liên tục.

## Chạy trên máy

Yêu cầu Python 3.12+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m dftrader.pipeline
.venv\Scripts\python -m http.server 8765 --directory site
```

Mở `http://localhost:8765`. Mở trang chỉ tải báo cáo đã tạo; không quét nguồn hoặc gửi thư. Chạy kiểm thử với `python -m unittest discover -v`.

## GitHub Actions và Pages

1. Đưa dự án lên nhánh `main` của một kho GitHub công khai.
2. Vào **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Chạy workflow **Market report** từ tab Actions. Workflow cũng chạy khi thay đổi code trên `main` và vào phút 17, 47 mỗi giờ UTC, tương đương phút 17, 47 mỗi giờ Việt Nam.
4. Link công khai: `https://<tài-khoản>.github.io/<tên-kho>/`.

Lịch chạy có thể trễ hoặc bỏ lượt. GitHub có thể tắt lịch ở kho công khai không hoạt động 60 ngày. Kiểm tra Actions khi trang báo dữ liệu cũ. Nếu kho dùng branch protection, cần cho phép bot ghi dữ liệu vào `main` hoặc chuyển lưu trữ sang nhánh dữ liệu; mặc định dự án dùng commit dữ liệu trực tiếp vào `main`.

Workflow chỉ xuất bản thư mục `site/`. Lịch sử 30 ngày nằm ở `history/YYYY-MM-DD.json`. Trạng thái chống gửi trùng nằm trong `state/alerts.json`, chỉ chứa mã vật phẩm và dữ liệu thị trường. Khi quét lỗi, báo cáo thành công gần nhất được giữ, `status.json` cập nhật lỗi, trang vẫn được triển khai và workflow báo thất bại để có thể theo dõi. Lỗi SMTP không chặn xuất bản.

## Xác nhận phí và bật cảnh báo

Hiện `fee.confirmed` là **false**: có phân tích giá nhưng không tính lãi ròng và không gửi cảnh báo mua.

Chỉ sửa `config.json` sau khi đã xác nhận phí đúng trong bản game đang chơi. Mô hình hỗ trợ:

```text
Tiền thu mỗi viên = giá bán × (1 − sale_rate − listing_rate) − fixed_per_unit
Giá hòa vốn = làm tròn lên((giá mua + fixed_per_unit) / (1 − sale_rate − listing_rate))
```

`sale_rate` và `listing_rate` là tỷ lệ thập phân (5% nhập `0.05`), đều tính trên giá bán mục tiêu. `fixed_per_unit` là phí cố định mỗi viên. Giả định rao một lần; không tính phí rao lại, phí theo lô hoặc quy tắc làm tròn phí riêng của game. Nếu phí thực tế không theo mô hình này, cần điều chỉnh công thức trước khi đặt `confirmed: true`.

Vào **Settings → Secrets and variables → Actions → New repository secret** và tạo đúng ba secrets:

| Secret | Nội dung |
| --- | --- |
| `SMTP_USER` | Gmail riêng dùng gửi cảnh báo |
| `SMTP_APP_PASSWORD` | Mật khẩu ứng dụng của Gmail gửi, đã bật xác minh hai bước |
| `ALERT_EMAIL` | Một địa chỉ email duy nhất nhận cảnh báo |

Không đưa các giá trị này vào mã, file cấu hình, issue hoặc chat. Không cần mật khẩu email nhận. Chỉ bước **Notify owner** được truyền secrets vào môi trường tiến trình. Không có chức năng gửi email hoặc sửa người nhận trên trang công khai.

Email chỉ gửi cho tối đa 10 ứng viên đủ điều kiện; lặp lại cùng timestamp bị bỏ qua. Với timestamp mới, chỉ gửi lại nếu giá thay đổi ít nhất 5% hoặc biên lợi nhuận thay đổi ít nhất 2 điểm phần trăm so với lần đã gửi. Chỉ cập nhật chống trùng sau khi SMTP chấp nhận thư. Nếu tiến trình bị dừng sau khi SMTP nhận nhưng trước khi lưu commit trạng thái, thư có thể bị gửi lặp ở lượt sau; SMTP không bảo đảm gửi đúng một lần. Không có secret thì bỏ qua gửi thư, báo cáo vẫn chạy.

## Quy tắc phân tích

- Thu thập tất cả trang, đối chiếu tổng vật phẩm và mã duy nhất. Vật phẩm hết hàng được giữ trong bảng với giá trống, không biến thành giá 0.
- Dùng timestamp nguồn UTC; lịch sử dạng bảng của nguồn được đọc theo UTC+7, đối chiếu giá và lượng đang rao với bản ghi hiện tại. Không nhận nguồn cũ quá 3 giờ hoặc timestamp tương lai.
- Giữ dữ liệu theo ngày trong 30 ngày, bỏ trùng theo mã + timestamp. Lấy điểm cuối trong mỗi giờ để tránh lịch sử nhiều điểm/phút làm lệch trọng số.
- Cần ít nhất 20 điểm giờ và độ dài tối thiểu 20 giờ trong cửa sổ 24 giờ. Trung vị 7 ngày cần ít nhất 120 giờ và độ phủ ít nhất 6 ngày.
- Ứng viên theo dõi: giảm ít nhất 5% so với trung vị 24 giờ, độ lệch chuẩn/giá trung bình không quá 12%, trung vị 6 điểm giờ gần nhất không giảm quá 3% so với 6 điểm giờ đầu cửa sổ, và đang có người rao.
- Mục tiêu là giá nhỏ nhất của trung vị 24 giờ, trung vị 7 ngày khi đủ dữ liệu, và trung vị 6 điểm giờ gần nhất; làm tròn xuống. Cơ hội sau phí còn cần phí đã xác nhận, đủ lịch sử 7 ngày và biên dự kiến ít nhất 5%.
- Điểm xếp hạng = mức giảm % − 0,5 × biến động % + phần âm của xu hướng %. Điểm tối thiểu 0. Tối đa 10 ứng viên, có thể không có ứng viên nào.
- Biến động dùng độ lệch chuẩn của mức giá, không phải độ lệch chuẩn lợi suất. Không có khối lượng khớp lệnh; không suy ra nhu cầu hoặc tốc độ bán từ lượng đang rao.

Ngưỡng cấu hình trong `config.json`. Thay đổi phí không cần sửa mã nếu phù hợp mô hình trên.

## Theo dõi thử 7 ngày

Giữ workflow chạy ít nhất 7 ngày từ lúc triển khai để đánh giá vận hành; lịch sử nguồn có sẵn không thay thế giai đoạn theo dõi này. Sau khi xác nhận phí, chạy:

```powershell
python -m dftrader.backtest --output .local/backtest.json
```

Mô phỏng từng thời điểm chỉ dùng các bản ghi đã xuất hiện lúc đó để tạo tín hiệu. Chỉ dữ liệu sau thời điểm tín hiệu được dùng đánh giá kết quả trong 24 giờ. Mỗi vật phẩm chỉ có một vị thế mô phỏng trong 24 giờ. Kết quả có `target_observed`, `expired`, `pending`; chỉ là giá rao, chưa chứng minh giao dịch khớp. Kết quả hết hạn được định giá theo quan sát cuối trong 24 giờ nếu có dữ liệu đến hạn.

Đối chiếu giao dịch thực của chủ app: giá vốn, lượng bán, phí, thời gian bán, lãi ròng. Bản đầu không lưu danh mục cá nhân trên web.

## Cấu trúc

```text
dftrader/           Thu thập, phân tích, lưu trữ, gửi email, mô phỏng
site/              Trang công khai và báo cáo JSON
history/           Lịch sử JSON theo ngày (30 ngày)
state/             Trạng thái chống gửi trùng, không có email/bí mật
tests/             Kiểm thử hồi quy bằng dữ liệu cố định
.github/workflows/ Thu thập và triển khai mỗi ~30 phút
```

DFTrader là công cụ quan sát độc lập. Không thực hiện giao dịch tự động và không bảo đảm lợi nhuận hoặc thanh khoản.
