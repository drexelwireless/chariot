from src.chariot.utility.exceptions import NoIdentifierError


class PayloadParser:
    # The purpose of this class is to parse payloads and check for certain criteria in the payloads. This allows
    # for parsing to be turned into function rather than be repeated in the api class.
    @staticmethod
    def checkForNetworkName(requestContent) -> str:
        # first ensure that a network name has been given to specify which network is to be modified
        networkName: str = requestContent.get('NetworkName')

        if not networkName:
            raise NoIdentifierError('Network name')
        return networkName

    @staticmethod
    def checkForNewNetworkName(requestContent) -> str:
        # first ensure that a network name has been given to specify which network is to be modified
        newNetworkName: str = requestContent.get('NewName')

        if not newNetworkName:
            raise NoIdentifierError(' new Network name')
        return newNetworkName

    @staticmethod
    def checkForDeviceName(requestContent) -> str:
        # first ensure that a network name has been given to specify which network is to be modified
        deviceName: str = requestContent.get('DeviceName')
        if not deviceName:
            raise NoIdentifierError('device name')
        return deviceName
