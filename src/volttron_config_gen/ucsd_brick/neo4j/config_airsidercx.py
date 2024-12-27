import sys
from collections import defaultdict
from unittest.loader import VALID_MODULE_NAME

import psycopg2

from volttron_config_gen.base.config_airsidercx import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import Neo4jConnection


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    airsidercx agent configuration
    """
    def __init__(self, config):
        super().__init__(config)

        # get details on haystack3 metadata
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"], connect_params["user"],
                                          connect_params["password"])

        self.point_meta_map = self.config_dict.get("point_meta_map")
        # Use label always
        #self.point_meta_field = self.config_dict.get("point_meta_field", "label")

        # Initialize point mapping for airsidercx config
        self.point_mapping = {x: [] for x in self.point_meta_map.keys()}
        self.volttron_point_types_ahu = ["fan_status", "duct_stcpr", "duct_stcpr_stpt",
                           "sa_temp", "sat_stpt", "fan_speedcmd"]
        self.volttron_point_types_vav = ["zone_reheat", "zone_damper"]

    def get_ahu_and_vavs(self):
        ahu_dict = defaultdict(list)
        query = ("MATCH "
                 "(c1:`Bacnet Controller`)-[:controls]->(a:AHU)-[:feeds]->(v:VAV)<-[:controls]-(c2:`Bacnet Controller`)  "
                 "RETURN a.name, c1.`IP Address`, c1.`Device Object Identifier`, "
                 "v.name, c2.`IP Address`, c2.`Device Object Identifier`;")
        result = self.connection.query(query)
        self.unmapped_device_details["ahus without device id/address"] = []
        self.unmapped_device_details["vavs without device id/address"] = []
        if result:
            for r in result:
                if r[1] and r[2] and r[4] and r[5]:
                    # if device address and device id  are not present skip those as
                    # driver won't be collecting data for those anyway.
                    ahu_dict[r[0]].append(r[3])
                elif not r[1] or not r[2]:
                    self.unmapped_device_details["ahus without device id/address"].append(r[0])
                elif not r[4] or not r[5]:
                    self.unmapped_device_details["vavs without device id/address"].append(r[3])

        # ahu without vavs and vav without ahuref are not applicable for AirsideRCx
        if not self.unmapped_device_details["vavs without device id/address"]:
            del self.unmapped_device_details["vavs without device id/address"]
        if not self.unmapped_device_details["ahus without device id/address"]:
            del self.unmapped_device_details["ahus without device id/address"]
        return ahu_dict


    def get_point_name(self, equip_id, equip_type, point_key):
        point_label = self.point_meta_map[point_key]
        # possible sql injection issue but no way to send parameterized query to cypher
        ## TODO: validate point_label, equip_id for valid characters length?

        if equip_type not in ["AHU", "VAV"]:
            raise ValueError(f"Unknown equipment type {equip_type}")
        query = ("MATCH "
                 f"(p:{point_label})-[:isPointOf]->(e:{equip_type}" "{name:'" f"{equip_id}" "'}) "
                 "RETURN p.name;")
        print(f"{query}")
        result = self.connection.query(query)
        if result:
            return result[0][0]
        return None

    def get_name_from_id(self, _id):
        return _id

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
