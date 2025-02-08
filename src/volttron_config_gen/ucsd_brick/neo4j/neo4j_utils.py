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

def query_point_name(equip_id, equip_type, point_labels, connection):
    if isinstance(point_labels, str):
        point_labels = [point_labels]
    elif not isinstance(point_labels, list):
        raise ValueError("Point mapping value should be string or list of strings")
    # possible sql injection issue but no way to send parameterized query for labels ?!
    ## TODO: validate point_label, equip_id for valid characters length?
    for point_label in point_labels:
        _query = (f"MATCH (p:{point_label})-[:isPointOf]->(e:{equip_type}"
                  "{name:'"
                  f"{equip_id}"
                  "'}) "
                  "RETURN p.name;")
        #print(f"{_query}")
        result = connection.query(_query)
        if result:
            return result[0][0]
    return None

def query_point_names(equip_id, equip_type, point_labels, connection):
    # possible sql injection issue but no way to send parameterized query for labels ?!
    ## TODO: validate point_label, equip_id for valid characters length?
    _query = (f"MATCH (p:Point)-[:isPointOf]->(e:{equip_type}"
              "{name:'"
              f"{equip_id}"
              "'}) "
              "WHERE any(label in labels(p) WHERE label IN $point_labels) "
              "RETURN labels(p)[1],  p.name;")
    result = connection.query(_query, parameters={'point_labels':point_labels})
    if result:
        return result
    return None

def get_points_for_equip(equip_id, equip_type, interested_point_types, point_meta_map, connection):
    result_dict = {}
    point_labels = []
    for key in interested_point_types:
        if isinstance(point_meta_map[key], str):
            point_labels.append(point_meta_map[key])
        else:
            point_labels.extend(point_meta_map[key])
    query_result = query_point_names(equip_id, equip_type.upper(), point_labels, connection)
    label_name_map = dict()
    if query_result:
        for row in query_result:
            label_name_map[row[0]] = row[1]
    for key in interested_point_types:
        if isinstance(point_meta_map[key], str):
            result_dict[key] = label_name_map.get(point_meta_map[key])
        else:
            for l in point_meta_map[key]:
                if label_name_map.get(l):
                    result_dict[key] = label_name_map[l]
                    break
    return result_dict