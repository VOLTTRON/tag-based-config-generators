import copy
import csv
import os
import sys
import re
from collections import defaultdict

from volttron_config_gen.base.config_driver import BaseConfigGenerator
from volttron_config_gen.ucsd_brick.neo4j.neo4j_utils import (Neo4jConnection,
                                                              query_lights_from_room,
                                                              query_occupancy_detector)


class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    platform driver configuration for driver
    """
    def __init__(self, config):
        super().__init__(config)

        # get details on neo4j metadata db
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"],
                                          connect_params["user"],
                                          connect_params["password"])
        self.device_details = {"ahu": defaultdict(dict),
                               "vav": defaultdict(dict),
                               "electric_meter": defaultdict(dict),
                               "lighting": defaultdict(dict),
                               "occupancy_detector": defaultdict(dict)}
        self.max_group_vav = 0
        self.group_device_count = {}

    def get_ahu_and_vavs(self):
        ahu_dict = defaultdict(list)
        # 1. Query for vavs that are mapped to ahu
        # query = ("MATCH (a:AHU)-[:feeds]->(v:VAV) "
        #          "RETURN a.name, a.`Remote Station IP`, a.`BACnet Device Object Identifier`, "
        #          "v.name, v.`Remote Station IP`, v.`BACnet Device Object Identifier`;")
        query = (
            "MATCH "
            "(c1:`Bacnet Controller`)-[:controls]->(a:AHU)-[:feeds]->(v:VAV)<-[:controls]-(c2:`Bacnet Controller`)  "
            "RETURN a.name, c1.`IP Address`, c1.`Device Object Identifier`, "
            "v.name, v.trunkId, c2.`IP Address`, c2.`Device Object Identifier`;"
        )
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[r[0]].append(r[3])
                grpnum = int(r[4][-1:])
                self.device_details["ahu"][r[0]]["device_address"]= r[1]
                self.device_details["ahu"][r[0]]["device_id"] = r[2]
                self.device_details["vav"][r[3]]["group"] = grpnum
                if self.group_device_count.get(grpnum):
                    self.group_device_count[grpnum] = self.group_device_count[grpnum] + 1
                else:
                    self.group_device_count[grpnum] = 1
                self.max_group_vav = self.max_group_vav if (self.max_group_vav >
                                                            grpnum) else grpnum
                self.device_details["vav"][r[3]]["device_address"]= r[5]
                self.device_details["vav"][r[3]]["device_id"] = r[6]

        # 2. Query for ahus without vavs
        # append to result
        query = ("MATCH "
                 "(c1:`Bacnet Controller`)-[:controls]->(a:AHU) WHERE not ((a)-[:feeds]->(:VAV)) "
                 "RETURN a.name, c1.`IP Address`, c1.`Device Object Identifier`;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[r[0]] = []
                self.device_details["ahu"][r[0]]["device_address"]= r[1]
                self.device_details["ahu"][r[0]]["device_id"] = r[2]

        # 3. query for vavs without
        # if exists add to self.unmapped_device_details
        query = ("MATCH (v:VAV)<-[:controls]-(c2:`Bacnet Controller`)  WHERE not ((:AHU)-[:feeds]->(v)) "
                 "RETURN v.name, c2.`IP Address`, c2.`Device Object Identifier`;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[""].append(r[0])
                self.device_details["vav"][r[0]]["device_address"]= r[1]
                self.device_details["vav"][r[0]]["device_id"] = r[2]
                self.unmapped_device_details[r[0]] = {"type": "vav",
                                                      "error": "Unable to find AHU that feeds vav"}
        return ahu_dict

    def get_lights_by_room(self):
        room_dict = defaultdict(list)
        # Only get lights where there is valid controller ip and controller id\
        # TODO- update query once controller is broken into a separate node similar to VAVs
        result = query_lights_from_room(self.connection)
        if result:
            for r in result:
                room_dict[r[0]].append(r[1])
                # for lighting we assume all lights in room are controlled by 1 controller
                # hence store device id and ip under room id and generate 1 device and registry
                # config per room
                if not self.device_details["lighting"].get(r[0]):
                    self.device_details["lighting"][r[0]]["device_address"]= r[2]
                    self.device_details["lighting"][r[0]]["device_id"] = r[3]
                    grpnum = int(r[3][-1:]) + self.max_group_vav
                    self.device_details["lighting"][r[0]]["group"] = grpnum
                    if self.group_device_count.get(grpnum):
                        self.group_device_count[grpnum] = self.group_device_count[grpnum] + 1
                    else:
                        self.group_device_count[grpnum] = 1
        return room_dict

    def get_occupancy_detector(self, room_id):
        occ_id, device_addr, device_id = query_occupancy_detector(room_id, self.connection)
        if occ_id:
            if not self.device_details["lighting"].get(room_id):
                self.device_details["lighting"][room_id]["device_address"] = device_addr
                self.device_details["lighting"][room_id]["device_id"] = device_id
        return occ_id

    def get_building_meter(self):
        raise ValueError("Not implemented")
        # if self.configured_power_meter_id:
        #     # query = f"SELECT tags->>'id' \
        #     #           FROM {self.equip_table} \
        #     #           WHERE tags->>'id' = '{self.configured_power_meter_id}'"
        # else:
        #     # query = f"SELECT tags->>'id' \
        #     #                       FROM {self.equip_table} \
        #     #                       WHERE tags->>'{self.power_meter_tag}' is NOT NULL"
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
        # raise ValueError(f"Unable to find building power meter using power_meter_tag {self.power_meter_tag} or "
        #                  f"configured power_meter_id {self.configured_power_meter_id}")


    def generate_config_from_template(self, equip_id, equip_type):
        _device_details = self.device_details.get(equip_type)
        if not _device_details:
            raise ValueError(f"Unknown device type {equip_type}")
        _equip = _device_details.get(equip_id)
        if not _equip:
            raise ValueError(f"Unknown device {equip_id}")

        device_address = _equip.get("device_address")
        device_id = _equip.get("device_id")

        driver = copy.deepcopy(self.config_template)

        if device_id and device_address:
            driver["driver_config"]["device_address"] = device_address
            driver["driver_config"]["device_id"] = device_id
            if equip_type =="ahu" or equip_type == "meter":
                driver["group"] = 0
            else:
                driver["group"] = _equip.get("group")
        else:
            if not self.unmapped_device_details.get(equip_id):
                self.unmapped_device_details[equip_id] = dict()
            self.unmapped_device_details[equip_id]["type"] = equip_type
            self.unmapped_device_details[equip_id]["error"] = ("Unable to get device address and "
                                                               f"id for {equip_id}. "
                                                               f"Got device address from db "
                                                               f"as {device_address}. "
                                                               f"Got device id from db as "
                                                               f"{device_id}")
            return None

        return driver

    def get_name_from_id(self, _id):
        return _id

    def generate_registry_config_file(self, equip_id, equip_type, data=None):
        header = ["Reference Point Name", "Volttron Point Name", "Units", "BACnet Object Type",
                  "Property", "Writable", "Index", "Notes"]
        if not data:
            data = self.generate_registry_config_data(equip_id, equip_type)
        if data:
            filename = os.path.join(self.output_configs,f"registry_{equip_id}.csv")
            with open(filename, "w") as csvfile:
                writer = csv.writer(csvfile, lineterminator='\n')
                writer.writerow(header)
                writer.writerows(data)
            return filename, "csv"
        return None, None

    def generate_registry_config_data(self, equip_id, equip_type, **kwargs):
        # TODO update for building electring meter once model is updated
        _notes = "auto generated"
        _property = "presentValue"
        query = None
        query_parameters = None
        if equip_type in ["ahu", "vav"]:
            db_type = equip_type.upper()
        elif equip_type == "electric_meter":
            db_type = None  # TODO
        elif equip_type == "lighting":
            # TODO- is equip id unique globally- i.e. across rooms and controllers? If so
            #  we could get rid of the special query with additional room match
            db_type = "Luminaire"
            room_id = kwargs.get("room_id")
            if not room_id:
                raise ValueError("No room_id provided for equip_type lighting")
                # TODO: Use may be controllerid_ballastid_ as the unique prefix?
            if equip_id.split("_")[0] == "B5B3":
                print("Skipping lights with balast id B5B3. As this id is not unique")
                return []
            query = (f"MATCH (p:Point)-[isPointOf]->(e:{db_type})-[:hasLocation]->(r:Room) "
                     f"WHERE e.name STARTS WITH $equip_id AND r.name=$room_id "
                     "RETURN p.`BACnet Object Name`, p.name, p.units, p.type, p.`BACnet Object "
                     "Identifier`;")
            query_parameters = {'equip_id': equip_id, 'room_id': room_id}
        elif equip_type == "occupancy_detector":
            # TODO- is equip id unique globally- i.e. across rooms and controllers? If so
            #  we could get rid of the special query with additional room match
            db_type = "OccupancyDetector"
            room_id = kwargs.get("room_id")
            if not room_id:
                raise ValueError("No room_id provided for equip_type occupancy_detector")
            query = (f"MATCH (p:Point)-[isPointOf]->(e:{db_type})-[:hasLocation]->(r:Room) "
                     f"WHERE e.name STARTS WITH $equip_id AND r.name=$room_id "
                     "RETURN p.`BACnet Object Name`, p.name, p.units, p.type, p.`BACnet Object "
                     "Identifier`;")
            query_parameters = {'equip_id': equip_id, 'room_id': room_id}
        else:
            raise ValueError(f"Unknown equipment type {equip_type}")

        if query is None:
            # default query only based on equip type label and equip id
            query = (f"MATCH(p:Point)-[isPointOf]->(e:{db_type}) "
                     f"WHERE e.name = $equip_id "
                     "RETURN p.`BACnet Object Name`, p.name, p.units, p.type, p.`BACnet Object "
                     "Identifier`;")
            query_parameters = {'equip_id': equip_id}
        result = self.connection.query(query, query_parameters)
        missing = []
        data = []
        if result:
            for r in result:
                if r[0] and r[1] and r[2] and r[3] and r[4]:
                    reference_point_name = r[0]
                    point_name = r[1]
                    units = r[2]
                    point_type = r[3]
                    point_type = point_type[0].lower() + point_type[1:]
                    # All Input types - AnalogInput, BinaryInput etc. are NOT writeable
                    writeable = False if point_type.endswith("Input") else True
                    index = r[4].split(":")[1]
                    data.append(
                        [reference_point_name, self.get_volttron_point_name(reference_point_name,
                                                                            point_name=point_name,
                                                                            equip_type=equip_type,
                                                                            **kwargs),
                         units, point_type,
                         _property, writeable, index,
                         _notes])
                else:
                    missing.append(r[1])
            if missing:
                if not self.unmapped_device_details.get(equip_id):
                    self.unmapped_device_details[equip_id] = dict()
                self.unmapped_device_details[equip_id]["type"] = equip_type
                err = ("Unable to find units, type, Bacnet Object Name and/or Bacnet Object "
                       "Identifier. Skipping registry config entry for: "
                       f"{missing}")
                self.unmapped_device_details[equip_id]["registry_warnings"] = err
        return data

    def get_volttron_point_name(self, reference_point_name, **kwargs):
        p = kwargs.get("point_name", None)
        if p:
            if kwargs.get("equip_type", "unknown") in ["lighting", "occupancy_detector"]:
                return f"{p}__{reference_point_name.split('_')[0]}"
            else:
                return p
        else:
            return reference_point_name

    def get_max_device_count_in_group(self):
        return max(self.group_device_count.values())

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()

if __name__ == '__main__':
    main()
    # connection = Neo4jConnection("neo4j://localhost:7687", "neo4j", "volttron")
    # test_result = connection.query("MATCH (a:AHU) WHERE not ((a)-[:feeds]->(:VAV)) RETURN a.name;")
    # print(test_result)
    # test_result = connection.query("MATCH (v:VAV) WHERE not ((:AHU)-[:feeds]->(v)) RETURN v.name;")
    # print(test_result)
    # test_result = connection.query("MATCH (a:AHU)-[:feeds]->(v:VAV) RETURN a.name, v.name;")
    # print(test_result)


    
    main()

