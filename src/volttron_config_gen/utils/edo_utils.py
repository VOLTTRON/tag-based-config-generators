import pandas

# Air Handler EquipmentClassID
AHU_ID = 1
# Dedicated Outside Air System EquipmentClassID
DOAS_ID = 167
# Rooftop Unit EquipClassID
RTU_ID = 5

# Variable Air Volume Terminal Unit EquipClassID
VAV_ID = 21
VAV_REHEAT_ID = 158

# Building Electric Meter EquipClassID
ELEC_METER_ID = 32

ELEC_MTR_POWER_POINT_ID = 235


def create_edo_dataframe(csv_file_path: str) -> pandas.DataFrame:
    try:
        return pandas.read_csv(
            csv_file_path,
            usecols=['EquipClassID', 'EquipmentID', 'EquipName', 'ParentEquipID', 'PointName', 'PointClassID'])
    except Exception:
        raise


def get_ahus_and_points(df: pandas.DataFrame):
    ahu_points = df.query(f'EquipClassID == [{AHU_ID}, {DOAS_ID}, {RTU_ID}]')
    return ahu_points.groupby('EquipmentID').nth(0), ahu_points


def get_vavs_and_points(df: pandas.DataFrame):
    vav_points = df.query(f'EquipClassID == [{VAV_ID}, {VAV_REHEAT_ID}]')
    return vav_points.groupby('EquipmentID').nth(0), vav_points


def get_power_meter_point(df: pandas.DataFrame, equip_class_id=None):
    # Based on current assumption.
    # Waiting on clarification from Easan
    # Question sent:
    # -------------
    # Is the whole building electric meter equipment the one with
    #       EquipClassID=32 and EquipClassDescription="Electric Main Meter" ?
    # Out of all the electric meters and sub meters could I assume that the equipment with a point that has
    # point class id=235, point class name=Mtr Power, is the one that represents the whole building power meter.
    # This narrows it down to single equipment for morris_ctr and catalysts_points.
    if not equip_class_id:
        equip_class_id = ELEC_METER_ID
    power_meter_points = df.query(f'EquipClassID == {equip_class_id}')
    for index, row in power_meter_points.iterrows():
        if row['PointClassID'] == ELEC_MTR_POWER_POINT_ID:
            return row
    return None



