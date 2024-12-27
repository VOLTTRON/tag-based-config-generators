import json
import copy
import os.path
import sys
from abc import abstractmethod
from volttron_config_gen.utils import strip_comments


class BaseConfigGenerator:
    """
    Base class that parses semantic tags to generate
    Airside Economizer agent configuration based on a configuration template
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

        # If there are AHUs without the right point details
        # use this dict to give additional details for user to help manually find the issue.
        # All points are mandatory for airside economizer
        self.unmapped_device_details = dict()
        # For all unmapped devices add topic name details to this variable for error reporting
        self.equip_id_point_topic_map = dict()

        self.config_template = self.config_dict.get("config_template")
        self.config_template["device"] = {
            "campus": self.campus,
            "building": self.building,
            "unit": {}
        }
        # initialize output dir
        default_prefix = self.building + "_" if self.building else ""
        self.output_dir = self.config_dict.get(
            "output_dir", f"{default_prefix}economizer_configs")
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

        self.agent_vip_prefix = self.config_dict.get("agent_vip_prefix", "economizer")

        self.point_meta_map = self.config_dict.get("point_meta_map")
        self.point_meta_field = self.config_dict.get("point_meta_field", "miniDis")
        self.point_default_map = self.config_dict.get("point_default_map", dict())
        # Initialize point mapping for airsidercx config
        self.point_mapping = {x: "" for x in self.point_meta_map.keys()}

    @abstractmethod
    def get_ahus(self):
        """
        Should return a list of ahus
        :return: list of ahu ids
        """
        pass

    def generate_configs(self):
        config_metadata = dict()
        results = self.get_ahus()

        for ahu in results:
            if isinstance(ahu, list):
                # results from db. list of rows, where each element in list is list of columns queried
                ahu_id = ahu[0]
            else:
                ahu_id = ahu
            ahu_name, result_dict = self.generate_ahu_configs(ahu_id)

            if result_dict:
                config_file_name = os.path.abspath(f"{self.output_configs}/{ahu_name}.json")
                with open(config_file_name, 'w') as outfile:
                    json.dump(result_dict, outfile, indent=4)
                config_metadata[f'{self.agent_vip_prefix}.{ahu_name}'] = [{"config": config_file_name}]

        if config_metadata:
            config_metafile_name = f"{self.output_dir}/config_metadata.json"
            with open(config_metafile_name, 'w') as f:
                json.dump(config_metadata, f, indent=4)

        if self.unmapped_device_details:
            err_file_name = f"{self.output_errors}/unmapped_device_details"
            with open(err_file_name, 'w') as outfile:
                json.dump(self.unmapped_device_details, outfile, indent=4)

            sys.stderr.write(f"\nUnable to generate configurations for all AHUs. "
                             f"Please see {err_file_name} for details\n")
            sys.exit(1)
        else:
            sys.exit(0)

    def generate_ahu_configs(self, ahu_id):
        final_config = copy.deepcopy(self.config_template)
        ahu = self.get_name_from_id(ahu_id)
        final_config["device"]["unit"] = {}
        final_config["device"]["unit"][ahu] = {}
        final_config["device"]["unit"][ahu]["subdevices"] = list()
        point_mapping = final_config["arguments"]["point_mapping"]
        missing_points = []
        default_points = []
        # Get ahu point details
        for volttron_point_type in self.point_meta_map.keys():
            point_name = self.get_point_name(ahu_id, "ahu", volttron_point_type)
            if point_name:
                point_mapping[volttron_point_type] = point_name
            elif self.point_default_map.get(volttron_point_type):
                point_mapping[volttron_point_type] = self.point_default_map.get(volttron_point_type)
                default_points.append(f"{volttron_point_type}({self.point_meta_map[volttron_point_type]})")
            else:
                missing_points.append(f"{volttron_point_type}({self.point_meta_map[volttron_point_type]})")

        if missing_points or default_points:
            self.unmapped_device_details[ahu_id] = {"type": "ahu"}
            if default_points:
                self.unmapped_device_details[ahu_id]["warning"] = (
                    f"Unable to find points using "
                    f"metadata field {self.point_meta_field} but found "
                    f"default point names. Using default point names "
                    f"Missing points and their configured mapping: "
                    f"{default_points}")
            if self.equip_id_point_topic_map.get(ahu_id):
                self.unmapped_device_details[ahu_id]["topic_name"] = self.equip_id_point_topic_map.get(ahu_id)
        if missing_points:
            self.unmapped_device_details[ahu_id]["error"] = (
                f"Unable to find points using "
                f"metadata field {self.point_meta_field}. "
                f"Missing points and their configured mapping: "
                f"{missing_points}")
            return ahu, None
        else:
            return ahu, final_config

    @abstractmethod
    def get_point_name(self, equip_id, equip_type, point_key):
        pass

    @abstractmethod
    def get_name_from_id(self, id):
        pass
