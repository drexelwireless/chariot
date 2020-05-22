import flask
from flask import jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from typing import Dict
from chariot.device import DeviceAdapterFactory, DeviceConfigurationFactory
from chariot.device.adapter import DeviceAdapter
from chariot.configuration import Configuration
from chariot.database.configuration import DatabaseConfiguration
from chariot.database import DatabaseConfigurationFactory, DatabaseWriterFactory
from chariot.database.writer import DatabaseWriter
from chariot.utility import PayloadParser
from chariot.network import Network, NetworkManager
from chariot.utility.exceptions import NameNotFoundError, DuplicateNameError, ItemNotSupported, DatabaseConnectionError, \
    NoIdentifierError
from chariot.network.configuration import NetworkConfiguration
from chariot.database import DatabaseManager
from chariot.utility import TypeStrings
from test.testutils import MockServer
from chariot.collection.configuration import DataCollectionConfiguration
from chariot.collection import DataCollector, DataCollectionManager
from chariot.utility.JSONTypes import JSONObject

app = flask.Flask(__name__)
CORS(app)  # This will enable CORS for all routes
socketio = SocketIO(app, cors_allowed_origins='*')

apiBaseUrl: str = '/chariot/api/v1.0'
parser: PayloadParser = PayloadParser()
defaultSuccessCode: int = 200

runningCollectors: Dict[str, bool] = {}
mockServer = MockServer()

# --- This section of api endpoints deals with netowrks  --- #

@app.route(apiBaseUrl + '/networks/names', methods=['GET'])
# This method will return all network names known to the networkManager and their descriptions
def retrieveAllNetworkNames():
    allNetworks: Dict[str, str] = NetworkManager.getAllNetworks()
    return buildSuccessfulRequest(allNetworks, defaultSuccessCode)


@app.route(apiBaseUrl + '/networks/all', methods=['GET'])
# This method will return all known networks along with their devices
def retrieveAllNetworkDetails():
    networksAndDevices = NetworkManager.getNetworksAndDevices()
    return buildSuccessfulRequest(networksAndDevices, defaultSuccessCode)


@app.route(apiBaseUrl + '/network', methods=['POST'])
def createNetwork():
    requestContent = request.get_json()

    # build a NetworkConfiguration from payload and verify it
    networkConfig: NetworkConfiguration = NetworkConfiguration(requestContent)

    # if configuration is successful, then create a Network and add it to the NetworkManager
    network: Network = Network(networkConfig)
    NetworkManager.addNetwork(network)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/network', methods=['PUT'])
def modifyNetwork():
    # through this endpoint, a network can have its name and/or description changed
    # it must be that the old name('networkName') is specified and a new name('newNetworkName') is given in the payload

    requestContent = request.get_json()
    hasNewName = False
    networkName: str = parser.getNameInPayload(requestContent)

    # check if a new network name is specified in the payload, if so capture old name so its deleted from collection
    if parser.getNewNetworkNameStr() in requestContent:
        hasNewName = True
        # for configuration validation, alter keys from 'newNetworkName' to 'networkName'
        requestContent[TypeStrings.Network_Identifier.value] = requestContent[parser.getNewNetworkNameStr()]
        del requestContent[parser.getNewNetworkNameStr()]

    # at this point, 'newNetworkName' is not a key, so validate configuration and update
    NetworkManager.getNetwork(networkName).updateConfig(requestContent)

    # if applicable, modify collection so the new network name is in collection and old one is deleted
    if hasNewName:
        # notice that requestContent[TypeStrings.Network_Identifier.value] is used, this will return the new name since
        # keys were updated. So 'networkName' would be the old name of the network
        NetworkManager.replaceNetwork(networkName, requestContent[TypeStrings.Network_Identifier.value])

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/network', methods=['DELETE'])
def deleteNetwork():
    networkToDelete = parser.getNameInURL(request)
    NetworkManager.deleteNetwork(networkToDelete)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/network', methods=['GET'])
def getNetworkDetails():
    # this method returns a specific network details
    networkName = parser.getNameInURL(request)
    network: Network = NetworkManager.getNetwork(networkName).getConfiguration().toDict()

    return buildSuccessfulRequest(network, defaultSuccessCode)


# ---  This section of endpoints deals with devices  --- #

