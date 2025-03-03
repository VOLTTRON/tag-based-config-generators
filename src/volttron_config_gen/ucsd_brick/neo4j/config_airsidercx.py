import sys
from collections import defaultdict

from volttron_config_gen.base.config_airsidercx import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import Neo4jConnection, query_points_for_equip


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    airsidercx agent configuration
    """
    def __init__(self, config):
        super().__init__(config)

        # get details on metadata neo4jdb
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"], connect_params["user"],
                                          connect_params["password"])

        self.point_meta_map = self.config_dict.get("point_meta_map")
        # Use label always
        #self.point_meta_field = self.config_dict.get("point_meta_field", "label")
        self.equip_point_label_name_map = dict()


    def get_ahu_and_vavs(self):
        ahu_dict = defaultdict(list)
        # TODO: ADD relationship to configured building name once model is updated
        #  current model is missing relationship between building and room/equipment
        query = ("MATCH (a:AHU)-[:feeds]->(v:VAV) "
                 "RETURN a.name, v.name;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[r[0]].append(r[1])
        # ahu without vavs and vav without ahuref are not applicable for AirsideRCx
        return ahu_dict


    def get_point_name(self, equip_id, equip_type, point_key):
        point_labels = self.point_meta_map[point_key]
        ## TODO: validate point_label, equip_id for valid characters length?
        ##  possible sql injection issue but no way to send parameterized query for query by labels
        interested_point_types = []
        if equip_type.upper() == "AHU":
            interested_point_types = self.volttron_point_types_ahu
        elif equip_type.upper() == "VAV":
            interested_point_types = self.volttron_point_types_vav
        else:
            raise ValueError(f"Unknown equipment type {equip_type}")

        # instead of querying single point at a time, get all interested points at a time.
        # querying single point at a time seems to take long with neo4j. may be because the
        # example db doesn't have any indexes?
        #return query_point_name(equip_id, equip_type.upper(), point_labels, self.connection)
        if not self.equip_point_label_name_map or not self.equip_point_label_name_map.get(equip_id):
            self.equip_point_label_name_map[equip_id] = query_points_for_equip(equip_id, equip_type,
                                                                               interested_point_types,
                                                                               self.point_meta_map,
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
