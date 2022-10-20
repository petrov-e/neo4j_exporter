import pickle
from multiprocessing import Process
from time import gmtime, strftime
import os
import threading
import prometheus_client
from prometheus_client.core import CollectorRegistry
from prometheus_client import Gauge
from py2neo import Graph
import urllib3
from flask import Response, Flask

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONTENT_TYPE_LATEST = str('text/plain; version=0.0.4; charset=utf-8')
SERVICE_URL = os.environ.get('NEO4J_SERVICE')
PREFIX = "neo4j_"
PROM_OUTPUT = []
BACKGROUND_CHECK = False
FLASK_FIRST_LAUNCH = True
NEO4J_REQUEST = []

with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace', encoding="utf-8") as f_file:
    PodNamespace = f_file.readline()

app = Flask(import_name=__name__)

def background_collector():
    """Collecting Neo4j metrics in the background"""
    global FLASK_FIRST_LAUNCH

    if FLASK_FIRST_LAUNCH is True:
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] Waiting for the web-server to start')
        FLASK_FIRST_LAUNCH = False
        threading.Timer(60, background_collector).start()
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] The task of background collection of metrics has been successfully created')
    else:
        global BACKGROUND_CHECK
        if BACKGROUND_CHECK is True:
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [WARN] Another background collector is already running, skipping the current run')
        else:
            BACKGROUND_CHECK = True
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] Start background collecting Prometheus metrics')
            lst = []
            registry = CollectorRegistry()

            ### Database statuses ###
            neo4j_db_status = Gauge('neo4j_db_status', 'List of all databases with their status. 1 – online, 0 – all other statuses', ['name', 'address', 'currentStatus', 'namespace'], registry=registry)
            print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [-] Getting the statuses of all tables in the cluster')
            try:
                global NEO4J_REQUEST
                NEO4J_REQUEST = Graph("bolt://"+SERVICE_URL+":7687")
                def neo_query_1():
                    global NEO4J_REQUEST
                    f_file = open('/tmp/result', 'wb')
                    f_file.close()
                    neo4j_request_result = NEO4J_REQUEST.run('SHOW DATABASES YIELD name, address, currentStatus').data()
                    f_file = open('/tmp/result', 'wb')
                    pickle.dump(neo4j_request_result,f_file)
                    f_file.close()
                    print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [+] Done')
                p_1 = Process(target=neo_query_1, name='Process_request_1')
                p_1.start()
                p_1.join(timeout=10)
                p_1.terminate()
                f_file = open('/tmp/result', 'rb')
                neo4j_request_result = pickle.load(f_file)
                f_file.close()
            except:
                neo4j_request_result = []
                print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [ERROR] Error connecting to the database to get statuses')
            for db_list in neo4j_request_result:
                if db_list['currentStatus'] == 'online':
                    db_status = 1
                else:
                    db_status = 0
                neo4j_db_status.labels(name=db_list['name'], address=db_list['address'].split('.')[0], currentStatus=db_list['currentStatus'], namespace=PodNamespace).set(db_status)
            lst.append(prometheus_client.generate_latest(neo4j_db_status))

            ### Long-running queries ###
            neo4j_db_slow_queries = Gauge('neo4j_db_slow_query', 'Queries that have been running for more than 10,000 milliseconds', ['database', 'transactionId', 'currentQueryId', 'status', 'activeLockCount', 'pageHits', 'cpuTimeMillis', 'waitTimeMillis', 'idleTimeSeconds', 'namespace', 'address'], registry=registry)
            neo4j_db_slow_queries_page_hits = Gauge('neo4j_db_slow_query_page_hits', 'Page hits amount of queries that have been running for more than 10,000 milliseconds', ['database', 'transactionId', 'currentQueryId', 'status', 'activeLockCount', 'cpuTimeMillis', 'waitTimeMillis', 'idleTimeSeconds', 'namespace', 'address'], registry=registry)
            for key, value in os.environ.items():
                if ("NEO4J_CORE" in key or "NEO4J_REPLICA" in key) and "PORT_7687_TCP_ADDR" in key and not "ADMIN" in key:
                    db_adress = key.split('_')[0] + '-' + key.split('_')[1] + '-' + key.split('_')[2]
                    print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [-] Getting long queries from ' + db_adress.lower())
                    try:
                        NEO4J_REQUEST = Graph("bolt://"+str(value)+":7687")
                        def neo_query_2():
                            global NEO4J_REQUEST
                            f_file = open('/tmp/result', 'wb')
                            f_file.close()
                            neo4j_request_result = NEO4J_REQUEST.run('SHOW TRANSACTIONS YIELD database, transactionId, currentQueryId, status, activeLockCount, pageHits, elapsedTime, cpuTime, waitTime, idleTime WHERE elapsedTime.milliseconds > 10000 RETURN database, transactionId, currentQueryId, status, activeLockCount, pageHits, elapsedTime.milliseconds AS elapsedTimeMillis, cpuTime.milliseconds AS cpuTimeMillis, waitTime.milliseconds AS waitTimeMillis, idleTime.seconds AS idleTimeSeconds').data()
                            f_file = open('/tmp/result', 'wb')
                            pickle.dump(neo4j_request_result,f_file)
                            f_file.close()
                            print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [+] Done')
                        p_2 = Process(target=neo_query_2, name='Process_request_2')
                        p_2.start()
                        p_2.join(timeout=10)
                        p_2.terminate()
                        f_file = open('/tmp/result', 'rb')
                        neo4j_request_result = pickle.load(f_file)
                        f_file.close()
                    except:
                        neo4j_request_result = []
                        print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [ERROR] Error connecting to the ' + db_adress.lower() + ' to get long queries')
                    for db_list in neo4j_request_result:
                        neo4j_db_slow_queries.labels(database=db_list['database'], transactionId=db_list['transactionId'], currentQueryId=db_list['currentQueryId'], status=db_list['status'], activeLockCount=db_list['activeLockCount'], pageHits=db_list['pageHits'], cpuTimeMillis=db_list['cpuTimeMillis'], waitTimeMillis=db_list['waitTimeMillis'], idleTimeSeconds=db_list['idleTimeSeconds'], namespace=PodNamespace, address=db_adress.lower()).set(db_list['elapsedTimeMillis'])
                        neo4j_db_slow_queries_page_hits.labels(database=db_list['database'], transactionId=db_list['transactionId'], currentQueryId=db_list['currentQueryId'], status=db_list['status'], activeLockCount=db_list['activeLockCount'], cpuTimeMillis=db_list['cpuTimeMillis'], waitTimeMillis=db_list['waitTimeMillis'], idleTimeSeconds=db_list['idleTimeSeconds'], namespace=PodNamespace, address=db_adress.lower()).set(db_list['pageHits'])
            lst.append(prometheus_client.generate_latest(neo4j_db_slow_queries))
            lst.append(prometheus_client.generate_latest(neo4j_db_slow_queries_page_hits))

            ### Final set of metrics ###
            global PROM_OUTPUT
            PROM_OUTPUT = lst
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] Prometheus metrics have been successfully collected in the background')

            BACKGROUND_CHECK = False

        threading.Timer(240, background_collector).start()

background_collector()

@app.route("/")
def hello():
    """Displaying the root page"""
    return "This is a Prometheus Exporter. Go to the /metrics page to get metrics"

@app.route('/metrics', methods=['GET'])
def metrics():
    """Displaying the Prometheus Metrics page"""
    return Response(PROM_OUTPUT,mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(debug=True)