@app.route(apiBaseUrl + '/network/device/supportedDevices', methods=['GET'])
def getSupportedDevices():
    # returns a dictionary of supported devices, with key as deviceType and value as the configuration
    return buildSuccessfulRequest(DeviceAdapterFactory.getsupportedDevices(), None)


@app.route(apiBaseUrl + '/network/device/config', methods=['GET'])
def getSupportedDeviceConfig():
    deviceTemplateName = parser.getDeviceNameInURL(request)

    # get specified device template
    deviceTemplate = DeviceAdapterFactory.getSpecifiedDeviceTemplate(deviceTemplateName)

    return buildSuccessfulRequest(deviceTemplate, defaultSuccessCode)


@app.route(apiBaseUrl + '/network/device', methods=['GET'])
def getDeviceDetails():
    # ensure that a network is specified in the payload
    networkName = parser.getNameInURL(request)
    network: Network = NetworkManager.getNetwork(networkName)

    # find device in network
    deviceName: str = parser.getDeviceNameInURL(request)
    deviceConfig: Configuration = network.getDevice(deviceName).getConfiguration()

    return buildSuccessfulRequest(deviceConfig.toDict(), defaultSuccessCode)


@app.route(apiBaseUrl + '/network/device', methods=['POST'])
def createDevice():
    # ensure that a network is specified in the payload
    requestContent = request.get_json()
    networkName = parser.getNameInPayload(requestContent)

    network: Network = NetworkManager.getNetwork(networkName)

    # build dictionary from payload and remove non-device fields
    payloadConfig = requestContent
    del payloadConfig[TypeStrings.Network_Identifier.value]

    # build configuration for device
    deviceConfig: Configuration = DeviceConfigurationFactory.getInstance(payloadConfig)

    # with configuration validated, now use the factory to create a deviceAdapter instance
    device: DeviceAdapter = DeviceAdapterFactory.getInstance(deviceConfig)

    # add device to specified network
    network.addDevice(device)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/network/device', methods=['PUT'])
def modifyDevice():
    # through this endpoint, a device can have its configuration changed
    # it must be that the old name('deviceId') is specified and a new name('newDeviceId') is given in the payload
    requestContent = request.get_json()
    newDeviceName: str = None
    networkName = parser.getNameInPayload(requestContent)
    deviceName: str = parser.getDeviceNameInPayload(requestContent)

    # check if a new device name is specified in the payload, if so capture old name so its deleted from collection
    if parser.getNewDeviceIdStr() in requestContent:
        newDeviceName = requestContent[parser.getNewDeviceIdStr()]
        requestContent[TypeStrings.Device_Identifier.value] = newDeviceName
        del requestContent[parser.getNewDeviceIdStr()]

    # remove networkName key so that updating configuration does not raise an error
    del requestContent[TypeStrings.Network_Identifier.value]

    NetworkManager.getNetwork(networkName).getDevice(deviceName).updateConfig(requestContent)

    # if applicable, modify collection so the new device name is in collection and old one is deleted
    if newDeviceName:
        NetworkManager.getNetwork(networkName).replaceDevice(deviceName, newDeviceName)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/network/device', methods=['DELETE'])
def deleteDevice():
    # ensure that a network is specified in the payload
    networkName = parser.getNameInURL(request)
    network: Network = NetworkManager.getNetwork(networkName)

    deviceName = parser.getDeviceNameInURL(request)

    # now delete device from specified network
    network.deleteDevice(deviceName)
    return buildSuccessfulRequest(None, defaultSuccessCode)


# ---  This section of endpoints deals with databases  --- #
@app.route(apiBaseUrl + '/database/test', methods=['POST'])
def testDBConfiguration():
    # one can test an already created configuration or by payload
    requestContent = request.get_json()
    dbId = parser.getDbNameInPayload(requestContent)

    try:
        dbWriter: DatabaseWriter = DatabaseManager.getDbWriter(dbId)
        dbWriter.connect()
    except NameNotFoundError:
        # if the name isn't found in collection, do not throw error as this can be to test
        # a non-managed configuration
        pass
    except Exception as e:
        raise DatabaseConnectionError(str(e))

    # from the payload, create a dbWriter and test the connection
    dbConfig: DatabaseConfiguration = DatabaseConfigurationFactory.getInstance(requestContent)
    # with configuration validated, now use the factory to create a dbWriter instance
    dbWriter: DatabaseWriter = DatabaseWriterFactory.getInstance(dbConfig)
    try:
        dbWriter.connect()
    except Exception as e:
        raise DatabaseConnectionError(str(e))

    dbWriter.disconnect()

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/database', methods=['POST'])
def createDBConfiguration():
    payloadConfig = request.get_json()

    dbConfig: DatabaseConfiguration = DatabaseConfigurationFactory.getInstance(payloadConfig)

    # with configuration validated, now use the factory to create a dbWriter instance
    dbWriter: DatabaseWriter = DatabaseWriterFactory.getInstance(dbConfig)

    # add to dbManager
    DatabaseManager.addDbWriter(dbWriter)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/database', methods=['PUT'])
