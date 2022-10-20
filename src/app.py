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
PromOutput = []
BACKGROUND_CHECK = False
FLASK_FIRST_LAUNCH = True
Neo4jRequest = []

with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace') as f:
    PodNamespace = f.readline()

app = Flask(import_name=__name__)

def BackgroundCollector():
    """Collecting Neo4j metrics in the background"""
    global FLASK_FIRST_LAUNCH

    if FLASK_FIRST_LAUNCH is True:
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] Waiting for the web-server to start')
        FLASK_FIRST_LAUNCH = False
        threading.Timer(60, BackgroundCollector).start()
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
            Neo4jDBStatus = Gauge('neo4j_db_status', 'List of all databases with their status. 1 – online, 0 – all other statuses', ['name', 'address', 'currentStatus', 'namespace'], registry=registry)
            print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [-] Getting the statuses of all tables in the cluster')
            try:
                global Neo4jRequest
                Neo4jRequest = Graph("bolt://"+SERVICE_URL+":7687")
                def NeoQuery1():
                    global Neo4jRequest
                    f = open('/tmp/result', 'wb')
                    f.close()
                    Neo4jRequestResult = Neo4jRequest.run('SHOW DATABASES YIELD name, address, currentStatus').data()
                    f = open('/tmp/result', 'wb')
                    pickle.dump(Neo4jRequestResult,f)
                    f.close()
                    print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [+] Done')
                p1 = Process(target=NeoQuery1, name='Process_request_1')
                p1.start()
                p1.join(timeout=10)
                p1.terminate()
                f = open('/tmp/result', 'rb')
                Neo4jRequestResult = pickle.load(f)
                f.close()
            except:
                Neo4jRequestResult = []
                print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [ERROR] Error connecting to the database to get statuses')
            for DBList in Neo4jRequestResult:
                if DBList['currentStatus'] == 'online':
                    DBStatus = 1
                else:
                    DBStatus = 0
                Neo4jDBStatus.labels(name=DBList['name'], address=DBList['address'].split('.')[0], currentStatus=DBList['currentStatus'], namespace=PodNamespace).set(DBStatus)
            lst.append(prometheus_client.generate_latest(Neo4jDBStatus))

            ### Long-running queries ###
            Neo4jDBSlowQueries = Gauge('neo4j_db_slow_query', 'Queries that have been running for more than 10,000 milliseconds', ['database', 'transactionId', 'currentQueryId', 'status', 'activeLockCount', 'pageHits', 'cpuTimeMillis', 'waitTimeMillis', 'idleTimeSeconds', 'namespace', 'address'], registry=registry)
            Neo4jDBSlowQueriesPageHits = Gauge('neo4j_db_slow_query_page_hits', 'Page hits amount of queries that have been running for more than 10,000 milliseconds', ['database', 'transactionId', 'currentQueryId', 'status', 'activeLockCount', 'cpuTimeMillis', 'waitTimeMillis', 'idleTimeSeconds', 'namespace', 'address'], registry=registry)
            for key, value in os.environ.items():
                if ("NEO4J_CORE" in key or "NEO4J_REPLICA" in key) and "PORT_7687_TCP_ADDR" in key and not "ADMIN" in key:
                    DBAdress = key.split('_')[0] + '-' + key.split('_')[1] + '-' + key.split('_')[2]
                    print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [-] Getting long queries from ' + DBAdress.lower())
                    try:
                        Neo4jRequest = Graph("bolt://"+str(value)+":7687")
                        def NeoQuery2():
                            global Neo4jRequest
                            f = open('/tmp/result', 'wb')
                            f.close()
                            Neo4jRequestResult = Neo4jRequest.run('SHOW TRANSACTIONS YIELD database, transactionId, currentQueryId, status, activeLockCount, pageHits, elapsedTime, cpuTime, waitTime, idleTime WHERE elapsedTime.milliseconds > 10000 RETURN database, transactionId, currentQueryId, status, activeLockCount, pageHits, elapsedTime.milliseconds AS elapsedTimeMillis, cpuTime.milliseconds AS cpuTimeMillis, waitTime.milliseconds AS waitTimeMillis, idleTime.seconds AS idleTimeSeconds').data()
                            f = open('/tmp/result', 'wb')
                            pickle.dump(Neo4jRequestResult,f)
                            f.close()
                            print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] [+] Done')
                        p2 = Process(target=NeoQuery2, name='Process_request_2')
                        p2.start()
                        p2.join(timeout=10)
                        p2.terminate()
                        f = open('/tmp/result', 'rb')
                        Neo4jRequestResult = pickle.load(f)
                        f.close()
                    except:
                        Neo4jRequestResult = []
                        print (strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [ERROR] Error connecting to the ' + DBAdress.lower() + ' to get long queries')
                    for DBList in Neo4jRequestResult:
                        Neo4jDBSlowQueries.labels(database=DBList['database'], transactionId=DBList['transactionId'], currentQueryId=DBList['currentQueryId'], status=DBList['status'], activeLockCount=DBList['activeLockCount'], pageHits=DBList['pageHits'], cpuTimeMillis=DBList['cpuTimeMillis'], waitTimeMillis=DBList['waitTimeMillis'], idleTimeSeconds=DBList['idleTimeSeconds'], namespace=PodNamespace, address=DBAdress.lower()).set(DBList['elapsedTimeMillis'])
                        Neo4jDBSlowQueriesPageHits.labels(database=DBList['database'], transactionId=DBList['transactionId'], currentQueryId=DBList['currentQueryId'], status=DBList['status'], activeLockCount=DBList['activeLockCount'], cpuTimeMillis=DBList['cpuTimeMillis'], waitTimeMillis=DBList['waitTimeMillis'], idleTimeSeconds=DBList['idleTimeSeconds'], namespace=PodNamespace, address=DBAdress.lower()).set(DBList['pageHits'])
            lst.append(prometheus_client.generate_latest(Neo4jDBSlowQueries))
            lst.append(prometheus_client.generate_latest(Neo4jDBSlowQueriesPageHits))

            ### Final set of metrics ###
            global PromOutput
            PromOutput = lst
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' [INFO] Prometheus metrics have been successfully collected in the background')

            BACKGROUND_CHECK = False

        threading.Timer(240, BackgroundCollector).start()

BackgroundCollector()

@app.route("/")
def hello():
    """Displaying the root page"""
    return "This is a Prometheus Exporter. Go to the /metrics page to get metrics"

@app.route('/metrics', methods=['GET'])
def metrics():
    """Displaying the Prometheus Metrics page"""
    return Response(PromOutput,mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(debug=True)
