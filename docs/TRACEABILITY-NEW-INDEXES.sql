/*
  Chạy một lần trên database eGMF bằng tài khoản có quyền CREATE INDEX.
  Các index này phục vụ riêng luồng /api/traceability/new.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping') AND name = N'IX_RFIDMapping_RFID')
    CREATE INDEX IX_RFIDMapping_RFID ON dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping (RFID) INCLUDE (RFID_Hex, BarcodeTachCay, po, productcode, ThoiGianMap, NguoiMap);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping') AND name = N'IX_RFIDMapping_RFID_Hex')
    CREATE INDEX IX_RFIDMapping_RFID_Hex ON dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping (RFID_Hex) INCLUDE (RFID, BarcodeTachCay, po, productcode, ThoiGianMap, NguoiMap);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping') AND name = N'IX_RFIDMapping_Code_RFID')
    CREATE INDEX IX_RFIDMapping_Code_RFID ON dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping (Code_RFID) INCLUDE (RFID, RFID_Hex, BarcodeTachCay, po, productcode, ThoiGianMap, NguoiMap);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping') AND name = N'IX_RFIDMapping_Code_RFID_Hex')
    CREATE INDEX IX_RFIDMapping_Code_RFID_Hex ON dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping (Code_RFID_Hex) INCLUDE (RFID, RFID_Hex, BarcodeTachCay, po, productcode, ThoiGianMap, NguoiMap);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping') AND name = N'IX_RFIDMapping_RFID_Barcode')
    CREATE INDEX IX_RFIDMapping_RFID_Barcode ON dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping (RFID_Barcode) INCLUDE (RFID, RFID_Hex, BarcodeTachCay, po, productcode, ThoiGianMap, NguoiMap);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_TemBarcode_TachCay') AND name = N'IX_TemBarcode_Code')
    CREATE INDEX IX_TemBarcode_Code ON dbo.CUTTING_TemBarcode_TachCay (Code) INCLUDE (TenSize, Mua, LenhSanXuat, Lot);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_PhieuCapBTP_ChiTiet') AND name = N'IX_PhieuCapBTPChiTiet_PO_IdCapBTP')
    CREATE INDEX IX_PhieuCapBTPChiTiet_PO_IdCapBTP ON dbo.CUTTING_PhieuCapBTP_ChiTiet (PO, IdCapBTP) INCLUDE (SizeCode, TenMau, Id);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet') AND name = N'IX_BarcodeChiTiet_SoPhieu_PO')
    CREATE INDEX IX_BarcodeChiTiet_SoPhieu_PO ON dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet (SoPhieuCapBTP, PO) INCLUDE (Lot, ChungLoai, TraBTP);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Bravo_DonDatHangBan_Master') AND name = N'IX_DonDatHang_PO_ProductCode')
    CREATE INDEX IX_DonDatHang_PO_ProductCode ON dbo.Bravo_DonDatHangBan_Master (PO, ProductCode, IsActive, Id DESC) INCLUDE (CustomerCode);

UPDATE STATISTICS dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping WITH FULLSCAN;
