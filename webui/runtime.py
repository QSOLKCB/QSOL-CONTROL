from .runtime_storage import StorageRuntimeMixin
from .runtime_query import QueryRuntimeMixin
from .runtime_inspect import InspectRuntimeMixin

class ControlWebUIRuntime(StorageRuntimeMixin, QueryRuntimeMixin, InspectRuntimeMixin):
    pass