def modifyDatabaseConfiguration():
    # through this endpoint, a database can have its id and/or attributes changed
    # it must be that the old name('dbId') is specified and a new name('newDbId') is given in the payload

    requestContent = request.get_json()
    hasNewName = False
    dbId: str = parser.getDbNameInPayload(requestContent)

    # check if a new dbId is specified in the payload, if so capture old name so its deleted from collection
    if parser.getNewDbIdStr() in requestContent:
        hasNewName = True
        # for configuration validation, alter keys from 'dbId' to 'newDbId'
        requestContent[TypeStrings.Database_Identifier.value] = requestContent[parser.getNewDbIdStr()]
        del requestContent[parser.getNewDbIdStr()]

    # at this point, 'newDbId' is not a key, so validate configuration and update
    DatabaseManager.getDbWriter(dbId).updateConfig(requestContent)

    # if applicable, modify collection so the new dbId is in collection and old one is deleted
    if hasNewName:
        # notice that requestContent['dbId'] is used, this will return the new name since keys were
        # updated. So variable dbId would be the old name of the network
        DatabaseManager.replaceDbWriter(requestContent[TypeStrings.Database_Identifier.value], dbId)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/database', methods=['DELETE'])
def deleteDatabaseConfiguration():
    dbId = parser.getDbNameInURL(request)
    DatabaseManager.deleteDbWriter(dbId)

    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/database', methods=['GET'])
def getDatabaseConfiguration():
    # this method returns a specific database config
    dbId = parser.getDbNameInURL(request)
    db: DatabaseWriter = DatabaseManager.getDbWriter(dbId).getConfiguration().toDict()

    return buildSuccessfulRequest(db, defaultSuccessCode)


@app.route(apiBaseUrl + '/database/supportedDatabases', methods=['GET'])
def getSupportedDatabases():
    # returns a dictionary of supported devices, with key as deviceType and value as the configuration
    return buildSuccessfulRequest(DatabaseWriterFactory.getsupportedDatabases(), None)


@app.route(apiBaseUrl + '/database/config', methods=['GET'])
def getSupportedDatabaseConfig():
    deviceTemplateName = parser.getDbNameInURL(request)

    # get specified device template
    deviceTemplate = DatabaseWriterFactory.getSpecifiedDbTemplate(deviceTemplateName)

    return buildSuccessfulRequest(deviceTemplate, defaultSuccessCode)


@app.route(apiBaseUrl + '/database/all', methods=['GET'])
# This method will return all known networks along with their devices
def retrieveAllDbConfigs():
    dbConfigs = DatabaseManager.getAllConfigurations()
    return buildSuccessfulRequest(dbConfigs, defaultSuccessCode)


# ---  This section deals with data collectors  --- #
@app.route(apiBaseUrl + '/data', methods=['POST'])
def createDataCollector():
    requestContent = request.get_json()
    # in this method, it is expected that a networkName and dbId are given in payload so that a DataCollection can be
    # created as well as a configId that is a unique identifier for DataCollector
    dbId: str = parser.getDbNameInPayload(requestContent)
    networkName: str = parser.getNameInPayload(requestContent)

    # Retrieve from respective managers, invalid names will throw error
    db: DatabaseWriter = DatabaseManager.getDbWriter(dbId)
    network: Network = NetworkManager.getNetwork(networkName)
    configId: str = parser.getDataCollectorInPayload(requestContent)

    # create a configMap to create a DataCollectionConfiguration
    configMap = {}
    configMap["configId"] = configId
    configMap[TypeStrings.Network_Type.value] = network
    configMap[TypeStrings.Database_Type.value] = db
    configMap["runTime"] = 100

    collectionConfig: DataCollectionConfiguration = DataCollectionConfiguration(configMap)

    collector: DataCollector = DataCollector(collectionConfig)

    DataCollectionManager.addCollector(collector)
    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/data', methods=['GET'])
