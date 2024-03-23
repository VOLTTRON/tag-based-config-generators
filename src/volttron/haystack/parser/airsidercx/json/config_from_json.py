import copy
import json
import re
from collections import defaultdict
import sys

from volttron.haystack.parser.airsidercx.config_base import \
    AirsideRCxConfigGenerator


class JsonAirsideRCxConfigGenerator(AirsideRCxConfigGenerator):
    """
    Class that parses haystack tags from two json files - one containing tags
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


    def get_ahu_and_vavs(self):
        rows = self.equip_json['rows']
        vav_list = []
        ahu_dict = defaultdict(list)
        for _d in rows:
            id_list = _d["id"].split(".")
            device = id_list[-1] if id_list else ""
            if "vav" in _d:  # if it is tagged as vav
                vav_list.append(_d)
                ahu_id = _d.get("ahuRef")
                if ahu_id:
                    ahu_dict[ahu_id].append(_d["id"])
                else:
                    # add to list of unmapped devices
                    self.unmapped_device_details[_d["id"]] = {"type": "vav", "error": "Unable to find ahuRef"}
                self.vav_list.append(_d["id"])
        self.ahu_list.extend(ahu_dict.keys())
        # ahu without vav not relevant for AirsideRcx
        return ahu_dict

    # Should be overridden for different sites if parsing logic is different
    # Parsing logic could also depend on equip type
    def get_point_name_from_topic(self, topic, equip_id=None,
                                  equip_type=None):
        point_name_part = topic.split("/")[-1]
        return point_name_part
        # return re.split(r"[\.|:]", point_name_part)[-1]

    def get_point_name(self, equip_id, equip_type, point_type_meta):
        if not self.equip_id_point_map:
            # Load it once and use it from map from next call
            rows = self.points_json['rows']
            for _d in rows:
                if not _d.get(self.point_meta_field):
                    # if there is no point type information this point is
                    # not useful to us skip
                    continue

                id_list = _d["id"].split(".")
                device = id_list[-2] if id_list else ""
                equip_ref = _d["equipRef"]
                if equip_ref in self.vav_list:
                    interested_point_types = self.vav_point_types
                    mandatory_point_types = self.vav_mandatory_types
                elif equip_ref in self.ahu_list:
                    interested_point_types = self.ahu_point_types
                    mandatory_point_types = self.ahu_mandatory_types
                else:
                    continue
                # if vav or ahu point
                # check if it is a point type we are interested in
                point_type = _d[self.point_meta_field]
                if point_type in interested_point_types:
                    # save the topic name - if none of the mandatory point are available, this topic name
                    # would be logged in unmapped devices file
                    if not self.equip_id_point_topic_map.get(equip_ref):
                        self.equip_id_point_topic_map[equip_ref] = dict()
                    self.equip_id_point_topic_map[equip_ref][point_type] = _d["topic_name"]
                    if not self.equip_id_point_map.get(equip_ref):
                        self.equip_id_point_map[equip_ref] = dict()
                    point_name = self.get_point_name_from_topic(_d["topic_name"])
                    if point_name:
                        self.equip_id_point_map[equip_ref][point_type] = point_name
                    elif point_type == self.point_meta_map["zone_damper"]:
                            self.unmapped_device_details[equip_ref] = {
                                "type": "vav",
                                "error": "Warning. Unable to parse point name from topic name",
                                "topic_name": _d["topic_name"]}
        point_type = self.point_meta_map[point_type_meta]
        point_name = self.equip_id_point_map[equip_id].get(point_type, "")
        return point_name

    def get_name_from_id(self, id):
        name = id.split(".")[-1]
        return name

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = JsonAirsideRCxConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
