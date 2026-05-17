import hashlib
import base64
import struct
import zlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import xml.etree.ElementTree as ET
import os
import re
from PIL import Image, ImageTk

# ============== Phần mã hóa/giải mã (Đã sửa lỗi Chunked RC4) ==============
def rc4_neo_crypt(data: bytes, key: bytes, chunk_size: int = None) -> bytes:
    """Thuật toán RC4 đặc biệt của NeoProgrammer: i, j reset mỗi chunk"""
    # Khởi tạo S-box
    s = list(range(256))
    j = 0
    key_len = len(key)
    for i in range(256):
        j = (j + s[i] + key[i % key_len]) & 0xFF
        s[i], s[j] = s[j], s[i]
    
    # Xử lý dữ liệu
    out = bytearray()
    # Nếu không có chunk_size (dùng cho password), coi như 1 chunk duy nhất
    c_size = chunk_size if chunk_size else len(data)
    
    for offset in range(0, len(data), c_size):
        chunk = data[offset : offset + c_size]
        curr_i = curr_j = 0 # ĐIỂM QUAN TRỌNG: i, j reset về 0 mỗi chunk
        for b in chunk:
            curr_i = (curr_i + 1) & 0xFF
            curr_j = (curr_j + s[curr_i]) & 0xFF
            s[curr_i], s[curr_j] = s[curr_j], s[curr_i]
            out.append(b ^ s[(s[curr_i] + s[curr_j]) & 0xFF])
    return bytes(out)

def build_password() -> str:
    parts = ["vd7", "SQP", "RBs", "HgX", "0bv", "pii", "sn8", "z1J", "92Z", "7xA", "eex", "MEW", "ulI", "wdX"]
    return "".join(s[1:3] for s in parts)

def derive_real_password() -> bytes:
    obf = base64.b64decode(build_password().encode("ascii"))
    unwrap_key = hashlib.sha1(b"chiplist.dat").digest()
    # Password không dùng chunking (hoặc chunk_size = len(data))
    return rc4_neo_crypt(obf, unwrap_key)

def encrypt_chiplist(xml_data: bytes) -> bytes:
    key = hashlib.sha1(derive_real_password()).digest()
    # Header: Size (4 bytes) + Reserved (4 bytes)
    plain = struct.pack("<II", len(xml_data), 0) + zlib.compress(xml_data)
    return rc4_neo_crypt(plain, key, chunk_size=0x2000)

def decrypt_chiplist(raw: bytes) -> bytes:
    if len(raw) < 8: raise ValueError("Data too short")
    key = hashlib.sha1(derive_real_password()).digest()
    dec = rc4_neo_crypt(raw, key, chunk_size=0x2000)
    
    unpacked_size, reserved = struct.unpack_from("<II", dec, 0)
    # Giải nén từ byte thứ 8 trở đi
    return zlib.decompress(dec[8:])

