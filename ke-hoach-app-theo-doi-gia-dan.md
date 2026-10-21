# Kế hoạch app theo dõi giá đạn Delta Force

Ngày cập nhật: 21/10/2026

## 1. Mục tiêu và phạm vi

Xây dựng app cá nhân theo dõi giá đạn trên DFLoadout, chạy định kỳ khoảng 30 phút ngay cả khi máy cá nhân tắt. App chọn các cơ hội mua rẻ, bán lại trong vòng 24 giờ, ưu tiên lợi nhuận sau phí và mức biến động thấp.

- Nguồn ban đầu: https://dfloadout.gg/cho-dau-gia?category=5&sort=listed-desc
- Theo dõi toàn bộ nhóm đạn để tự lọc ứng viên, thay vì mặc định chọn các món có nhiều hàng đang rao.
- Chỉ phân tích, đưa ra tín hiệu và cảnh báo; người dùng tự quyết định và thực hiện giao dịch.
- Theo xác nhận của chủ app, đạn mua từ chợ trong phiên bản game đang chơi có thể bán lại.
- Không cam kết lợi nhuận hoặc bảo đảm bán được. Chất lượng được đánh giá bằng kết quả theo dõi và giao dịch thực tế.

## 2. Người nhận email và người xem trang web

### Email cảnh báo

- Trong phiên bản đầu, chỉ gửi cảnh báo đến một địa chỉ email của chủ app.
- Chỉ cần địa chỉ nhận thư; không cần mật khẩu Gmail, quyền đọc thư hoặc đăng nhập Google của người nhận.
- Người xem công khai không đăng ký email và không thay đổi địa chỉ nhận thông báo.
- Địa chỉ nhận được lưu trong GitHub Actions Secrets, không đưa vào giao diện hoặc dữ liệu công khai.
- Việc gửi thư vẫn cần một tài khoản hoặc dịch vụ gửi. Phương án dự kiến là Gmail riêng để gửi cảnh báo, dùng mật khẩu ứng dụng lưu trong Secrets; không dùng mật khẩu Gmail chính của chủ app.
- Chỉ gửi khi có tín hiệu mới hoặc thay đổi đáng kể; không lặp lại cùng cảnh báo sau mỗi lần quét.

### Trang xem báo cáo

- Trang web công khai, người dùng bình thường mở link là xem được, không cần đăng nhập.
- Khi mở trang, tải báo cáo đã xuất bản gần nhất; không cần đợi một lượt thu thập mới.
- Việc mở trang không kích hoạt thu thập dữ liệu hoặc gửi email.
- Hiển thị rõ thời điểm chạy phân tích thành công, thời điểm dữ liệu nguồn cập nhật và tình trạng dữ liệu mới/cũ.
- Khi lượt quét mới thất bại, vẫn hiển thị báo cáo thành công gần nhất và cảnh báo dữ liệu cũ.
- Người xem chỉ có quyền xem báo cáo, biểu đồ, bộ lọc và link tham khảo nguồn.
- Giao diện dùng tiếng Việt, đọc được trên điện thoại và máy tính.

## 3. Công nghệ và luồng xử lý

| Thành phần | Công nghệ đề xuất | Vai trò |
| --- | --- | --- |
| Thu thập dữ liệu | Python, Requests, BeautifulSoup | Đọc danh sách, giá, số lượng đang rao và lịch sử có sẵn |
| Chạy định kỳ | GitHub Actions, máy chạy Linux tiêu chuẩn | Chạy khoảng 30 phút/lần khi máy cá nhân tắt |
| Lưu lịch sử | JSON theo ngày | Lưu bền vững giữa các lượt chạy, giữ cửa sổ dữ liệu 30 ngày |
| Phân tích | Python, quy tắc thống kê minh bạch | So sánh giá, xu hướng, biến động và biên lợi nhuận sau phí |
| Giao diện công khai | HTML, CSS, JavaScript trên GitHub Pages | Hiển thị báo cáo gần nhất và biểu đồ |
| Gửi thông báo | Gmail SMTP với tài khoản gửi riêng | Gửi cảnh báo đến email của chủ app |

