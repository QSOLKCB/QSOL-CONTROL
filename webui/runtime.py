from .runtime_storage import StorageRuntimeMixin
from .runtime_query import QueryRuntimeMixin
from .runtime_inspect import InspectRuntimeMixin
from .runtime_replay import ReplayRuntimeMixin


class ControlWebUIRuntime(
    StorageRuntimeMixin,
    QueryRuntimeMixin,
    InspectRuntimeMixin,
    ReplayRuntimeMixin,
):
    pass
