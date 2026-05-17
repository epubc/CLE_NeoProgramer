# ChipList Editor for NeoProgrammer

GUI editor và công cụ giải mã / mã hóa `chiplist.dat` dùng cho **NeoProgrammer / CH341A**.

Chương trình cho phép:

- Mở và chỉnh sửa database chip của NeoProgrammer
- Giải mã `chiplist.dat` → XML
- Mã hóa XML → `chiplist.dat`
- Thêm / sửa / xóa chip
- Tìm kiếm chip theo hãng hoặc tên
- Hiển thị sơ đồ adapter CH341A tương ứng
- Xây dựng lại database tùy chỉnh cho NeoProgrammer

---

## Screenshot

*(Thêm ảnh giao diện tại đây)*
![Giao diện chính đơn giản.](https://github.com/epubc/CLE_NeoProgramer/blob/main/main.jpg)
![Edit thông tin.](https://github.com/epubc/CLE_NeoProgramer/blob/main/edit.jpg)
```text
GUI
 ├── Category
 │    ├── Manufacturer
 │    │      └── Chip
 │
 ├── Chip information
 │
 └── Adapter image preview
```

---

# Features

## 1. Open NeoProgrammer DAT Database

Mở trực tiếp file:

```text
chiplist.dat
```

Chương trình tự động:

```text
DAT
 ↓
RC4 decrypt
 ↓
zlib decompress
 ↓
XML
 ↓
GUI editor
```

Menu:

```text
File → Open DAT...
```

---

## 2. Export XML

Xuất database sang XML để chỉnh sửa thủ công:

```text
File → Save as XML...
```

Ví dụ:

```xml
<chiplist>
    <SPI_NOR>
        <Winbond>
            <W25Q128
                size="16777216"
                page="256"
                id="EF4018"/>
        </Winbond>
    </SPI_NOR>
</chiplist>
```

---

## 3. Build DAT Again

Sau khi chỉnh sửa XML:

```text
XML
 ↓
Compress
 ↓
RC4 encrypt
 ↓
chiplist.dat
```

Menu:

```text
File → Save as DAT...
```

Database tạo ra có thể dùng lại với NeoProgrammer.

---

## 4. Chip Database Editor

Cho phép:

### Add chip

```text
Edit → Add Chip
```

Nhập:

- Chip name
- Manufacturer
- Size
- Page
- ID
- Voltage
- Adapter
- Comment

---

### Edit chip

Double click chip trong TreeView:

```text
Double Click → Edit
```

Có thể sửa:

- Tên chip
- Manufacturer
- Memory size
- ID
- Adapter
- Metadata

---

### Delete chip

```text
Edit → Delete Chip
```

---

## 5. Search Engine

Tìm kiếm theo:

- Chip name

Ví dụ:

```text
W25Q128
GD25
MX25
```

- Manufacturer

Ví dụ:

```text
Winbond
MXIC
GigaDevice
```

---

## 6. Adapter Preview System

Khi chọn chip, chương trình tự hiển thị sơ đồ adapter tương ứng.

Ví dụ:

### SPI 1.8V

```text
SPI_1.8v_Adapter.jpg
```

### I2C 1.8V

```text
I2C_1.8v_Adapter.jpg
```

### AVR

```text
scheme_AVRISP.jpg
```

Hoặc mapping adapter:

```text
adap93C
   → scheme_93Cxx.jpg

adapM35080
   → scheme_M35080.jpg

adapKB90
   → scheme_KB901x.jpg
```

Ảnh được load từ:

```text
Adapters/
   CH341/
```

---

# Supported Categories

Mặc định hỗ trợ:

```text
SPI_NOR
SPI_NAND
I2C
AVR
```

---

## SPI NOR fields

```text
size
page
id
vcc
adapt

secreg0
secreg1
secreg2
secreg3

vmod
```

---

## SPI NAND fields

```text
besize
spare
dies
planes
```

---

## AVR fields

```text
pageep
sizeeep
```

---

# Reverse Engineering Notes

NeoProgrammer sử dụng:

- SHA1
- Base64
- RC4 variant
- zlib compression

Format:

```text
chiplist.dat

HEADER
 ├── size (4 bytes)
 └── reserved (4 bytes)

Compressed XML

Encrypted by Neo RC4
```

Tool triển khai lại toàn bộ pipeline:

```text
decrypt:

DAT
 ↓
RC4
 ↓
zlib
 ↓
XML

encrypt:

XML
 ↓
zlib
 ↓
RC4
 ↓
DAT
```

---

# Requirements

```bash
pip install pillow
```

Python:

```text
Python 3.9+
```

Modules:

```text
tkinter
Pillow
hashlib
base64
zlib
ElementTree
```

---

# Run

```bash
python CLE_NeoProgramer3.py
```

---

# Use Cases

- Thêm chip mới chưa có trong NeoProgrammer
- Reverse engineering `chiplist.dat`
- Chỉnh sửa database CH341A
- Tạo database tùy chỉnh
- Xem sơ đồ adapter
- Build lại database NeoProgrammer

---

# Disclaimer

Project phục vụ mục đích nghiên cứu cấu trúc database NeoProgrammer và chỉnh sửa dữ liệu chip. Không liên kết với NeoProgrammer.
