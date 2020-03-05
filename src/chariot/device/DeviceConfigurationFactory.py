from typing import Dict, Type
from chariot.device.configuration import DeviceConfiguration, ImpinjR420Configuration, ImpinjXArrayConfiguration, TestConfiguration
from chariot.utility import AbstractFactory
from chariot.utility.JSONTypes import JSONObject


class _DeviceConfigurationFactory(AbstractFactory):
    def __init__(self):
        self.instanceMap: Dict[str, Type[DeviceConfiguration]] = {
            'ImpinjXArray': ImpinjXArrayConfiguration,
            'ImpinjSpeedwayR420': ImpinjR420Configuration,
            'TestDevice': TestConfiguration
        }
        self.typeField = 'deviceType'
        self.instanceName: str = 'device configuration'

    def getInstance(self, config: JSONObject) -> DeviceConfiguration:
        return super().getInstance(config)


# Return singleton
DeviceConfigurationFactory = _DeviceConfigurationFactory()

__all__ = ['DeviceConfigurationFactory']
