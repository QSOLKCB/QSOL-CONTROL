#!/usr/bin/env python3
"""Launch the optional authenticated QSOL-CONTROL remote Agent API gateway."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.remote_http import RemoteGatewayError, build_server, load_gateway_config
from tools.webui import command_vector, read_members
from webui.common import WebUIConfig, WebUIError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QSOL-CONTROL optional authenticated remote Agent API gateway"
    )
    parser.add_argument("--gateway-config", required=True, help="0600 JSON gateway configuration")
    parser.add_argument("--root", default=".qsol-control-store", help="CONTROL storage root")
    parser.add_argument("--oracle-root", help="optional local QSOL-ORACLE repository")
    parser.add_argument("--nexus-command-json", help="optional JSON argv array for NEXUS")
    parser.add_argument("--nexus-cwd", help="optional NEXUS working directory")
    parser.add_argument("--nexus-members", help="optional default Council member JSON array")
    parser.add_argument("--nexus-timeout-seconds", type=float, default=1800.0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        gateway = load_gateway_config(args.gateway_config)
        control = WebUIConfig(
            control_root=Path(args.root),
            oracle_root=Path(args.oracle_root) if args.oracle_root else None,
            nexus_command=command_vector(args.nexus_command_json),
            nexus_cwd=Path(args.nexus_cwd) if args.nexus_cwd else None,
            nexus_timeout_seconds=args.nexus_timeout_seconds,
            default_council_members=read_members(args.nexus_members),
        )
        server = build_server(gateway, control)
        scheme = "https" if gateway.tls_enabled else "http"
        print(f"QSOL-CONTROL remote gateway listening on {scheme}://{gateway.bind}:{server.server_port}/v1/agent")
        server.serve_forever(poll_interval=0.25)
        return 0
    except KeyboardInterrupt:
        return 130
    except (RemoteGatewayError, WebUIError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
