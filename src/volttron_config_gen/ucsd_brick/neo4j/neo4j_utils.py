from neo4j import GraphDatabase

equip_type_db_label_map = {
    "ahu": "AHU",
    "vav": "VAV",
    "power_meter": "Building_Electrical_Meter", #?
    "lighting": "Luminaire",
    "occupancy_detector": "OccupancyDetector"
}

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

def query_lights_from_room(connection):
    # Only get lights where there is valid controller ip and controller id\
    # TODO- update query once controller is broken into a separate node similar to VAVs
    query = ("MATCH (l:Luminaire)-[:hasLocation]->(r:Room) "
             "WHERE l.controllerId IS NOT NULL AND l.controller IS NOT NULL "
             "RETURN r.name, l.name, l.controller, l.controllerId")
    return connection.query(query)

def query_occupancy_detector(room_id, connection):
    query = ("MATCH (o:OccupancyDetector)-[:hasLocation]->(r:Room) "
             "WHERE o.controllerId IS NOT NULL AND o.controller IS NOT NULL "
             "AND r.name = $room_name "
             "RETURN o.name, o.controller, o.controllerId")
    result =connection.query(query, parameters={"room_name": room_id})
    if result:
        return result[0][0], result[0][1], result[0][2]
    return None, None, None


def query_point_names(equip_id, equip_type, point_labels, connection, **kwargs):
    # possible sql injection issue but no way to send parameterized query for labels ?!
    ## TODO: validate point_label, equip_id for valid characters length?
    db_type = equip_type_db_label_map[equip_type]
    _query = (f"MATCH (p:Point)-[:isPointOf]->(e:{db_type}"
              "{name: $equip_id}) "
              "WHERE any(label in labels(p) WHERE label IN $point_labels) "
              "RETURN labels(p)[1],  p.name;")
    query_parameters = {'equip_id':equip_id, 'point_labels':point_labels}
    if equip_type == "lighting":
        # TODO- is equip id unique globally- i.e. across rooms and controllers? If so
        #  we could get rid of the special query with additional room match
        room_id = kwargs.get("room_id")
        if not room_id:
            raise ValueError("No room_id provided for equip_type lighting")
        _query = (f"MATCH (p:Point)-[isPointOf]->(e:{db_type})-[:hasLocation]->(r:Room) "
                  f"WHERE e.name STARTS WITH $equip_id AND r.name=$room_id "
                  f"AND any(label in labels(p) WHERE label IN $point_labels) "
                  "RETURN labels(p)[1],  p.name;")
        query_parameters = {'equip_id': equip_id, 'room_id': room_id, 'point_labels':point_labels}
    elif equip_type == "occupancy_detector":
        # TODO- is equip id unique globally- i.e. across rooms and controllers? If so
        #  we could get rid of the special query with additional room match
        room_id = kwargs.get("room_id")
        if not room_id:
            raise ValueError("No room_id provided for equip_type occupancy_detector")
        _query = (f"MATCH (p:Point)-[isPointOf]->(e:{db_type})-[:hasLocation]->(r:Room) "
                  f"WHERE e.name STARTS WITH $equip_id AND r.name=$room_id "
                  f"AND any(label in labels(p) WHERE label IN $point_labels) "
                  "RETURN labels(p)[1],  p.name;")
        query_parameters = {'equip_id': equip_id, 'room_id': room_id, 'point_labels':point_labels}

    result = connection.query(_query, parameters=query_parameters)
    if result:
        return result
    return None


def query_points_for_equip(equip_id, equip_type, interested_point_types, point_meta_map,
                           connection, **kwargs):
    result_dict = {}
    point_labels = []
    for key in interested_point_types:
        if isinstance(point_meta_map[key], str):
            point_labels.append(point_meta_map[key])
        else:
            point_labels.extend(point_meta_map[key])
    query_result = query_point_names(equip_id, equip_type, point_labels, connection, **kwargs)
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