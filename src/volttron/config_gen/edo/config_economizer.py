import sys
from volttron.config_gen.utils.edo_utils import *
from volttron.config_gen.base.config_economizer import \
    AirsideEconomizerConfigGenerator


class EdoAirsideEconomizerConfigGenerator(AirsideEconomizerConfigGenerator):
    """
    Class that parses edo semantic model from csv file to generate
    AirsideEconomizer agent configurations.
    """
    def __init__(self, config):
        super().__init__(config)
        metadata = self.config_dict.get("metadata")
        self.df = create_edo_dataframe(metadata.get("points_csv"))
        self.ahus = None
        self.ahu_points = None
        self.equip_id_name_map = dict()

    def get_ahus(self):
        self.ahus, self.ahu_points = get_ahus_and_points(self.df)
        ahu_ids = []
        for index, ahu in self.ahus.iterrows():
            self.equip_id_name_map[ahu['EquipmentID']] = ahu['EquipName']
            ahu_ids.append(ahu['EquipmentID'])
        return ahu_ids

    def get_point_name(self, equip_id, equip_type, point_key):
        if equip_type == "ahu":
            df = self.ahu_points
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
    d = EdoAirsideEconomizerConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
