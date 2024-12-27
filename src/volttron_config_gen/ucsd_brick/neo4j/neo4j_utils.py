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
