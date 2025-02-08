import sys

from volttron_config_gen.base.config_ilc import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import Neo4jConnection, get_points_for_equip


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    ILC agent configurations
    """

    def __init__(self, config):
        super().__init__(config)

        # get details on metadata neo4jdb
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"], connect_params["user"],
                                          connect_params["password"])
        self.vav_ahu_list = list()
        self.equip_point_label_name_map = dict()

    def get_building_power_meter(self):
        # if self.configured_power_meter_id:
        #     query = f"SELECT tags->>'id' \
        #               FROM {self.equip_table} \
        #               WHERE tags->>'id' = '{self.configured_power_meter_id}'"
        # else:
        #     query = f"SELECT tags->>'id' \
        #                           FROM {self.equip_table} \
        #                           WHERE tags->>'{self.power_meter_tag}' is NOT NULL"
        # if self.site_id:
        #     query = query + f" AND tags->>'siteRef'='{self.site_id}' "
        # print(query)
        #
        # result = self.execute_query(query)
        # if result:
        #     if len(result) == 1:
        #         return result[0][0]
        #     if len(result) > 1 and not self.configured_power_meter_id:
        #         raise ValueError(f"More than one equipment found with the tag {self.power_meter_tag}. Please "
        #                          f"add 'power_meter_id' parameter to configuration to uniquely identify whole "
        #                          f"building power meter")
        #     if len(result) > 1 and self.configured_power_meter_id:
        #         raise ValueError(f"More than one equipment found with the id {self.configured_power_meter_id}. Please "
        #                          f"add 'power_meter_id' parameter to configuration to uniquely identify whole "
        #                          f"building power meter")
        # return ""
        # TODO
        return ""

    def get_building_power_point(self):
        point_name = ""
        if self.power_meter_id:
            point_name = self.get_point_name(self.power_meter_id, "power_meter", "WholeBuildingPower")

        if self.unmapped_device_details.get(self.power_meter_id):
            # Could have been more than 1 point name.
            return ""
        else:
            return point_name

    def get_vav_ahu_map(self):
        # TODO: Update query with building name configured
        #  current model is missing relationship between building and room/equipment
        if not self.vav_ahu_list:
            q = "MATCH (a:AHU)-[:feeds]->(v:VAV) RETURN v.name, a.name;"
            result = self.connection.query(q)
            if result:
                self.vav_ahu_list = result
        return self.vav_ahu_list


    def get_point_name(self, equip_id, equip_type, point_key):
        if not equip_type or equip_type.upper() not in ["AHU", "VAV", "POWER_METER"]:
            raise ValueError(f"Unknown equipment type {equip_type}")

        if not self.equip_point_label_name_map or not self.equip_point_label_name_map.get(equip_id):
            self.equip_point_label_name_map[equip_id] = get_points_for_equip(
                equip_id, equip_type, self.volttron_point_types_vav, self.point_meta_map,
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
