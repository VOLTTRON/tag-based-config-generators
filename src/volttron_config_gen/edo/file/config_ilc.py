import math
import sys

from volttron_config_gen.base.config_ilc import BaseConfigGenerator
from volttron_config_gen.utils.edo_utils import *


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses semantic tags from a postgres db to generate
    ILC configs
    """

    def __init__(self, config):
        super().__init__(config)
        metadata = self.config_dict.get("metadata")
        self.df = create_edo_dataframe(metadata.get("points_csv"))
        self.ahus = None
        self.vavs = None
        self.ahu_points = None
        self.vav_points = None
        self.power_meter_point_row = None
        self.equip_id_name_map = dict()
        self.vavs_and_ahuref = list()

    def get_building_power_meter(self):

        row = get_power_meter_point(self.df, self.configured_power_meter_id)
        if not row.empty:
            self.power_meter_point_row = row
            self.equip_id_name_map[row["EquipmentID"]] = row["EquipName"]
            return row["EquipmentID"]
        else:
            if self.configured_power_meter_id:
                raise ValueError(f"No equipment found with the EquipClassID={self.configured_power_meter_id}"
                                 f"and a point with PointClassID={ELEC_MTR_POWER_POINT_ID}. Please fix "
                                 f"configured_power_meter_id parameter to configuration to uniquely identify whole "
                                 f"building power meter or if you want to manually configure this, set both"
                                 f"building_power_meter and building_power_point in configuration. If both values "
                                 f"are set then no semantic lookup is done and values are used as is")
            else:
                raise ValueError(f"No equipment found with the EquipClassID={ELEC_METER_ID}"
                                 f"and a point with PointClassID={ELEC_MTR_POWER_POINT_ID}. Please fix "
                                 f"configured_power_meter_id parameter to configuration to use a custom building power "
                                 f"meter EquipClassID or if you want to manually configure this, set both"
                                 f"building_power_meter and building_power_point in configuration. If both values "
                                 f"are set then no semantic lookup is done and values are used as is")

    def get_building_power_point(self):
        point_name = ""
        if self.power_meter_id:
            point_name = self.power_meter_point_row.get("PointName", "")

        if self.unmapped_device_details.get(self.power_meter_id):
            # Could have been more than 1 point name.
            return ""
        else:
            return point_name

    def get_vav_ahu_map(self):
        self.ahus, self.ahu_points = get_ahus_and_points(self.df)
        self.vavs, self.vav_points = get_vavs_and_points(self.df)

        vav_ahu_mapping = dict()
        for index, ahu in self.ahus.iterrows():
            self.equip_id_name_map[ahu['EquipmentID']] = ahu['EquipName']

        for index, vav in self.vavs.iterrows():
            self.equip_id_name_map[vav['EquipmentID']] = vav['EquipName']
            parent_ahu_id = vav.get('ParentEquipID', "")
            # vav without ahuref are not applicable for AirsideRCx
            if not math.isnan(parent_ahu_id):
                # if parent id is not empty and corresponds to a valid equipment
                # add vav to the parent equip dict, else assign it to empty key
                vav_ahu_mapping[vav['EquipmentID']] = parent_ahu_id
            else:
                vav_ahu_mapping[vav['EquipmentID']] = ""
        return vav_ahu_mapping

    def get_point_name(self, equip_id, equip_type, point_key):
        if equip_type == "ahu":
            df = self.ahu_points
        elif equip_type == "vav":
            df = self.vav_points
        else:
            raise ValueError(f"Unknown equip type {equip_type}")

        pd_series = df.query(
            f'EquipmentID== {equip_id} and {self.point_meta_field} == {self.point_meta_map[point_key]}').PointName

        if pd_series.size == 1:
            return pd_series.iat[0]
        else:
            return ""

    def get_name_from_id(self, equip_id):
        return f"{equip_id}_{self.equip_id_name_map[equip_id]}"


def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
