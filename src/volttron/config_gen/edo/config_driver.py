import copy
import math
import sys
from volttron.config_gen.utils.edo_utils import *
from volttron.config_gen.base.config_driver import \
    DriverConfigGenerator


class EdoDriverConfigGenerator(DriverConfigGenerator):
    """
    Class that parses edo semantic model from csv file to
    generate VOLTTRON platform driver agent configurations for
    AHU, DOAS, RTU, VAV, WHOLE BUILDING ELECTRIC METER.
    This generates driver configuration for  normal framework driver
    
    This class can be extended and customized for
    specific device types and configurations
    For example, override self.driver_config_template in configuration file and
    self.generate_config_from_template() if you want to generate
    driver configurations for bacnet or modbus drivers
    """

    def __init__(self, config):
        super().__init__(config)
        metadata = self.config_dict.get("metadata")
        self.df = create_edo_dataframe(metadata.get("points_csv"))
        self.ahus = None
        self.vavs = None
        self.power_meter = None
        self._map = dict()

    def get_ahu_and_vavs(self):
        # Get devices we are interested in
        self.ahus, _ = get_ahus_and_points(self.df)
        self.vavs, _ = get_vavs_and_points(self.df)

        ahu_vav_mapping = dict()
        for index, ahu in self.ahus.iterrows():
            ahu_vav_mapping[ahu['EquipmentID']] = []
            self._map[ahu['EquipmentID']] = ahu['EquipName']
        ahu_vav_mapping[""] = []

        for index, vav in self.vavs.iterrows():
            self._map[vav['EquipmentID']] = vav['EquipName']
            parent_ahu_id = vav.get('ParentEquipID', "")
            if math.isnan(parent_ahu_id):
                parent_ahu_id = ""
            # if parent id is not empty and corresponds to a valid equipment
            # add vav to the parent equip dict, else assign it to empty key
            ahu_vav_mapping[parent_ahu_id].append(vav['EquipmentID'])

        return ahu_vav_mapping

    def get_building_meter(self):
        # to do query and return building meter id/name
        if self.configured_power_meter_id:
            elec_meter_point = self.df.query(f'EquipmentID == {self.configured_power_meter_id}')
            if len(elec_meter_point.index) > 1:
                # ideally shouldn't reach here. don't expect more than 1 entry per configured power meter equipment id
                raise ValueError("More than one equipment found with configured power meter id"
                                 f"{self.configured_power_meter_id}"
                                 "Please add 'power_meter_id' parameter to the configuration and provide"
                                 "value as the equipment id of whole building power meter")

        else:
            elec_meter_point = self.df.query(
                 f'EquipClassID == {ELEC_METER_ID} and PointClassID == {ELEC_MTR_POWER_POINT_ID}')

            if len(elec_meter_point.index) > 1:
                raise ValueError(f"More than one equipment found with the Equip Class ID {ELEC_METER_ID} "
                                 f"and Point Class ID {ELEC_MTR_POWER_POINT_ID}. "
                                 "Please add 'power_meter_id' parameter to the configuration and provide"
                                 "value as the equipment id of whole building power meter")

        if elec_meter_point.empty:
            if self.configured_power_meter_id:
                raise ValueError("Unable to find whole building power meter using configured power meter id"
                                 f"{self.configured_power_meter_id}")
            else:
                raise ValueError(f"Unable to find equipment with the Equip Class ID {ELEC_METER_ID} "
                                 f"and Point Class ID {ELEC_MTR_POWER_POINT_ID}. "
                                 "Please add 'power_meter_id' parameter to the configuration and provide"
                                 "value as the equipment id of whole building power meter")

        self.power_meter = elec_meter_point
        s = elec_meter_point.iloc[0]
        self._map[s['EquipmentID']] = s['EquipName']
        return s['EquipmentID']

    def generate_config_from_template(self, equip_id, equip_type):
        if equip_type == "ahu":
            df = self.ahus
        elif equip_type == "vav":
            df = self.vavs
        elif equip_type == "meter":
            df = self.power_meter
        else:
            raise ValueError(f"Unknown equip type {equip_type}")

        pd_series = df.query(f'EquipmentID== {equip_id}').PointName
        device_id = None
        p = None
        for p in pd_series:
            tokens = p.split(':')
            if len(tokens) == 3:
                device_id = tokens[0]
                break
        # Using only device id in template
        device_name = None
        driver = copy.deepcopy(self.config_template)
        nf_query_format = driver["driver_config"]["query"]
        if "{device_id}" in nf_query_format and device_id is None or \
                "{obj_name}" in nf_query_format and device_name is None:
            if not self.unmapped_device_details.get(equip_id):
                self.unmapped_device_details[equip_id] = dict()
            self.unmapped_device_details[equip_id]["type"] = equip_type
            self.unmapped_device_details[equip_id]["equip_id"] = equip_id
            self.unmapped_device_details[equip_id]["error"] = \
                ("Unable to parse device id from any of the PointName values. "
                 f"Expected format: device_id:device_name:point_name. Last read point name: {p}")
            return None
        else:
            nf_query = nf_query_format.format(device_id=device_id,
                                              obj_name=device_name)
            driver["driver_config"]["query"] = nf_query
            return driver

    def get_name_from_id(self, equip_id):
        return f"{equip_id}_{self._map[equip_id]}"


def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = EdoDriverConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()