Luồng xử lý:

1. GitHub Actions tải dữ liệu từ các trang trong nhóm đạn, có giới hạn tốc độ và thử lại có giới hạn khi lỗi tạm thời.
2. Kiểm tra cấu trúc, giá trị, thời gian nguồn cập nhật và mức độ đầy đủ của dữ liệu.
3. Lưu lịch sử hợp lệ, bỏ bản ghi trùng; không ghi đè dữ liệu tốt bằng một lượt thu thập lỗi.
4. Tính chỉ số và tạo báo cáo cùng danh sách tối đa 10 ứng viên đáng xem.
5. Xuất bản báo cáo công khai khi quá trình xử lý thành công.
6. Gửi email nếu có tín hiệu mới đáp ứng điều kiện; lưu trạng thái chống gửi trùng.

Việc gửi email lỗi không được làm mất báo cáo đã tạo. Không đặt thông tin xác thực trong báo cáo, dữ liệu xuất bản hoặc mã chạy trên trình duyệt.

## 4. Nội dung báo cáo và nguyên tắc phân tích

Mỗi ứng viên hiển thị tên đạn, giá rao thấp nhất, lượng đang rao, lịch sử giá, mức biến động, giá hòa vốn sau phí, giá bán mục tiêu tham khảo, biên lợi nhuận dự kiến và lý do được chọn.

- So sánh giá hiện tại với dữ liệu 24 giờ và 7 ngày khi có đủ lịch sử; tận dụng lịch sử công khai của nguồn nếu kiểm tra được tính nhất quán.
- Ưu tiên cơ hội quay vòng trong 24 giờ và xu hướng ổn định; không xem một cú giảm giá là bằng chứng giá chắc chắn phục hồi.
- Phải xác nhận cách tính phí trong game trước khi bật tín hiệu có lợi nhuận ròng. Nếu chưa xác định phí, chỉ hiển thị phân tích giá và thông báo chưa đủ điều kiện tính lãi ròng.
- Phân biệt số lượng đang rao với khối lượng đã bán. Thay đổi lượng rao có thể do mua, hủy hoặc bổ sung hàng; không diễn giải thành số giao dịch thực tế.
- Khi không có dữ liệu giao dịch thành công, ghi rõ chưa xác minh tốc độ bán và nhu cầu thực tế.
- Khi dữ liệu thiếu, cũ hoặc không đạt yêu cầu, hiển thị “chưa đủ cơ sở” hoặc “chưa có cơ hội phù hợp”. Không bắt buộc luôn phải có món nên mua.
- Tín hiệu bán trên báo cáo công khai là đánh giá thị trường. Lãi thực tế của từng người còn phụ thuộc giá vốn, số lượng và phí của họ; phiên bản đầu không quản lý danh mục cá nhân.
- Chưa cần API AI trả phí. Kết quả tính toán phải có thể giải thích và kiểm chứng.

DFLoadout công bố cập nhật giá mỗi giờ. Lượt kiểm tra mỗi 30 phút có thể nhận dữ liệu giống nhau; không tạo tín hiệu mới chỉ vì app vừa chạy lại.

## 5. Bảo mật và chi phí

