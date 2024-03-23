import re
import sys
import psycopg2

from volttron.haystack.parser.airside_economizer.config_base import \
    AirsideEconomizerConfigGenerator


class IntellimationAirsideEconomizerConfigGenerator(AirsideEconomizerConfigGenerator):
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

    def get_ahus(self):
        query = f"SELECT tags #>>'{{id}}' \
                FROM {self.equip_table} \
                WHERE tags->>'ahu'='m:' "
        if self.site_id:
            query = query + f" AND tags->>'siteRef'='{self.site_id}' "
        return self.execute_query(query)

    def get_topic_by_point_type(self, equip_id, point_key):
        point_type = self.point_meta_map[point_key]
        if isinstance(point_type, str):
            point_type_list = [point_type,]
        else:
            point_type_list = point_type
        point_type, topic = self.query_for_topic(equip_id, point_type_list)

        if not self.equip_id_point_topic_map.get(equip_id):
            self.equip_id_point_topic_map[equip_id] = dict()
        self.equip_id_point_topic_map[equip_id][point_type] = topic
        return topic

    def query_for_topic(self, equip_id, point_types):
        # could get more than one possible point type if so find the first matching point
        topic = ""
        point_type = ""
        for p in point_types:
            point_type = p
            query = f"SELECT topic_name " \
                    f"FROM {self.point_table} " \
                    f"WHERE tags->>'equipRef'='{equip_id}' " \
                    f"AND tags->>'{self.point_meta_field}'=" \
                    f"'{p}'"
            result = self.execute_query(query)
            if result:
                # for each device there should be only be one point that matches
                # the point type.
                topic = result[0][0]
                if topic:
                    break
        return point_type, topic

    # Should be overridden for different sites if parsing logic is different
    # Parsing logic could also depend on equip type
    def get_point_name_from_topic(self, topic, equip_id=None, equip_type=None):
        point_name_part = topic.split("/")[-1]
        return point_name_part
        #return re.split(r"[\.|:]", point_name_part)[-1]

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

def main():
    if len(sys.argv) != 2:
        print("script requires one argument - path to configuration file")
        exit()
    config_path = sys.argv[1]
    d = IntellimationAirsideEconomizerConfigGenerator(config_path)
    d.generate_configs()


if __name__ == '__main__':
    main()
