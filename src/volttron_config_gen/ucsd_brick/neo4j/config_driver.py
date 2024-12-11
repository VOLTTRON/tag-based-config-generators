import copy
import csv
import os
import sys
import re
from collections import defaultdict

import psycopg2
from volttron_config_gen.base.config_driver import BaseConfigGenerator

from neo4j import GraphDatabase

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def __del__(self):
        self._driver.close()

    def query(self, query, parameters=None):
        with self._driver.session() as session:
            r = session.run(query, parameters)
            return [record for record in r]

class ConfigGenerator(BaseConfigGenerator):
    """
    class that parses BRICK like tags from a neo4j db to generate
    platform driver configuration for driver
    """
    def __init__(self, config):
        super().__init__(config)

        # get details on haystack3 metadata
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")

        self.connection = Neo4jConnection(connect_params["uri"],
                                          connect_params["user"],
                                          connect_params["password"])
        self.device_details = {"ahu": defaultdict(dict),
                               "vav": defaultdict(dict),
                               "electric_meter": defaultdict(dict)}

    def get_ahu_and_vavs(self):
        ahu_dict = defaultdict(list)
        # 1. Query for vavs that are mapped to ahu
        query = ("MATCH (a:AHU)-[:feeds]->(v:VAV) "
                 "RETURN a.name, a.`Remote Station IP`, a.`BACnet Device Object Identifier`, "
                 "v.name, v.`Remote Station IP`, v.`BACnet Device Object Identifier`;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[r[0]].append(r[3])
                self.device_details["ahu"][r[0]]["device_address"]= r[1]
                self.device_details["ahu"][r[0]]["device_id"] = r[2]
                self.device_details["vav"][r[3]]["device_address"]= r[4]
                self.device_details["vav"][r[3]]["device_id"] = r[5]

        # 2. Query for ahus without vavs
        # append to result
        query = ("MATCH (a:AHU) WHERE not ((a)-[:feeds]->(:VAV)) "
                 "RETURN a.name, a.`Remote Station IP`, a.`BACnet Device Object Identifier`;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[r[0]] = []
                self.device_details["ahu"][r[0]]["device_address"]= r[1]
                self.device_details["ahu"][r[0]]["device_id"] = r[2]

        # 3. query for vavs without
        # if exists add to self.unmapped_device_details
        query = ("MATCH (v:VAV) WHERE not ((:AHU)-[:feeds]->(v)) "
                 "RETURN v.name, v.`Remote Station IP`, v.`BACnet Device Object Identifier`;")
        result = self.connection.query(query)
        if result:
            for r in result:
                ahu_dict[""].append(r[0])
                self.device_details["vav"][r[0]]["device_address"]= r[1]
                self.device_details["vav"][r[0]]["device_id"] = r[2]
                self.unmapped_device_details[r[0]] = {"type": "vav",
                                                      "error": "Unable to find AHU that feeds vav"}
        return ahu_dict

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

    def generate_registry_config(self, equip_id, equip_type):
        header = ["Point Name", "Volttron Point Name", "Units", "BACnet Object Type", "Property",
                  "Writable", "Index", "Notes"]
        _notes = "auto generated"
        _property = "presentValue"
        if equip_type in ["ahu", "vav"]:
            db_type = equip_type.upper()
        elif equip_type == "electric_meter":
            db_type = None # TODO
        else:
            raise ValueError(f"Unknown equipment type {equip_type}")

        query = (f"MATCH(p:Point)-[isPointOf]->(a:{db_type}{{name:'{equip_id}'}})"
                 "RETURN p.name, p.units, p.type, p.`BACnet Object Identifier`;")
        result = self.connection.query(query)
        missing = []
        data = []
        if result:
            for r in result:
                if r[0] and r[1] and r[2] and r[3]:
                    point_name = r[0]
                    units = r[1]
                    point_type = r[2]
                    # All Input types - AnalogInput, BinaryInput etc. are NOT writeable
                    writeable = False if point_type.endswith("Input") else True
                    index = r[3].split(":")[1]
                    data.append([point_name, point_name, units, point_type, _property,
                                 writeable, index, _notes])
                else:
                    missing.append(r[0])
            if missing:
                if not self.unmapped_device_details.get(equip_id):
                    self.unmapped_device_details[equip_id] = dict()
                self.unmapped_device_details[equip_id]["type"] = equip_type
                err = ("Unable to find units, type, and/or Bacnet Object Identifier. "
                       "Skipping registry config entry for: "
                       f"{missing}")
                self.unmapped_device_details[equip_id]["registry_warnings"] = err
        if data:
            filename = os.path.join(self.output_configs,f"registry_{equip_id}.csv")
            with open(filename, "w") as csvfile:
                writer = csv.writer(csvfile, lineterminator='\n')
                writer.writerow(header)
                writer.writerows(data)
            return filename, "csv"
        return None, None




def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = ConfigGenerator(config_path)
    d.generate_configs()

if __name__ == '__main__':
    #main()
    connection = Neo4jConnection("neo4j://localhost:7687", "neo4j", "volttron")
    test_result = connection.query("MATCH (a:AHU) WHERE not ((a)-[:feeds]->(:VAV)) RETURN a.name;")
    print(test_result)
    test_result = connection.query("MATCH (v:VAV) WHERE not ((:AHU)-[:feeds]->(v)) RETURN v.name;")
    print(test_result)
    test_result = connection.query("MATCH (a:AHU)-[:feeds]->(v:VAV) RETURN a.name, v.name;")
    print(test_result)


    
    main()