# ============== Phần GUI (Giữ nguyên cấu trúc tối ưu) ==============
class ChipEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ChipList Editor - NeoProgrammer Database")
        self.center_window(self.root, 780, 750)
        self.current_file, self.xml_root, self.search_var = None, None, tk.StringVar()
        self.setup_menu()
        self.setup_main_layout()
        self.new_file()
    
    def center_window(self, win, w, h):
        """Hàm bổ trợ để đưa cửa sổ ra giữa màn hình"""
        ws = win.winfo_screenwidth()
        hs = win.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
    
    def setup_menu(self):
        m = tk.Menu(self.root)
        self.root.config(menu=m)
        f = tk.Menu(m, tearoff=0)
        m.add_cascade(label="File", menu=f)
        f.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        f.add_command(label="Open XML...", command=self.open_xml, accelerator="Ctrl+O")
        f.add_command(label="Open DAT...", command=self.open_dat, accelerator="Ctrl+Shift+O")
        f.add_separator()
        f.add_command(label="Save as XML...", command=self.save_as_xml, accelerator="Ctrl+S")
        f.add_command(label="Save as DAT...", command=self.save_as_dat, accelerator="Ctrl+Shift+S")
        f.add_separator()
        f.add_command(label="Exit", command=self.root.quit)

        e = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Edit", menu=e)
        e.add_command(label="Add Chip...", command=self.add_chip, accelerator="Insert")
        e.add_command(label="Delete Chip", command=self.delete_chip, accelerator="Delete")
        
        self.root.bind("<Control-n>", lambda event: self.new_file())
        self.root.bind("<Control-o>", lambda event: self.open_xml())
        self.root.bind("<Control-s>", lambda event: self.save_as_xml())
        self.root.bind("<Control-S>", lambda event: self.save_as_dat())
        self.root.bind("<Insert>", lambda event: self.add_chip())
        self.root.bind("<Delete>", lambda event: self.delete_chip())

    def setup_main_layout(self):
        p = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        p.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left = ttk.Frame(p)
        p.add(left, weight=1)
        sf = ttk.Frame(left)
        sf.pack(fill=tk.X, pady=5)
        self.search_var.trace_add('write', lambda *a: self.update_tree())
        ttk.Entry(sf, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.tree = ttk.Treeview(left, show="tree", columns=("path",))
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_chip())
        
        right = ttk.Frame(p)
        p.add(right, weight=2)

        # Chia khung bên phải làm 2 phần: trên là chữ, dưới là ảnh
        self.details_text = tk.Text(right, wrap=tk.WORD, font=("Consolas", 10), height=12)
        self.details_text.pack(fill=tk.X, side=tk.TOP)

        # Khung chứa ảnh
        self.img_label = ttk.Label(right, text="No Adapter Image", anchor=tk.CENTER)
        self.img_label.pack(fill=tk.BOTH, expand=True, pady=5)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def is_element_node(self, elem):
        return isinstance(elem, ET.Element) and elem.tag != 'Comment'

    def new_file(self):
        self.xml_root = ET.Element("chiplist")
        for cat in ["SPI_NOR", "SPI_NAND", "I2C", "AVR"]: ET.SubElement(self.xml_root, cat)
        self.current_file = None
        self.update_tree()

    def update_tree(self):
        self.tree.delete(*self.tree.get_children())
        kw = self.search_var.get().lower()
        if self.xml_root is None: return

        for cat in self.xml_root:
            if not self.is_element_node(cat): continue
            cat_node = None
            for manu in cat:
                if not self.is_element_node(manu): continue
                manu_node = None
                for chip in manu:
                    if not self.is_element_node(chip): continue
                    # Hiển thị: bỏ dấu gạch dưới nếu nó là ký tự đầu tiên
                    display_name = chip.tag[1:] if chip.tag.startswith("_") else chip.tag
                    if kw and kw not in display_name.lower() and kw not in manu.tag.lower(): continue
                    
                    if cat_node is None: cat_node = self.tree.insert("", "end", text=f"[{cat.tag}]", open=True)
                    if manu_node is None: manu_node = self.tree.insert(cat_node, "end", text=manu.tag, open=True)
                    
                    size = chip.get("size", "")
                    if size.isdigit():
                        sz = int(size)
                        size = f" ({sz/1024:.0f}KB)" if sz < 1048576 else f" ({sz/1048576:.0f}MB)"
                    
                    path = f"{cat.tag}|{manu.tag}|{chip.tag}"
                    self.tree.insert(manu_node, "end", text=f"{display_name}{size}", values=(path,), tags=("chip",))
        self.update_status()
        
    def update_status(self):
        count = sum(len([c for c in manu if self.is_element_node(c)]) 
                   for cat in self.xml_root if self.is_element_node(cat) 
                   for manu in cat if self.is_element_node(manu))
        self.status_var.set(f"Total Chips: {count} | {os.path.basename(self.current_file or 'New File')}")

    def _get_chip_elements(self, path):
        c_tag, m_tag, ch_tag = path.split('|')
        cat_el = next(c for c in self.xml_root if c.tag == c_tag)
        manu_el = next(m for m in cat_el if m.tag == m_tag)
        chip_el = next(ch for ch in manu_el if ch.tag == ch_tag)
        return cat_el, manu_el, chip_el

    def on_tree_select(self, event):
        item = self.tree.selection()
        if not item or "chip" not in self.tree.item(item[0], "tags"): return
        path = self.tree.item(item[0], "values")[0]

        # Lấy thông tin category, manufacturer và chip element
        cat_tag, manu, _ = path.split('|')
        _, _, chip_el = self._get_chip_elements(path)

        # 1. Hiển thị thông tin text
        self.details_text.delete(1.0, tk.END)
        res = f"Category: {cat_tag}\nManufacturer: {manu}\nChip: {chip_el.tag}\n" + "-"*30 + "\n"
        res += "\n".join(f"{k:10}: {v}" for k, v in chip_el.attrib.items())
        self.details_text.insert(tk.END, res)

        # 2. Xử lý hiển thị ảnh theo logic yêu cầu
        self.process_adapter_logic(cat_tag, chip_el)

    def process_adapter_logic(self, category, chip_el):
        vcc = chip_el.get("vcc", "")
        adapt = chip_el.get("adapt", "")
        img_name = None

        # --- QUY TẮC ƯU TIÊN ---

        # 3. Đối với category là AVR -> luôn hiện scheme_AVRISP.jpg
        if category == "AVR":
            img_name = "scheme_AVRISP.jpg"

        # 1. SPI_xx và VCC 1.8
        elif category.startswith("SPI") and vcc == "1.8":
            img_name = "SPI_1.8v_Adapter.jpg"

        # 2. I2C_xx và VCC 1.8
        elif category.startswith("I2C") and vcc == "1.8":
            img_name = "I2C_1.8v_Adapter.jpg"

        # --- QUY TẮC THEO BẢNG MAPPING (Dựa trên tham số adapt) ---
        else:
            mapping = {
                "adapTC8912": "scheme_TC8912x.jpg", # Ưu tiên theo tên cụ thể
                "adap59C": "scheme_ER59xx.jpg",
                "adapN76E": "scheme_N76Exx.jpg",
                "adapKB90": "scheme_KB901x.jpg",
                "adapM35080": "scheme_M35080.jpg",
                "adapI2CM34": "scheme_I2C_M34E0x.jpg",
                "adapI2C": "scheme_I2C.jpg",
                "adapCT1C": "scheme_CT1C08.jpg",
                "adapBR90": "scheme_BR90xx.jpg",
                "adap93S": "scheme_93Sxx.jpg",
                "adap93C": "scheme_93Cxx.jpg",
                "adap93Cx5": "scheme_93Cx5.jpg"
            }

            if adapt in mapping:
                img_name = mapping[adapt]
            elif adapt.startswith("adap"):
                # Mặc định nếu không nằm trong mapping nhưng có tiền tố adap
                # Ví dụ: adapSPI45 -> scheme_SPI45.jpg
                suffix = adapt.replace("adap", "")
                img_name = f"scheme_{suffix}.jpg"

        # Gọi hàm hiển thị ảnh lên giao diện
        self.show_image(img_name)

    def show_image(self, img_file):
        """Hàm thực thi việc load ảnh và vẽ lên Label"""
        if not img_file:
            self.img_label.config(image='', text="No specific adapter required")
            return

        # Đường dẫn: .../Adapters/CH341/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, "Adapters", "CH341", img_file)

        if os.path.exists(path):
            try:
                img = Image.open(path)
                # Resize ảnh cho phù hợp với khung (ví dụ rộng tối đa 450px)
                w_max = 450
                ratio = w_max / float(img.size[0])
                h_size = int(float(img.size[1]) * float(ratio))
                img = img.resize((w_max, h_size), Image.Resampling.LANCZOS)

                photo = ImageTk.PhotoImage(img)
                self.img_label.config(image=photo, text="")
                self.img_label.image = photo # Quan trọng: giữ reference
            except Exception as e:
                self.img_label.config(image='', text=f"Error loading: {img_file}")
        else:
            self.img_label.config(image='', text=f"Missing image: {img_file}")

    def _show_chip_form(self, cat_tag, manu_tag="", chip_el=None):
        dialog = tk.Toplevel(self.root)
        is_edit = chip_el is not None  # Kiểm tra rõ ràng

        if is_edit:
            dialog.title("Edit Chip Info")
        else:
            dialog.title("Add New Chip")

        self.center_window(dialog, 350, 550)

        # Đợi dialog được tạo xong mới grab
        dialog.update_idletasks()
        dialog.grab_set()

        # Danh sách field cần hiển thị
        fields = ["Name", "Manufacturer", "page", "size", "id", "vcc", "adapt", "comment"]
        if cat_tag == "SPI_NAND":
            fields += ["besize", "spare", "dies", "planes"]
        elif cat_tag == "SPI_NOR":
            fields += ["secreg0", "secreg1", "secreg2", "secreg3", "vmod"]
        elif cat_tag == "AVR":
            fields += ["pageep", "sizeeep"]

        entries = {}

        # Tạo các widget nhập liệu
        for i, f in enumerate(fields):
            ttk.Label(dialog, text=f"{f}:").grid(row=i, column=0, padx=10, pady=5, sticky="w")
            en = ttk.Entry(dialog, width=35)
            en.grid(row=i, column=1, padx=10, pady=5)
            entries[f.lower()] = en

            # Điền dữ liệu nếu đang edit
            if is_edit:
                if f == "Name":
                    # Bỏ dấu _ ở đầu nếu có (khi hiển thị)
                    display_name = chip_el.tag
                    if display_name.startswith("_"):
                        display_name = display_name[1:]
                    en.insert(0, display_name)
                elif f == "Manufacturer":
                    en.insert(0, manu_tag)
                else:
                    # Lấy giá trị từ attrib, nếu không có thì để trống
                    val = chip_el.get(f.lower(), "")
                    en.insert(0, val)
            elif f == "Manufacturer":
                # Nếu thêm mới và có manufacturer mặc định
                if manu_tag:
                    en.insert(0, manu_tag)

        def save():
            nonlocal chip_el
            # Lấy tên chip và xử lý
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning("Warning", "Chip name cannot be empty!")
                return

            name = name.replace(" ", "_")
            # Nếu tên bắt đầu bằng số, tự động thêm dấu "_" ở đầu
            if name and name[0].isdigit():
                name = "_" + name

            # Lấy manufacturer
            manu = entries['manufacturer'].get().strip()
            if not manu:
                messagebox.showwarning("Warning", "Manufacturer cannot be empty!")
                return
            manu = manu.replace(" ", "_")

            # Tìm category element
            cat_el = None
            for c in self.xml_root:
                if c.tag == cat_tag:
                    cat_el = c
                    break

            if cat_el is None:
                messagebox.showerror("Error", f"Category '{cat_tag}' not found!")
                return

            # Xử lý lưu chip (thêm mới hoặc cập nhật)
            if is_edit:
                # Edit mode: cập nhật chip hiện có
                # Nếu manufacturer thay đổi, cần di chuyển chip
                if manu != manu_tag:
                    # Tìm manufacturer cũ và xóa chip khỏi đó
                    old_manu_el = None
                    for m in cat_el:
                        if m.tag == manu_tag:
                            old_manu_el = m
                            break
                    if old_manu_el:
                        old_manu_el.remove(chip_el)
                        # Xóa manufacturer nếu không còn chip nào
                        if len(old_manu_el) == 0:
                            cat_el.remove(old_manu_el)

                    # Tìm hoặc tạo manufacturer mới
                    new_manu_el = None
                    for m in cat_el:
                        if m.tag == manu:
                            new_manu_el = m
                            break
                    if new_manu_el is None:
                        new_manu_el = ET.SubElement(cat_el, manu)
                    new_manu_el.append(chip_el)

                # Cập nhật tên chip
                chip_el.tag = name
            else:
                # Add mode: tạo chip mới
                # Tìm hoặc tạo manufacturer
                manu_el = None
                for m in cat_el:
                    if m.tag == manu:
                        manu_el = m
                        break
                if manu_el is None:
                    manu_el = ET.SubElement(cat_el, manu)

                # Tạo chip mới
                chip_el = ET.SubElement(manu_el, name)

            # Cập nhật các attributes
            skip_fields = ["name", "manufacturer"]
            for f in fields:
                field_name = f.lower()
                if field_name in skip_fields:
                    continue

                val = entries[field_name].get().strip()
                if val:
                    chip_el.set(field_name, val)
                else:
                    # Xóa attribute nếu tồn tại và giá trị rỗng
                    if field_name in chip_el.attrib:
                        del chip_el.attrib[field_name]

            self.update_tree()
            dialog.destroy()

        # Nút Save và Cancel
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)

        # Đảm bảo dialog ở trên cùng
        dialog.transient(self.root)
        dialog.focus_force()

    def add_chip(self):
        # Lấy danh sách tên các Category hiện có trong XML
        cats = [c.tag for c in self.xml_root if self.is_element_node(c)]
        if not cats:
            messagebox.showerror("Error", "No categories found in the database!")
            return

        # Tạo cửa sổ phụ để chọn Category
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Category")
        self.center_window(dialog, 300, 150)
        dialog.grab_set()  # Khóa cửa sổ chính cho đến khi chọn xong
        dialog.resizable(False, False)

        ttk.Label(dialog, text="Choose a category:").pack(pady=10)

        # Menu thả xuống chứa danh sách category
        cat_var = tk.StringVar()
        combo = ttk.Combobox(dialog, textvariable=cat_var, values=cats, state="readonly")
        combo.pack(padx=20, fill=tk.X)
        combo.current(0) # Mặc định chọn cái đầu tiên

        def on_next():
            selected_cat = cat_var.get()
            dialog.destroy()
            self._show_chip_form(selected_cat) # Gọi form nhập liệu với category đã chọn

        ttk.Button(dialog, text="Next", command=on_next).pack(pady=10)

    def edit_chip(self):
        item = self.tree.selection()
        if item and "chip" in self.tree.item(item[0], "tags"):
            path = self.tree.item(item[0], "values")[0]
            parts = path.split('|')
            if len(parts) == 3:
                cat_tag = parts[0]
                manu_tag = parts[1]
                chip_tag = parts[2]
                _, _, chip_el = self._get_chip_elements(path)
                self._show_chip_form(cat_tag, manu_tag, chip_el)

    def delete_chip(self):
        item = self.tree.selection()
        if item and "chip" in self.tree.item(item[0], "tags"):
            path = self.tree.item(item[0], "values")[0]
            if messagebox.askyesno("Confirm", f"Delete {path.split('|')[-1]}?"):
                cat_el, manu_el, chip_el = self._get_chip_elements(path)
                manu_el.remove(chip_el)
                if len(manu_el) == 0: cat_el.remove(manu_el)
                self.update_tree()

    def open_xml(self):
        path = filedialog.askopenfilename(filetypes=[("XML Files", "*.xml")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                # Tối ưu: Tự động thêm dấu _ vào trước các thẻ bắt đầu bằng số để tránh lỗi parse
                content = re.sub(r'<(/?)([0-9])', r'<\1_\2', f.read())
            self.xml_root = ET.fromstring(content)
            self.current_file = path
            self.update_tree()

    def open_dat(self):
        path = filedialog.askopenfilename(filetypes=[("DAT Files", "*.dat")])
        if path:
            try:
                with open(path, "rb") as f:
                    raw_data = decrypt_chiplist(f.read()).decode("utf-8")
                    # Tối ưu: Xử lý thẻ số tương tự như open_xml
                    content = re.sub(r'<(/?)([0-9])', r'<\1_\2', raw_data)
                self.xml_root = ET.fromstring(content)
                self.current_file = path
                self.update_tree()
            except Exception as e:
                messagebox.showerror("Decryption Error", f"Failed to decrypt: {e}")

    def get_formatted_xml(self):
        """Tạo XML có Header/Comment chuẩn và tự động sửa thẻ bắt đầu bằng số"""
        header = '<?xml version="1.0" encoding="utf-8"?>'
        comment = """<!---
  size - memory chip data size in bytes (Decimal)
  page - memory chip page size in bytes and in WORD for ATmega AVR (Decimal).
         For SST AAI Word programm - SSTW.
         For SST AAI Byte programm - SSTB.
  pageep  - ATmega Eeprom page size in bytes (Decimal)
  sizeeep - ATmega Eeprom memory size in bytes (Decimal)
  id     - Memory chip identifier (HEX).
  vcc    - voltage (1.8, 3.3, 5.0) for information only, (3.3 default if absent)
  dies   - number of dies (for large spi flash over 256Mo)
  planes - number of planes (for some SPI NAND)
  script - script file name from scripts folder
  besize - block erase size in kbytes with opcode $D8 (SPI NOR/NAND)
  adapt  - adapter (adapKB90, adapI2C, adapI2CM34, adapSPI45, adap93C, adap93S, adap59C, adapM35080, adapCT1C)
  comment- Any comment
  otpsize- OTP size (EON)
  secreg0, secreg1, secreg2, secreg3 - Security registers size (winbond/gigadevice)
  Vmod    - Vmod3.3v, Vmod5.0v
 -->"""
        lines = [header, comment, "<chiplist>"]
        for cat in self.xml_root:
            if not self.is_element_node(cat): continue
            lines.append(f"  <{cat.tag}>")
            for manu in cat:
                if not self.is_element_node(manu): continue
                lines.append(f"    <{manu.tag}>")
                for chip in manu:
                    if not self.is_element_node(chip): continue
                    # Đảm bảo tên chip không bắt đầu bằng số khi lưu
                    tag = "_" + chip.tag if chip.tag[0].isdigit() else chip.tag
                    attrs = " ".join([f'{k}="{v}"' for k, v in chip.attrib.items()])
                    lines.append(f"      <{tag} {attrs}/>")
                lines.append(f"    </{manu.tag}>")
            lines.append(f"  </{cat.tag}>")
        lines.append("</chiplist>")
        return "\n".join(lines).encode("utf-8")
    
    def save_as_xml(self):
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML Files", "*.xml")])
        if path:
            try:
                formatted_data = self.get_formatted_xml()
                with open(path, "wb") as f:
                    f.write(formatted_data)
                messagebox.showinfo("Success", "XML saved with standard Header.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save XML: {e}")

    def save_as_dat(self):
        path = filedialog.asksaveasfilename(defaultextension=".dat", filetypes=[("DAT Files", "*.dat")])
        if path:
            try:
                xml_data = self.get_formatted_xml() # Lấy dữ liệu đã format chuẩn
                with open(path, "wb") as f:
                    f.write(encrypt_chiplist(xml_data))
                messagebox.showinfo("Success", "DAT saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save DAT: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChipEditor(root)
    root.mainloop()
