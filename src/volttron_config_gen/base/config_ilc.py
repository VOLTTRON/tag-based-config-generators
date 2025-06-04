import datetime
import json
import os.path
import sys
from abc import abstractmethod
import copy
import shutil
from typing import Tuple

from volttron_config_gen.utils import strip_comments
from volttron_config_gen.utils.ilc.validate_pairwise import extract_criteria as pairwise_extract_criteria, \
    validate_input as pairwise_validate_input, calc_column_sums as pairwise_calc_column_sums


class BaseConfigGenerator:
    """
    Base class that parses semantic tags to generate
    ILC agent configurations based on a configuration templates
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
        self.lighting_actuator_config = {}
        self.site_id = self.config_dict.get("site_id", "")
        self.building = self.config_dict.get("building", "")
        self.campus = self.config_dict.get("campus", "")
        if not self.building and self.site_id:
            self.building = self.get_name_from_id(self.site_id)
        if not self.campus and self.site_id:
            self.campus = self.site_id.split(".")[-2]

        self.topic_prefix = self.campus + "/" if self.campus else ""
        self.topic_prefix = self.topic_prefix + self.building + "/" if self.building else ""
        self.power_meter_tag = 'siteMeter'
        self.power_meter_name = self.config_dict.get("building_power_meter", "")
        self.building_power_point = self.config_dict.get("building_power_point", "")
        self.configured_power_meter_id = self.config_dict.get("power_meter_id", "")

        self.point_meta_map = self.config_dict.get("point_meta_map")
        self.point_meta_field = self.config_dict.get("point_meta_field", "miniDis")
        self.point_default_map = self.config_dict.get("point_default_map", dict())

        self.power_meter_id = None
        self.volttron_point_type_building_power = "WholeBuildingPower"
        self.point_type_building_power = self.point_meta_map.get("power_meter", {}).get(
            self.volttron_point_type_building_power, "")

        # use this dict to give additional details for user to help manually find the issue
        self.unmapped_device_details = dict()

        self.config_template = self.config_dict.get("config_template")
        if not self.config_template:
            raise ValueError(f"Missing parameter in config:'config_template'")

        self.ilc_template = {
            "campus": self.campus,
            "building": self.building,
            "power_meter": {
                "device_topic": "",
                "point": ""
            },
            "application_category": "Load Control",
            "application_name": "Intelligent Load Control",
            "clusters": []
        }
        self.ilc_template.update(self.config_template["ilc_config"])

        # initialize output dir
        default_prefix = self.building + "_" if self.building else ""
        self.output_dir = self.config_dict.get(
            "output_dir", f"{default_prefix}ILC_configs")
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

        self.ilc_agent_vip = self.config_dict.get("ilc_agent_vip", "platform.ilc")

        # Initialize map of haystack3 id and nf device name
        self.equip_id_point_map = dict()
        self.equip_id_device_id_map = dict()
        self.config_metadata_dict = dict()
        self.config_metadata_dict[self.ilc_agent_vip] = []

    def generate_configs(self):
        """
        Generated all configuration files for ILC agent for a given site
        """
        st = datetime.datetime.utcnow()
        print(f"Starting generation at {st}")
        device_types = self.config_template["control_config"].keys()

        self.generate_control_and_criteria_config(device_types)

        self.generate_pairwise_config(device_types)

        self.generate_ilc_config(device_types)

        if "lighting" in device_types:
            self.generate_generate_lighting_actuator_config()

        et = datetime.datetime.utcnow()
        print(f"Done with config generation. end time is {et} time taken {et-st}")
        if self.config_metadata_dict[self.ilc_agent_vip]:
            config_metafile_name = f"{self.output_dir}/config_metadata.json"
            with open(config_metafile_name, 'w') as f:
                json.dump(self.config_metadata_dict, f, indent=4)
        if self.unmapped_device_details:
            err_file_name = f"{self.output_errors}/unmapped_device_details"
            with open(err_file_name, 'w') as outfile:
                json.dump(self.unmapped_device_details, outfile, indent=4)

            sys.stderr.write(f"\nUnable to generate configurations for all devices. "
                             f"Please see {err_file_name} for details\n")
            sys.exit(1)
        else:
            sys.exit(0)

    def generate_pairwise_config(self, device_types):

        for device_type in device_types:
            pairwise_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils/ilc",
                                              f"pairwise_criteria_{device_type}.json")
            if not os.path.exists(pairwise_path):
                raise ValueError(
                    f"Given device type is {device_type}. But unable to find corresponding "
                    f"pairwise criteria file {pairwise_path}")

            # Validate pairwise criteria if needed. exit if validation fails
            if self.config_template.get("validate_pairwise_criteria"):
                try:
                    with open(pairwise_path, "r") as f:
                        pairwise_dict = json.loads(strip_comments(f.read()))
                except Exception as e:
                    raise ValueError(f"Invalid json: pairwise criteria file "
                                     f"{pairwise_path} failed. Exception {e}")

                criteria_labels, criteria_array = pairwise_extract_criteria(
                    pairwise_dict["curtail"])
                col_sums = pairwise_calc_column_sums(criteria_array)

                result, ratio = pairwise_validate_input(criteria_array, col_sums)
                if not result:
                    sys.stderr.write(f"\nValidation of pairwise criteria file "
                                     f"{pairwise_path} failed.\n"
                                     f"Computed criteria array:{criteria_array} "
                                     f"column sums:{col_sums}\n"
                                     f"Inconsistency ratio is: {ratio}\n")
                    sys.exit(1)

            # write pairwise criteria file
            file_name = f"{device_type}_criteria_matrix.json"
            file_path = os.path.abspath(os.path.join(self.output_configs, file_name))
            shutil.copy(pairwise_path, file_path)
            self.config_metadata_dict[self.ilc_agent_vip].append({"config-name": file_name,
                                                                  "config": file_path})

    def generate_ilc_config(self, device_types):
        if not self.power_meter_name or not self.building_power_point:
            # if both are provided then use that don't try to look up device or point.
            # it might be a power meter agent and no actual power meter device
            if not self.power_meter_id:
                try:
                    self.power_meter_id = self.get_building_power_meter()
                    if not self.power_meter_id:
                        self.unmapped_device_details["building_power_meter"] = {
                            "type": "building power meter",
                            "error": "Unable to locate building power meter"}
                except ValueError as e:
                    # Unable to uniquely identify power meter using siteMeter tag or with configured power meter id
                    self.unmapped_device_details["building_power_meter"] = {
                        "type": "building power meter",
                        "error": f"Unable to locate building power meter: Error: {e}"}

            if not self.building_power_point:
                self.building_power_point = self.get_building_power_point()
                if not self.building_power_point and self.point_default_map.get("power_meter"):
                    self.building_power_point = self.point_default_map["power_meter"].get(
                        "WholeBuildingPower", "")

            if not self.building_power_point and \
                    self.power_meter_id and \
                    not self.unmapped_device_details.get(self.power_meter_id):
                self.unmapped_device_details[self.power_meter_id] = {
                    "type": "building power meter",
                    "error": f"Unable to locate building power point using the metadata "
                             f"{self.point_type_building_power}"}

            if not self.power_meter_name and self.power_meter_id:
                self.power_meter_name = self.get_name_from_id(self.power_meter_id)

            #  Error case
            if (not self.power_meter_name and
                    not self.unmapped_device_details["building_power_meter"]):
                err = (f"Unable to locate building power meter using the "
                       f"tag '{self.power_meter_tag}' ")
                if self.configured_power_meter_id:
                    err = (f"Unable to locate building power meter using "
                           f"id '{self.configured_power_meter_id}' ")

                self.unmapped_device_details["building_power_meter"] = {
                    "type": "building power meter",
                    "error": err
                }

        for device_type in device_types:
            default_config = {
                "device_control_config": f"config://{device_type}_control.config",
                "device_criteria_config": f"config://{device_type}_criteria.config",
                "pairwise_criteria_config": f"config://{device_type}_criteria_matrix.json",
                "cluster_priority": 1.0
            }
            c = self.config_template.get("ilc_config").get("cluster_config")
            if c:
                default_config.update(c.pop(device_type, {}))
            self.ilc_template["clusters"].append(default_config)
        self.ilc_template.pop("cluster_config")
        # Generate ilc config file and metadata
        self.ilc_template["power_meter"]["device_topic"] = self.topic_prefix + self.power_meter_name
        self.ilc_template["power_meter"]["point"] = self.building_power_point
        file_path = os.path.abspath(os.path.join(self.output_configs, "ilc.config"))
        with open(file_path, 'w') as outfile:
            json.dump(self.ilc_template, outfile, indent=4)

        self.config_metadata_dict[self.ilc_agent_vip].append({"config-name": "config",
                                                              "config": file_path})

    def generate_control_and_criteria_config(self, device_types):

        for device_type in device_types:
            # sort the list of point before doing find and replace of volttron point name with actual point names
            # so that we avoid matching substrings. For example find and replace ZoneAirFlowSetpoint before ZoneAirFlow
            control_template = self.config_template["control_config"].get(device_type)
            if not control_template:
                raise ValueError(f"No control config template provided for device type {device_type}")

            _criteria_template = self.config_template["criteria_config"].get(device_type)
            if not control_template:
                raise ValueError(f"No criteria config template provided for device type {device_type}")
            criteria_template = {"device_topic": ""}
            criteria_template.update(_criteria_template)
            mappers = self.config_template.get('mapper_config', {})
            volttron_point_types = [x for x in self.point_meta_map[device_type]]
            volttron_point_types.sort(key=len)
            control_config = dict()
            criteria_config = dict()
            if device_type == "vav":
                vav_details = self.get_vav_ahu_map()
                if isinstance(vav_details, dict):
                    iterator = vav_details.items()
                else:
                    iterator = vav_details

                for vav_id, ahu_id in iterator:
                    config = copy.deepcopy(control_template)
                    curtail_config = {"device_topic": ""}
                    curtail_config.update(copy.deepcopy(criteria_template))
                    vav = self.get_name_from_id(vav_id)
                    if ahu_id:
                        vav_topic = self.get_name_from_id(ahu_id) + "/" + vav
                    else:
                        vav_topic = vav
                    config["device_topic"] = self.topic_prefix + vav_topic
                    curtail_config["device_topic"] = self.topic_prefix + vav_topic
                    point_mapping, missing_vav_points = self.get_point_mapping(device_type, vav_id,
                                                                               volttron_point_types)

                    if missing_vav_points:
                        # some points are missing, details in umapped_device_details skip vav and move to next
                        self.unmapped_device_details[vav_id] = {"type": device_type,
                            "error": f"Unable to find point(s) using using metadata field "
                                     f"{self.point_meta_field}. Missing "
                                     f"points and their configured mapping: {missing_vav_points}"}
                        continue

                    # If all necessary points are found go ahead and add it to control config
                    control_config[vav_topic] = {vav: self.update_control_config(config,
                                                                                 point_mapping)}
                    criteria_config[vav_topic] = {vav: self.update_criteria_config(curtail_config,
                                                                                   point_mapping)
                                                  }
            elif device_type == "lighting":
                room_lights = self.get_lights_by_room()
                if isinstance(room_lights, dict):
                    iterator = room_lights.items()
                else:
                    iterator = room_lights

                for room_id, lights in iterator:
                    config = copy.deepcopy(control_template)
                    curtail_config = {"device_topic": ""}
                    curtail_config.update(copy.deepcopy(criteria_template))
                    room_name = self.get_name_from_id(room_id)
                    room_light_topic = room_name + "_lights"
                    config["device_topic"] = self.topic_prefix + room_light_topic
                    curtail_config["device_topic"] = self.topic_prefix + room_light_topic
                    # TODO: is it enough if I get point mapping based on just 1 light
                    #  if point is ActivePowerSensor then would ilc automatically apply
                    #  same rule for all points that ends with _ActivePowerSensor in that room?
                    point_mapping, missing_points = self.get_point_mapping(device_type, lights[0],
                                                                           volttron_point_types,
                                                                           room_id=room_id)
                    # add occupancy detector points if available
                    occ_points = [x for x in self.point_meta_map.get("occupancy_detector", [])]
                    if occ_points:
                        # if we care about occupancy detector points i.e. if it is in ilc config
                        # template
                        # find the occupancy detector and its points
                        occ_detector = self.get_occ_detector(room_id)
                        occ_mapping, occ_missing_points = self.get_point_mapping("occupancy_detector",
                                                                                 occ_detector,
                                                                                 occ_points,
                                                                                 room_id=room_id)
                        #volttron_point_types.extend(occ_points)
                        point_mapping.update(occ_mapping)
                        missing_points.extend(occ_missing_points)

                    if missing_points:
                        # some points are missing, details in umapped_device_details skip vav and move to next
                        self.unmapped_device_details[room_light_topic] = {"type": "lighting",
                            "error": f"Unable to find point(s) using using metadata field "
                                     f"{self.point_meta_field}. Missing "
                                     f"points and their configured mapping: {missing_points}"}
                        continue

                    # If all necessary points are found go ahead and add it to configs
                    self.lighting_actuator_config[self.topic_prefix + room_light_topic] = (
                        self.get_lighting_points(room_id,
                                                 lights,
                                                 point_mapping['DimmingLevelOutput']))
                    control_config[room_light_topic] = {
                        room_light_topic: self.update_control_config(config, point_mapping,
                                                                     room_id, lights)}

                    criteria_config[room_light_topic] = {
                        room_light_topic: self.update_criteria_config(curtail_config,
                                                                      point_mapping,
                                                                      room_id, lights)}


            if criteria_config:
                criteria_config['mappers'] = mappers
                file_name = f"{device_type}_criteria.config"
                file_path = os.path.abspath(os.path.join(self.output_configs, file_name))
                with open(file_path, 'w') as outfile:
                    json.dump(criteria_config, outfile, indent=4)
                self.config_metadata_dict[self.ilc_agent_vip].append({"config-name": file_name,
                                                                      "config": file_path})

            if control_config:
                file_name = f"{device_type}_control.config"
                file_path = os.path.abspath(os.path.join(self.output_configs, file_name))
                with open(file_path, 'w') as outfile2:
                    json.dump(control_config, outfile2, indent=4)
                self.config_metadata_dict[self.ilc_agent_vip].append(
                    {"config-name": file_name, "config": file_path})

    def get_point_mapping(self, device_type, device_id, volttron_point_types, **kwargs) -> Tuple[
        dict,list]:
        point_mapping = dict()
        missing_points = []
        # get vav point name
        for volttron_point_type in volttron_point_types:
            point_name = self.get_point_name(device_id, device_type, volttron_point_type, **kwargs)
            if not point_name and self.point_default_map.get(device_type):
                # see if there is a default
                point_name = self.point_default_map.get(volttron_point_type, "")
            if point_name:
                point_mapping[volttron_point_type] = point_name
            else:
                if not self.unmapped_device_details.get(device_id):
                    self.unmapped_device_details[device_id] = {"type": device_type}
                missing_points.append(f"{volttron_point_type}"
                                      f"({self.point_meta_map[device_type][volttron_point_type]})")
        return point_mapping, missing_points


    def update_control_config(self, config, point_mapping, room_id=None, lights=None):
        volttron_point = config["curtail_settings"]["point"]
        # For now this is a single point due to ILC limitation
        # work around is the lighting actuator config
        config["curtail_settings"]["point"] = point_mapping[volttron_point]

        if isinstance(config["curtail_settings"]["load"], dict):
            args = config["curtail_settings"]["load"]['equation_args']
            v_conditions = [config["curtail_settings"]["load"]["operation"]]
            point_list, updated_conditions = self.substitute_point_names(
                args, v_conditions, point_mapping, room_id, lights)
            config["curtail_settings"]["load"]["equation_args"] = point_list
            config["curtail_settings"]["load"]["operation"] = updated_conditions[0]
        # More than 1 curtail possible? should we loop through?
        args = config["device_status"]["curtail"]["device_status_args"]
        v_conditions = config["device_status"]["curtail"]["condition"]
        point_list, updated_conditions = self.substitute_point_names(args, v_conditions,
                                                                     point_mapping, room_id,
                                                                     lights)
        # replace curtail values with actual point names
        config["device_status"]["curtail"]["device_status_args"] = point_list
        config["device_status"]["curtail"]["condition"] = updated_conditions
        return config

    def update_criteria_config(self, curtail_config, point_mapping, room_id=None, lights=None):
        for key, value_dict in curtail_config.items():
            if key in ["room_type", "device_topic"]:
                continue
            # else it is an operation - look for operation and operation_args and replace
            # volttron point names with actual point names

            value_dict["operation_args"], value_dict["operation"] = self.substitute_point_names(
                value_dict["operation_args"], value_dict["operation"], point_mapping, room_id,
                lights)

        return curtail_config

    def substitute_point_names(self, v_args, v_conditions, point_mapping, room_id=None,
                               lights=None):
        expand_point_names = False
        volttron_point_list =[]
        point_list = []

        # Step1 parse all v_args and collate list of volttron points and points used in conditions
        if isinstance(v_args, dict):
            args_dict = v_args
        else:
            args_dict = {"dummy": v_args}

        for k, args in args_dict.items():
            if k not in ["always", "nc", "dummy"]:
                continue
            if isinstance(args, list):
                vpoint_list = args
            elif isinstance(args, str):
                if args.startswith("LIST("):
                    vpoint_list = args[5: -1].split(",")
                    expand_point_names = True
                else:
                    vpoint_list = [args]
            else:
                raise ValueError("Invalid operation_args type. Should be string or list")

            args_dict[k] = []
            for v_point in vpoint_list:
                v_point = v_point.strip()
                volttron_point_list.append(v_point)
                point_list.append(point_mapping[v_point])
                if expand_point_names:
                    args_dict[k].extend(self.get_lighting_points(room_id, lights,
                                                                 point_mapping[v_point]))
                else:
                    args_dict[k].append(point_mapping[v_point])

        # Step2 - replace points in conditions, expand points for lighting if it is an aggregate
        # operation - currently supported - SUM(condition) or AVG(condition)

        # sort the list of point before doing find and replace of volttron point name with actual point names
        # so that we avoid matching substrings. For example find and replace ZoneAirFlowSetpoint before ZoneAirFlow
        volttron_point_list.sort(key=len)
        updated_conditions = []
        if isinstance(v_conditions, str):
            v_conditions = [v_conditions]

        for condition in v_conditions:
            for point in volttron_point_list:
                point = point.strip()
                try:
                    condition = condition.replace(point, point_mapping[point])
                except Exception as e:
                    raise Exception(f"Exception replacing point names in curtail conditions {e}")
            updated_conditions.append(condition)

        if expand_point_names:
            # args and conditions should be expanded to multiple points  # args will always be a list
            expanded_conditions = []
            for c in updated_conditions:
                if c.startswith('AVG(') or c.startswith('SUM('):
                    c_list = []
                    index_open = 3  # index of open paranthesis
                    index_close = BaseConfigGenerator.find_closing_parenthesis(c, index_open)
                    for light in lights:
                        # will start with SUM or AVG - only supported methods

                        c1 = c[4:index_close].strip()
                        if c1.find(' ') > 0:
                            # may be not a single point name but an expression. enclose in ()
                            c1 = f"({c1})"
                        for p in point_list:
                            c1 = c1.replace(p, self.get_volttron_point_name(light, point_name=p,
                                                                            equip_type="lighting"))
                        c_list.append(c1)  # condition specific to 1 light
                    if c.startswith("SUM"):
                        expanded_sum = "(" + " + ".join(c_list) + ")"
                        expanded_condition = c.replace(c[0: index_close+1], expanded_sum)
                        expanded_conditions.append(expanded_condition)
                    else:
                        expanded_avg = "((" + " + ".join(c_list)+ f")/{len(lights)})"
                        expanded_condition = c.replace(c[0: index_close+1], expanded_avg)
                        expanded_conditions.append(expanded_condition)
                else:
                    expanded_conditions.append(c)
            updated_conditions = expanded_conditions

        if isinstance(v_args, dict):
            return args_dict, updated_conditions
        else:
            return args_dict["dummy"], updated_conditions



    def generate_generate_lighting_actuator_config(self):

        if self.lighting_actuator_config:
            file_name = "lighting_actuator.config"
            file_path = os.path.abspath(os.path.join(self.output_configs, file_name))
            with open(file_path, 'w') as outfile:
                json.dump(self.lighting_actuator_config, outfile, indent=4)
            self.config_metadata_dict[self.ilc_agent_vip].append(
                {"config-name": file_name, "config": file_path})
        else:
            self.unmapped_device_details["lighting_actuator"] = {
                "type": "lighting",
                "error": f"No lighting actuator config was generated."
                         f" Config should be generated with format "
                         "{'campus/building/room1': LIST(DimmingLevelOutput), ..}"}

    @staticmethod
    def find_closing_parenthesis(s, open_pos):
        # Ensure the given position is an opening parenthesis
        if s[open_pos] != '(':
            raise ValueError(
                "The character at the given position is not an opening parenthesis.")

        # Initialize a counter for open parentheses
        open_count = 1

        # Iterate through the string starting from the next character
        for i in range(open_pos + 1, len(s)):
            if s[i] == '(':
                open_count += 1
            elif s[i] == ')':
                open_count -= 1

            # When open_count reaches zero, we found the matching closing parenthesis
            if open_count == 0:
                return i

        # If no matching closing parenthesis is found
        raise ValueError("No matching closing parenthesis found.")

    @abstractmethod
    def get_building_power_meter(self):
        pass

    @abstractmethod
    def get_building_power_point(self):
        pass

    @abstractmethod
    def get_point_name(self, equip_id, equip_type, point_key, **kwargs):
        pass

    @abstractmethod
    def get_name_from_id(self, id):
        pass

    @abstractmethod
    def get_vav_ahu_map(self):
        """
        Should return vavs with its corresponding ahu
        :return: list of tuples with the format [(va1, ahu1), (vav2,ahu1),...]
                 or dict mapping vav to ahu with format
                 {'vav1':'ahu1', 'vav2':'ahu1',...}
        """
        pass

    def get_lights_by_room(self):
        # not all implementation might have lighting info
        # return empty dict
        # specific implementations should override
        return dict()

    def get_occ_detector(self, room_id):
        # not all implementation might have lighting info
        # return None
        # specific implementations should override
        return None

    def get_volttron_point_name(self, reference_point_name, **kwargs):
        return reference_point_name

    def get_lighting_points(self, room_id, lights, point_name)->list[str]:
        pass