def getDataCollector():
    dataConfigId: str = parser.getDataCollectorInURL(request)
    dataCollector: DataCollector = DataCollectionManager.getCollector(dataConfigId).getConfiguration().toDict()

    return buildSuccessfulRequest(dataCollector, defaultSuccessCode)


@app.route(apiBaseUrl + '/data', methods=['DELETE'])
def deleteDataCollector():
    dataConfigId: str = parser.getDataCollectorInURL(request)
    if dataConfigId in runningCollectors:
        # can't delete a running data collector
        response = jsonify(toDict(f'The data collector with id {dataConfigId} cannot be deleted while it is running.'))
        response.status_code = 400
        return response
    DataCollectionManager.deleteCollector(dataConfigId)
    return buildSuccessfulRequest(None, defaultSuccessCode)


# ---  This section deals with data collection  --- #
@app.route(apiBaseUrl + '/data/start', methods=['GET'])
def startDataCollection():
    configId: str = parser.getDataCollectorInURL(request)

    dataCollector: DataCollector = DataCollectionManager.getCollector(configId)
    if configId in runningCollectors:
        # data collection is already running
        response = jsonify(toDict(f'The data collection with id {configId} is already running.'))
        response.status_code = 400
        return response

    # For a test device, the MockServer must be started in order to get generated data
    devices = dataCollector.getNetwork().getDevices()
    hasTestDevice = False
    for device in devices.values():
        if device.getDeviceType() == 'TestDeviceAdapter':
            if not mockServer.isRunning():
                mockServer.start()
            hasTestDevice = True
            break
    
    dataCollector.addOutputHook(emitData)
    # if it is timed, this will make sure it is no longer flagged as running when it stops
    dataCollector.setEndHandler(removeRunningCollector)
    # start data collection    
    runningCollectors[configId] = hasTestDevice
    dataCollector.startCollection()
    return buildSuccessfulRequest(None, defaultSuccessCode)


@app.route(apiBaseUrl + '/data/stop', methods=['GET'])
def endDataCollection():
    configId: str = parser.getDataCollectorInURL(request)
    if not configId in runningCollectors:
         # data collection was not running
        response = jsonify(toDict(f'The data collection with id {configId} was not running.'))
        response.status_code = 400
        return response

    dataCollector: DataCollector = DataCollectionManager.getCollector(configId)
    dataCollector.stopCollection()
    del runningCollectors[configId]

    # if no running collectors are using the MockServer, shut it down
    if not any(runningCollectors.values()) and mockServer.isRunning():
        mockServer.stop()

    # inform socket subscribers that data collection has ended
    socketio.emit('end')
    return buildSuccessfulRequest(None, defaultSuccessCode)


# ---  This section deals with errorHandlers  --- #
@app.errorhandler(NameNotFoundError)
def handleNameNotFound(error):
    res = jsonify(toDict(error.message))
    res.status_code = error.status_code
    return res


@app.errorhandler(NoIdentifierError)
def handleInvalidUsage(error):
    res = jsonify(toDict(error.message))
    res.status_code = error.status_code
    return res


@app.errorhandler(DuplicateNameError)
def handleDuplicateName(error):
    res = jsonify(toDict(error.message))
    res.status_code = error.status_code
    return res


@app.errorhandler(ItemNotSupported)
def handleItemNotSupported(error):
    res = jsonify(toDict(error.message))
    res.status_code = error.status_code
    return res


@app.errorhandler(DatabaseConnectionError)
def handleDatabaseNotConnected(error):
    res = jsonify(toDict(error.message))
    res.status_code = error.status_code
    return res


# -- useful utility methods --
def toDict(e):
    rv = dict()
    rv["message"] = e
    return rv


def buildSuccessfulRequest(data, code):
    # NOTE: data should be in dictionary format
    if data is None:
        data = {'success': True}

    if code is None:
        code = 200

    response = jsonify(data)

    return response, code

def emitData(data: JSONObject) -> None:
    socketio.emit('data', data)

def removeRunningCollector(configId: str) -> None:
    if configId in runningCollectors:
        del runningCollectors[configId]

    if not any(runningCollectors.values()):
        mockServer.stop()


if __name__ == '__main__':
    socketio.run(app)
