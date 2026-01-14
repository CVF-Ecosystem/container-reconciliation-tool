# USER GUIDE - Cong Cu Doi Soat Ton Bai V5.7

## Muc Luc
1. [Tong Quan](#1-tong-quan)
2. [Logic Doi Soat](#2-logic-doi-soat)
3. [Cau Truc Thu Muc](#3-cau-truc-thu-muc)
4. [Huong Dan Su Dung](#4-huong-dan-su-dung)
5. [Batch Mode - Xu Ly Nhieu Ngay](#5-batch-mode---xu-ly-nhieu-ngay)
6. [Xuat Bao Cao Theo Hang Tau](#6-xuat-bao-cao-theo-hang-tau)
7. [So Sanh File App vs TOS](#7-so-sanh-file-app-vs-tos) ⭐ MOI V5.4
8. [Web Dashboard](#8-web-dashboard) ⭐ MOI
9. [Cau Hinh Email](#9-cau-hinh-email) ⭐ MOI
10. [Cac Bao Cao Output](#10-cac-bao-cao-output)
11. [Xu Ly Su Co](#11-xu-ly-su-co)

---

## 1. Tong Quan

### Muc dich
Cong cu doi soat ton kho container tu dong:
- So sanh Ton Cu (8H) vs Ton Moi (15H)
- Xac dinh nguon goc bien dong
- Phat hien container bat thuong

### Cac cai tien V5.7 (Moi nhat) ⭐
- **Kiem tra Tinh Lien Tuc**: Tu dong phat hien thieu slot trong chuoi thoi gian
- **Canh bao Trung Lap Database**: Phat hien khi import du lieu da ton tai
- **Xu ly Cuoi Tuan Thong Minh**: Tu dong nhan dien 15H Thu 6 → 8H Thu 2 la hop le
- **Canh bao TON CU Khong Khop**: So sanh TON MOI slot N voi TON CU slot N+1
- **Dialog Canh Bao Chi Tiet**: Hien thi tong hop tat ca van de truoc khi xu ly
- **Thoi Gian Xu Ly**: Hien thi thoi gian chay doi soat khi hoan tat
- **RESTOW = SHIFTING**: Nhan dien file RESTOW.xlsx tuong duong SHIFTING.xlsx (Shifting Tau: Tau-Bai-Tau)
- **Canh bao Conflict**: Phat hien neu co ca 2 file RESTOW va SHIFTING trong cung slot

### Cac cai tien V5.6
- **VLC Grouping**: VLC chuyen sang nhom VIMC Lines (VMC, SVM, VLC). Vinaline chi con VNL.
- **Gate-Only Filter**: File BIEN DONG trong `7_Email_Templates` chi chua Gate In/Out, loai bo nhap/xuat tau va shifting.
- **Vosco COC Summary**: Sheet `Vosco_COC_Only` trong Movement Summary chi tinh container VOC (loai tru SOC/SVC).
- **Stacking/Incoming Sheets**: File TON BAI co sheet rieng cho container Stacking (chua vao bai) va Incoming (dang cho).
- **Raw Data Enrichment**: Bo sung thong tin thoi gian tu raw gate data vao file xuat.
- **Excel Formatting Fix**: Ho tro ca xlsxwriter va openpyxl engines.
- **Open Latest Report**: Nut "Mo Bao Cao" mo folder moi nhat theo thoi gian tao.

### Cac cai tien V5.4
- **Web Dashboard**: Giao dien web truc quan de xem bao cao.
- **So sanh File App vs TOS**: Doi chieu file xuat tu App voi TOS Cang.
- **Full Column Mapping**: 100% cot duoc map (BIEN DONG 49 cot, TON BAI 46 cot).
- **Cau hinh Email**: Tuy chinh email gui bao cao de dang qua `email_config.json`.
- **Translation hoàn chinh**: Ho tro song ngu Viet-Anh day du.

### Cac cai tien V5.2
- **Time Slots (8H/15H)**: Ho tro xu ly nhieu lan trong ngay
  - Half-day: `8H N7.1 - 15H N7.1` -> slot 15H ngay 7/1
  - Full-day: `8H N7.1 - 8H N8.1` -> nguyen ngay 8/1
- **Auto-detect mode**: Tu dong nhan dien half-day hoac full-day
- **Mix format warning**: Canh bao khi co ca full-day va half-day cung ngay
- **Logic don gian hoa**: Loai bo cac sheet trung lap
- **Xu ly CFS**: Nhan dien container Dong/Rut hang
- **Calendar picker**: Chon ngay bang lich
- **Subfolder support**: Ho tro dat file trong thu muc con

---


## 2. Logic Doi Soat

### 2.1 So do Logic Chinh

```
TON MOI (thuc te)
    |
    +-- KHOP voi ly thuyet ---------> 2. TON_BAI_CHUAN.xlsx
    |
    +-- KHONG khop
    |       |
    |       +-- Chi sai vi tri -----> 4. DAO_CHUYEN_NOI_BAI.xlsx
    |       |
    +-- Sai thong tin ------> 3. CHENH_LECH.xlsx (Sai_Thong_Tin)
    |
    +-- KHONG co trong ly thuyet
            |
            +-- Co Gate OUT + IN, doi F/E --> 3. CHENH_LECH.xlsx (Bien_Dong_FE_CFS)
            |                                  (Container CFS: Dong/Rut hang)
            |
            +-- Con lai ---------------> 3. CHENH_LECH.xlsx (Ton_Chua_Co_Lenh)

LY THUYET co, thuc te KHONG co -----> 3. CHENH_LECH.xlsx (Co_Lenh_Chua_Ve)

XUAT TAU nhung van ton bai ---------> 3. CHENH_LECH.xlsx (Xuat_Tau_Van_Ton_LOI)
                                       ** LOI NGHIEM TRONG **
```

### 2.2 Giai thich Thuat ngu

| Thuat ngu | Y nghia |
|-----------|---------|
| **Ton ly thuyet** | = Ton Cu + Nhap (Gate In, Tau) - Xuat (Gate Out, Tau) |
| **Ton thuc te** | = File TON MOI |
| **Khop** | Container co trong ca ly thuyet va thuc te |
| **CFS** | Container Floor Storage - Dong/Rut hang trong kho |
| **F/E** | Full/Empty - Trang thai container day/rong |

### 2.3 Container CFS (Dong/Rut hang)

Container CFS la truong hop dac biet:
- Co **Gate OUT** (ra khoi bai de dong/rut hang)
- Co **Gate IN** (vao lai bai sau khi dong/rut)
- **Doi F/E**: E → F (dong hang) hoac F → E (rut hang)
- **Van ton bai** - khong phai "ton chua co lenh"

---

## 3. Cau Truc Thu Muc

### 3.1 Cau truc co ban
```
Check list Ton Bai V5.1/
+-- data_input/                <- Du lieu dau vao
+-- data_output/               <- Ket qua & DB lich su
+-- logs/                      <- Log chi tiet
+-- core/batch_processor.py    <- Module batch nhieu ngay
+-- app_gui.py                 <- Chay GUI
+-- app.py                     <- Web Dashboard (Streamlit)
+-- export_data.py             <- Tool trich xuat du lieu
+-- email_config.json          <- File cau hinh email ⭐ MOI
```

### 3.2 Cau truc data_input - Ho tro 3 cach

**Cach 1: File truc tiep (co ngay trong ten)**
```
data_input/
├── TON CU N7.1.2026.xlsx
├── TON MOI N7.1.2026.xlsx
├── GATE IN OUT 8H-15H N7.1.2026.xlsx
└── ...
```

**Cach 2: Subfolder theo ngay (file co ngay)**
```
data_input/
├── N7.1.2026/
│   ├── TON CU N7.1.2026.xlsx
│   └── TON MOI N7.1.2026.xlsx
├── N8.1.2026/
│   └── ...
```

**Cach 3: Subfolder theo ngay (file KHONG can ngay)** ⭐ MOI
```
data_input/
├── N7.1.2026/
│   ├── TON CU.xlsx           <- Khong can ngay trong ten!
│   ├── TON MOI.xlsx
│   └── GATE IN OUT.xlsx
├── N8.1.2026/
│   └── ...
```

**Cach 4: Subfolder voi Time Slots (V5.2) ⭐ MOI**
```
data_input/
├── 8H N7.1 - 15H N7.1/        <- Slot 15H ngay 7/1
│   ├── TON CU.xlsx
│   ├── TON MOI.xlsx
│   └── GATE IN OUT.xlsx
├── 15H N7.1 - 8H N8.1/        <- Slot 8H ngay 8/1
│   ├── TON CU.xlsx
│   └── TON MOI.xlsx
└── 8H N7.1 - 8H N8.1/         <- Full-day ngay 8/1
    ├── TON CU.xlsx
    └── TON MOI.xlsx
```

**Luu y**:
- He thong se tu dong nhan dien ngay va slot tu ten folder
- **QUAN TRONG**: Dung DONG NHAT mot format (hoac full-day hoac half-day)
- Neu mix format, he thong se hien canh bao "Mix Format Detected"

### 3.3 Quy Tac Dat Ten File (V5.2)

#### Tu khoa bat buoc trong ten file

| Loai file | Tu khoa chap nhan | Vi du |
|-----------|-------------------|-------|
| **Ton cu** | `TON CU`, `TON CŨ`, `BASELINE` | `TON CU.xlsx`, `TON CU N10.1.2026.xlsx` |
| **Ton moi** | `TON MOI`, `TỒN MỚI`, `CURRENT` | `TON MOI.xlsx`, `TON MOI N12.1.xlsx` |
| **Gate** | `GATE` | `GATE.xlsx`, `GATE IN OUT 8H-15H.xlsx` |
| **Nhap xuat tau** | `NHAPXUAT`, `NHAP XUAT` | `NHAPXUAT.xlsx`, `LIST NHAP XUAT.xlsx` |
| **Shifting** | `SHIFTING` | `SHIFTING.xlsx`, `LIST SHIFTING.xlsx` |

#### Logic xac dinh ngay

```
1. Folder co ngay? → Dung DateSlot tu folder cho TAT CA files ben trong
2. Khong? → Lay DateSlot tu ten file
3. Van khong co? → ⚠️ BO QUA file + hien canh bao
```

| Truong hop | Folder | File | Ket qua |
|------------|--------|------|---------|
| ✅ Folder co ngay | `8H N10.1 - 8H N12.1/` | `TON CU.xlsx` | Ngay 12/01 (tu folder) |
| ✅ File co ngay | `ABC/` hoac truc tiep | `TON CU N10.1.2026.xlsx` | Ngay 10/01 (tu file) |
| ❌ Khong co ngay | `ABC/` | `TON CU.xlsx` | BO QUA + Warning |

#### Format ngay ho tro

| Dinh dang folder | Ket qua |
|------------------|---------|
| `8H N7.1 - 15H N7.1` | Half-day: Slot 15H ngay 7/1 |
| `15H N7.1 - 8H N8.1` | Half-day: Slot 8H ngay 8/1 |
| `8H N7.1 - 8H N8.1` | Full-day: Ngay 8/1 (cung gio = full-day) |
| `N8.1.2026` | Full-day: Ngay 8/1/2026 |

**Luu y ve RANGE folder (vi du: 8H N10.1 - 8H N12.1):**
- Day la 1 KY doi soat (tu 10/1 den 12/1)
- TON CU = Ton dau ky (ngay 10)
- TON MOI = Ton cuoi ky (ngay 12)
- Bien dong = TONG tat ca thay doi trong ky
- Output folder = Ngay ket thuc (12/01)

---

## 4. Huong Dan Su Dung

### Buoc 1: Chuan bi du lieu
Dat cac file Excel vao `data_input/` theo 1 trong 3 cach o tren.

**Cac file can thiet:**
- `TON CU.xlsx` hoac `TON CU N7.1.2026.xlsx`
- `TON MOI.xlsx` hoac `TON MOI N7.1.2026.xlsx`
- `GATE.xlsx` hoac `GATE IN OUT 8H-15H N7.1.2026.xlsx`
- `NHAPXUAT.xlsx` hoac `NHAP XUAT N7.1.2026.xlsx`

### Buoc 2: Chay ung dung

#### Cach 1: GUI - Don ngay
1. Mo `app_gui.py`
2. Nhan "Run Reconciliation"
3. Doi ket qua

#### Cach 2: Batch Mode - Nhieu ngay
1. Dat file nhieu ngay vao data_input
2. Nhan "Batch Mode"
3. Xem danh sach ngay, chon ngay can xu ly
4. Nhan "Chay Batch"

#### Cach 3: Web Dashboard (Mới)
1. Chạy lệnh `streamlit run app.py` hoac mo file bat neu co.
2. Truy cap `http://localhost:8501` tren trinh duyet.

### Buoc 3: Xem ket qua
- Ket qua luu tai `data_output/Report_N{DD}.{MM}.{YYYY}_{HH}h{MM}/`
- Vi du: `Report_N12.01.2026_14h30/`

---

## 5. Batch Mode - Xu Ly Nhieu Ngay

### 5.1 Muc dich
Xu ly doi soat cho nhieu ngay lien tuc chi voi 1 lan click.

### 5.2 Logic
```
TON MOI ngay N = TON CU ngay N+1
```

Vi du:
- Ngay 7.1: TON CU (7.1) + Bien dong → TON MOI (7.1)
- Ngay 8.1: TON MOI (7.1) lam TON CU + Bien dong → TON MOI (8.1)

### 5.3 Cach dung
1. Dat cac file theo ten hoac trong subfolder:
   - `TON CU N7.1.2026.xlsx`, `TON MOI N7.1.2026.xlsx`
   - Hoac: `N7.1.2026/TON CU.xlsx`, `N7.1.2026/TON MOI.xlsx`
2. Mo GUI → Click "Batch Mode"
3. He thong se:
   - Tu dong nhan dien ngay tu ten file hoac folder
   - Nhom file theo ngay
   - Kiem tra TON MOI N = TON CU N+1
4. Chon ngay → Click "Chay Batch"

### 5.4 Dinh dang ngay ho tro
| Dinh dang | Vi du |
|-----------|-------|
| N{d}.{m}.{yyyy} | N7.1.2026, N07.01.2026 |
| {d}-{m}-{yyyy} | 7-1-2026, 07-01-2026 |
| {d}_{m}_{yyyy} | 7_1_2026, 07_01_2026 |
| {yyyy}-{mm}-{dd} | 2026-01-07 |
| {yyyymmdd} | 20260107 |

### 5.5 Dinh dang Time Slots (V5.2) ⭐ MOI

| Dinh dang Folder | Ket qua |
|------------------|--------|
| `8H N7.1 - 15H N7.1` | Slot 15H ngay 7/1 |
| `15H N7.1 - 8H N8.1` | Slot 8H ngay 8/1 |
| `8H N7.1 - 8H N8.1` | Full-day ngay 8/1 |
| `2 - BDTB DEN 8H N7.1 - 15H N7.1` | Slot 15H ngay 7/1 |

**Logic:**
- Cung gio, khac ngay (8H-8H) = Full-day
- Khac gio (8H-15H hoac 15H-8H) = Half-day voi slot = gio ket thuc

### 5.6 Canh bao Mix Format

He thong se hien canh bao neu phat hien:
- Cung 1 ngay co CA full-day VA half-day
- Vi du: `07/01/2026` va `07/01/2026 (15H)` cung xuat hien

**Khac phuc**: Dung DONG NHAT mot format cho tat ca.

### 5.5 Canh bao khi quet data_input
He thong se hien canh bao neu:
- **Khong co ngay**: File/folder khong co ngay de nhan dien → Bo qua
- **Khong nhan dang duoc loai file**: File co ngay nhung khong phai TON CU, TON MOI, GATE...

### 5.6 Kiem tra Tinh Lien Tuc (V5.5) ⭐ MOI

Khi xu ly batch nhieu ngay/slots, he thong se tu dong kiem tra:

#### Logic Nghiep Vu
```
Bao cao 8H:  Bien dong tu 15H hom truoc → 8H hom nay
Bao cao 15H: Bien dong tu 8H → 15H cung ngay

Vi du:
  09.01 (15H) → 10.01 (8H) → 10.01 (15H) → 12.01 (8H)
              ↑ qua dem      ↑ cung ngay    ↑ qua weekend (OK)
```

#### Cac loai canh bao

| Loai canh bao | Mo ta | Xu ly |
|---------------|-------|-------|
| **⚠️ THIEU DU LIEU LIEN TUC** | Thieu slot giua 2 ngay (vd: thieu 13.01) | Kiem tra lai data_input |
| **⚠️ TRUNG LAP DATABASE** | Slot da co trong database, import se ghi de | Xac nhan tiep tuc hoac huy |
| **⚠️ THIEU TON CU** | Slot khong co file TON CU | He thong dung TON MOI slot truoc |
| **❌ TON CU KHONG KHOP** | TON CU slot N+1 khac TON MOI slot N | Kiem tra file TON CU |

#### Logic xu ly cuoi tuan
He thong tu dong nhan dien ngay nghi:
- **15H Thu 6 → 8H Thu 2**: Hop le (qua T7, CN)
- **8H Thu 6 → 8H Thu 2**: Hop le (full-day qua weekend)

Vi du:
```
09/01 (Thu 6) 15H → 12/01 (Thu 2) 8H  ✅ Hop le
09/01 (Thu 6) 15H → 13/01 (Thu 3) 8H  ⚠️ Thieu 12/01
```

#### Man hinh canh bao

Khi phat hien van de, he thong hien dialog:
```
═══ THIEU DU LIEU LIEN TUC ═══
⚠️ Tu 12/01/2026 (15H) → 14/01/2026 (8H): Thieu 1 ngay du lieu

═══ DU LIEU DA TON TAI TRONG DATABASE ═══
⚠️ 09/01/2026 (8H): Da co 1500 container
→ Import moi se GHI DE du lieu cu!

═══ KIEM TRA TINH LIEN TUC TON CU/TON MOI ═══
✅ 09/01 (15H) → 10/01 (8H): KHOP (99.5%)
⚠️ 10/01 (8H) → 10/01 (15H): THIEU TON CU
   → Se dung TON MOI cua 10/01 (8H) lam TON CU

📋 Giai thich logic:
• Bao cao 8H: Bien dong tu 15H hom truoc → 8H hom nay
• Bao cao 15H: Bien dong tu 8H → 15H cung ngay
• Cuoi tuan: 8H Thu 6 → 8H Thu 2 la hop le

Ban co muon tiep tuc xu ly?
```

---

## 6. Xuat Bao Cao Theo Hang Tau

### 6.1 Muc dich
Xuat danh sach container cu the cho tung hang tau, loc theo thoi gian (ca sang/chieu/ca ngay).

### 6.2 Cach su dung
1. Sau khi chay doi soat thanh cong
2. Click nut **"Xuat theo Hang tau"** tren thanh cong cu
3. Cua so xuat bao cao se mo:
   - **Chon ngay**: Nhan nut lich 📅 de chon ngay (dinh dang DD-MM-YYYY)
   - **Chon hang tau**: VMC, VFC, VOSCO... (co the chon nhieu hang)
   - **Chon khung gio**: Ca sang (8H-15H), Ca chieu (15H-8H), hoac Ca ngay
4. Click **"Xuat File"**
5. File Excel se duoc tao va tu dong mo

### 6.3 Du lieu xuat ra
File xuat chua cac sheet:
- **Bien dong**: Container ra/vao trong khung gio da chon
- Cot: CNTR NO, Size, F/E, Operator, Thoi gian, Nguon...

### 6.4 Luu y
- Phai co file `5. BIEN_DONG_CHI_TIET.xlsx` trong bao cao
- Khung gio loc dua tren cot `Thoi_Gian_Nhap` va `Thoi_Gian_Xuat`

---

## 7. So Sanh File App vs TOS ⭐ MOI V5.4

### 7.1 Muc dich
So sanh file BIEN DONG hoac TON BAI xuat tu ung dung voi file tuong ung tu he thong TOS cua Cang.
- Xac nhan 2 file khop 100% hay co sai lech
- Phat hien container thieu/thua giua 2 nguon
- Xuat bao cao chi tiet de kiem tra

### 7.2 Cach su dung

#### Buoc 1: Mo cong cu So sanh
1. Click nut **"🔍 So sanh File"** tren thanh cong cu chinh
2. Cua so "So sanh File - App vs TOS" se hien len

#### Buoc 2: Chon 2 file can so sanh
1. **File 1 - Tu Ung Dung**:
   - Click "Chon..." hoac "Mo thu muc Email Templates"
   - Chon file tu thu muc `7_Email_Templates/`
   - Vi du: `BIEN DONG - VIMC Lines - N12.1.2026.xlsx`

2. **File 2 - Tu TOS Cang**:
   - Click "Chon..."
   - Chon file xuat tu he thong TOS cua Cang
   - Vi du: `TOS_Export_VIMC_12012026.xlsx`

#### Buoc 3: Thuc hien so sanh
1. Click **"🔍 So Sanh"**
2. He thong se:
   - Doc 2 file Excel
   - Tim cot Container (tu dong nhan dien)
   - So sanh danh sach container

#### Buoc 4: Xem ket qua
- **✅ Khop 100%**: Hai file hoan toan giong nhau
- **⚠️ Khop X%**: Co sai lech, hien thi:
  - So container khop
  - Container chi co trong File 1 (App)
  - Container chi co trong File 2 (TOS)

#### Buoc 5: Xuat bao cao (tuy chon)
1. Click **"📊 Xuat Bao Cao"**
2. Chon noi luu file
3. File Excel se chua cac sheet:
   - **Tom tat**: Thong ke tong quat
   - **Khop**: Danh sach container khop
   - **Chi File 1**: Container chi co trong App
   - **Chi File 2**: Container chi co trong TOS

### 7.3 Vi du ket qua

```
==================================================
📊 KET QUA SO SANH 2 FILE
==================================================

📁 File 1 (Ung dung): BIEN DONG - VIMC Lines - N12.1.2026.xlsx
📁 File 2 (TOS Cang): TOS_Export_VIMC_12012026.xlsx

--------------------------------------------------

⚠️ KET QUA: KHOP 98.5%

   📊 File 1: 200 container
   📊 File 2: 198 container

   ✅ Khop nhau: 196 container
   ❌ Chi co trong File 1: 4 container
   ❌ Chi co trong File 2: 2 container

📋 Container CHI CO trong File 1 (thieu trong TOS):
   • ABCU1234567
   • XYZU7654321
   ...

--------------------------------------------------
⏰ Thoi gian so sanh: 12/01/2026 15:30:45
==================================================
```

### 7.4 Luu y
- He thong so sanh dua tren **so Container** (tu dong chuan hoa: uppercase, bo khoang trang)
- Ho tro nhieu ten cot: "So Container", "Container", "CONTAINER", "Cont"...
- Nen so sanh file cung loai: BIEN DONG voi BIEN DONG, TON BAI voi TON BAI
- File TOS co the co dinh dang khac nhau, he thong se tu dong nhan dien

### 7.5 Ung dung thuc te
1. **Kiem tra truoc khi gui email**: Dam bao file xuat tu App khop voi TOS
2. **Doi chieu khi co tranh chap**: Xac dinh nguon goc sai lech
3. **Audit dinh ky**: Kiem tra do chinh xac cua he thong

---

## 8. Web Dashboard ⭐ MOI

### 8.1 Gioi thieu
Web Dashboard cung cap mot giao dien truc quan de xem va phan tich ket qua doi soat. Ban co the xem tren trinh duyet voi cac bieu do va bang du lieu chi tiet.

### 8.2 Cach khoi dong
Mo Command Prompt va chay lenh sau:
```bash
streamlit run app.py
```
Sau do truy cap: `http://localhost:8501`

### 8.3 Cac Tinh Nang Chinh
1. **📊 Tong quan**: Xem thong ke ton bai tong quat, so sanh Ton Cu vs Ton Moi.
2. **🏢 Hãng tàu**: Xem phan bo container theo hang tau, so luong TEU.
3. **📈 Analytics**: Bieu do truc quan ve bien dong, xu huong.
4. **📦 Trang thai**: Phan tich container Full (F) va Empty (E).
5. **📤 Trich xuat**: Tai xuong cac bao cao duoi dang Excel.

---

## 9. Cau Hinh Email ⭐ MOI

### 9.1 Muc dich
Tu dong gui email bao cao sau khi thuc hien doi soat xong.

### 9.2 File cau hinh
Chinh sua file `email_config.json` de thiet lap cac thong so email.
```json
{
    "enabled": "True",
    "sender_email": "your_email@example.com",
    "sender_password": "your_app_password",
    "recipients": "manager@example.com,ops@example.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": "587"
}
```

### 9.3 Cach lay Mat khau ung dung (App Password)
Doi voi Gmail, ban can tao "App Password" chu khong dung mat khau dang nhap thong thuong.
1. Vao **Google Account** -> **Security**.
2. Bat **2-Step Verification**.
3. Tim muc **App passwords**.
4. Tao mat khau moi cho "Mail" va "Windows Computer".
5. Copy mat khau 16 ky tu vao file `email_config.json`.

---

## 10. Cac Bao Cao Output

### 10.1 Ten Thu Muc Bao Cao
Bao cao duoc luu voi dinh dang: `Report_N{DD}.{MM}.{YYYY}_{HH}h{MM}`
- Vi du: `Report_N12.01.2026_14h30`
- DD.MM.YYYY: Ngay thang nam tao bao cao
- HH:MM: Gio phut tao bao cao

### 10.2 Danh sach File

| File/Folder | Noi dung | Mo ta chi tiet |
|-------------|----------|----------------|
| `1. SUMMARY.xlsx` | Tong hop tat ca chi so | Thong ke nguon, phuong an, bien dong |
| `2. TON_BAI_CHUAN.xlsx` | Container khop hoan toan | Ton ly thuyet = Ton thuc te |
| `3. CHENH_LECH.xlsx` | Container chenh lech | Xem chi tiet ben duoi |
| `4. DAO_CHUYEN_NOI_BAI.xlsx` | Container dao chuyen | Doi vi tri trong bai |
| `5. BIEN_DONG_CHI_TIET.xlsx` | Chi tiet bien dong | Vao/Ra theo nguon |
| `6_Ton_Theo_Hang/` | Thong ke theo hang tau | Internal review |
| `7_Email_Templates/` | **MOI V5.2**: Email hang tau | Theo dung template TOS |
| `8. MASTER_LOG.xlsx` | Log tat ca giao dich | Tra cuu timeline |
| `9. MOVEMENT_SUMMARY.xlsx` | Bien dong 20E/20F/40E/40F | Phan loai theo kich co |
| `10. ERRORS_V51.xlsx` | Loi V5.1 | Thieu phuong an, doi OPR/Size/FE |

### 10.2a Folder 7_Email_Templates (V5.6 - Cai tien moi)
Xuat file theo dung template da thong nhat voi hang tau de gui email:
```
7_Email_Templates/
├── BIEN DONG - VIMC Lines - N12.1.2026.xlsx
├── TON BAI - VIMC Lines - N12.1.2026.xlsx
│   ├── Sheet: TON BAI (container chinh)
│   ├── Sheet: Stacking (container chua hoan tat vao bai)
│   └── Sheet: Incoming (container dang cho ha bai)
├── BIEN DONG - Vinafco - N12.1.2026.xlsx
├── TON BAI - Vinafco - N12.1.2026.xlsx
└── ...
```

**Cai tien V5.6:**
- **BIEN DONG**: Chi chua Gate In/Out (loai bo nhap/xuat tau, shifting)
- **TON BAI**: Co 3 sheets:
  - `TON BAI`: Container ton bai chinh
  - `Stacking`: Container co trong TON MOI nhung khong co trong Gate + Ton Cu
  - `Incoming`: Container dang cho vao bai (co phuong an ha nhung chua co gio)

**Nhom Hang tau V5.6:**
- VIMC Lines = VMC + SVM + VLC
- Vinaline = VNL
- Vosco = VOC + SVC


### 10.3 Chi tiet File 3. CHENH_LECH.xlsx

| Sheet | Noi dung | Hanh dong |
|-------|----------|-----------|
| `Co_Lenh_Chua_Ve` | Ly thuyet co, thuc te KHONG | Kiem tra lenh nhap da thuc hien chua |
| `Ton_Chua_Co_Lenh` | Thuc te co, ly thuyet KHONG | Kiem tra nguon vao cua container |
| `Bien_Dong_FE_CFS` | Container CFS doi F/E | Binh thuong - Dong/Rut hang |
| `Sai_Thong_Tin` | Khop nhung sai info | Kiem tra OPR, Size, F/E |
| `Xuat_Tau_Van_Ton_LOI` | Xuat tau nhung van ton | **LOI NGHIEM TRONG** - Kiem tra ngay |

### 10.4 Chi tiet File 6. TON_THEO_HANG.xlsx

| Sheet | Noi dung |
|-------|----------|
| `Tong_Hop` | Bang tong hop: Lines, Ton Cu, Ton Moi, Bien Dong |
| `CT_Roi_Bai` | Danh sach chi tiet container DA ROI bai (theo hang) |
| `CT_Moi_Vao` | Danh sach chi tiet container MOI VAO bai (theo hang) |
| `CT_Van_Ton` | Danh sach chi tiet container VAN TON bai (theo hang) |

**Luu y**: Moi sheet chi tiet co cot `Lines` de loc theo hang tau.

---

## 11. Xu Ly Su Co

### 11.1 Batch Mode khong nhan dien ngay
**Nguyen nhan**: Ten file/folder khong chua ngay dung format
**Khac phuc**:
- Doi ten file: `TON MOI N7.1.2026.xlsx`
- Hoac dat trong subfolder: `N7.1.2026/TON MOI.xlsx`

### 11.2 Canh bao "File bi bo qua vi KHONG CO NGAY"
**Nguyen nhan**: File dat truc tiep trong data_input nhung khong co ngay trong ten
**Khac phuc**:
- Them ngay vao ten file: `TON CU.xlsx` → `TON CU N8.1.2026.xlsx`
- Hoac dat file vao subfolder co ngay: `N8.1.2026/TON CU.xlsx`

### 11.3 Canh bao "File KHONG NHAN DANG duoc loai"
**Nguyen nhan**: Ten file khong chua tu khoa de nhan dien loai
**Khac phuc**: Ten file can chua mot trong cac tu khoa:
- TON CU, TON MOI
- GATE IN OUT, GATE
- NHAP XUAT, SHIFTING

### 11.4 TON MOI N khong khop TON CU N+1
**Nguyen nhan**: Du lieu ban dau khong dong bo
**Khac phuc**:
- Kiem tra lai file nguon
- Tiep tuc - he thong se dung TON MOI ngay truoc lam TON CU

### 11.5 Container CFS bi danh dau "Ton chua co lenh"
**Nguyen nhan**: Phien ban cu chua nhan dien CFS
**Khac phuc**: Cap nhat len V5.1 - container CFS se duoc tach rieng vao sheet `Bien_Dong_FE_CFS`

### 11.6 Sheet "Xuat_Tau_Van_Ton_LOI" co du lieu
**Nguyen nhan**: Container da xuat tau nhung van con trong TON MOI
**Hanh dong**:
- Kiem tra ngay voi he thong TOS
- Day la loi nghiem trong can xu ly gap

### 11.7 Xuat theo hang tau - Bien dong trong
**Nguyen nhan**: Khong co du lieu trong khung gio da chon
**Khac phuc**:
- Kiem tra ngay da chon co dung khong
- Thu chon "Ca ngay (8H-8H)" de xem toan bo
- Kiem tra file `5. BIEN_DONG_CHI_TIET.xlsx` co du lieu khong

---

*Phien ban: V5.6 - Cap nhat: 13/01/2026*

