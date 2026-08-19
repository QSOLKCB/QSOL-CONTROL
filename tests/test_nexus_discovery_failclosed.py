import unittest

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter


class StubTransport:
    def __init__(self, *, protocol="nexus/0.14", operations=None):
        self.protocol = protocol
        self.operations = operations or [
            "system.health",
            "system.operations",
            "council.run",
            "world.inspect",
            "receipt.verify",
        ]

    def request(self, request):
        request_id = request.get("request_id")
        if request.get("operation") == "system.health":
            return {
                "request_id": request_id,
                "status": "ok",
                "protocol": self.protocol,
                "runtime_version": "2.0.0",
                "control_transport": "jsonl_stdio",
            }
        if request.get("operation") == "system.operations":
            return {
                "request_id": request_id,
                "status": "ok",
                "operations": list(self.operations),
            }
        raise AssertionError("discovery should not invoke other operations")


class NexusDiscoveryFailClosedTests(unittest.TestCase):
    def test_unknown_parent_protocol_major_fails_closed(self):
        adapter = NexusCouncilAdapter(StubTransport(protocol="nexus/1.0"))
        with self.assertRaisesRegex(NexusAdapterError, "unsupported NEXUS protocol major"):
            adapter.discover()

    def test_missing_required_operation_fails_closed(self):
        operations = [
            "system.health",
            "system.operations",
            "world.inspect",
            "receipt.verify",
        ]
        adapter = NexusCouncilAdapter(StubTransport(operations=operations))
        with self.assertRaisesRegex(NexusAdapterError, "council.run"):
            adapter.discover()

    def test_non_jsonl_transport_fails_closed(self):
        class WrongTransport(StubTransport):
            def request(self, request):
                response = super().request(request)
                if request.get("operation") == "system.health":
                    response["control_transport"] = "http"
                return response

        adapter = NexusCouncilAdapter(WrongTransport())
        with self.assertRaisesRegex(NexusAdapterError, "jsonl_stdio"):
            adapter.discover()


if __name__ == "__main__":
    unittest.main()
