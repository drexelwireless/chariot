from abc import ABC, abstractmethod
from typing import Dict, Type
from json import dumps
from chariot.utility.JSONTypes import JSONDict, JSONObject


class Configuration(ABC):
    requiredFields: Dict[str, Type[JSONObject]] = {}
    optionalFields: Dict[str, Type[JSONObject]] = {}

    def __init__(self, configMap: JSONDict):
        self._validateInitialConfig(configMap)
        for key, value in configMap.items():
            setattr(self, key, value)

    def __iter__(self):
        for key in self.requiredFields:
            yield(key, getattr(self, key))
        for key in self.optionalFields:
            val = getattr(self, key, None)
            if val is not None:
                yield(key, val)

    def __str__(self):
        output: JSONDict = dict(self)
        return dumps(output)

    def _isValidField(self, field: str) -> bool:
        return field in self.requiredFields or field in self.optionalFields

    def _validateInitialConfig(self, configMap: JSONDict) -> None:
        for field in configMap:
            if not self._isValidField(field):
                raise AssertionError(field)

        for field, fieldType in self.requiredFields.items():
            if field not in configMap or not isinstance(configMap[field], fieldType):
                raise ValueError(field)

        for field, fieldType in self.optionalFields.items():
            if field in configMap and not isinstance(configMap[field], fieldType):
                raise ValueError(field)

    def _validateSubsetConfig(self, newConfig: JSONDict) -> None:
        for field, value in newConfig.items():
            if not self._isValidField(field):
                raise AssertionError(field)
            if field in self.optionalFields:
                if not isinstance(value, self.optionalFields[field]):
                    raise ValueError(field)
            elif field in self.requiredFields:
                if not isinstance(value, self.requiredFields[field]):
                    raise ValueError(field)

    def updateConfig(self, newConfig: JSONDict) -> None:
        self._validateSubsetConfig(newConfig)
        for key, value in newConfig.items():
            setattr(self, key, value)

    def toJSON(self) -> str:
        return self.__str__()

    def toDict(self) -> JSONDict:
        return dict(self)

    @abstractmethod
    def getId(self) -> str:
        pass

    @abstractmethod
    def getIdField(self) -> str:
        pass
