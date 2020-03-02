from threading import Thread
# unused right now, but will be useful for scaling past a couple of devices
from multiprocessing.queues import Queue as ProcessQueue
from typing import List, Dict, Optional, Type, Union
from queue import Empty as QueueEmptyException, Queue as ThreadQueue
from chariot.device.adapter.DeviceAdapter import DeviceAdapter
from chariot.utility.JSONTypes import JSONObject
from chariot.network.Network import Network
from chariot.network.NetworkManager import NetworkManager
from chariot.database.writer.DatabaseWriter import DatabaseWriter
from chariot.utility.ChariotExceptions import *
from sys import exc_info

class WorkerThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
        super().__init__(group=group, target=target, name=name)
        self.args = args
        self.kwargs = kwargs
        self.target = target

    def run(self):
        try:
            self.target()
        except Exception as err:
            # add the error to the errorQueue for handling on the main thread
            # args[0]: the errorQueue passed in
            self.args[0].put((self.name, exc_info()))
        finally:
            # https://github.com/python/cpython/blob/9c87fbe54e1c797e3c690c6426bdf5e79c457cf1/Lib/threading.py#L872
            del self.target, self.args, self.kwargs


class DataCollectionManager:
    # This class is intended to work with an instance of NetworkManager. The NetworkManager
    # is responsible for housing multiple user-defined networks. Once a network has been selected
    # for data collection, this class interacts with the NetworkManager to start and stop data collection
    # of all devices from the selected network
    DEFAULT_TIMEOUT: float = 5.0
    ERROR_CHECK_TIMEOUT: float = 0.5
    PRODUCERS_PER_CONSUMER: int = 2
    THREAD_JOIN_TIMEOUT:float = 2.0

    # TODO: complete handleError method to continuously examine the error queue
    # TODO: when DatabaseWriter is implemented, remove quotes around type definition
    # TODO: add __del__ method to stop data collection when this object goes out of scope
    # TODO: add DataOutputStream for outputThread to also send data to
    def __init__(self, network: Optional[Network], dbWriter: DatabaseWriter):
        self.activeNetwork: Optional[Network] = network
        self.devices: List[DeviceAdapter] = network.getDevices() if network is not None else []
        self.consumerThreads: List[WorkerThread] = []
        self.producerThreads: Dict[str, WorkerThread] = {}
        self.outputThread: WorkerThread = WorkerThread(target=self._outputData)
        self.errorQueue: ThreadQueue = ThreadQueue()
        self.dataQueue: ThreadQueue = ThreadQueue()
        self.databaseWriter: DatabaseWriter = dbWriter
        self._inCollectionEpisode: bool = False
        self._episodeStartTime: float = 0.0

    def _consumeDataFromDevice(self, deviceIdx: int) -> None:
        device: DeviceAdapter = self.devices[deviceIdx]
        while self._inCollectionEpisode:
            output: List[JSONObject] = []
            try:
                data: JSONObject = device.getDataQueue().get(block=True, timeout=self.DEFAULT_TIMEOUT)
                output.append(data)
            except QueueEmptyException:
                pass

            while True:
                try:
                    data: JSONObject = device.getDataQueue().get_nowait()
                    output.append(data)
                except QueueEmptyException:
                    break
        self.dataQueue.put(output, block=True)

    def _consumeDataFromDevices(self, startIdx: int, numDevices: int) -> None:
        if numDevices == 1:
            self._consumeDataFromDevice(startIdx)
        else:
            while self._inCollectionEpisode:
                output: List[JSONObject] = []
                for i in range(startIdx, startIdx + numDevices):
                    try:
                        data: JSONObject = self.devices[i].getDataQueue().get_nowait()
                        output.append(data)
                    except QueueEmptyException:
                        continue
                if len(output) > 0:
                    self.dataQueue.put(output, block=True)

    def _handleErrorsInQueue(self) -> None:
        MAX_ATTEMPTS: int = 3
        disconnectedDevices: Dict[str, int] = {}          # Used with DeviceNotConncectedErrors to track how many attempts were made to reconnect
        failedCollections: Dict[str, int] = {}           # Used with FailedToBeginCollectionErrors to track attempts to begin collecting

        while self._inCollectionEpisode:
            try:
                # Errors received are a tuple of the Thread name/id and the stacktrace
                deviceID, error = self.errorQueue.get(block=True, timeout=self.ERROR_CHECK_TIMEOUT)

                # For making changes to the correct device in the producerThreads
                errorDevice: DeviceAdapter = self.activeNetwork.getDeviceByDeviceName(deviceID)
                exc_type, exc_val, exc_trace = error

                if isinstance(exc_val, DeviceNotConnectedError):
                    if deviceID in disconnectedDevices:
                        if disconnectedDevices[deviceID] > MAX_ATTEMPTS:
                            disconnectedDevices[deviceID] += 1
                            disconnectedDevices.move_to_end(deviceID)
                        elif disconnectedDevices[deviceID] == MAX_ATTEMPTS:
                            #LOG: f'{deviceID} has failed to reconnect. Stopping collection from device.'
                            errorDevice.stopDataCollection()
                            disconnectedDevices[deviceID] += 1
                        else:
                            #LOG: f'Attemtpting to reconnect to {deviceID}'
                            disconnectedDevices[deviceID] += 1
                            errorDevice.connect()
                    else:
                        #LOG: f'Attempting to reconnect to {deviceID}'
                            disconnectedDevices[deviceID] = 0
                            errorDevice.connect()
                elif isinstance(exc_val, FailedToBeginCollectionError):
                    if deviceID in failedCollections:
                        if failedCollections[deviceID] > MAX_ATTEMPTS:
                            disconnectedDevices[deviceID] += 1
                            disconnectedDevices.move_to_end(deviceID)
                        elif failedCollections[deviceID] == MAX_ATTEMPTS:
                            #LOG: f'{deviceID} has failed to start collecting data after {MAX_ATTEMPTS} attempts.'
                            disconnectedDevices[deviceID] += 1
                        else:
                            #LOG: f'Attempting to begin {deviceID}'s collection'
                            disconnectedDevices[deviceID] += 1
                            errorDevice.beginDataCollection()
                    else:
                        disconnectedDevices[deviceID] = 0
                        errorDevice.beginDataCollection()
                else:   #Unkown error, stop device before it floods queues with useless data, or causes damages to the physical device
                    #LOG: f'{deviceID} has encountered a fatal error.
                    errorDevice.stopDataCollection()
                    errorDevice.disconnect()
            except QueueEmptyException:
                continue

    def _outputData(self) -> None:
        while self._inCollectionEpisode:
            output: List[JSONObject] = []
            try:
                data: JSONObject = self.dataQueue.get(block=True, timeout=self.DEFAULT_TIMEOUT)
                output.append(data)
            except QueueEmptyException:
                pass

            while True:
                try:
                    data = self.dataQueue.get_nowait()
                    output.append(data)
                except QueueEmptyException:
                    break
            self.databaseWriter.insertMany(output)

    def inCollectionEpisode(self) -> bool:
        return self._inCollectionEpisode

    def setActiveNetwork(self, network: Optional[Network]):
        if self._inCollectionEpisode:
            # can't set an active network during a data collection episode
            # to support concurrent network data collection, a new instance of DataCollectionManager has to be spawned
            raise InCollectionEpisodeError()
        self.activeNetwork = network
        self.devices = network.getDevices()

    def getActiveNetwork(self) -> Optional[Network]:
        return self.activeNetwork

    def beginDataCollection(self) -> None:
        if self._inCollectionEpisode:
            raise InCollectionEpisodeError()

        if len(self.devices) == 0:
            # can't collect data from a network with no devices
            raise AssertionError('Must have at least one device to collect from.')
        for device in self.devices:
            producer = WorkerThread(
                name=f'Producer_{device.getId()}', target=device.beginDataCollection, args=(self.errorQueue,))
            self.producerThreads[device.getId()] = producer

        numConsumers = int(len(self.devices) / self.PRODUCERS_PER_CONSUMER)
        # in the special case of only one device this will end up being zero so we manually set it to 1
        if len(self.devices) == 1:
            numConsumers = 1

        if numConsumers > 1:
            mismatch: bool = len(self.devices) % self.PRODUCERS_PER_CONSUMER != 0
            for i in range(numConsumers):
                startIdx = self.PRODUCERS_PER_CONSUMER * i
                numDevices = self.PRODUCERS_PER_CONSUMER
                if i == numConsumers - 1 and mismatch:
                    # in the case of devices left over, we append them to the last consumer if there are less than 50%
                    # of the expected producers per consumer. else, we add one last consumer to take care of the rest
                    leftOver = len(self.devices) - startIdx - 1
                    if leftOver < int(numConsumers / 2):
                        numDevices += leftOver
                    else:
                        self.consumerThreads.append(WorkerThread(
                            target=self._consumeDataFromDevices, args=(startIdx + numDevices - 1, leftOver,)))

                # TODO: add names of devices assigned as names of the threads for easier debugging
                self.consumerThreads.append(WorkerThread(
                    target=self._consumeDataFromDevices, args=(startIdx, numDevices,)))
        else:
            self.consumerThreads.append(WorkerThread(
                target=self._consumeDataFromDevices, args=(0, 1,)))

        self._inCollectionEpisode = True

        for producer in self.producerThreads.values():
            producer.start()
        for consumer in self.consumerThreads:
            consumer.start()
        self.outputThread.start()

        # begin the error-handling procedure on the main thread till we stop data collection
        self._handleErrorsInQueue()


    def stopDataCollection(self) -> None:
        if not self._inCollectionEpisode:
            raise NotInCollectionEpisodeError()
        for device in self.devices:
            device.stopDataCollection()

        self._inCollectionEpisode = False
        for producer in self.producerThreads.values():
            producer.join(self.THREAD_JOIN_TIMEOUT)
        for consumer in self.consumerThreads:
            consumer.join(self.THREAD_JOIN_TIMEOUT)
        self.outputThread.join(self.THREAD_JOIN_TIMEOUT)
