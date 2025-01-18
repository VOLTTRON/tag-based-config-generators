import sys

from volttron_config_gen.base.config_economizer import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import Neo4jConnection, query_point_name


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    AirsideEconomizer agent configuration
    """

    def __init__(self, config):
        super().__init__(config)

        # get details on metadata neo4jdb
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"], connect_params["user"],
                                          connect_params["password"])

    def get_ahus(self):
        ahus = []
        query = ("MATCH "
                 "(c1:`Bacnet Controller`)-[:controls]->(a:AHU) "
                 "RETURN a.name, c1.`IP Address`, c1.`Device Object Identifier`;")
        result = self.connection.query(query)
        self.unmapped_device_details["ahus without device id/address"] = []
        if result:
            for r in result:
                if r[1] and r[2]:
                    # if device address and device id  are not present skip those as
                    # driver won't be collecting data for those anyway.
                    ahus.append(r[0])
                elif not r[1] or not r[2]:
                    self.unmapped_device_details["ahus without device id/address"].append(r[0])

        # ahu without vavs and vav without ahuref are not applicable for AirsideRCx
        if not self.unmapped_device_details["ahus without device id/address"]:
            del self.unmapped_device_details["ahus without device id/address"]
        return ahus

    def get_point_name(self, equip_id, equip_type, point_key):
        point_labels = self.point_meta_map[point_key]
        # possible sql injection issue but no way to send parameterized query to cypher
        ## TODO: validate point_label, equip_id for valid characters length?

        if not equip_type or equip_type.upper() not in ["AHU", "VAV"]:
            raise ValueError(f"Unknown equipment type {equip_type}")
        return query_point_name(equip_id, equip_type.upper(), point_labels, self.connection)

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
