-- Migration 07: 量測設備校驗類別新增「遊校」
-- 對應 MeasurementEquipment.calibration_type 新增 'itinerant' 選項

ALTER TABLE "量測設備"
    DROP CONSTRAINT IF EXISTS ck_equipment_calibration_type;

ALTER TABLE "量測設備"
    ADD CONSTRAINT ck_equipment_calibration_type
    CHECK ("校驗類別" IS NULL OR "校驗類別" IN (
        'internal', 'external', 'itinerant', 'exempt'
    ));
