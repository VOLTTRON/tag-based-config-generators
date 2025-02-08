import sys

from volttron_config_gen.base.config_economizer import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import Neo4jConnection, get_points_for_equip


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
        self.equip_point_label_name_map = dict()

    def get_ahus(self):
        ahus = []
        # TODO: Update query with building name after model is updated.
        #  current model is missing relationship between building and room/equipment
        query = "MATCH (a:AHU) RETURN a.name;"
        result = self.connection.query(query)
        if result:
            for r in result:
                ahus.append(r[0])
        return ahus

    def get_point_name(self, equip_id, equip_type, point_key):
        if not equip_type or equip_type.upper() != "AHU":
            raise ValueError(f"Unknown equipment type {equip_type}")

        if not self.equip_point_label_name_map or not self.equip_point_label_name_map.get(equip_id):
            self.equip_point_label_name_map[equip_id] = get_points_for_equip(
                equip_id, equip_type, self.point_meta_map.keys(), self.point_meta_map,
                self.connection)

        # Done finding interested points for a given equip id
        return self.equip_point_label_name_map[equip_id].get(point_key)

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