- Mã nguồn, dữ liệu thị trường và báo cáo dự kiến công khai. Không quảng cáo không có nghĩa là người khác không tìm được.
- Không thu thập hoặc lưu thông tin đăng nhập game, mật khẩu Gmail cá nhân hay nội dung hộp thư của người nhận.
- Lưu địa chỉ gửi, địa chỉ nhận và thông tin xác thực gửi thư trong GitHub Actions Secrets; không commit file chứa bí mật.
- Chỉ bước gửi thư được cấp thông tin xác thực email. Không ghi chúng vào log, thông báo lỗi, artifact hoặc file xuất bản.
- Kiểm soát quyền sửa kho và workflow, kiểm tra các phụ thuộc và cố định phiên bản Actions. Mã độc trong workflow có quyền dùng Secrets vẫn có thể làm lộ thông tin.
- Tài khoản Gmail gửi riêng bật xác minh hai bước và dùng mật khẩu ứng dụng có thể thu hồi. Mật khẩu ứng dụng không phải khóa chỉ có quyền gửi thư.
- Nếu lộ khóa hoặc mật khẩu ứng dụng: thu hồi/thay mới ngay, sau đó xử lý file và lịch sử Git liên quan.
- Trước khi xuất bản, kiểm tra mã, lịch sử Git, log và nội dung trang không chứa địa chỉ email riêng tư hoặc bí mật.

Mục tiêu là vận hành trong gói miễn phí: GitHub Actions với máy chạy tiêu chuẩn trên kho công khai và GitHub Pages. Không cần thuê máy chủ hay mua tên miền riêng. Cần tài khoản GitHub và cấu hình tài khoản gửi thư một lần.

Lịch GitHub Actions có thể trễ hoặc bỏ lượt khi tải cao; không coi đây là hệ thống bắt giá tức thời. Lịch trên kho công khai có thể bị tắt sau 60 ngày không có hoạt động kho. Cần theo dõi trạng thái chạy và dung lượng lưu trữ trong quá trình vận hành.

## 6. Kiểm tra và tiêu chí nghiệm thu

- Lấy đủ các trang trong nhóm đạn; đọc đúng giá, dấu phân cách, mã vật phẩm và thời gian; không nhân đôi dữ liệu.
- Mô phỏng lỗi mạng, trang thay cấu trúc và dữ liệu cũ: giữ báo cáo tốt gần nhất và ngừng cảnh báo mua từ dữ liệu lỗi.
- Mở link trên điện thoại hoặc trình duyệt chưa đăng nhập vẫn xem được báo cáo gần nhất, có thời gian cập nhật và lý do đánh giá.
- Kiểm tra chỉ email của chủ app được cấu hình nhận cảnh báo; người xem trang không thể truy cập địa chỉ nhận, mật khẩu hay chức năng gửi thư.
- Kiểm tra chống gửi trùng và trường hợp gửi mail thất bại nhưng báo cáo vẫn xuất bản được.
- Chạy theo dõi thử 7 ngày; mô phỏng tín hiệu bằng dữ liệu sau thời điểm phát tín hiệu, tính phí. Không dùng dữ liệu tương lai khi tạo tín hiệu trong quá khứ.
- Giá rao chạm mục tiêu chỉ là kết quả mô phỏng, chưa chứng minh giao dịch khớp. Đối chiếu thêm giao dịch thực tế của chủ app: số lượng bán, thời gian bán và lãi ròng.

## 7. Thông tin cần khi triển khai

1. Tài khoản GitHub dùng sở hữu kho mã và xuất bản trang.
2. Địa chỉ email của chủ app để nhận cảnh báo.
3. Tài khoản gửi thư riêng và thông tin xác thực được nhập trực tiếp vào Secrets, không gửi trong mã hoặc tài liệu công khai.
4. Cách tính phí bán đạn trong game để tính hòa vốn và lãi ròng đúng.

## Nguồn tham khảo

- DFLoadout: https://dfloadout.gg/cho-dau-gia?category=5&sort=listed-desc
- GitHub Actions và chi phí: https://docs.github.com/en/actions/concepts/billing-and-usage
- Lịch chạy GitHub Actions: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- GitHub Actions Secrets: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- Mật khẩu ứng dụng Google: https://support.google.com/mail/answer/185833?hl=vi
- Xử lý bí mật đã lộ trên GitHub: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
