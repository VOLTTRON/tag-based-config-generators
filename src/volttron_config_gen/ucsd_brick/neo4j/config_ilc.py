import sys
from collections import defaultdict

from volttron_config_gen.base.config_ilc import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import (Neo4jConnection,
                                                              query_points_for_equip,
                                                              query_lights_from_room,
                                                              query_occupancy_detector)


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
                                          connect_params["password"], connect_params["database"])
        self.vav_ahu_list = list()
        self.equip_point_label_name_map = dict()

    def get_building_power_meter(self):
        # TODO current model doesn't have building power meter. Update after model is updated
        # Example query based on  example from https://docs.brickschema.org/modeling/meters.html
        #     bldg:building_power_sensor a brick:Electric_Power_Sensor ;
        #         brick:hasUnit unit:KiloW ;
        #         brick:isPointOf bldg:main-meter ;
        #         brick:timeseries [ brick:hasTimeseriesId "fd64fbc8-0742-4e1e-8f88-e2cd8a3d78af" ] .
        #
        #     bldg:mybldg a brick:Building ;
        #         brick:isMeteredBy bldg:main-meter .
        #     bldg:main-meter a brick:Building_Electrical_Meter .

        # Query model (modification - would it be directly linked to building or a room in a
        # building?)
        # q = ("MATCH (e:Building_Electrical_Meter)-[:hasLocation]-(b:Building) "
        #      "WHERE b.name = $building"
        #      "RETURN e.name;")
        # result = self.connection.query(q, parameters={'building':self.building})
        # if result:
        #     return result[0][0]
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
        # TODO: Update query with building name configured (self.building)
        #  current model is missing relationship between building and room/equipment
        if not self.vav_ahu_list:
            q = "MATCH (a:AHU)-[:feeds]->(v:VAV) RETURN v.name, a.name;"
            result = self.connection.query(q)
            if result:
                self.vav_ahu_list = result
        return self.vav_ahu_list


    def get_point_name(self, equip_id, equip_type, point_key, **kwargs):
        if not equip_type or equip_type not in ["ahu", "vav", "power_meter", "lighting",
                                                "occupancy_detector"]:
            raise ValueError(f"Unknown equipment type {equip_type}")
        if not equip_id:
            return None
        if not self.equip_point_label_name_map or not self.equip_point_label_name_map.get(equip_id):
            self.equip_point_label_name_map[equip_id] = query_points_for_equip(
                equip_id, equip_type, self.point_meta_map[equip_type].keys(),
                self.point_meta_map[equip_type], self.connection, **kwargs)

        # Done finding interested points for a given equip id
        return self.equip_point_label_name_map[equip_id].get(point_key)

    def get_name_from_id(self, _id):
        return _id


    def get_lights_by_room(self):
        room_dict = defaultdict(list)
        # Only get lights where there is valid controller ip and controller id\
        # TODO- update query once controller is broken into a separate node similar to VAVs
        result = query_lights_from_room(self.connection)
        if result:
            for r in result:
                room_dict[r[0]].append(r[1])
        return room_dict

    def get_occ_detector(self, room_id):
        occ_id, device_addr, device_id = query_occupancy_detector(room_id, self.connection)
        return occ_id

    def get_volttron_point_name(self, reference_point_name, **kwargs):
        p = kwargs.get("point_name", None)
        if p:
            if kwargs.get("equip_type", "unknown") in ["lighting", "occupancy_detector"]:
                return f"{p}__{reference_point_name.split('_')[0]}"
            else:
                return p
        else:
            return reference_point_name

    def get_lighting_points(self, room_id, devices, point_name)->list[str]:
        return [self.get_volttron_point_name(l, point_name=point_name, equip_type="lighting") for
                l in devices]

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
