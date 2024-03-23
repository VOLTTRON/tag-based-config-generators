import copy
import json
import re
from collections import defaultdict
import sys

from volttron.haystack.parser.airside_economizer.config_base import \
    AirsideEconomizerConfigGenerator


class JsonAirsideEconomizerConfigGenerator(AirsideEconomizerConfigGenerator):
    """
    Class that parses haystack tags from two jsonfile files - one containing tags
    for equipments/devices and another containing haystack tags for points
    This is a reference implementation to show case airsidercx agent config
    generation based on haystack tags. This class can be extended and
    customized for specific device types and configurations
    """

    def __init__(self, config):
        super().__init__(config)
        # get details on haystack metadata
        metadata = self.config_dict.get("metadata")
        try:
            with open(metadata.get("equip_json"), "r") as f:
                self.equip_json = json.load(f)
            with open(metadata.get("points_json"), "r") as f:
                self.points_json = json.load(f)
        except Exception:
            raise
        # Initialize map of haystack id and nf device name
        self.equip_id_point_map = dict()
        self.equip_id_device_id_map = dict()
        # List of all ahus equip ids
        self.ahu_list = []
        # List of all vav equip ids
        self.vav_list = []

        self.point_meta_map = self.config_dict.get("point_meta_map")
        self.point_meta_field = self.config_dict.get("point_meta_field",
                                                     "miniDis")
        self.interested_point_types = []

    def get_ahus(self):
        rows = self.equip_json['rows']
        for _d in rows:
            id_list = _d["id"].split(".")
            device = id_list[-1] if id_list else ""
            if "ahu" in _d:  # if it is tagged as ahu
                self.ahu_list.append(_d["id"])
        return self.ahu_list

    # Should be overridden for different sites if parsing logic is different
    # Parsing logic could also depend on equip type
    def get_point_name_from_topic(self, topic, equip_id=None,
                                  equip_type=None):
        point_name_part = topic.split("/")[-1]
        return point_name_part
        # return re.split(r"[\.|:]", point_name_part)[-1]

    def get_point_name(self, equip_id, equip_type, point_type_meta):
        if not self.equip_id_point_map:
            for p in self.point_meta_map.values():
                if isinstance(p, str):
                    self.interested_point_types.append(p)
                else:
                    self.interested_point_types.extend(p)
            # Load it once and use it from map from next call
            rows = self.points_json['rows']
            for _d in rows:
                if _d["id"] == "r:@intellimation.dc_dgs.dcps.anacostia_hs.eru-d1_s-wing.onrly1":
                    print("r:@intellimation.dc_dgs.dcps.anacostia_hs.eru-d1_s-wing.onrly1")
                if not _d.get(self.point_meta_field):
                    # if there is no point type information this point is
                    # not useful to us skip
                    continue
                equip_ref = _d["equipRef"]
                id_list = _d["id"].split(".")
                device = id_list[-2] if id_list else ""
                # if this is a ahu point
                point_type = _d[self.point_meta_field]
                if equip_ref in self.ahu_list:
                    if not self.equip_id_point_map.get(equip_ref):
                        self.equip_id_point_map[equip_ref] = dict()
                    # and if it is a point type we are interested in
                    if point_type in self.interested_point_types:
                        # save the topic name - if none of the mandatory point are available, this topic name
                        # would be logged in unmapped devices file
                        if not self.equip_id_point_topic_map.get(equip_ref):
                            self.equip_id_point_topic_map[equip_ref] = dict()
                        self.equip_id_point_topic_map[equip_ref][point_type] = _d["topic_name"]
                        self.equip_id_point_map[equip_ref][point_type] = \
                            self.get_point_name_from_topic(_d["topic_name"])

        point_types = self.point_meta_map[point_type_meta]
        point_name = ""
        if isinstance(point_types, str):
            point_name = self.equip_id_point_map[equip_id].get(point_types, "")
        else:
            for point_type in point_types:
                point_name = self.equip_id_point_map[equip_id].get(point_type, "")
                if point_name:
                    break
        return point_name


def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = JsonAirsideEconomizerConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
