import copy
import json
import re
import sys
import psycopg2

from volttron.haystack.parser.airsidercx.config_base import \
    AirsideRCxConfigGenerator


class IntellimationAirsideRCxConfigGenerator(AirsideRCxConfigGenerator):
    """
    class that parses haystack tags from a postgres db to generate
    platform driver configuration for normal framework driver type
    """
    def __init__(self, config):
        super().__init__(config)

        # get details on haystack metadata
        metadata = self.config_dict.get("metadata")
        connect_params = metadata.get("connection_params")
        if "timescale_dialect" in metadata:
            self.timescale_dialect = metadata.get("timescale_dialect",
                                                  False)
            del connect_params["timescale_dialect"]
        else:
            self.timescale_dialect = False
        self.connection = psycopg2.connect(**connect_params)
        self.connection.autocommit = True
        self.equip_table = metadata.get("equip_table")
        self.point_table = metadata.get("point_table")

        # # AirsideRCx point name to metadata(miniDis/Dis field) map
        # self.point_metadata_map = {
        #     "fan_status": "SaFanCmd", #ahu
        #     "zone_reheat": "RhtVlvPos" or "ElecRht1", or "RhtVlvCmd"# "ElecRht2"???
        #     "zone_damper": "DmpCmd", or "vavDmpPos" #vav
        #     "duct_stcpr": "SaPress", #ahu
        #     "duct_stcpr_stpt": "SaPressSp", #ahu
        #     "sa_temp": "SaTemp", #ahu
        #     "fan_speedcmd": "SaFanSpdCmd", #ahu
        #     "sat_stpt": "SaTempSp" #ahu
        # }
        self.point_meta_map = self.config_dict.get("point_meta_map")
        self.point_meta_field = self.config_dict.get("point_meta_field", "miniDis")
        # Initialize point mapping for airsidercx config
        self.point_mapping = {x: [] for x in self.point_meta_map.keys()}
        self.volttron_point_types_ahu = ["fan_status", "duct_stcpr", "duct_stcpr_stpt",
                           "sa_temp", "sat_stpt", "fan_speedcmd"]
        self.volttron_point_types_vav = ["zone_reheat", "zone_damper"]

    def get_ahu_and_vavs(self):
        query = f"SELECT tags #>>'{{ahuRef}}', json_agg(topic_name) \
        FROM {self.equip_table} \
        WHERE tags->>'ahuRef' is NOT NULL AND tags->>'ahuRef' != '' AND tags->>'vav'='m:' "
        if self.site_id:
            query = query + f" AND tags->>'siteRef'='{self.site_id}' "
        query = query + f" GROUP BY tags #>>'{{ahuRef}}'"
        # ahu without vavs and vav without ahuref are not applicable for AirsideRCx
        return self.execute_query(query)

    def get_topic_by_point_type(self, equip_id, point_key):
        point_type = self.point_meta_map[point_key]
        query = f"SELECT topic_name " \
                f"FROM {self.point_table} " \
                f"WHERE tags->>'equipRef'='{equip_id}' " \
                f"AND tags->>'{self.point_meta_field}'=" \
                f"'{point_type}'"
        result = self.execute_query(query)
        if result:
            # for each device there should be only be one point that matches
            # the point type.
            topic = result[0][0]
            if not self.equip_id_point_topic_map.get(equip_id):
                self.equip_id_point_topic_map[equip_id] = dict()
            self.equip_id_point_topic_map[equip_id][point_type] = topic
            return topic
        else:
            # raise ValueError(
            #     f"No point name with "
            #     f"tag->>'{self.point_meta_field}'="
            #     f"'{self.point_meta_map[point_key]}' found for {equip_id}")
            return ""

    # Should be overridden for different sites if parsing logic is different
    # Parsing logic could also depend on equip type
    def get_point_name_from_topic(self, topic, equip_id=None, equip_type=None):
        point_name_part = topic.split("/")[-1]
        return point_name_part
        # return re.split(r"[\.|:]", point_name_part)[-1]

    def execute_query(self, query):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            result = cursor.fetchall()
            return result
        except Exception:
            raise
        finally:
            if cursor:
                cursor.close()

    def get_point_name(self, equip_id, equip_type, point_key):
        topic = self.get_topic_by_point_type(equip_id, point_key)
        point_name = self.get_point_name_from_topic(topic)
        return point_name

    def get_name_from_id(self, id):
        name = id.split(".")[-1]
        return name


def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = IntellimationAirsideRCxConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
