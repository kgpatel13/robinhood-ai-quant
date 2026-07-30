from __future__ import annotations

import argparse
import json

from src.robinhood_crypto import (
    RobinhoodCryptoClient,
    RobinhoodCryptoCredentialManager,
    RobinhoodCryptoDiagnostics,
    RobinhoodCryptoReadService,
    RobinhoodCryptoSigner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitized Robinhood Crypto read-only check")
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=["BTC-USD", "ETH-USD"],
        help="Optional symbols used only for read-only quote checks",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    credentials = RobinhoodCryptoCredentialManager().resolve()
    client = RobinhoodCryptoClient(RobinhoodCryptoSigner(credentials))
    diagnostics = RobinhoodCryptoDiagnostics(RobinhoodCryptoReadService(client))
    print(json.dumps(diagnostics.run(quote_symbols=list(args.symbols)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
