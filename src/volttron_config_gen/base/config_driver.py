import json
import os.path
import sys
from abc import abstractmethod
from pathlib import Path

from volttron_config_gen.utils import strip_comments


class BaseConfigGenerator:
    """
    Base class to generate platform driver configuration based on a configuration template.
    Generates configuration templates for Air Handling Units (AHU, DOAS, RTU) and associated VAVs, and
    building electric meter
    """

    def __init__(self, config):
        if isinstance(config, dict):
            self.config_dict = config
        else:
            try:
                with open(config, "r") as f:
                    self.config_dict = json.loads(strip_comments(f.read()))
            except Exception:
                raise

        self.site_id = self.config_dict.get("site_id", "")
        self.building = self.config_dict.get("building")
        self.campus = self.config_dict.get("campus")
        if not self.building and self.site_id:
            self.building = self.get_name_from_id(self.site_id)
        if not self.campus and self.site_id:
            self.campus = self.site_id.split(".")[-2]

        topic_prefix = self.config_dict.get("topic_prefix")
        if not topic_prefix:
            topic_prefix = "devices"
            if self.campus:
                topic_prefix = topic_prefix + f"/{self.campus}"
            if self.building:
                topic_prefix = topic_prefix + f"/{self.building}"

        if not topic_prefix.endswith("/"):
            topic_prefix = topic_prefix + "/"
        self.ahu_topic_pattern = topic_prefix + "{}"
        self.meter_topic_pattern = topic_prefix + "{}"
        self.vav_topic_pattern = topic_prefix + "{ahu}/{vav}"
        # logical volttron "device" that will have registry config with points of all lights in the
        # room + point from the occupancy detector of the room
        self.light_topic_pattern = topic_prefix + "{room}_lights"

        self.power_meter_tag = 'siteMeter'
        self.configured_power_meter_id = self.config_dict.get("power_meter_id", "")
        self.power_meter_name = self.config_dict.get("building_power_meter", "")

        self.power_meter_id = None

        # If there are any vav's that are not mapped to a AHU use this dict to give
        # additional details for user to help manually find the corresponding ahu
        self.unmapped_device_details = dict()

        self.config_template = self.config_dict.get("config_template")

        # initialize output dir
        default_prefix = self.building + "_" if self.building else ""
        self.output_dir = self.config_dict.get(
            "output_dir", f"{default_prefix}driver_configs")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        elif not os.path.isdir(self.output_dir):
            raise ValueError(f"Output directory {self.output_dir} "
                             f"does not exist")
        print(f"Output directory {os.path.abspath(self.output_dir)}")
        self.output_configs = os.path.join(self.output_dir, "configs")
        os.makedirs(self.output_configs, exist_ok=True)
        self.output_errors = os.path.join(self.output_dir, "errors")
        os.makedirs(self.output_errors, exist_ok=True)
        self.driver_vip = self.config_dict.get("driver_vip", "platform.driver")

    @abstractmethod
    def get_ahu_and_vavs(self):
        """
        Should return a list of ahu and vav mappings
        :return: list of tuples with the format [(ahu1, (vav1,vav2..)),...]
                 or dict mapping ahu with vavs with format
                 {'ahu1':(vav1,vav2,..), ...}
        """
        pass

    @abstractmethod
    def get_building_meter(self):
        """
        Should return a meter.

        """
        pass

    def get_lights_by_room(self):
        # not all implementation might have lighting info
        # return empty dict
        return dict()

    def get_occupancy_detector(self, room_id):
        # not all implementation might have lighting info
        # return None
        return None

    def generate_configs(self):
        ahu_and_vavs = self.get_ahu_and_vavs()
        if isinstance(ahu_and_vavs, dict):
            iterator = ahu_and_vavs.items()
        else:
            iterator = ahu_and_vavs
        for ahu_id, vavs in iterator:
            ahu_name, result_dict = self.generate_ahu_configs(ahu_id, vavs)
            if not result_dict:
                continue  # no valid configs, move to the next ahu
            if ahu_name:
                with open(f"{self.output_configs}/{ahu_name}.json", 'w') as outfile:
                    json.dump(result_dict, outfile, indent=4)
            else:
                with open(f"{self.output_errors}/unmapped_vavs.json", 'w') as outfile:
                    json.dump(result_dict, outfile, indent=4)

        try:
            self.power_meter_id = self.get_building_meter()
            meter_name, result_dict = self.generate_meter_config()
            with open(f"{self.output_configs}/{meter_name}.json", 'w') as outfile:
                json.dump(result_dict, outfile, indent=4)
        except ValueError as e:
            self.unmapped_device_details["building_power_meter"] = {"error": f"{e}"}

        try:
            room_lights = self.get_lights_by_room()
            if isinstance(room_lights, dict):
                iterator = room_lights.items()
            else:
                iterator = room_lights
            lights_dict = {self.driver_vip:[]}
            for room_id, lights in iterator:
                try:
                    occ_detector = self.get_occupancy_detector(room_id)
                except Exception as e:
                    self.unmapped_device_details[f"{room_id}_occupancy_detector"] = {
                        "error": f"Unable to get occupancy detector for and room  {room_id}. "
                                 f"Exception{e}"}
                    continue
                try:
                    room_name, result_dict = self.generate_room_light_configs(room_id,
                                                                              lights,
                                                                              occ_detector)
                except Exception as e:
                    self.unmapped_device_details[f"{room_id}_lights"] = {
                        "error": f"Unable to get lights details for room  {room_id}. "
                                 f"Exception: {e}"}
                    continue
                if not result_dict or not result_dict.get(self.driver_vip):
                    continue  # no valid configs, move to the next room
                else:
                    lights_dict[self.driver_vip].extend(result_dict[self.driver_vip])

            if lights_dict[self.driver_vip]:
                with open(f"{self.output_configs}/all_lights.json", 'w') as outfile:
                    json.dump(lights_dict, outfile, indent=4)

        except ValueError as e:
            self.unmapped_device_details["lights"] = {"error": f"Unable to get lights and room {e}"}

        # Generate driver agent config
        agent_dict = dict()
        interval = 60/(self.get_max_device_count_in_group()+1)
        agent_dict[self.driver_vip] = [
            {"config-name": "config",
             "config": {"driver_scrape_interval": interval}
             }
        ]
        with open(f"{self.output_configs}/driver-agent-config.json", 'w') as outfile:
            json.dump(agent_dict, outfile, indent=4)

        # If unmapped devices exists, write additional unmapped_devices.txt that gives more info to user to map manually
        if self.unmapped_device_details:
            err_file = f"{self.output_errors}/unmapped_device_details"
            with open(err_file, 'w') as outfile:
                json.dump(self.unmapped_device_details, outfile, indent=4)

            sys.stderr.write(f"\nUnable to generate configurations for all AHUs and VAVs. "
                             f"Please see {err_file} for details\n")
            sys.exit(1)
        else:
            sys.exit(0)

    def generate_meter_config(self):
        final_mapper = dict()
        final_mapper[self.driver_vip] = []
        meter = ""
        meter = self.get_name_from_id(self.power_meter_id)
        topic = self.meter_topic_pattern.format(meter)
        driver_config = self.generate_config_from_template(self.power_meter_id, 'meter')
        if driver_config:
            final_mapper[self.driver_vip].append({"config-name": topic, "config": driver_config})
        return meter, final_mapper

    def generate_ahu_configs(self, ahu_id, vavs):
        final_mapper = dict()
        final_mapper[self.driver_vip] = []
        ahu_name = ""

        # First create the config for the ahu
        if ahu_id:
            ahu_name = self.get_name_from_id(ahu_id)
            topic = self.ahu_topic_pattern.format(ahu_name)
            # replace right variables in driver_config_template
            driver_config = self.generate_config_from_template(ahu_id, "ahu")
            result = self.generate_registry_config(driver_config, ahu_id, "ahu", final_mapper)
            if result:
                final_mapper[self.driver_vip].append({"config-name": topic,
                                                      "config": driver_config})
            # fill ahu, leave vav variable
            vav_topic = self.vav_topic_pattern.format(ahu=ahu_name, vav='{vav}')
        else:
            vav_topic = self.vav_topic_pattern.replace("{ahu}/", "")  # ahu
        # Now loop through and do the same for all vavs
        for vav_id in vavs:
            vav = self.get_name_from_id(vav_id)
            topic = vav_topic.format(vav=vav)
            # replace right variables in driver_config_template
            driver_config = self.generate_config_from_template(vav_id, "vav")
            result = self.generate_registry_config(driver_config, vav_id, "vav", final_mapper)
            if result:
                final_mapper[self.driver_vip].append({"config-name": topic,
                                                      "config": driver_config})

        if not final_mapper[self.driver_vip]:
            final_mapper = None
        return ahu_name, final_mapper

    def generate_room_light_configs(self, room_id, lights, occ_detector):
        if not room_id or not lights:
            return None, None

        final_mapper = dict()
        final_mapper[self.driver_vip] = []
        room_name = ""

        room_name = self.get_name_from_id(room_id)
        topic = self.light_topic_pattern.format(room=room_name)
        # replace right variables in driver_config_template
        # there will be one logical device per room for all lights + occupancy detector in it
        driver_config = self.generate_config_from_template(room_id, "lighting")

        # Now loop through and do the same for all vavs
        all_points = []
        for light_id in lights:
            if driver_config.get("registry_config"):
                # replace right variables in driver_config_template
                light_points = self.generate_registry_config_data(light_id, "lighting",
                                                                  room_id=room_id)
                all_points.extend(light_points)
        if occ_detector:
            if driver_config.get("registry_config"):
                # replace right variables in driver_config_template
                occ_detector_points = self.generate_registry_config_data(occ_detector,
                                                                         "occupancy_detector",
                                                                         room_id=room_id)
                all_points.extend(occ_detector_points)
        if all_points:
            final_mapper[self.driver_vip].append({"config-name": topic, "config": driver_config})
            self.generate_registry_config(driver_config, f"{room_name}_lights", "lighting",
                                          final_mapper, all_points)
        if not final_mapper[self.driver_vip]:
            final_mapper = None
        return room_name, final_mapper

    def generate_registry_config(self, driver_config, equip_id, equip_type, final_mapper,
                                 data=None):
        if not driver_config:
            return False
        if driver_config.get("registry_config"):
            # generate registry config
            rfile, rtype = self.generate_registry_config_file(equip_id, equip_type, data)
            if not rfile:
                return False
            driver_config["registry_config"] = f"config://registry_config/{equip_id}.{rtype}"
            final_mapper[self.driver_vip].append(
                {"config-name": f"registry_config/{equip_id}.{rtype}",
                 "config": rfile,
                 "config-type": rtype})
        return True

    @abstractmethod
    def generate_config_from_template(self, equip_id, equip_type):
        pass

    def get_name_from_id(self, _id):
        return _id

    def get_volttron_point_name(self, reference_point_name, **kwargs):
        return reference_point_name

    def generate_registry_config_file(self, equip_id, equip_type, data=None):
        """
        Method to be overridden by driver config generators for bacnet, modbus etc.
        where a registry config file is needed.
        method should return registry config name and config file and config file type
        config name returned will be included in driver config as config://<config_name>
        """
        raise NotImplementedError

    def generate_registry_config_data(self, equip_id, equip_type, **kwargs):
        """
        Method to be overridden by driver config generators for bacnet, modbus etc.
        where a registry config file is needed.
        method should return registry config name and config file and config file type
        config name returned will be included in driver config as config://<config_name>
        """
        raise NotImplementedError

    def get_max_device_count_in_group(self):
        return 1
