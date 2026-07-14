"""Compatibility helpers for environments without pydantic installed."""

from __future__ import annotations

from typing import Any, get_args, get_origin
import json

try:
    from pydantic import BaseModel as PydanticBaseModel, Field  # type: ignore

    class BaseModel(PydanticBaseModel):
        """Thin compatibility wrapper across Pydantic versions."""

        @classmethod
        def model_validate(cls, obj: Any) -> "BaseModel":
            parent = super()
            validator = getattr(parent, "model_validate", None)
            if callable(validator):
                return validator(obj)
            return cls.parse_obj(obj)

        def model_dump(self, **kwargs: Any) -> dict[str, Any]:
            parent = super()
            dumper = getattr(parent, "model_dump", None)
            if callable(dumper):
                return dumper(**kwargs)
            return self.dict(**kwargs)

        def model_dump_json(self, **kwargs: Any) -> str:
            parent = super()
            dumper = getattr(parent, "model_dump_json", None)
            if callable(dumper):
                return dumper(**kwargs)
            return self.json(**kwargs)
except ModuleNotFoundError:
    class BaseModel:
        """A tiny fallback with a subset of the Pydantic API used in this project."""

        def __init__(self, **data: Any) -> None:
            annotations = getattr(self.__class__, "__annotations__", {})
            for name, annotation in annotations.items():
                if name in data:
                    value = data[name]
                elif hasattr(self.__class__, name):
                    default = getattr(self.__class__, name)
                    value = default() if callable(default) and getattr(default, "__name__", "") == "<lambda>" else default
                else:
                    raise TypeError(f"Missing required field: {name}")

                setattr(self, name, self._coerce_value(annotation, value))

        @classmethod
        def _coerce_value(cls, annotation: Any, value: Any) -> Any:
            origin = get_origin(annotation)
            args = get_args(annotation)

            if value is None:
                return None

            if origin in (list, list[Any]):
                inner = args[0] if args else Any
                return [cls._coerce_value(inner, item) for item in value]

            if origin is dict:
                key_type = args[0] if len(args) > 0 else Any
                value_type = args[1] if len(args) > 1 else Any
                return {
                    cls._coerce_value(key_type, key): cls._coerce_value(value_type, item)
                    for key, item in dict(value).items()
                }

            if origin is None and isinstance(annotation, type) and issubclass(annotation, BaseModel):
                if isinstance(value, annotation):
                    return value
                return annotation(**value)

            if origin is not None and type(None) in args:
                non_none = next((arg for arg in args if arg is not type(None)), Any)
                return cls._coerce_value(non_none, value)

            return value

        def model_dump(self) -> dict[str, Any]:
            result: dict[str, Any] = {}
            annotations = getattr(self.__class__, "__annotations__", {})
            for name in annotations:
                value = getattr(self, name)
                if isinstance(value, BaseModel):
                    result[name] = value.model_dump()
                elif isinstance(value, list):
                    result[name] = [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in value
                    ]
                elif isinstance(value, dict):
                    result[name] = {
                        key: (
                            item.model_dump() if isinstance(item, BaseModel)
                            else [
                                sub_item.model_dump() if isinstance(sub_item, BaseModel) else sub_item
                                for sub_item in item
                            ] if isinstance(item, list)
                            else item
                        )
                        for key, item in value.items()
                    }
                else:
                    result[name] = value
            return result

        def model_dump_json(self, **kwargs: Any) -> str:
            return json.dumps(self.model_dump(), **kwargs)

        @classmethod
        def model_validate(cls, obj: Any) -> "BaseModel":
            if isinstance(obj, cls):
                return obj
            if not isinstance(obj, dict):
                raise TypeError(f"{cls.__name__}.model_validate expects a dict or model instance.")
            return cls(**obj)

        def __repr__(self) -> str:
            return f"{self.__class__.__name__}({self.model_dump()!r})"

    def Field(default: Any = None, default_factory: Any | None = None, **_: Any) -> Any:
        if default_factory is not None:
            return default_factory()
        return default
