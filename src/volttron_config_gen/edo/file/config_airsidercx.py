import math
import sys

from volttron_config_gen.utils.edo_utils import *
from volttron_config_gen.base.config_airsidercx import BaseConfigGenerator


class ConfigGenerator(BaseConfigGenerator):
    """
    Class that parses edo semantic model from csv file to generate
    AirsideRCx agent configurations.
    """

    def __init__(self, config):
        super().__init__(config)
        metadata = self.config_dict.get("metadata")
        self.df = create_edo_dataframe(metadata.get("points_csv"))
        self.ahus = None
        self.vavs = None
        self.ahu_points = None
        self.vav_points = None
        self.equip_id_name_map = dict()

    def get_ahu_and_vavs(self):
        # Get devices we are interested in
        self.ahus, self.ahu_points = get_ahus_and_points(self.df)
        self.vavs, self.vav_points = get_vavs_and_points(self.df)

        ahu_vav_mapping = dict()
        for index, ahu in self.ahus.iterrows():
            ahu_vav_mapping[ahu['EquipmentID']] = []
            self.equip_id_name_map[ahu['EquipmentID']] = ahu['EquipName']

        for index, vav in self.vavs.iterrows():
            self.equip_id_name_map[vav['EquipmentID']] = vav['EquipName']
            parent_ahu_id = vav.get('ParentEquipID', "")
            # vav without ahuref are not applicable for AirsideRCx
            if not math.isnan(parent_ahu_id):
                # if parent id is not empty and corresponds to a valid equipment
                # add vav to the parent equip dict, else assign it to empty key
                ahu_vav_mapping[parent_ahu_id].append(vav['EquipmentID'])
        return ahu_vav_mapping

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
