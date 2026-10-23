import csv
import json
import sys

from io import StringIO

from ...base.config_ilc import BaseConfigGenerator


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses an existing Platform Driver configuration store to generate
    ILC agent configurations
    """

    def __init__(self, config_dict):
        super().__init__(config_dict)
        metadata = self.config_dict.get("metadata")
        if configuration_stores := metadata.get("configuration_stores"):
            self.device_configs = self._load_config_stores(configuration_stores)
        else:
            # TODO: Implement loading from running driver.
            self.device_configs = {}

    def _load_config_stores(self, configuration_stores):
        configs = {}
        for configuration_store in configuration_stores:
            with open(configuration_store, "r") as f:
                pdc = json.load(f)
            prefix = f'devices/{self.campus}/{self.building}'
            devices = [d for d in pdc if d.startswith(prefix)]
            for device in devices:
                configs[device] = self._read_config_from_store(pdc, device)
                reg_name = configs[device]['registry_config']
                if reg_name.startswith('config://'):
                    configs[device]['registry_config'] = self._read_config_from_store(pdc, reg_name[len('config://'):])
        return configs

    @staticmethod
    def _read_config_from_store(config_store, config_name):
        config_contents = config_store.get(config_name)
        if not config_contents:
            return None
        elif config_contents['type'] == 'json':
            return json.loads(config_contents['data'])
        elif config_contents['type'] == 'csv':
            with StringIO(config_contents['data']) as f:
                return [row for row in csv.DictReader(f)]
        else:
            return None

    def get_building_power_meter(self):
        candidates = [c for c in self.device_configs if 'meter' in c.lower()]
        return candidates[0] if candidates else ""

    def get_building_power_point(self):
        return (self.get_point_name(self.power_meter_id, "power_meter", "WholeBuildingPower")
                if self.power_meter_id else "")

    def get_vav_ahu_map(self):
        return [(topic, topic.split('/')[-2]) for topic in (c for c in self.device_configs if 'vav' in c.lower())]

    def get_rtus(self):
        rtus = [c for c in self.device_configs if any(item in c.lower() for item in ['rtu', 'hp'])]
        return [
            (point['Volttron Point Name'], rtu_topic)
            for rtu_topic in rtus
            for point in self.device_configs[rtu_topic]['registry_config']
            if 'stage' in point['Volttron Point Name'].lower()
        ]

    def get_point_name(self, equip_id, equip_type, point_key, **kwargs):
        meta_map = self.point_meta_map.get(equip_type, {})
        meta_map_name = meta_map.get(point_key)
        if isinstance(meta_map_name, str):
            meta_map_name = [meta_map_name]
        points_on_device = [p['Volttron Point Name'] for p in self.device_configs[equip_id]['registry_config']]
        equip_name = self.get_name_from_id(equip_id)
        for candidate in meta_map_name:
            candidate = self.apply_template(candidate, device_id=equip_id, device_type=equip_type,
                                            device_name=equip_name, meta_map=meta_map, **kwargs)
            if candidate in points_on_device:
                return candidate
        return None

    def get_name_from_id(self, _id):
        return _id.split('/')[-1]

    # def get_lights_by_room(self):
    #     pass
    #
    # def get_occ_detector(self, room_id):
    #     pass
    #
    # def get_lighting_points(self, room_id, devices, point_name)->list[str]:
    #     pass

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
